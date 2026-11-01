"""HTTP acceptance of new role registration and lifecycle in an isolated project."""
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPCookieProcessor, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def main():
    results = []
    project = f'campus-workflow-check-{os.getpid()}'
    password, admin_code, worker_code = (secrets.token_urlsafe(20) for _ in range(3))
    base_url = 'http://127.0.0.1:18081'
    with tempfile.TemporaryDirectory(prefix='campus-workflow-') as temporary:
        envfile = Path(temporary) / '.env'
        envfile.write_text(f'HOST_PORT=18081\nDEMO_MODE=true\nDEMO_PASSWORD={password}\nADMIN_INVITE_CODE={admin_code}\nWORKER_INVITE_CODE={worker_code}\n')
        base = ['docker', 'compose', '--env-file', str(envfile), '-p', project]
        def run(args):
            result = subprocess.run(base + args, cwd=ROOT, capture_output=True, text=True)
            if result.returncode:
                print(result.stderr[-3000:])
                raise RuntimeError('Compose verification command failed')
            return result
        def client():
            return build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        def request(opener, path, data=None, expected=200):
            headers = {}
            payload = None
            if data is not None:
                token = json.load(opener.open(base_url + '/api/v1/session'))['data']['csrf']
                headers = {'Content-Type':'application/json','X-CSRF-Token':token,'Idempotency-Key':str(uuid4())}
                payload = json.dumps(data).encode()
            try:
                response = opener.open(Request(base_url + path, data=payload, headers=headers))
            except HTTPError as error:
                response = error
            assert response.code == expected, (path, response.code)
            return json.load(response)
        try:
            run(['up', '--build', '-d'])
            deadline = time.monotonic() + 60
            while True:
                try:
                    assert json.load(urlopen(base_url + '/health'))['status'] == 'ok'
                    break
                except (URLError, ConnectionError):
                    assert time.monotonic() < deadline
                    time.sleep(0.2)
            actors = {}
            for role in ['student','admin','worker']:
                opener = client()
                request(opener, '/api/v1/register', {'username':'live_'+role,'name':'独立验收'+role,
                        'password':password,'role':role,'invite_code':admin_code if role=='admin' else worker_code if role=='worker' else ''})
                assert request(opener, '/api/v1/session')['data']['user']['role'] == role
                actors[role] = opener
            results.append('A01: real student/admin/worker registration and login passed')
            student, admin, worker = (actors[role] for role in ['student','admin','worker'])
            data = {'title':'独立容器验收照明故障','location':'验收楼101室','description':'今天早上发现照明灯无法点亮，请安排维修人员检查。','category':'水电','priority':'normal'}
            identifier = request(student,'/api/v1/tickets',data)['data']['id']
            request(worker,f'/api/v1/tickets/{identifier}',expected=403)
            worker_id = request(worker,'/api/v1/session')['data']['user']['id']
            def action(opener, name, **extra):
                version = request(opener,f'/api/v1/tickets/{identifier}')['data']['version']
                return request(opener,f'/api/v1/tickets/{identifier}/actions',{'action':name,'version':version,**extra})
            action(admin,'assign',assignee_id=worker_id)
            action(worker,'accept')
            action(worker,'finish',note='已处理并测试正常，请确认')
            action(student,'reopen',note='仍有异常，请继续检查')
            action(worker,'finish',note='再次处理后测试正常')
            action(student,'confirm')
            request(student,f'/api/v1/tickets/{identifier}/review',{'rating':5,'comment':'处理及时'})
            result = request(student,f'/api/v1/tickets/{identifier}')['data']
            assert result['status']=='completed' and len(result['events'])==7 and result['review']['rating']==5
            request(student,'/api/v1/tickets?status=invalid',expected=400)
            request(client(),f'/api/v1/tickets/{identifier}',expected=401)
            results.append('W01/W02/W03/W06: complete role lifecycle, reopen, evaluation, authorization and invalid filter passed')
            run(['restart','app'])
            deadline = time.monotonic()+30
            while True:
                try:
                    assert json.load(urlopen(base_url + '/health'))['status'] == 'ok'
                    break
                except (URLError, ConnectionError):
                    assert time.monotonic()<deadline
                    time.sleep(0.2)
            assert request(student,f'/api/v1/tickets/{identifier}')['data']['status']=='completed'
            results.append('U04: restart preserved registered users, session and work order data')
            run(['run','--rm','--no-deps','--build','test'])
            results.append('Container full pytest passed')
        finally:
            subprocess.run(base + ['down','-v'], cwd=ROOT, capture_output=True)
    output = {'date':'2026-11-02 Asia/Shanghai','result':'passed','checks':results,
              'project':project,'sensitive_values':'not recorded','cleanup':'only isolated verification project removed'}
    (ROOT/'docs/verification/workflow-docker.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(output,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
