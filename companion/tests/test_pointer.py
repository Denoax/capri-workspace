import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from capri.pointer import PointerUnavailable, Sampling, read_position, read_outputs


class SamplingTests(unittest.TestCase):
    def test_movement_gets_eight_hertz_then_stationary_backoff(self):
        s = Sampling()
        self.assertTrue(s.observe((-1200, 420), 1))
        self.assertEqual(s.interval(2), .125)
        self.assertFalse(s.observe((-1199, 421), 2))
        self.assertEqual(s.interval(5), 1)
        self.assertTrue(s.observe((-1199, 421), 5))

    def test_loss_backs_off_and_recovers_without_replaying_trace(self):
        s = Sampling()
        s.observe((8, 9), 0)
        self.assertTrue(s.failed())
        self.assertFalse(s.failed())
        for _ in range(20): s.failed()
        self.assertEqual(s.interval(50), 4)
        self.assertIsNone(s.last)
        self.assertTrue(s.observe((-2, -3), 51))
        self.assertEqual(s.failures, 0)

    def test_reader_requires_owned_socket_and_exact_bounded_integer_shape(self):
        with tempfile.TemporaryDirectory() as folder:
            plain = Path(folder) / 'plain'
            plain.write_text('x')
            with self.assertRaises(PointerUnavailable): read_position(plain)
            for value, accepted in [({'x': -1920, 'y': 33}, True), ({'x': True, 'y': 3}, False), ({'x': 2, 'y': 3, 'command': 'x'}, False), ({'x': 100001, 'y': 0}, False)]:
                path = Path(folder) / 'socket'
                with socket.socket(socket.AF_UNIX) as server:
                    server.bind(str(path));server.listen(1)
                    def serve():
                        c, _ = server.accept()
                        with c:
                            assert c.recv(100) == b'j/cursorpos'
                            c.sendall(json.dumps(value).encode())
                    t = threading.Thread(target=serve);t.start()
                    if accepted: self.assertEqual(read_position(path), (-1920, 33))
                    else:
                        with self.assertRaises(PointerUnavailable): read_position(path)
                    t.join(timeout=2);self.assertFalse(t.is_alive())
                path.unlink()


class OutputGeometryTests(unittest.TestCase):
    def test_native_geometry_is_bounded_normalized_and_strips_monitor_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'socket'
            with socket.socket(socket.AF_UNIX) as server:
                server.bind(str(path)); server.listen(1)
                def serve():
                    c, _ = server.accept()
                    with c:
                        assert c.recv(100) == b'j/monitors'
                        raw = json.dumps([{'name': 'DP-1', 'x': -864, 'y': -400, 'width': 1920, 'height': 1080, 'scale': 1.25, 'transform': 1, 'serial': 'never-forward'}]).encode()
                        c.sendall(raw[:17]); c.sendall(raw[17:])
                thread = threading.Thread(target=serve); thread.start()
                self.assertEqual(read_outputs(path), [{'name': 'DP-1', 'x': -864, 'y': -400, 'width': 864, 'height': 1536}])
                thread.join(timeout=2); self.assertFalse(thread.is_alive())
