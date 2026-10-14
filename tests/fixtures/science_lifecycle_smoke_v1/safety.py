"""Harmless OS canaries, including child inheritance; no provider endpoints."""
import errno
import os
import socket
import subprocess
import sys
from pathlib import Path
from common import BASE, OUT, dump

def boundary():
    facts = {}
    for name, path in [('product_readonly','/repo/SCIENCE_FORBIDDEN'),
                       ('kit_readonly','/kit/SCIENCE_FORBIDDEN'),
                       ('root_readonly','/SCIENCE_FORBIDDEN')]:
        try:
            Path(path).write_text('canary')
        except OSError:
            facts[name] = True
        else:
            facts[name] = False
    facts['nonroot'] = os.geteuid() == 1000
    facts['loopback_only'] = set(socket.if_nameindex()) == {(1,'lo')}
    facts['no_default_route'] = not any(r.split()[1]=='00000000' for r in Path('/proc/net/route').read_text().splitlines()[1:])
    def accessible(path):
        try:
            return Path(path).exists()
        except PermissionError:
            return False
    facts['no_accessible_socket_or_credentials'] = not any(accessible(p) for p in
        ['/var/run/docker.sock','/root/.ssh','/root/.aws','/repo/.env','/repo/data','/repo/local','/repo/.venv'])
    facts['no_secret_environment'] = not any(k in os.environ for k in
        ['GITHUB_TOKEN','GH_TOKEN','AWS_SECRET_ACCESS_KEY','OPENAI_API_KEY','JUPITER_API_KEY'])
    facts['egress_denied_locally'] = False
    if facts['loopback_only'] and facts['no_default_route']:
        sock=socket.socket()
        try:
            sock.settimeout(1)
            sock.connect(('192.0.2.1',9))
        except OSError as exc:
            facts['egress_denied_locally'] = exc.errno in (errno.ENETUNREACH,errno.EHOSTUNREACH)
        finally:
            sock.close()
    return facts

def check():
    facts=boundary()
    facts['head_exact'] = subprocess.check_output(['git','-C','/repo','rev-parse','HEAD'],text=True).strip()==BASE
    facts['tracked_bytes_exact'] = subprocess.run(['git','-C','/repo','diff','--exit-code','HEAD'],capture_output=True).returncode==0
    child=subprocess.run([sys.executable,'-B','/kit/safety.py','child'],capture_output=True,text=True,check=True,timeout=20)
    facts['child_inherits_boundary'] = all(__import__('json').loads(child.stdout).values())
    for name in ('home','tmp','config'):
        (OUT/name).mkdir(exist_ok=True)
    control=OUT/'WRITE_CONTROL'
    control.write_text('canary')
    facts['own_output_writable']=control.read_text()=='canary'
    control.unlink()
    dump(OUT/'containment-canaries.json',{'pass':all(facts.values()),'facts':facts,
        'scope':'OS_CONTAINER_BOUNDARY; host orchestration is outside; no blind Actor claim'})
    assert all(facts.values()), facts
    return facts

if __name__=='__main__':
    if len(sys.argv)>1:
        print(__import__('json').dumps(boundary()))
    else:
        print(__import__('json').dumps(check()))
