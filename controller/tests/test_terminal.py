"""Synthetic terminal I/O tests; these never perform or prove a human decision."""
import json
import os
from pathlib import Path
import pty
import select
import signal
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loop.cli import require_human_tty
from loop.util import Rejected


def probe_terminal(mode):
    reader, writer = os.pipe()
    if mode == "none":
        pid = os.fork()
        master = None
    else:
        pid, master = pty.fork()
    if pid == 0:
        os.close(reader)
        if mode == "none":
            os.setsid()
        elif mode == "background":
            nested = os.fork()
            if nested:
                os.close(writer)
                os.waitpid(nested, 0)
                os._exit(0)
            os.setpgrp()
            signal.signal(signal.SIGTTOU, signal.SIG_IGN)
        try:
            with require_human_tty() as terminal:
                terminal.write("SYNTHETIC_IO_TEST\n")
                terminal.flush()
                result = {"opened": True, "isatty": terminal.isatty()}
        except Rejected as error:
            result = {"opened": False, "error": str(error)}
        except BaseException as error:
            result = {"unexpected_error": repr(error)}
        os.write(writer, json.dumps(result).encode())
        os.close(writer)
        os._exit(0)
    os.close(writer)
    try:
        ready, _, _ = select.select([reader], [], [], 3)
        if not ready:
            os.kill(pid, signal.SIGKILL)
            raise AssertionError("Synthetic terminal check exceeded its 3-second budget")
        return json.loads(os.read(reader, 8192))
    finally:
        os.close(reader)
        os.waitpid(pid, 0)
        if master is not None:
            os.close(master)


class TerminalBoundaryTests(unittest.TestCase):
    def test_foreground_nonseekable_terminal_supports_text_io(self):
        self.assertEqual({"opened": True, "isatty": True}, probe_terminal("foreground"))

    def test_background_process_group_is_rejected(self):
        result = probe_terminal("background")
        self.assertFalse(result["opened"])
        self.assertIn("foreground human terminal", result["error"])

    def test_process_without_controlling_terminal_is_rejected(self):
        result = probe_terminal("none")
        self.assertFalse(result["opened"])
        self.assertIn("real controlling terminal", result["error"])


class DeadPaneRecoveryTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from types import SimpleNamespace
        from loop.native import NativeTerminals
        from loop.settings import Settings, ROLES
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rows, self.panes, self.calls = {}, {}, []
        records = {'_server': dict(pid=100, process_identity='100')}
        for i, role in enumerate(ROLES):
            self.rows[role] = dict(thread=role, generation=0, empty=False, endpoint='unix:///role')
            records[role] = dict(pane='%'+str(i), pid=200+i,
                process_identity=str(200+i), thread=role, generation=0)
            self.panes[role] = ['%'+str(i), str(200+i), '0']
        (self.root/'terminal-registry.json').write_text(json.dumps(records))
        self.panes['thinker'][1:] = ['', '1']
        def runner(argv, **kwargs):
            self.calls.append(argv)
            output = ''
            if 'list-panes' in argv:
                output = '\n'.join(r+'\t'+'\t'.join(self.panes[r]) for r in ROLES)
            elif 'respawn-pane' in argv:
                self.panes['thinker'][1:] = ['777', '0']
            elif 'display-message' in argv:
                output = '777\n'
            return SimpleNamespace(returncode=0, stdout=output, stderr='')
        slots = SimpleNamespace(root=self.root,
            settings=Settings(sys.executable, '/operator/auth', str(self.root)))
        self.terminals = NativeTerminals(slots, runner=runner)

    def test_blank_dead_pid_reconnects_exact_pane_then_cleanup(self):
        from unittest.mock import patch
        with patch('loop.native.process_identity', side_effect=lambda pid: str(pid)):
            self.terminals.sync(self.rows)
            self.assertEqual(self.terminals.records['thinker']['pid'], 777)
            self.terminals.close()
        respawns = [a for a in self.calls if 'respawn-pane' in a]
        self.assertEqual(len(respawns), 1)
        self.assertEqual(respawns[0][respawns[0].index('-t')+1], '%0')
        self.assertEqual(respawns[0][2], str(self.root/'ui.sock'))
        self.assertTrue(any('kill-session' in a for a in self.calls))
        self.assertEqual(self.terminals.records, {})

    def test_blank_dead_pid_cleanup_without_reconnect(self):
        from unittest.mock import patch
        with patch('loop.native.process_identity', side_effect=lambda pid: str(pid)):
            self.terminals.close()
        self.assertTrue(any('kill-session' in a for a in self.calls))

    def test_unowned_or_live_identity_drift_blocks_all_signaling(self):
        from unittest.mock import patch
        import copy
        original = copy.deepcopy(self.panes)
        for operation in ('sync', 'close'):
            for failure in ('pane', 'live_blank', 'live_reused', 'dead_pid', 'server'):
                with self.subTest(operation=operation, failure=failure):
                    self.calls.clear()
                    self.panes = copy.deepcopy(original)
                    if failure == 'pane': self.panes['thinker'][0] = '%999'
                    if failure == 'live_blank': self.panes['thinker'][2] = '0'
                    if failure == 'dead_pid': self.panes['thinker'][1] = '999'
                    def identity(pid):
                        return 'reused' if ((failure == 'server' and pid == 100) or
                            (failure == 'live_reused' and pid == 201)) else str(pid)
                    with patch('loop.native.process_identity', side_effect=identity):
                        with self.assertRaises(Rejected):
                            if operation == 'sync': self.terminals.sync(self.rows)
                            else: self.terminals.close()
                    self.assertFalse(any('respawn-pane' in a or 'kill-session' in a for a in self.calls))


if __name__ == "__main__":
    unittest.main()
