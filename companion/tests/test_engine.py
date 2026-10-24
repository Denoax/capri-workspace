import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
import httpx
from capri.engine import WorkEngine
from capri.task_sandbox import TaskSandbox


def stream_events(output,model):
    item={'id':'message-fixture','type':'message','role':'assistant','status':'completed','content':[{'type':'output_text','text':output,'annotations':[]}]}
    response={'id':'response-fixture','object':'response','created_at':0,'status':'completed','model':model,'output':[item],'usage':{'input_tokens':10,'output_tokens':1,'total_tokens':11,'input_tokens_details':{'cached_tokens':0},'output_tokens_details':{'reasoning_tokens':0}}}
    return item,response

@unittest.skipUnless(os.environ.get('CAPRI_HOST_INTEGRATION')=='1','Pinned native app-server/cgroup fixture requires host run')
class NativeEngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_pinned_stdio_bridge_edits_and_checks_real_scoped_files(self):
        with tempfile.TemporaryDirectory(prefix='capri-engine-fixture-') as folder:
            base=Path(folder);project=base/'project';project.mkdir();runner=TaskSandbox(base/'worker-control')
            events=[];requests=[];calls=[]
            code="from pathlib import Path;import os;assert 'ACCESS_TOKEN' not in os.environ;Path('answer.txt').write_text('42');assert Path('answer.txt').read_text()=='42';print('VERIFIED')"
            argv=['/usr/bin/python3','-c',code]
            def provider_response(request):
                body=json.loads(request.content);requests.append(body)
                groups=[g for i in body['input'] if i.get('type')=='additional_tools' for g in i['tools']]
                self.assertTrue(groups);self.assertTrue(all(g['name']=='capri' for g in groups))
                self.assertEqual(request.headers['Authorization'],'Bearer fixture-token')
                item,response=stream_events('Fixture change verified.','gpt-6.1-sol')
                if len(requests)==1:
                    item={'id':'call-fixture','type':'function_call','namespace':'capri','name':'exec','call_id':'once-fixture','arguments':json.dumps({'argv':argv})};response['output']=[item]
                values=[{'type':'response.created','response':{**response,'status':'in_progress','output':[]}},{'type':'response.output_item.added','output_index':0,'item':item}]
                if item['type']=='message':values.append({'type':'response.output_text.delta','item_id':item['id'],'output_index':0,'content_index':0,'delta':'Fixture change verified.'})
                values +=[{'type':'response.output_item.done','output_index':0,'item':item},{'type':'response.completed','response':response}]
                return httpx.Response(200,headers={'content-type':'text/event-stream'},content=''.join('data: '+json.dumps(v)+'\n\n' for v in values))
            client=httpx.AsyncClient(transport=httpx.MockTransport(provider_response))
            class Provider:
                calls=0
                async def access_token(self, min_validity=90):return 'fixture-token'
                async def client(self):return client
            async def dispatch(call,tool,args):
                self.assertEqual(call,'once-fixture');self.assertEqual(tool,'exec');self.assertEqual(args,{'argv':argv});self.assertFalse(calls)
                calls.append(call)
                return await runner.run(args['argv'],[str(project)],str(project))
            async def event(kind,value):events.append((kind,value))
            tool={'type':'function','name':'exec','description':'Run one scoped fixture command.','inputSchema':{'type':'object','properties':{'argv':{'type':'array','items':{'type':'string'}}},'required':['argv'],'additionalProperties':False}}
            engine=WorkEngine(Provider(),base/'engine','gpt-6.1-sol',[str(project)],lambda:True,dispatch,event,[tool])
            try:
                await engine.start();result=await engine.run('Edit the selected public fixture and verify it.')
                self.assertEqual(result['status'],'completed');self.assertEqual(result['text'],'Fixture change verified.')
                self.assertEqual((project/'answer.txt').read_text(),'42');self.assertEqual(len(calls),1);self.assertEqual(len(requests),2);self.assertEqual(engine.provider.calls,len(requests))
            finally:
                await engine.close();await runner.stop();await client.aclose()

    async def test_restart_resumes_thread_with_a_fresh_account_token(self):
        with tempfile.TemporaryDirectory(prefix='capri-resume-') as folder:
            calls=[];minimums=[];token=['before-refresh']
            def response(request):
                calls.append((request.headers['Authorization'],json.loads(request.content)))
                item,result=stream_events('Continuity fixture verified.','gpt-6.1-sol')
                events=[{'type':'response.created','response':{**result,'status':'in_progress','output':[]}},{'type':'response.output_item.added','output_index':0,'item':item},{'type':'response.output_text.delta','item_id':item['id'],'output_index':0,'content_index':0,'delta':'Continuity fixture verified.'},{'type':'response.output_item.done','output_index':0,'item':item},{'type':'response.completed','response':result}]
                return httpx.Response(200,headers={'content-type':'text/event-stream'},content=''.join('data: '+json.dumps(e)+'\n\n' for e in events))
            client=httpx.AsyncClient(transport=httpx.MockTransport(response));self.addAsyncCleanup(client.aclose)
            class Provider:
                async def access_token(self,min_validity=90):minimums.append(min_validity);return token[0]
                async def client(self):return client
            async def dispatch(*args):raise AssertionError('No tools authorized')
            async def event(*args):pass
            engine=WorkEngine(Provider(),folder,'gpt-6.1-sol',[],lambda:True,dispatch,event,[])
            try:
                thread=await engine.start();self.assertEqual((await engine.run('Public continuity marker: ORCHID42.'))['status'],'completed')
            finally:await engine.close()
            token[0]='after-refresh'
            resumed=WorkEngine(Provider(),folder,'gpt-6.1-sol',[],lambda:True,dispatch,event,[])
            try:
                self.assertEqual(await resumed.start(thread),thread)
                self.assertEqual((await resumed.run('Continue the existing public fixture.'))['status'],'completed')
            finally:await resumed.close()
            self.assertEqual([c[0] for c in calls],['Bearer before-refresh','Bearer after-refresh'])
            self.assertIn('ORCHID42',json.dumps(calls[1][1]['input']))
            self.assertEqual(minimums,[1800,90,1800,90])

class WorkMessageTests(unittest.IsolatedAsyncioTestCase):
    async def test_multiple_streamed_blocks_and_a_final_without_deltas_keep_complete_paragraphs(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory(prefix='capri-message-') as folder:
            async def event(*args):pass
            async def dispatch(*args):raise AssertionError('No tools expected')
            engine=WorkEngine(None,folder,'fixture-model',[],lambda:True,dispatch,event,[])
            engine.thread_id='thread-fixture';engine.turn_done=asyncio.get_running_loop().create_future()
            reader=asyncio.StreamReader();engine.proc=SimpleNamespace(stdout=reader)
            notifications=[('item/agentMessage/delta',{'itemId':'first','delta':'Inspecting '}),('item/agentMessage/delta',{'itemId':'first','delta':'public files.'}),('item/completed',{'item':{'type':'agentMessage','id':'first','text':'Inspecting public files.'}}),('item/completed',{'item':{'type':'agentMessage','id':'final','text':'Both tests passed.'}}),('turn/completed',{'turn':{'status':'completed'}})]
            for method,params in notifications:reader.feed_data((json.dumps({'method':method,'params':{'threadId':engine.thread_id,**params}})+'\n').encode())
            reader.feed_eof();await engine.read_loop()
            self.assertEqual(engine.text,'Inspecting public files.\n\nBoth tests passed.');self.assertEqual(engine.turn_done.result(),'completed')
