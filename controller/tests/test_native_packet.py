import copy
import json
from pathlib import Path
import tempfile
import unittest

from loop.native_packet import prepare, load, feasibility, read_commands, grade_reads, visible_sections
from loop.util import Rejected, digest, identity


class CurrentPacketTests(unittest.TestCase):
    def args(self):
        requirements=[dict(id='N0'+str(i),text='Exact requirement '+str(i),origin='original',check_ids=[])
                      for i in range(1,9)]
        original=json.dumps(requirements).encode()
        return dict(originals={'requirements.json':original,'policy.md':b'Keep the human gate.','older.md':b'Retained guard.'},
            classifications={'requirements.json':dict(category='duplicate',equals='requirements',reason='Exact value duplicate',sha256=digest(original)),
                             'policy.md':dict(category='current',reason='Current source policy',sha256=digest(b'Keep the human gate.')),
                             'older.md':dict(category='reference',reason='Guard retained by exact current requirement',covers=['requirements.N01'],sha256=digest(b'Retained guard.'))},
            requirements=requirements,proposal=dict(requirements=requirements,checks=[],steps=[]),
            current_request=dict(text='Current scope',human_answers=[dict(question='q',text='Untitled')]),
            answers=[dict(question='q',text='Untitled')],binding=dict(source='source',owner='owner',scope='scope',active_originals=['policy.md']))

    def frozen(self, args):
        p=dict(requirements=args['requirements'],request={},source={},instructions=[],
            limits=dict(step_wall_seconds=240,max_tool_interactions=12,max_prompt_bytes=60000,context_occupancy='UNKNOWN'),checks=[],steps=[])
        p.update(requirements_hash=identity(p['requirements']),instructions_hash=identity([]))
        return p

    def capture(self, root,index,folder):
        values=[]
        for n,command in enumerate(read_commands(index)):
            item=dict(id='read-'+str(n),type='commandExecution',command=command,status='completed',exitCode=0,
                      aggregatedOutput=(folder/index['sections'][n]['name']).read_text())
            for method in ['item/started','item/completed']:
                values.append(dict(message=dict(method=method,params=dict(threadId='thread',turnId='turn',item=item))))
        (root/'events.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in values))
        return values

    def test_exact_semantic_units_and_duplicate_projection(self):
        with tempfile.TemporaryDirectory() as temp:
            args=self.args();index=prepare(Path(temp),**args,section_limit=2048)
            self.assertEqual(index,load(Path(temp)))
            units=[u for s in index['sections'] for u in json.loads((Path(temp)/s['name']).read_text())['units']]
            self.assertEqual([u['value'] for u in units if u['name'].startswith('requirements.')],args['requirements'])
            self.assertTrue(all(s['bytes']<=2048 for s in index['sections']))

    def test_changed_requirement_stale_answer_and_unmapped_history_reject(self):
        for kind in ['requirement','answer','classification','coverage','active_omission']:
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as temp:
                args=self.args()
                if kind=='requirement':
                    args['proposal']=copy.deepcopy(args['proposal']);args['proposal']['requirements'][0]['text']+='x'
                elif kind=='answer':args['answers']=[]
                elif kind=='classification':del args['classifications']['policy.md']
                elif kind=='coverage':args['classifications']['older.md'].update(covers=['missing'])
                else:args['classifications']['policy.md'].update(category='history')
                with self.assertRaises(Rejected):prepare(Path(temp),**args)

    def test_complete_serialization_and_six_read_plan_reject_before_dispatch(self):
        args=self.args();packet=self.frozen(args)
        with self.assertRaisesRegex(Rejected,'infeasible'):
            feasibility(dict(sections=[{}]*6),packet)
        packet['late_research']='x'*60000
        with self.assertRaisesRegex(Rejected,'serialized'):
            feasibility(dict(sections=[{}]),packet)
        with self.assertRaisesRegex(Rejected,'infeasible'):
            feasibility(dict(sections=[{}]),self.frozen(args),seconds_left=30)

    def test_ordered_paired_reads_are_required(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'current-context';index=prepare(folder,**self.args(),section_limit=2048)
            rows=self.capture(root,index,folder)
            self.assertTrue(grade_reads(root,folder,thread='thread',turn='turn'))
            for broken in [rows[:-1],list(reversed(rows)),rows+rows[:2]]:
                (root/'events.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in broken))
                self.assertFalse(grade_reads(root,folder,thread='thread',turn='turn'))
            self.capture(root,index,folder)
            self.assertFalse(grade_reads(root,folder,thread='wrong',turn='turn'))

    def test_public_visibility_is_separate_and_bound_to_turn(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'current-context';index=prepare(folder,**self.args())
            self.capture(root,index,folder)
            self.assertFalse(grade_reads(root,folder,runtime=root,thread='thread',turn='turn'))
            sessions=root/'sessions';sessions.mkdir();path=sessions/'rollout-thread.jsonl'
            body=(folder/index['sections'][0]['name']).read_bytes()
            rows=[dict(type='turn_context',payload=dict(turn_id='turn')),
                  dict(type='response_item',payload=dict(type='function_call_output',output=json.dumps(dict(output=body.decode()))))]
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            self.assertTrue(visible_sections(root,'thread','turn',[body]))
            self.assertFalse(visible_sections(root,'thread','other',[body]))
            rows[-1]['payload']['output']='Warning: truncated output\n'+body.decode()[:10]
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            self.assertFalse(visible_sections(root,'thread','turn',[body]))

    def test_tampered_section_and_envelope_hold(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);index=prepare(root,**self.args());p=root/index['sections'][0]['name']
            p.write_text(p.read_text()+' ')
            with self.assertRaises(Rejected):load(root)


if __name__=='__main__':
    unittest.main()
