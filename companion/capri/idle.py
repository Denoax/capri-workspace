"""Compile a pinned local read-only Wayland helper; unavailable means not idle."""
import asyncio
import hashlib
import os
from pathlib import Path
import tempfile
from .broker import Denied

async def helper(directory):
    source=Path(__file__).parent.parent/'native/idle_watch.c'
    protocol=Path('/usr/share/wayland-protocols/staging/ext-idle-notify/ext-idle-notify-v1.xml')
    directory=Path(directory);directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    if not protocol.is_file():raise Denied('Input-idle protocol is unavailable; unsolicited speech stays paused')
    digest=hashlib.sha256(source.read_bytes()+protocol.read_bytes()).hexdigest()
    target=directory/('idle-watch-'+digest[:16])
    if target.exists():return target
    with tempfile.TemporaryDirectory(prefix='capri-idle-build-') as folder:
        base=Path(folder);header=base/'ext-idle-notify-v1-client-protocol.h';code=base/'protocol.c';binary=base/'idle-watch'
        commands=[['/usr/bin/wayland-scanner','client-header',str(protocol),str(header)],['/usr/bin/wayland-scanner','private-code',str(protocol),str(code)],['/usr/bin/cc','-O2','-Wall','-Wextra','-Werror','-I'+str(base),str(source),str(code),'-lwayland-client','-o',str(binary)]]
        for argv in commands:
            p=await asyncio.create_subprocess_exec(*argv,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.PIPE)
            try:_,stderr=await asyncio.wait_for(p.communicate(),30)
            finally:
                if p.returncode is None:p.kill();await p.wait()
            if p.returncode:raise Denied('Read-only idle helper build failed: '+stderr.decode(errors='replace')[:300])
        temporary=target.with_suffix('.new');temporary.write_bytes(binary.read_bytes());temporary.chmod(0o700);os.replace(temporary,target)
    return target
