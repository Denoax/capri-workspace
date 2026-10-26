"""Ephemeral presentation-only Hyprland cursor reader. Never talks to the core.

One resident helper uses bounded native IPC; no subprocesses, keys, injection,
files, provider context or disk trace. Quickshell consumes changed positions.
"""
import ctypes
import json
import os
from pathlib import Path
import re
import signal
import socket
import stat
import struct
import sys
import time


class PointerUnavailable(ValueError):
    pass


def read_response(path, command, bound=1024, timeout=0.25):
    info = Path(path).lstat()
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
        raise PointerUnavailable("Compositor socket ownership mismatch")
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(timeout)
        client.connect(str(path))
        _, uid, _ = struct.unpack("3i", client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if uid != os.getuid():
            raise PointerUnavailable("Compositor peer ownership mismatch")
        client.sendall(command)
        chunks = []
        size = 0
        while True:
            chunk = client.recv(min(4096, bound + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > bound:
                raise PointerUnavailable("Compositor response exceeds bound")
        raw = b"".join(chunks)
    if len(raw) > bound:
        raise PointerUnavailable("Compositor response exceeds bound")
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError) as error:
        raise PointerUnavailable("Invalid compositor response") from error
    return value


def read_position(path, timeout=0.25):
    value = read_response(path, b"j/cursorpos", timeout=timeout)
    if not isinstance(value, dict) or set(value) != {"x", "y"}:
        raise PointerUnavailable("Unexpected compositor response")
    if any(type(value[k]) is not int or abs(value[k]) > 100000 for k in ("x", "y")):
        raise PointerUnavailable("Invalid layout coordinates")
    return value["x"], value["y"]


def read_outputs(path):
    """Keep only logical geometry, never serials, EDID or other monitor data."""
    values = read_response(path, b"j/monitors", bound=65536)
    if not isinstance(values, list) or len(values) > 32:
        raise PointerUnavailable("Invalid output list")
    outputs = []
    for v in values:
        if not isinstance(v, dict) or not isinstance(v.get("name"), str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", v["name"]):
            raise PointerUnavailable("Invalid output name")
        if any(type(v.get(k)) is not int or abs(v[k]) > 100000 for k in ("x", "y", "width", "height", "transform")):
            raise PointerUnavailable("Invalid output geometry")
        scale = v.get("scale")
        if type(scale) not in (int, float) or not 0.25 <= scale <= 8 or v["width"] <= 0 or v["height"] <= 0 or not 0 <= v["transform"] <= 7:
            raise PointerUnavailable("Invalid output scale or transform")
        width, height = v["width"], v["height"]
        if v["transform"] % 2:
            width, height = height, width
        outputs.append({"name": v["name"], "x": v["x"], "y": v["y"], "width": width / scale, "height": height / scale})
    return outputs


class Sampling:
    """Sampling policy owns no coordinate history; only the last ephemeral point."""
    def __init__(self):
        self.last = None
        self.last_move = -100.0
        self.last_emit = -100.0
        self.failures = 0

    def observe(self, point, now):
        changed = self.last is None or abs(point[0] - self.last[0]) + abs(point[1] - self.last[1]) >= 3
        if changed:
            self.last_move = now
        self.last = point
        self.failures = 0
        emit = changed or now - self.last_emit >= 2
        if emit:
            self.last_emit = now
        return emit

    def failed(self):
        first = self.failures == 0
        self.failures = min(self.failures + 1, 5)
        self.last = None
        return first

    def interval(self, now):
        if self.failures:
            return min(4.0, 0.25 * 2 ** self.failures)
        return 0.125 if now - self.last_move < 2.5 else 1.0


def gesture_samples(path, epoch, *, clock=time.monotonic, wait=time.sleep, final_requested=lambda: False):
    """Independent on-demand 120Hz global-input clock for a held gesture.

    No scene/window coordinates, key hooks, input injection or stored trace.
    Failure ends the gesture instead of replaying an old coordinate.
    """
    outputs = []
    geometry_at = float("-inf")
    while True:
        started = clock()
        try:
            final = final_requested()
            if started - geometry_at >= 0.25:
                outputs = read_outputs(path)
                geometry_at = started
            x, y = read_position(path)
        except (OSError, PointerUnavailable):
            yield {"kind": "drag", "epoch": epoch, "valid": False, "monotonic": clock()}
            return
        yield {"kind": "drag", "epoch": epoch, "valid": True,
               "x": x, "y": y, "outputs": outputs, "monotonic": clock(), "final": final}
        wait(max(0.0, 1 / 120 - (clock() - started)))


def main():
    parent = os.getppid()
    if parent <= 1 or ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGTERM, 0, 0, 0) != 0 or os.getppid() != parent:
        return 125
    signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,200}", signature):
        return 1
    path = Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user/" + str(os.getuid()))) / "hypr" / signature / ".socket.sock"
    if len(sys.argv) > 1:
        if len(sys.argv) != 3 or sys.argv[1] != "--gesture" or not re.fullmatch(r"[1-9][0-9]{0,9}", sys.argv[2]):
            return 2
        epoch = int(sys.argv[2])
        if epoch > 2147483647:
            return 2
        os.set_blocking(sys.stdin.fileno(), False)
        release = bytearray()
        def final_requested():
            try:
                release.extend(os.read(sys.stdin.fileno(), 64))
            except BlockingIOError:
                pass
            if not b"release\n".startswith(release):
                raise PointerUnavailable("Invalid gesture control")
            return release == b"release\n"
        try:
            for packet in gesture_samples(path, epoch, final_requested=final_requested):
                print(json.dumps(packet), flush=True)
        except BrokenPipeError:
            return 0
        return 0
    sampling = Sampling()
    outputs = []
    geometry_at = -100.0
    try:
        while True:
            now = time.monotonic()
            try:
                if now - geometry_at >= 5:
                    outputs = read_outputs(path)
                    geometry_at = now
                point = read_position(path)
                if sampling.observe(point, now):
                    print(json.dumps({"valid": True, "x": point[0], "y": point[1], "outputs": outputs}), flush=True)
            except (OSError, PointerUnavailable):
                if sampling.failed():
                    print('{"valid":false}', flush=True)
            time.sleep(sampling.interval(time.monotonic()))
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
