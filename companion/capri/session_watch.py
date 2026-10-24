"""login1 lock/sleep watcher; reports lock state and session identity only."""
import json
import os
import ctypes
import signal
import sys

# A SIGKILL/crash of the core cannot run Python cleanup. Bind this read-only
# watcher to its exact parent and close the fork/prctl race in both directions.
capri_parent_pid = int(sys.argv[1])
if os.getppid() != capri_parent_pid:
    raise SystemExit("Companion parent no longer exists")
PR_SET_PDEATHSIG = 1
capri_libc = ctypes.CDLL(None, use_errno=True)
capri_libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
if capri_libc.prctl(PR_SET_PDEATHSIG, signal.SIGTERM, 0, 0, 0) != 0:
    raise OSError(ctypes.get_errno(), "Cannot bind session watcher lifetime")
if os.getppid() != capri_parent_pid:
    raise SystemExit("Companion parent exited during watcher startup")
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()
manager = bus.get_object("org.freedesktop.login1", "/org/freedesktop/login1")
try:
    path = str(manager.GetSessionByPID(os.getpid(), dbus_interface="org.freedesktop.login1.Manager"))
except dbus.DBusException as error:
    if error.get_dbus_name() != "org.freedesktop.login1.NoSessionForPID":
        raise
    # Flatpak host-spawn/user services have no login session themselves. Select
    # only a unique active local graphical session of this UID; ambiguity denies.
    matches = []
    for sid, uid, user, seat, candidate in manager.ListSessions(dbus_interface="org.freedesktop.login1.Manager"):
        if int(uid) != os.getuid():
            continue
        obj = bus.get_object("org.freedesktop.login1", str(candidate))
        props = obj.GetAll("org.freedesktop.login1.Session", dbus_interface="org.freedesktop.DBus.Properties")
        if props.get("Active") and not props.get("Remote") and props.get("Type") in ("wayland", "x11") and props.get("Class") == "user":
            matches.append(str(candidate))
    if len(matches) != 1:
        raise SystemExit("Unique active graphical session unavailable")
    path = matches[0]
session = bus.get_object("org.freedesktop.login1", path)
locked = True
sleeping = False
active = False


def emit():
    print(json.dumps({"locked": locked or sleeping or not active,"session": path}), flush=True)


def properties(interface, changed, invalidated):
    global locked, active
    if interface != "org.freedesktop.login1.Session":
        return
    # Invalidated properties fail closed until a fresh read.
    if "LockedHint" in changed:
        locked = bool(changed["LockedHint"])
    if "Active" in changed:
        active = bool(changed["Active"])
    if "LockedHint" in invalidated or "Active" in invalidated:
        locked = True
    emit()


def lock_signal():
    global locked
    locked = True
    emit()


def unlock_signal():
    global locked
    locked = False
    emit()


def sleep_signal(value):
    global sleeping
    sleeping = bool(value)
    emit()

bus.add_signal_receiver(properties, signal_name="PropertiesChanged", dbus_interface="org.freedesktop.DBus.Properties", path=path)
bus.add_signal_receiver(lock_signal, signal_name="Lock", dbus_interface="org.freedesktop.login1.Session", path=path)
bus.add_signal_receiver(unlock_signal, signal_name="Unlock", dbus_interface="org.freedesktop.login1.Session", path=path)
bus.add_signal_receiver(sleep_signal, signal_name="PrepareForSleep", dbus_interface="org.freedesktop.login1.Manager")
initial = session.GetAll("org.freedesktop.login1.Session", dbus_interface="org.freedesktop.DBus.Properties")
locked, active = bool(initial.get("LockedHint", True)), bool(initial.get("Active", False))
emit()
GLib.MainLoop().run()
