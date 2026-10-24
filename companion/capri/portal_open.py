"""Only the documented OAuth authorization URL may be opened by this helper."""
import sys
from urllib.parse import urlparse
import dbus

url = sys.stdin.buffer.read(16000).decode()
p = urlparse(url)
if p.scheme != "https" or p.netloc != "auth.openai.com" or p.path != "/api/accounts/authorize":
    raise SystemExit(2)
portal = dbus.SessionBus().get_object("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop")
portal.OpenURI("", url, dbus.Dictionary({}, signature="sv"), dbus_interface="org.freedesktop.portal.OpenURI")
