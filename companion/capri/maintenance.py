"""Isolated self-patch proposals; native review binds exact bytes before install."""
import difflib
import json
from pathlib import Path
import secrets
import sysconfig
from .broker import Denied
from .task_sandbox import TaskSandbox
from .versions import Versions,atomic,snapshot,identity,write_tree

class Maintenance:
    def __init__(self,data,state,source):
        self.data=Path(data);self.state=Path(state)/'maintenance';self.state.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.source=Path(source);self.versions=Versions(self.data)
        self.status='No owner-established trusted release channel. Self-authored code requires native review.'
        active=self.state/'active.json'
        self.proposal=json.loads(active.read_text()) if active.exists() else None
    def stage(self):
        files=snapshot(self.source);base,hashes=identity(files);id=secrets.token_hex(16)
        target=self.data/'candidates'/id;write_tree(target,files)
        record={'id':id,'root':str(target),'base_source':str(self.source),'base_digest':base,'base_files':hashes,'verification':None}
        atomic(self.state/(id+'.json'),record);atomic(self.state/'active.json',{'id':id});self.proposal=record
        self.status='Isolated proposal ready at '+str(target)+'. Give Task mode a specific improvement; running code is protected.'
        return record
    def current(self):
        if not self.proposal:raise Denied('Stage a proposal first')
        return json.loads((self.state/(self.proposal['id']+'.json')).read_text())
    async def verify(self):
        record=self.current();root=Path(record['root']);before,hashes=identity(snapshot(root))
        runner=TaskSandbox(self.state/'verification-control')
        # Dependencies are a fixed read-only library, never credentials or executable authority.
        result=await runner.run(['/usr/bin/python3','-B','-m','unittest','discover','-s','tests','-v'],[str(root)],str(root),read_only=True,library=sysconfig.get_paths()['purelib'])
        after,_=identity(snapshot(root))
        if before!=after:raise Denied('Proposal changed during verification')
        record['verification']={'digest':after,'exit_code':result['exit_code'],'output':result['output'][-30000:],'host_only_checks':'Not run inside proposal sandbox; native review must inspect these separately'}
        atomic(self.state/(record['id']+'.json'),record);self.proposal=record
        self.status='Proposal checks '+('passed' if result['exit_code']==0 else 'failed')+'; review exact source and remaining host checks.'
        return record['verification']
    def review(self):
        record=self.current();candidate=snapshot(record['root']);digest,hashes=identity(candidate)
        baseline=snapshot(record['base_source']);baseline_digest,_=identity(baseline)
        if baseline_digest!=record['base_digest']:raise Denied('Proposal baseline changed; stage from an immutable installed version')
        changed=[p for p in sorted(set(baseline)|set(candidate)) if baseline.get(p)!=candidate.get(p)]
        patch=''.join(''.join(difflib.unified_diff(baseline.get(p,b'').decode(errors='replace').splitlines(True),candidate.get(p,b'').decode(errors='replace').splitlines(True),fromfile='before/'+p,tofile='after/'+p)) for p in changed)
        report={'id':record['id'],'digest':digest,'files':changed,'patch':patch[:256000],'patch_truncated':len(patch)>256000,'verification':record['verification'],'source':record['root'],'authority':'Self-authored proposal. No automatic trust, signature or independent approval.'}
        atomic(self.state/(record['id']+'-review.json'),report)
        self.proposal=record;return report
    def install(self,id,digest,*,origin):
        record=self.current()
        if origin!='owner-ui' or id!=record['id']:raise Denied('Only a native decision can approve this proposal')
        review=json.loads((self.state/(id+'-review.json')).read_text())
        receipt=record['verification']
        if review.get('patch_truncated') or review['digest']!=digest or not review['files'] or not receipt or receipt['digest']!=digest or receipt['exit_code']!=0:raise Denied('Review and passing verification must match these exact bytes')
        staged=self.versions.stage(record['root'],{'kind':'self-authored','proposal':id,'approval':'native-owner','baseline':record['base_digest']},expected=digest)
        self.versions.activate(staged,origin=origin)
        self.status='Exact reviewed version selected. Restart after the draft has been saved.';return staged
