"""Private D-Bus fixture, never registered on the owner's real session bus."""
import subprocess
import sys
import threading
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

DBusGMainLoop(set_as_default=True)
bus=dbus.SessionBus()
name=dbus.service.BusName('org.freedesktop.portal.Desktop',bus)
loop=GLib.MainLoop()
objects=[]
class Request(dbus.service.Object):
    @dbus.service.signal('org.freedesktop.portal.Request',signature='ua{sv}')
    def Response(self,code,values):pass
class Portal(dbus.service.Object):
    @dbus.service.method('org.freedesktop.portal.OpenURI',in_signature='ssa{sv}',out_signature='o',sender_keyword='sender')
    def OpenURI(self,parent,uri,options,sender):
        assert str(uri)=='https://auth.openai.com/api/accounts/authorize?fixture=true'
        path='/org/freedesktop/portal/desktop/request/'+sender.lstrip(':').replace('.','_')+'/'+str(options.get('handle_token','legacy'))
        request=Request(bus,path);objects.append(request)
        def respond():request.Response(2,dbus.Dictionary({},signature='sv'));return False
        GLib.idle_add(respond)
        return dbus.ObjectPath(path)
portal=Portal(bus,'/org/freedesktop/portal/desktop')
result=[]
def run():
    try:
        proc=subprocess.run(['/usr/bin/python3',sys.argv[1]],input='https://auth.openai.com/api/accounts/authorize?fixture=true',text=True,capture_output=True,timeout=7)
        result.append(proc.returncode)
    finally:GLib.idle_add(loop.quit)
thread=threading.Thread(target=run);thread.start();loop.run();thread.join(timeout=8)
print(result[0] if result else 'timeout')
raise SystemExit(0 if result==[2] else 1)
