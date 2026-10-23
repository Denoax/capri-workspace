#!/usr/bin/env python3
"""Capture namespace prerequisites and probe the unmodified trusted collector."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'controller'))
from loop.collector import check_command
from loop.util import write_json


def command(args):
    if not shutil.which(args[0]):return {'argv':args,'status':'UNAVAILABLE'}
    try:
        run=subprocess.run(args,capture_output=True,text=True,timeout=10)
        return {'argv':args,'exit':run.returncode,'stdout':run.stdout[-12000:],'stderr':run.stderr[-12000:]}
    except (OSError,subprocess.TimeoutExpired) as ex:return {'argv':args,'status':'UNAVAILABLE','error':str(ex)}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    report={'origin':'ACTUAL_HOST_DIAGNOSTICS','platform':platform.platform(),'kernel':platform.release(),'python':sys.version,'executable':sys.executable,
        'runner':{key:os.environ.get(key,'UNKNOWN') for key in ('ImageOS','ImageVersion','RUNNER_OS','RUNNER_ARCH')},'policy_files':{},
        'commands':[command(argv) for argv in (['bwrap','--version'],['getcap','/usr/bin/bwrap'],['sysctl','kernel.unprivileged_userns_clone','user.max_user_namespaces','kernel.apparmor_restrict_unprivileged_userns'],['journalctl','-k','--no-pager','-n','100'])]}
    for name in ('/etc/os-release','/proc/self/status','/proc/self/attr/current','/sys/module/apparmor/parameters/enabled'):
        try:report['policy_files'][name]=Path(name).read_text()[-16000:]
        except OSError as ex:report['policy_files'][name]='UNAVAILABLE: '+str(ex)
    names=('user','mnt','pid','net');outer={name:os.readlink('/proc/self/ns/'+name) for name in names}
    script="import json,os,socket;print(json.dumps({'namespaces':{n:os.readlink('/proc/self/ns/'+n) for n in "+repr(names)+"},'interfaces':socket.if_nameindex()}))"
    with tempfile.TemporaryDirectory() as temp:
        checkout=Path(temp)/'checkout';checkout.mkdir()
        result=check_command(checkout,['python3','-c',script],args.output/'collector-probe',timeout=10)
    try:observed=json.loads((args.output/'collector-probe/stdout.txt').read_text())
    except (ValueError,OSError):observed={}
    valid=result['exit']==0 and not result['timeout'] and result['source_unchanged'] and all(observed.get('namespaces',{}).get(name)!=outer[name] for name in names) and set(observed.get('namespaces',{}))==set(names) and all(name=='lo' for _,name in observed.get('interfaces',[]))
    report.update(status='SUPPORTED_COLLECTOR_PROBE' if valid else 'ISOLATION_PREREQUISITE_FAILED',outer_namespaces=outer,observed=observed,collector=result,
        limitation='A successful probe does not certify the suite or model runtime. Failure has no inferred kernel-policy cause; unavailable denial logs remain unavailable.')
    write_json(args.output/'diagnostics.json',report)
    print(json.dumps({'status':report['status'],'diagnostics':str(args.output/'diagnostics.json'),'collector_exit':result['exit']}))
    return 0 if valid else 1


if __name__=='__main__':raise SystemExit(main())
