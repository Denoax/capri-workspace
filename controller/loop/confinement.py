"""Outer mount/PID namespace plus Codex command sandbox, never prompt-only isolation."""
import os
from pathlib import Path
import shutil

from .util import atomic, Rejected


def config(role, mcp=None):
    parent = ":workspace" if role == "doer" else ":read-only"
    text = f'''model = "gpt-6.1-sol"
model_reasoning_effort = "{'high' if role == 'reviewer' else 'medium'}"
approval_policy = "never"
default_permissions = "role"
web_search = "disabled"
allow_login_shell = false
check_for_update_on_startup = false
[features]
apps = false
plugins = false
hooks = false
multi_agent = false
memories = false
chronicle = false
browser_use = false
shell_snapshot = false
image_generation = false
[agents]
enabled = false
max_depth = 0
[permissions.role]
extends = "{parent}"
[permissions.role.filesystem]
"/codex-home" = "deny"
"/bridge" = "deny"
"/controller" = "read"
[shell_environment_policy]
inherit = "none"
[shell_environment_policy.set]
PATH = "/usr/bin:/bin"
HOME = "/tmp/model-home"
PYTHONDONTWRITEBYTECODE = "1"
'''
    if mcp:
        import json
        text += '\n[mcp_servers.loop]\ncommand = "/usr/bin/python3"\nargs = ["/controller/bridge.py"]\nrequired = true\nenabled_tools = ["submit_task", "request_status", "read_artifact", "ask_human"]\ndefault_tools_approval_mode = "approve"\n'
        text += '[mcp_servers.loop.env]\nLOOP_SOCKET = "/bridge/intake.sock"\nLOOP_CAPABILITY = ' + json.dumps(mcp) + '\n'
    return text


def prepare_runtime(path, role, mcp=None):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    auth = path / "auth.json"
    if not auth.exists():
        atomic(auth, "")  # Mount target only. Existing authentication is mounted read-only.
    atomic(path / "config.toml", config(role, mcp))


def argv(binary, runtime, workspace, inputs, controller, role, command, socket=None, auth_file=None):
    binary = Path(binary).resolve()
    auth = Path(auth_file) if auth_file else Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"
    if not auth.is_file():
        raise Rejected("Existing file-based Codex authentication unavailable")
    if not shutil.which("bwrap"):
        raise Rejected("Required mount isolation unavailable")
    args = ["/usr/bin/bwrap", "--die-with-parent", "--new-session", "--unshare-user", "--unshare-pid", "--unshare-ipc", "--unshare-uts",
            "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib", "/lib64",
            "--ro-bind", "/etc", "/etc", "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--dir", "/tmp/model-home",
            "--ro-bind", str(binary.parent), "/opt",
            "--bind", str(Path(runtime).resolve()), "/codex-home", "--ro-bind", str(auth), "/codex-home/auth.json",
            "--bind" if role == "doer" else "--ro-bind", str(Path(workspace).resolve()), "/workspace",
            "--ro-bind", str(Path(inputs).resolve()), "/inputs", "--ro-bind", str(Path(controller).resolve()), "/controller",
            "--dir", "/bridge"]
    if socket:
        args += ["--ro-bind", str(socket), "/bridge/intake.sock"]
    args += ["--clearenv", "--setenv", "PATH", "/usr/bin:/bin", "--setenv", "HOME", "/tmp/model-home", "--setenv", "CODEX_HOME", "/codex-home",
             "--setenv", "LANG", "C.UTF-8", "--setenv", "PYTHONDONTWRITEBYTECODE", "1", "--chdir", "/workspace", "/opt/codex"] + command
    return args
