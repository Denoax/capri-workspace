"""Trusted child gate: cgroup first, exact-owner lifetime, then the confined program."""
import ctypes
import json
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import sys
import time
import dbus


def main():
    path=Path(sys.argv[1]);info=path.stat()
    if path.is_symlink() or info.st_uid!=os.getuid() or info.st_mode & 0o077:raise SystemExit(125)
    spec=json.loads(path.read_text())
    owner=spec['owner_pid'];unit=spec['unit']
    if not re.fullmatch(r'capri-v2-[0-9a-f]{24}\.scope',unit) or os.getppid()!=owner:raise SystemExit(125)
    fd=os.pidfd_open(owner);poll=select.poll();poll.register(fd,select.POLLIN|select.POLLHUP|select.POLLERR)
    start=Path(f'/proc/{owner}/stat').read_text().rsplit(') ',1)[1].split()[19]
    if start!=spec['owner_start'] or poll.poll(0):raise SystemExit(125)
    stopping=False
    def stop(*_):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.prctl(1,signal.SIGTERM,0,0,0)!=0 or os.getppid()!=owner:raise SystemExit(125)
    if not 1<=spec['timeout']<=1800 or not 128<=spec['memory_mib']<=1024 or spec['argv'][0]!='/usr/bin/bwrap':raise SystemExit(125)
    manager=dbus.SessionBus().get_object('org.freedesktop.systemd1','/org/freedesktop/systemd1')
    props=[('PIDs',dbus.Array([os.getpid()],signature='u')),('Description',dbus.String('Capri scoped '+spec['kind'])),
           ('MemoryMax',dbus.UInt64(spec['memory_mib']*1024*1024)),('TasksMax',dbus.UInt64(64)),
           ('CPUQuotaPerSecUSec',dbus.UInt64(1000000)),('CollectMode',dbus.String('inactive-or-failed'))]
    manager.StartTransientUnit(unit,'fail',props,dbus.Array([],signature='(sa(sv))'),dbus_interface='org.freedesktop.systemd1.Manager')
    for _ in range(100):
        if unit in Path('/proc/self/cgroup').read_text():break
        time.sleep(.01)
    else:raise SystemExit('Resource scope was not established')
    if stopping or poll.poll(0):return 125
    if spec['kind']=='engine':
        env={k:os.environ[k] for k in ('PATH','HOME','CODEX_HOME','ACCESS_TOKEN') if k in os.environ}
    else:env={'PATH':'/usr/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'}
    child=None
    try:
        child=subprocess.Popen(spec['argv'],close_fds=True,pass_fds=tuple(spec['fds']),start_new_session=True,env=env)
        deadline=time.monotonic()+spec['timeout']
        while child.poll() is None:
            if stopping or poll.poll(100) or time.monotonic()>=deadline:
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                child.wait();return 125
        return child.returncode if child.returncode>=0 else 128-child.returncode
    finally:
        os.close(fd)
        if child and child.poll() is None:
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            child.wait()

if __name__=='__main__':raise SystemExit(main())
