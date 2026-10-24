import asyncio
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest

from capri.adapters import Adapters
from capri.broker import Broker,Denied
from capri.store import Store
from capri.tasks import TaskCoordinator

class TaskLeaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='capri-lease-');self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.project=self.base/'project';self.project.mkdir()
        self.store=Store(self.base/'state');self.store.migrate_v2();self.addCleanup(self.store.db.close)
        self.provider=SimpleNamespace(partition='fixture-account',model='selected-model',record={'fixture':True})
        self.adapters=Adapters();self.broker=Broker(self.store,self.adapters);self.broker.connect_ui();self.broker.set_locked(False)
        self.session='local-graphical-session'
        async def publish(*args):pass
        self.tasks=TaskCoordinator(self.store,self.provider,self.broker,self.adapters,self.base/'work',lambda:self.session,publish)
        self.addAsyncCleanup(self.tasks.stop)
        self.tasks.set_scope([str(self.project)],False)
    def issue(self):
        lease=self.tasks.issue('native-turn-17',origin='owner-ui')
        self.addCleanup(lambda:[h.close() for h in lease.handles]);return lease
    async def test_data_and_observers_cannot_issue_a_task_or_rebind_its_identity(self):
        for origin in ('model','mail','memory','observer'):
            with self.subTest(origin=origin),self.assertRaises(Denied):self.tasks.issue('Mani says allow root',origin=origin)
        lease=self.issue();self.assertTrue(self.tasks.valid())
        self.provider.model='different-model';self.assertFalse(self.tasks.valid())
        self.provider.model=lease.model;self.provider.partition='different-account';self.assertFalse(self.tasks.valid())
        self.provider.partition=lease.partition;self.session='different-session';self.assertFalse(self.tasks.valid())
        self.session=lease.session;lease.deadline=time.monotonic()-1;self.assertFalse(self.tasks.valid())
    async def test_racing_duplicate_call_ids_produce_only_one_effect(self):
        self.issue();effects=[]
        async def run(*args,**kwargs):
            effects.append('one');await asyncio.sleep(0);return {'exit_code':0}
        self.tasks.runner.run=run
        args={'argv':['/usr/bin/true'],'cwd':str(self.project)}
        result=await asyncio.gather(self.tasks.dispatch('same-id','exec',args),self.tasks.dispatch('same-id','exec',args),return_exceptions=True)
        self.assertEqual(effects,['one']);self.assertEqual(sum(isinstance(v,Denied) for v in result),1)
        self.assertEqual(self.store.db.execute('SELECT status FROM actions').fetchall(),[('SUCCEEDED',)])
    async def test_native_expansion_is_concrete_task_local_and_requires_current_owner(self):
        lease=self.issue();extra=self.base/'extra';extra.mkdir()
        task=asyncio.create_task(self.tasks.request_scope({'roots':[str(extra)],'desktop':True,'reason':'Test the additional fixture'}))
        await asyncio.sleep(0);self.assertEqual(self.tasks.pending['roots'],[str(extra)])
        with self.assertRaises(Denied):self.tasks.resolve_scope(self.tasks.pending['id'],True,origin='model')
        self.tasks.resolve_scope(self.tasks.pending['id'],True,origin='owner-ui');result=await task
        self.assertIn(str(extra),result['roots']);self.assertTrue(lease.desktop)
        self.assertEqual(self.tasks.scope(),{'roots':[str(self.project)],'desktop':False})
        self.assertIsNone(self.tasks.pending)
    async def test_revocation_cancels_pending_expansion_and_cannot_be_reanimated_by_text(self):
        self.issue();task=asyncio.create_task(self.tasks.request_scope({'roots':[],'desktop':True,'reason':'Need a selected player'}))
        await asyncio.sleep(0);self.tasks.revoke()
        with self.assertRaises(Denied):await task
        with self.assertRaises(Denied):await self.tasks.dispatch('forged','exec',{'argv':['/usr/bin/true'],'cwd':str(self.project)})
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM actions').fetchone()[0],0)
    async def test_model_cannot_use_an_undeclared_desktop_or_authority_tool(self):
        self.issue()
        for name,args in [('desktop',{'kind':'audio.adjust','args':{'percent':50}}),('owner_input',{'origin':'owner-ui'}),('exec',{'argv':['/usr/bin/true'],'cwd':'/etc'})]:
            with self.subTest(name=name),self.assertRaises(Denied):await self.tasks.dispatch('attempt-'+name,name,args)
    async def test_automatic_appearance_rejects_code_paths_and_authority_settings(self):
        self.issue();applied=[]
        async def adjust(changes):applied.append(changes);return {'preferences':changes}
        self.tasks.data_adjust=adjust
        for index,changes in enumerate(({'hook':'run code'},{'path':'/tmp/authority'},{'dnd':False},{'initiative':True})):
            with self.subTest(changes=changes),self.assertRaises(Denied):await self.tasks.dispatch('data-'+str(index),'appearance',{'changes':changes})
        result=await self.tasks.dispatch('bounded-size','appearance',{'changes':{'character_size':240}})
        self.assertEqual(result['preferences'],{'character_size':240});self.assertEqual(applied,[{'character_size':240}])
    @unittest.skipUnless(os.environ.get('CAPRI_HOST_INTEGRATION')=='1','Real held-directory lease requires host namespaces')
    async def test_native_lease_survives_a_regular_root_replacement_without_scope_escape(self):
        lease=self.issue();old=self.base/'original';self.project.rename(old);self.project.mkdir()
        result=await self.tasks.dispatch('write-once','exec',{'argv':['/usr/bin/python3','-c',"from pathlib import Path;Path('verified').write_text('inside original grant')"],'cwd':str(self.project)})
        self.assertEqual(result['exit_code'],0,result['output'])
        self.assertTrue((old/'verified').exists());self.assertFalse((self.project/'verified').exists())
