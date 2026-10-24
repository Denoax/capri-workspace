import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from capri.broker import Denied
from capri.maintenance import Maintenance
from capri.versions import Versions,VersionError,identity,snapshot

BASE=Path(__file__).resolve().parents[1]
class VersionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='capri-versions-');self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
        self.source=self.base/'source';(self.source/'qml').mkdir(parents=True)
        (self.source/'launcher.py').write_text("print('PUBLIC-BASELINE')\n");(self.source/'qml/shell.qml').write_text('// Public native fixture\n')
        self.manager=Versions(self.base/'install')
        self.baseline=self.manager.stage(self.source,{'legacy':True,'kind':'public fixture'})
        self.manager.activate(self.baseline,origin='owner-ui');self.manager.mark_good(self.baseline)
    def candidate(self):
        (self.source/'launcher.py').write_text('raise SystemExit(1)\n')
        return self.manager.stage(self.source,{'kind':'public deliberate crash fixture'})
    def test_exact_hash_and_owner_approval_are_required_before_any_switch(self):
        candidate=self.candidate()
        with self.assertRaises(VersionError):self.manager.activate(candidate,origin='model')
        with self.assertRaises(VersionError):self.manager.stage(self.source,{'ci':'green','signature':'self-created'},expected='0'*64)
        self.assertEqual(self.manager.state()['current'],self.baseline)
        self.assertEqual((self.manager.root/'current').resolve(),self.manager.versions/self.baseline)
    def test_tampering_with_installed_bytes_is_detected_even_if_provenance_claims_success(self):
        candidate=self.candidate();path=self.manager.versions/candidate/'launcher.py';path.chmod(0o600);path.write_text("print('forged success')\n")
        with self.assertRaises(VersionError):self.manager.verify(candidate)
    def test_rollback_is_one_shot_and_preserves_independent_private_state(self):
        private=self.base/'private-account-and-draft';private.write_text('PUBLIC-FIXTURE-NOT-CREDENTIALS');before=private.read_bytes()
        candidate=self.candidate();self.manager.activate(candidate,origin='owner-ui')
        result=self.manager.rollback(automatic=True)
        self.assertEqual(result['current'],self.baseline);self.assertIn(candidate,self.manager.state()['failed']);self.assertEqual(private.read_bytes(),before)
        with self.assertRaises(VersionError):self.manager.rollback(automatic=True)
        with self.assertRaises(VersionError):self.manager.activate(candidate,origin='owner-ui')
    def test_real_supervisor_rolls_back_after_three_deliberate_process_crashes(self):
        bootstrap=self.manager.root/'bootstrap';bootstrap.mkdir()
        for name,source in [('bootstrap.py',BASE/'tools/bootstrap.py'),('versions.py',BASE/'capri/versions.py'),('parent_exec.py',BASE/'capri/parent_exec.py')]:shutil.copyfile(source,bootstrap/name)
        candidate=self.candidate();self.manager.activate(candidate,origin='owner-ui')
        env={**os.environ,'CAPRI_RUNTIME_NAME':'capri-test-crash'}
        result=subprocess.run([sys.executable,'-B',str(bootstrap/'bootstrap.py'),'run'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr.decode())
        self.assertIn(b'PUBLIC-BASELINE',result.stdout);self.assertEqual(self.manager.state()['current'],self.baseline)
        self.assertTrue(self.manager.state()['rollback_used']);self.assertTrue((self.manager.root/'last-rollback.json').exists())
    def test_duplicate_supervisor_and_live_rollback_cannot_change_the_active_version(self):
        bootstrap=self.manager.root/'bootstrap';bootstrap.mkdir()
        for name,source in [('bootstrap.py',BASE/'tools/bootstrap.py'),('versions.py',BASE/'capri/versions.py'),('parent_exec.py',BASE/'capri/parent_exec.py')]:shutil.copyfile(source,bootstrap/name)
        (self.source/'launcher.py').write_text("import time\nprint('OWNER-READY',flush=True)\ntime.sleep(60)\n")
        candidate=self.manager.stage(self.source,{'kind':'public resident owner fixture'});self.manager.activate(candidate,origin='owner-ui');before=self.manager.state()
        env={**os.environ,'CAPRI_RUNTIME_NAME':'capri-test-dupe','XDG_RUNTIME_DIR':str(self.base)}
        argv=[sys.executable,'-B',str(bootstrap/'bootstrap.py')]
        owner=subprocess.Popen([*argv,'run'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            import select
            self.assertTrue(select.select([owner.stdout],[],[],5)[0],'Fixture owner never became ready')
            self.assertEqual(owner.stdout.readline().strip(),b'OWNER-READY')
            duplicate=subprocess.run([*argv,'run'],env=env,capture_output=True,timeout=3)
            self.assertEqual(duplicate.returncode,0,duplicate.stderr.decode());self.assertIn(b'already running',duplicate.stdout)
            denied=subprocess.run([*argv,'rollback'],env=env,capture_output=True,timeout=3)
            self.assertNotEqual(denied.returncode,0);self.assertEqual(self.manager.state(),before);self.assertIsNone(owner.poll())
        finally:owner.terminate();owner.communicate(timeout=10)
    def test_ended_wayland_session_exits_without_launching_or_disabling_the_candidate(self):
        bootstrap=self.manager.root/'bootstrap';bootstrap.mkdir()
        for name,source in [('bootstrap.py',BASE/'tools/bootstrap.py'),('versions.py',BASE/'capri/versions.py'),('parent_exec.py',BASE/'capri/parent_exec.py'),('session_start.py',BASE/'tools/session_start.py')]:shutil.copyfile(source,bootstrap/name)
        (bootstrap/'session-hook.json').write_text('{}')
        candidate=self.candidate();self.manager.activate(candidate,origin='owner-ui');before=self.manager.state()
        env={**os.environ,'CAPRI_RUNTIME_NAME':'capri-test-ended','XDG_RUNTIME_DIR':str(self.base),'WAYLAND_DISPLAY':'wayland-missing'}
        result=subprocess.run([sys.executable,'-B',str(bootstrap/'bootstrap.py'),'run'],env=env,capture_output=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr.decode());self.assertEqual(self.manager.state(),before)
        self.assertFalse((self.manager.root/'last-rollback.json').exists())
    def test_disposable_installer_restores_exact_owned_v1_files_and_keeps_private_data(self):
        prefix=self.base/'home';data=prefix/'.local/share/capri';data.mkdir(parents=True)
        files={prefix/'.local/bin/capri':'#!/bin/sh\n# public old launcher\n',prefix/'.local/share/applications/capri.desktop':'# public old desktop\n',prefix/'.config/systemd/user/capri-companion.service':'# public old unit\n'}
        for p,text in files.items():p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
        old={'marker':'CAPRI_DESKTOP_COMPANION_V1_OWNED','source':str(self.source),'files':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
        manifest=data/'install.json';manifest.write_text(json.dumps(old));private=data/'retained-public-state';private.write_text('PUBLIC-DRAFT-AND-HISTORY-FIXTURE')
        env={**os.environ,'CAPRI_PYTHON':sys.executable}
        installed=subprocess.run([sys.executable,'-B',str(BASE/'tools/install_v2.py'),'--prefix',str(prefix),'--baseline',str(self.source),'--baseline-sha','public-fixture-baseline','--sha','public-fixture-candidate'],env=env,capture_output=True,text=True,timeout=30)
        self.assertEqual(installed.returncode,0,installed.stderr)
        self.assertEqual(json.loads(manifest.read_text())['marker'],'CAPRI_DESKTOP_COMPANION_V2_OWNED')
        removed=subprocess.run([sys.executable,'-B',str(BASE/'tools/install_v2.py'),'--prefix',str(prefix),'--uninstall'],env=env,capture_output=True,text=True,timeout=20)
        self.assertEqual(removed.returncode,0,removed.stderr)
        self.assertEqual(json.loads(manifest.read_text()),old)
        self.assertEqual({p:p.read_text() for p in files},files);self.assertEqual(private.read_text(),'PUBLIC-DRAFT-AND-HISTORY-FIXTURE')

class ProposalTests(unittest.IsolatedAsyncioTestCase):
    async def test_changed_proposal_cannot_reuse_a_passing_verification_or_forge_install_authority(self):
        with tempfile.TemporaryDirectory(prefix='capri-proposal-') as folder:
            base=Path(folder);source=base/'source';(source/'qml').mkdir(parents=True);(source/'tests').mkdir()
            (source/'launcher.py').write_text("print('PUBLIC SOURCE')\n");(source/'qml/shell.qml').write_text('// PUBLIC UI\n')
            manager=Maintenance(base/'data',base/'state',source);record=manager.stage()
            with self.assertRaises(Denied):manager.install(record['id'],'0'*64,origin='model')
            root=Path(record['root']);(root/'launcher.py').write_text("print('PUBLIC PROPOSED CHANGE')\n")
            review=manager.review();self.assertIn('launcher.py',review['files']);self.assertIsNone(review['verification'])
            with self.assertRaises(Denied):manager.install(record['id'],review['digest'],origin='owner-ui')
            (root/'qml').rename(root/'moved-ui');(root/'qml').symlink_to(source/'qml',target_is_directory=True)
            with self.assertRaises((ValueError,OSError)):manager.review()
    @unittest.skipUnless(os.environ.get('CAPRI_HOST_INTEGRATION')=='1','Actual proposal verification requires host namespaces')
    async def test_isolated_proposal_runs_actual_tests_and_installs_only_unchanged_reviewed_bytes(self):
        with tempfile.TemporaryDirectory(prefix='capri-proposal-run-') as folder:
            base=Path(folder);source=base/'source';(source/'qml').mkdir(parents=True);(source/'tests').mkdir()
            (source/'launcher.py').write_text("print('PUBLIC SOURCE')\n");(source/'qml/shell.qml').write_text('// PUBLIC UI\n')
            (source/'calc.py').write_text('def add(a,b):return a-b\n')
            (source/'tests/test_public.py').write_text('import unittest\nfrom calc import add\nclass Contract(unittest.TestCase):\n def test_sum(self):self.assertEqual(add(2,3),5)\n')
            manager=Maintenance(base/'data',base/'state',source);record=manager.stage();root=Path(record['root'])
            failed=await manager.verify();self.assertNotEqual(failed['exit_code'],0)
            (root/'calc.py').write_text('def add(a,b):return a+b\n')
            passed=await manager.verify();self.assertEqual(passed['exit_code'],0,passed['output'])
            review=manager.review();(root/'calc.py').write_text('def add(a,b):return a+b+1\n')
            with self.assertRaises(ValueError):manager.install(record['id'],review['digest'],origin='owner-ui')
            (root/'calc.py').write_text('def add(a,b):return a+b\n')
            installed=manager.install(record['id'],review['digest'],origin='owner-ui');self.assertEqual(installed,review['digest'])
