"""Verify actual Docker COPY behavior using synthetic local-data fixtures."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = 'python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e'


def main():
    excluded = ['.env', '.env.local', 'nested/.env', 'nested/.env.production',
                'instance/a.sqlite3', 'data/a.sqlite3', 'data/a.sqlite3-journal',
                'data/a.sqlite3-wal', 'data/a.sqlite3-shm', 'data/a.db',
                'data/a.db-journal', 'data/a.db-wal', 'data/a.db-shm',
                'uploads/image.jpg', 'nested/uploads/image.jpg', 'logs/event.json',
                'nested/logs/event.json', 'app.log', '.venv/bin/python', 'nested/.venv/bin/python',
                'venv/bin/python', 'pkg/__pycache__/x.pyc', '.pytest_cache/v/cache',
                '.coverage', '.coverage.unit', 'htmlcov/index.html', 'build/a', 'dist/a.whl',
                '.git/config', 'nested/.git/config']
    included = ['.env.example', 'nested/.env.example', 'requirements.lock',
                'requirements-dev.lock', 'campus_repair/config.py', 'README.md', 'tests/test_health.py']
    tag = f'campus-repair-context-check:{os.getpid()}'
    with tempfile.TemporaryDirectory(prefix='campus-context-') as temporary:
        context = Path(temporary)
        shutil.copy(ROOT / '.dockerignore', context / '.dockerignore')
        shutil.copy(ROOT / '.gitignore', context / '.gitignore')
        subprocess.run(['git', 'init', '-q', str(context)], check=True)
        for name in excluded + included:
            # Do not overwrite the temp repository's real metadata; synthetic nested .git is sufficient.
            if name == '.git/config':
                continue
            path = context / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('synthetic-fixture\n')
        for name in [name for name in excluded if '.git/' not in name]:
            result = subprocess.run(['git', '-C', str(context), '-c', 'core.excludesFile=/dev/null',
                                     'check-ignore', '--no-index', '-q', '--', name])
            assert result.returncode == 0, name
        for name in included:
            result = subprocess.run(['git', '-C', str(context), '-c', 'core.excludesFile=/dev/null',
                                     'check-ignore', '--no-index', '-q', '--', name])
            assert result.returncode == 1, name
        program = ('from pathlib import Path; p=Path("/context"); '
                   + f'assert all(not (p/n).exists() for n in {excluded!r}); '
                   + f'assert all((p/n).is_file() for n in {included!r}); print("Actual Docker context checks passed")')
        dockerfile = f'FROM {BASE}\nCOPY . /context/\nRUN python -c {json.dumps(program)}\n'
        try:
            result = subprocess.run(['docker', 'build', '--no-cache', '--progress=plain', '-t', tag, '-f', '-', str(context)],
                                    input=dockerfile, capture_output=True, text=True)
            output = result.stdout + result.stderr
            (ROOT / 'docs/verification/context-transcript.txt').write_text(output)
            assert result.returncode == 0, output
        finally:
            subprocess.run(['docker', 'image', 'rm', tag], capture_output=True)
    record = {'scenario': 'R06', 'result': 'passed', 'docker_excluded': len(excluded),
              'git_excluded': len([name for name in excluded if '.git/' not in name]),
              'retained': len(included), 'method': 'Native Git and real Docker build/COPY with synthetic fixtures'}
    (ROOT / 'docs/verification/context-results.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
