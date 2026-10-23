"""Offline portability and required supported-host isolation prerequisites."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from loop.adapter import Adapter
from loop.collector import check_command
from loop.engine import Engine
from loop.settings import policy_path
from loop.store import Store
from loop.util import NeedsInput, digest, identity


class NamespacePrerequisiteTests(unittest.TestCase):
    def test_required_collector_namespaces(self):
        # Exercise the production collector flags, not merely bwrap installation.
        names = ('user', 'mnt', 'pid', 'net')
        outer = {name: os.readlink('/proc/self/ns/' + name) for name in names}
        script = (
            "import json,os,socket; "
            "print(json.dumps({'namespaces':{name:os.readlink('/proc/self/ns/'+name) "
            "for name in " + repr(names) + "},'interfaces':socket.if_nameindex()}))"
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            checkout = root / 'checkout'
            checkout.mkdir()
            result = check_command(checkout, ['python3', '-c', script], root / 'probe', timeout=10)
            output = (root / 'probe' / 'stdout.txt').read_text()
            errors = (root / 'probe' / 'stderr.txt').read_text()
            self.assertFalse(result['timeout'], output + errors)
            self.assertEqual(result['exit'], 0, output + errors)
            self.assertTrue(result['source_unchanged'])
            observed = json.loads(output)
            for name in names:
                with self.subTest(namespace=name):
                    self.assertNotEqual(outer[name], observed['namespaces'][name])
            self.assertTrue(all(name == 'lo' for _, name in observed['interfaces']))


class PortabilityTests(unittest.TestCase):
    def test_pending_question_precedes_any_credential_or_binary_preparation(self):
        with tempfile.TemporaryDirectory() as temp:
            store=Store(temp)
            try:
                task=store.create('portable',{'requirements':['frozen']},'owner')
                store.ask_question('owner','portable',1,'Synthetic pending question')
                with patch('loop.adapter.argv',side_effect=AssertionError('credential-dependent preparation reached')):
                    with self.assertRaises(NeedsInput):
                        Adapter(store,{}).run(task['id'],'preflight',temp,temp,'synthetic')
                self.assertEqual(store.db.execute('SELECT count(*) FROM attempts').fetchone()[0],0)
                self.assertEqual(store.task(task['id'])['state'],'NEEDS_INPUT')
            finally:store.close()

    def test_shipped_policy_is_bound_and_available_from_another_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);store=Store(root)
            try:
                engine=Engine(store,{'notes':str(root/'notes')})
                instruction=engine.instructions(root/'repo')[0]
                self.assertEqual(instruction['sha256'],digest(policy_path().read_bytes()))
                packet={'requirements':['frozen'],'instructions':[instruction]}
                task=store.create('policy',packet,'owner')
                result=engine.inputs(task['id'],'portable')
                self.assertEqual((result/'REFERENCE_LED_DESIGN.md').read_bytes(),policy_path().read_bytes())
                self.assertEqual(json.loads((result/'packet.json').read_text()),packet)
                self.assertEqual(store.task(task['id'])['content_hash'],identity(packet))
            finally:store.close()

    def test_portable_subset_runs_in_separate_root_without_model_or_auth(self):
        controller=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            env={'PATH':os.environ.get('PATH','/usr/bin:/bin'),'HOME':temp,
                 'PYTHONPATH':str(controller),'PYTHONDONTWRITEBYTECODE':'1'}
            script="import unittest; from loop.settings import policy_path; from loop.native_protocol import decode; assert policy_path().is_file(); assert decode('{\"id\":1}')[\"id\"]==1; suite=unittest.defaultTestLoader.discover("+repr(str(controller/'tests'))+",pattern='test_native.py'); result=unittest.TextTestRunner().run(suite); assert result.testsRun>=8 and result.wasSuccessful()"
            run=subprocess.run([sys.executable,'-c',script],cwd=temp,env=env,capture_output=True,text=True,timeout=15)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
