"""Content-bound immutable versions and atomic pointers. Standard library only.

Copied to the protected bootstrap on initial installation; proposals cannot edit it.
"""
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat

class VersionError(ValueError):pass
SKIP={'.git','__pycache__','.venv','node_modules','local-assets'}
EXTENSIONS={'.py','.qml','.js','.md','.json','.lock','.txt','.in','.yml','.yaml','.c','.h','.sh','.service','.desktop'}

def atomic(path,value):
    path=Path(path);path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.'+secrets.token_hex(8))
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'w') as f:json.dump(value,f,sort_keys=True);f.flush();os.fsync(f.fileno())
        os.replace(temporary,path)
        sync=os.open(path.parent,os.O_DIRECTORY);os.fsync(sync);os.close(sync)
    finally:temporary.unlink(missing_ok=True)

def snapshot(root):
    """Read source through directory FDs; reject symlinks and bounded-size violations."""
    root=Path(root)
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);files={};total=0
    try:
        for folder,dirs,names,dirfd in os.fwalk('.',dir_fd=fd,follow_symlinks=False):
            for name in list(dirs):
                if name in SKIP:dirs.remove(name);continue
                if stat.S_ISLNK(os.stat(name,dir_fd=dirfd,follow_symlinks=False).st_mode):raise VersionError('Source directory symlink rejected')
            for name in sorted(names):
                if name=='version-record.json' or Path(name).suffix not in EXTENSIONS:continue
                relative=str(Path(folder)/name)
                stream=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=dirfd)
                with os.fdopen(stream,'rb') as f:
                    info=os.fstat(f.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_size>2*1024*1024:raise VersionError('Unsupported source file')
                    data=f.read(2*1024*1024+1)
                total+=len(data)
                if len(data)>2*1024*1024 or total>16*1024*1024 or len(files)>1000:raise VersionError('Source snapshot exceeds its bound')
                files[relative]=data
        if 'launcher.py' not in files or 'qml/shell.qml' not in files:raise VersionError('Incomplete Capri source')
        return files
    finally:os.close(fd)

def identity(files):
    hashes={p:hashlib.sha256(v).hexdigest() for p,v in sorted(files.items())}
    digest=hashlib.sha256(json.dumps(hashes,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return digest,hashes

def write_tree(root,files):
    root=Path(root);root.mkdir(mode=0o700,parents=True,exist_ok=False)
    for name,data in files.items():
        path=root/name;path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())

class Versions:
    def __init__(self,root):
        self.root=Path(root);self.root.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.versions=self.root/'versions';self.versions.mkdir(mode=0o700,exist_ok=True)
        self.meta=self.root/'versions-state.json'
    def state(self):return json.loads(self.meta.read_text()) if self.meta.exists() else {'current':None,'last_good':None,'previous':None,'failed':[],'rollback_used':False}
    def stage(self,source,provenance,expected=None):
        files=snapshot(source);digest,hashes=identity(files)
        if expected is not None and digest!=expected:raise VersionError('Source changed after review; installation denied')
        target=self.versions/digest
        if not target.exists():
            temporary=self.versions/('.stage-'+secrets.token_hex(12));write_tree(temporary,files)
            atomic(temporary/'version-record.json',{'digest':digest,'files':hashes,'provenance':provenance})
            os.replace(temporary,target)
            for p in target.rglob('*'):p.chmod(0o500 if p.is_dir() else 0o400)
            target.chmod(0o500)
        self.verify(digest);return digest
    def verify(self,digest):
        if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise VersionError('Invalid version identity')
        target=self.versions/digest
        if target.is_symlink() or not target.is_dir():raise VersionError('Version is unavailable')
        files=snapshot(target);files.pop('version-record.json',None)
        actual,hashes=identity(files)
        record=json.loads((target/'version-record.json').read_text())
        if actual!=digest or record.get('digest')!=digest or record.get('files')!=hashes:raise VersionError('Installed version content changed')
        return target
    def switch(self,digest):
        self.verify(digest)
        pointer=self.root/('current.'+secrets.token_hex(8));pointer.symlink_to('versions/'+digest)
        os.replace(pointer,self.root/'current')
        fd=os.open(self.root,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
    def activate(self,digest,*,origin):
        if origin!='owner-ui':raise VersionError('Executable proposals require exact native owner approval; no trusted automatic release channel is configured')
        state=self.state()
        if digest in state['failed']:raise VersionError('This failed version is disabled')
        self.verify(digest)
        state.update(previous=state['current'],current=digest,rollback_used=False)
        atomic(self.meta,state);self.switch(digest)
    def mark_good(self,digest):
        state=self.state()
        if state['current']!=digest:raise VersionError('Health report is for a different version')
        self.verify(digest);state['last_good']=digest;atomic(self.meta,state)
    def rollback(self,*,automatic=False):
        state=self.state();target=state['last_good']
        if target==state['current']:target=state['previous']
        if not target or target==state['current'] or (automatic and state['rollback_used']):raise VersionError('No unused last-known-good rollback is available')
        self.verify(target);failed=state['current']
        state['current']=target;state['previous']=failed;state['failed']=list(dict.fromkeys(state['failed']+[failed]));state['rollback_used']=True
        atomic(self.meta,state);self.switch(target);return {'current':target,'disabled':failed,'automatic':automatic}
