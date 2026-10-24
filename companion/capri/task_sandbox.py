"""OS boundary for owner-selected read/write projects; no credential or desktop mounts."""
import asyncio
import json
import sys
import os
from pathlib import Path
import re
import secrets
import stat
import time

from .broker import Denied
from .provider import atomic_private


class RootHandle:
    def __init__(self, path):
        if not isinstance(path,str) or not path.startswith('/') or '\0' in path or '..' in Path(path).parts:
            raise Denied("Choose an absolute directory without parent traversal")
        self.path=str(Path(path))
        fd=os.open('/',os.O_PATH|os.O_DIRECTORY)
        try:
            for part in Path(self.path).parts[1:]:
                new=os.open(part,os.O_PATH|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
                os.close(fd);fd=new
            self.fd=fd;self.identity=os.fstat(fd)
        except OSError as e:
            os.close(fd);raise Denied("Directory is missing, inaccessible or contains a symlink") from e
    def close(self):
        if self.fd is not None:os.close(self.fd);self.fd=None


def check_tree(handle):
    # A writable bind alone cannot contain pre-existing hardlinks or host sockets.
    count=0
    for _,dirs,names,fd in os.fwalk('.',dir_fd=handle.fd,follow_symlinks=False):
        for name in dirs+names:
            info=os.stat(name,dir_fd=fd,follow_symlinks=False);count+=1
            if count>100000:raise Denied('Project exceeds the bounded writable scan; choose a smaller exact directory')
            if stat.S_ISREG(info.st_mode) and info.st_nlink!=1:raise Denied('Writable roots cannot contain hardlinked files; use an independent project copy')
            if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)):raise Denied('Work roots cannot expose host sockets, devices or pipes')


def protected_paths():
    home=Path.home()
    config=Path(os.environ.get('XDG_CONFIG_HOME',str(home/'.config')))
    state=Path(os.environ.get('XDG_STATE_HOME',str(home/'.local/state')))
    data=Path(os.environ.get('XDG_DATA_HOME',str(home/'.local/share')))
    sources=[]
    for manifest in (home/'.local/share/capri/install.json',data/'capri/install.json'):
        try:
            if not manifest.is_symlink() and manifest.stat().st_uid==os.getuid() and manifest.stat().st_size<64000:
                source=json.loads(manifest.read_text()).get('source')
                if isinstance(source,str) and Path(source).is_absolute():sources.append(Path(source))
        except (OSError,ValueError):pass
    return sources+[Path(sys.prefix)]+[home/x for x in ('.ssh','.gnupg','.aws','.codex','.agents','.pki','.mozilla','.local/share/keyrings')]+[
        home/'.config/capri',home/'.local/state/capri',home/'.local/share/capri/versions',home/'.local/share/capri/bootstrap',
        Path(os.environ.get('CODEX_HOME',str(home/'.codex'))),config/'capri',config/'BraveSoftware',config/'google-chrome',config/'chromium',
        state/'capri',data/'capri/versions',data/'capri/bootstrap',data/'capri/trust',data/'capri/helpers',data/'capri/venv',data/'capri/versions-state.json',data/'capri/current',data/'capri/engines',data/'capri/assets',data/'capri/install.json',
        home/'.config/systemd/user/capri-companion.service',home/'.local/bin/capri',home/'.local/share/applications/capri.desktop',
        home/'.local/share/capri/venv',home/'.local/share/capri/engines',home/'.local/share/capri/helpers',home/'.local/share/capri/trust',home/'.local/share/capri/current',home/'.local/share/capri/versions-state.json',
        Path(__file__).resolve().parent.parent,
        Path(os.environ.get('XDG_RUNTIME_DIR','/run/user/'+str(os.getuid()))) ]


def validate_roots(paths, protected=None):
    if not isinstance(paths,list) or not 1<=len(paths)<=8 or not all(isinstance(p,str) for p in paths):
        raise Denied("Choose one to eight exact project/configuration directories")
    denied=protected if protected is not None else protected_paths()
    result=[]
    for text in paths:
        path=Path(text)
        if not path.is_absolute() or path in (Path('/'),Path('/home'),Path.home(),Path.home()/'Documents',Path.home()/'.config',Path.home()/'.local'):
            raise Denied("Broad home/system roots are unavailable; choose exact projects")
        if any(path==p or path in p.parents or p in path.parents for p in denied):
            raise Denied("That root intersects protected credentials, runtime or Capri authority")
        if not (Path.home() in path.parents or Path('/tmp') in path.parents):
            raise Denied("Work roots must be selected owner projects or task-private temporary directories")
        handle=RootHandle(text)
        try:
            if handle.identity.st_uid!=os.getuid():raise Denied("The selected root must be owned by this user")
        finally:handle.close()
        if str(path) not in result:result.append(str(path))
    return result


class TaskSandbox:
    def __init__(self, directory):
        self.directory=Path(directory);self.directory.mkdir(parents=True,mode=0o700,exist_ok=True)
        self.children={}

    @staticmethod
    def validate(argv,roots,cwd,held=False):
        if not held:validate_roots(roots)
        if not isinstance(argv,list) or not 1<=len(argv)<=64 or not all(isinstance(v,str) and len(v)<=32000 and '\0' not in v for v in argv):
            raise Denied("Expected bounded exact command arguments")
        if not re.fullmatch(r'/usr/bin/[A-Za-z0-9_.+-]+',argv[0]):
            raise Denied("Use an exact installed executable under /usr/bin")
        if not isinstance(cwd,str) or '..' in Path(cwd).parts or not any(Path(cwd)==Path(p) or Path(p) in Path(cwd).parents for p in roots):
            raise Denied("The working directory must be inside a selected root")
        if not held:
            handle=RootHandle(cwd);handle.close()

    async def spawn(self, argv, *, environment=None, pass_fds=(), timeout=30, memory_mib=512, kind='work'):
        """Register a resource-limited scope before executing any untrusted program."""
        unit='capri-v2-'+secrets.token_hex(12)+'.scope'
        spec=self.directory/(unit+'.json')
        owner_start=Path('/proc/self/stat').read_text().rsplit(') ',1)[1].split()[19]
        atomic_private(spec,{'owner_pid':os.getpid(),'owner_start':owner_start,'unit':unit,
                            'argv':argv,'fds':list(pass_fds),'timeout':timeout,'memory_mib':memory_mib,'kind':kind})
        env={k:os.environ[k] for k in ('PATH','XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS','HOME','CODEX_HOME') if k in os.environ}
        if environment:env.update(environment)
        proc=await asyncio.create_subprocess_exec('/usr/bin/python3',str(Path(__file__).with_name('managed_child.py')),str(spec),
                stdin=asyncio.subprocess.PIPE if kind=='engine' else asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,
                pass_fds=tuple(pass_fds),close_fds=True,start_new_session=True,env=env,limit=2*1024*1024)
        self.children[proc.pid]=(proc,unit,spec)
        return proc

    async def release(self, proc):
        item=self.children.get(proc.pid)
        if proc.returncode is None:
            try:proc.terminate()
            except ProcessLookupError:pass
            try:await asyncio.wait_for(proc.wait(),3)
            except asyncio.TimeoutError:proc.kill();await proc.wait()
        if item:
            stop=await asyncio.create_subprocess_exec('/usr/bin/systemctl','--user','stop',item[1],stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL,close_fds=True)
            code=await stop.wait()
            if code not in (0,5):
                # A scope collected after its final process exits is also clean.
                check=await asyncio.create_subprocess_exec('/usr/bin/systemctl','--user','is-active',item[1],stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
                state,_=await check.communicate()
                if state.strip() not in (b'inactive',b'failed',b'unknown'):
                    raise Denied('Task scope cleanup failed; authority remains revoked')
            self.children.pop(proc.pid,None);item[2].unlink(missing_ok=True)

    async def stop(self):
        await asyncio.gather(*(self.release(p) for p,_,_ in tuple(self.children.values())))

    async def run(self, argv,roots,cwd, *, read_only=False, held_handles=None, library=None, timeout=30):
        self.validate(argv,roots,cwd,held=held_handles is not None)
        if not 1<=timeout<=30:raise Denied('Command deadline is outside the current task lease')
        handles=[];proc=None
        if held_handles is not None:
            if [h.path for h in held_handles]!=roots or any(h.fd is None or os.fstat(h.fd).st_ino!=h.identity.st_ino or os.fstat(h.fd).st_dev!=h.identity.st_dev for h in held_handles):
                raise Denied('Task root handle identity changed')
        try:
            handles=list(held_handles) if held_handles is not None else [RootHandle(p) for p in roots]
            for root in handles:await asyncio.to_thread(check_tree,root)
            command=['/usr/bin/bwrap','--unshare-all','--die-with-parent','--new-session','--clearenv',
                     '--setenv','PATH','/usr/bin','--setenv','LANG','C.UTF-8','--setenv','PYTHONDONTWRITEBYTECODE','1',
                     '--ro-bind','/usr','/usr','--symlink','usr/bin','/bin','--symlink','usr/lib','/lib','--symlink','usr/lib','/lib64',
                     '--proc','/proc','--dev','/dev','--tmpfs','/tmp']
            if library:
                dependency=RootHandle(library);handles.append(dependency)
                command+=['--ro-bind-fd',str(dependency.fd),'/opt/capri-deps','--setenv','PYTHONPATH','/opt/capri-deps']
            for root in handles[:len(roots)]:command+=['--ro-bind-fd' if read_only else '--bind-fd',str(root.fd),root.path]
            command+=['--chdir',cwd,'--remount-ro','/','--',*argv]
            proc=await self.spawn(command,pass_fds=[h.fd for h in handles],timeout=timeout)
            output=bytearray()
            async def read(stream):
                while chunk:=await stream.read(8192):
                    output.extend(chunk)
                    if len(output)>1024*1024:raise Denied("Task output exceeded 1 MiB")
            await asyncio.wait_for(asyncio.gather(read(proc.stdout),read(proc.stderr),proc.wait()),timeout+5)
            return {'exit_code':proc.returncode,'output':output.decode(errors='replace'),'network':'denied','roots':roots,'access':'read-only' if read_only else 'read/write'}
        finally:
            if proc:await self.release(proc)
            if held_handles is None:
                for handle in handles:handle.close()
            elif library and len(handles)>len(roots):handles[-1].close()
