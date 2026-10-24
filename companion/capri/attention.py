"""Read existing notification state; one licensed local sound, no notification daemon."""
import asyncio
import json
from pathlib import Path
import re
from .broker import Denied

async def command(argv):
    p=await asyncio.create_subprocess_exec(*argv,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,close_fds=True)
    try:
        out,_=await asyncio.wait_for(p.communicate(),3)
        if p.returncode:raise Denied('Native attention status unavailable')
        return out.decode()
    finally:
        if p.returncode is None:p.kill();await p.wait()

async def desktop_dnd():
    # Resolve the actual bus owner each time; never assume a stale process ID.
    result=await command(['/usr/bin/gdbus','call','--session','--dest','org.freedesktop.DBus','--object-path','/org/freedesktop/DBus','--method','org.freedesktop.DBus.GetConnectionUnixProcessID','org.freedesktop.Notifications'])
    match=re.fullmatch(r'\(uint32 (\d+),\)\s*',result)
    if not match:raise Denied('Notification owner identity unavailable')
    pid=int(match[1])
    if not Path(f'/proc/{pid}/exe').resolve().name=='quickshell':raise Denied('This desktop notification DND API has not been qualified')
    value=json.loads(await command(['/usr/bin/quickshell','ipc','--pid',str(pid),'call','konaNotifications','status']))
    if type(value.get('silent')) is not bool:raise Denied('Desktop DND state unavailable')
    return value['silent']

class Sound:
    def __init__(self,adapters):self.adapters=adapters;self.last=-1000;self.status='Licensed PipeWire fallback; existing daemon has no sound capability'
    async def play(self,profile,attention,now):
        if profile['mute'] or profile['quiet'] or profile['paused'] or profile['dnd'] or attention.get('desktop_dnd') is not False or attention.get('fullscreen') or not attention.get('unlocked') or profile['sound_volume']==0:return False
        if now-self.last<10:return False
        sound=Path('/usr/share/sounds/ocean/stereo/message-new-instant.oga')
        if not sound.is_file():sound=Path('/usr/share/sounds/freedesktop/stereo/message-new-instant.oga')
        if not sound.is_file():raise Denied('No licensed notification sound is installed')
        self.last=now
        await self.adapters.command(['/usr/bin/pw-play','--volume='+str(profile['sound_volume']/100),str(sound)],timeout=8)
        return True
