"""Restart uses the same real section-read grader as ordinary owner recovery."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_native_resume
import test_native_packet
from loop.context import Checkpoint
from loop.native import NativeAdapter, original_read_command
from loop.native_packet import prepare, read_commands, grade_reads
from loop.native_resume import run_resume
from loop.util import Rejected, digest


class RuntimePacketResumeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_native_resume.RuntimeResumeTests(
            'test_checkpoint_stops_existing_supervisor_and_check_is_read_only')
        self.fixture.setUp()

    def tearDown(self):
        self.fixture.tearDown()
        self.fixture.doCleanups()

    def run_restart(self, omit_last=False):
        f = self.fixture
        folder = f.inputs / 'current-context'
        args = test_native_packet.CurrentPacketTests().args()
        policy = b'Keep the human gate and original source. ' * 35
        args['originals']['policy.md'] = policy
        args['classifications']['policy.md']['sha256'] = digest(policy)
        index = prepare(folder, **args, section_limit=2048)
        self.assertGreater(len(index['sections']), 1)
        # This added fixture data is frozen before restarting, just like intake.
        saved = json.loads(f.saved_path.read_text())
        saved['maintenance_binding'].update(operation='synthetic-packet-runtime',
            predecessor_receipt={'sha256': '0' * 64})
        from loop.native_startup import StartupJournal
        f.journal = StartupJournal(f.store, 'synthetic-packet-runtime', saved['maintenance_binding'])
        from loop.util import tree
        for role in saved['roles'].values():
            role['input_files'] = tree(f.inputs)
        parent = Checkpoint(Path(saved['owner_checkpoint']), f.root)
        old_authority = json.loads(parent.path.read_text())['state']['authority']
        old_authority['lease_generations'] = dict(
            role_generation=4, thread='old-thinker', server='old-server',
            process='old-process', phase='read')
        parent = Checkpoint(f.root / 'packet-owner-checkpoint.json', f.root)
        parent.save(old_authority, ['original.txt'])
        saved['owner_checkpoint'] = str(parent.path)
        f.saved_path.write_text(json.dumps(saved))
        sha = digest(f.saved_path.read_bytes())
        # The fixture's committed checkpoint receipt changes along with its inputs.
        f.journal.append('RUNTIME_CHECKPOINTED', dict(receipt_sha256=sha))
        authority = copy.deepcopy(old_authority)
        authority['lease_generations'].update(
            role_generation=5, server='new-server', process='new-process')
        state = SimpleNamespace(persist=lambda: None,
            recovery_probe=lambda *a, **k: None, rehydrate=lambda *a: None)
        originals = {'/inputs/current-context/' + s['name']: s['sha256']
                     for s in index['sections']}
        captures = f.root / 'read-capture'
        captures.mkdir()
        commands = read_commands(index)
        dispatched = []

        def dispatch(payload, *, probe=False, validate, **kwargs):
            text = payload[0]['text']
            if probe:
                self.assertTrue(validate('READY'))
                return 'READY', {}
            rows = []
            # A deterministic stand-in follows literal read commands. The real
            # packet grader independently decides whether that output suffices.
            selected = [line.partition(': ')[2] for line in text.splitlines()
                        if line.partition(': ')[0].isdigit()
                        and line.partition(': ')[2].startswith('python3 ')]
            if 'Read originals using ' in text:
                selected = [original_read_command(originals)]
            if omit_last:
                selected = selected[:-1]
            for n, command in enumerate(selected):
                if command in commands:
                    body = (folder / index['sections'][commands.index(command)]['name']).read_text()
                else:
                    body = json.dumps({'files': {name: {
                        'sha256': expected, 'content': (folder / Path(name).name).read_text()}
                        for name, expected in originals.items()}})
                item = dict(id='read-' + str(n), type='commandExecution',
                    command=command, status='completed', exitCode=0, aggregatedOutput=body)
                for method in ('item/started', 'item/completed'):
                    rows.append(dict(message=dict(method=method, params=dict(
                        threadId='thread', turnId='turn', item=item))))
            (captures / 'events.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
            if not grade_reads(captures, folder, thread='thread', turn='turn'):
                raise Rejected('Required separate section reads were not delivered')
            final = text.rsplit('Return exactly ', 1)[1]
            self.assertTrue(validate(final))
            dispatched.extend(selected)
            return final, {}

        backend = SimpleNamespace(clients=True, error=None,
                                  proc=SimpleNamespace(poll=lambda: None))
        slots = SimpleNamespace(root=f.root_runtime,
            backends={r: backend for r in f.rows},
            start_role=lambda *a, **k: None, restore_saved_role=lambda *a, **k: None,
            save=lambda: f.rows, mapping_changed=None)
        adapter = SimpleNamespace(slots=slots,
            create_held_capability=lambda *a: 'synthetic-held-token',
            register_thinker=lambda *a, **k: None, hold_thinker_tools=lambda: None,
            prepare_owner_context=lambda: (state, {}), owner_authority=lambda: authority,
            owner_originals=lambda: originals, owner_packet=lambda: index,
            owner_dispatch=dispatch, prepare_context=lambda *a: state,
            derive_recovery_checkpoint=lambda *a: parent,
            probe=lambda *a: None, rehydrate=lambda *a: None, close=lambda: None)
        adapter.owner_read_guide = lambda value: NativeAdapter.owner_read_guide(adapter, value)
        intake = SimpleNamespace(path=f.root / 'unused-intake', start=lambda: None, close=lambda: None)
        terminals = SimpleNamespace(sync=lambda *a: None, attach_command=lambda: 'synthetic', close=lambda: None)
        operator = SimpleNamespace(path=f.root / 'unused-operator', stop_requested=False,
            start=lambda: None, close=lambda: None)
        operator.poll = lambda *_: setattr(operator, 'stop_requested', True)
        args = SimpleNamespace(prepared=f.saved_path, prepared_sha256=sha, check=False, headless=False)
        with patch('loop.native_resume.process_identity', return_value=None), \
             patch('loop.native.NativeAdapter', return_value=adapter), \
             patch('loop.native.NativeIntake', return_value=intake), \
             patch('loop.native.NativeTerminals', return_value=terminals), \
             patch('loop.native_operator.NativeOperator', return_value=operator):
            run_resume(f.cfg, args, f.controller)
        return dispatched, commands

    def test_restart_delivers_every_current_section_in_order(self):
        dispatched, required = self.run_restart()
        self.assertEqual(dispatched, required)

    def test_missing_section_keeps_restart_held(self):
        with self.assertRaisesRegex(Rejected, 'separate section'):
            self.run_restart(omit_last=True)


if __name__ == '__main__':
    unittest.main()
