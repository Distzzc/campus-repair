"""Run container acceptance checks in a unique disposable Compose project."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs/verification'


def main():
    results = []
    transcript = []
    project = f'campus-repair-check-{os.getpid()}'
    with tempfile.TemporaryDirectory(prefix='campus-compose-') as temporary:
        envfile = Path(temporary) / '.env'
        envfile.write_text('APP_ENV=development\nDATABASE_PATH=/unused/host/path.sqlite3\nHOST_PORT=18080\nLOG_LEVEL=ERROR\nDB_TIMEOUT_SECONDS=1\n')
        base = ['docker', 'compose', '--env-file', str(envfile), '-p', project]

        def run(arguments, *, check=True):
            command = base + arguments
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            transcript.append('$ docker compose --env-file <isolated-env> -p <isolated-project> ' + ' '.join(arguments)
                              + '\n' + completed.stdout + completed.stderr + f'\nexit={completed.returncode}\n')
            if check and completed.returncode:
                raise RuntimeError(f'Compose command failed: {arguments[0]}')
            return completed

        def wait_health():
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                try:
                    with urlopen('http://127.0.0.1:18080/health', timeout=2) as response:
                        body = json.load(response)
                        assert response.status == 200 and body['checks'] == {'database': 'ok'}
                        assert body['request_id'] == response.headers['X-Request-ID']
                    container = run(['ps', '-q', 'app']).stdout.strip()
                    state = subprocess.check_output(['docker', 'inspect', '--format', '{{.State.Health.Status}}', container], text=True).strip()
                    if state == 'healthy':
                        return
                    time.sleep(0.2)
                except (URLError, ConnectionError):
                    time.sleep(0.2)
            raise RuntimeError('Health readiness timeout')

        def execute(code):
            return run(['exec', '-T', 'app', 'python', '-c', code]).stdout.strip()

        try:
            run(['up', '--build', '-d'])
            wait_health()
            details = json.loads(execute("import os,importlib.util,json; print(json.dumps({'uid':os.getuid(),'database':os.environ['DATABASE_PATH'],'pytest_present':importlib.util.find_spec('pytest') is not None}))"))
            assert details == {'uid': 10001, 'database': '/data/campus-repair.sqlite3', 'pytest_present': False}
            run(['exec', '-T', 'app', 'python', '-m', 'pip', 'check'])
            details['docker_health'] = 'healthy'
            results.append({'scenario': 'R02', 'result': 'passed', 'details': details})
            run(['run', '--rm', '--no-deps', '--build', 'test'])
            results.append({'scenario': 'R05', 'result': 'passed', 'details': 'Isolated container pytest, no runtime volume'})
            execute("import sqlite3; c=sqlite3.connect('/data/campus-repair.sqlite3'); c.execute('CREATE TABLE verify_sentinel(value TEXT)'); c.execute(\"INSERT INTO verify_sentinel VALUES ('preserved')\"); c.commit(); c.close()")
            before = execute("import sqlite3; c=sqlite3.connect('/data/campus-repair.sqlite3'); print(c.execute('SELECT value FROM verify_sentinel').fetchone()[0]); c.close()")
            run(['down'])
            run(['up', '--build', '-d'])
            wait_health()
            after = execute("import sqlite3; c=sqlite3.connect('/data/campus-repair.sqlite3'); print(c.execute('SELECT value FROM verify_sentinel').fetchone()[0]); c.close()")
            assert before == after == 'preserved'
            results.append({'scenario': 'R03', 'result': 'passed', 'details': 'down/up and repeated init retained sentinel'})
            run(['exec', '-T', 'app', 'python', 'scripts/database_backup.py', 'backup', '/data/campus-repair.sqlite3', '/data/check-backup.sqlite3'])
            run(['exec', '-T', 'app', 'python', 'scripts/database_backup.py', 'restore', '/data/check-backup.sqlite3', '/data/check-restored.sqlite3'])
            restored = execute("import sqlite3; c=sqlite3.connect('/data/check-restored.sqlite3'); print(c.execute('SELECT value FROM verify_sentinel').fetchone()[0]); print(c.execute('PRAGMA integrity_check').fetchone()[0]); c.close()")
            assert restored.splitlines() == ['preserved', 'ok']
            logs = run(['logs', '--no-color', '--no-log-prefix', 'app']).stdout
            records = [json.loads(line) for line in logs.splitlines() if line.strip()]
            assert any(record['event'] == 'request_completed' for record in records)
            results.append({'scenario': 'H07', 'result': 'passed', 'details': 'All real server log lines parse as JSON'})
            container = run(['ps', '-q', 'app']).stdout.strip()
            started = time.monotonic()
            run(['stop', 'app'])
            elapsed = time.monotonic() - started
            state = subprocess.check_output(['docker', 'inspect', '--format', '{{json .State}}', container], text=True)
            state = json.loads(state)
            assert elapsed < 15 and state['ExitCode'] == 0 and not state['OOMKilled']
            results.append({'scenario': 'R04', 'result': 'passed', 'details': {'stop_seconds': round(elapsed, 3), 'exit_code': 0, 'restored': restored.splitlines()}})
            run(['down'])
            for value in ['1023', '65536', '', 'not-a-number']:
                envfile.write_text(f'HOST_PORT={value}\nLOG_LEVEL=INFO\nDB_TIMEOUT_SECONDS=1\n')
                failed = run(['up', '-d'], check=False)
                assert failed.returncode != 0
                running = run(['ps', '--status', 'running', '-q', 'app'], check=False)
                assert not running.stdout.strip()
                run(['down'], check=False)
            # The same validator is used by init; validate legal boundaries without reserving privileged/occupied host ports.
            for value in ['1024', '65535']:
                envfile.write_text(f'HOST_PORT={value}\n')
                run(['run', '--rm', '--no-deps', 'init', 'python', '-c', f"from campus_repair.config import decimal_integer; assert decimal_integer('{value}', 'HOST_PORT', 1024, 65535)=={value}"])
            results.append({'scenario': 'R02-port-boundaries', 'result': 'passed', 'details': 'illegal values block app; legal boundary validator accepted'})
        except Exception as error:
            results.append({'scenario': 'execution', 'result': 'failed', 'details': str(error)})
            raise
        finally:
            # Only the unique project created above is removed, never a user's project.
            envfile.write_text('HOST_PORT=18080\n')
            run(['down', '-v'], check=False)
            OUTPUT.mkdir(parents=True, exist_ok=True)
            (OUTPUT / 'compose-transcript.txt').write_text('\n'.join(transcript))
            (OUTPUT / 'compose-results.json').write_text(json.dumps({'date': datetime.now(timezone.utc).isoformat(), 'project': project, 'results': results}, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
