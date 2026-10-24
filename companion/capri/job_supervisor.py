"""Bind a transient confined job to its exact core lifetime, including SIGKILL.

systemd-run's service is not a child of the core. A pidfd prevents an orphaned
service or PID reuse from keeping an old grant alive. This helper accepts only
our bubblewrap runner and never receives provider credentials or model prose.
"""
import argparse
import os
from pathlib import Path
import select
import signal
import subprocess


def starttime(pid):
    # /proc stat starttime is field 22; fields after the comm end begin at 3.
    return Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()[19]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-pid", type=int, required=True)
    parser.add_argument("--owner-start", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if args.owner_pid <= 1 or not args.owner_start.isdecimal() or not command or command[0] != "/usr/bin/bwrap":
        raise SystemExit(125)
    owner = os.pidfd_open(args.owner_pid)
    poll = select.poll()
    poll.register(owner, select.POLLIN | select.POLLHUP | select.POLLERR)
    process = None
    try:
        if starttime(args.owner_pid) != args.owner_start or poll.poll(0):
            return 125
        process = subprocess.Popen(command, close_fds=True, start_new_session=True)
        while process.poll() is None:
            if poll.poll(100):
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                return 125
        return process.returncode if process.returncode >= 0 else 128 - process.returncode
    finally:
        os.close(owner)
        if process and process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
