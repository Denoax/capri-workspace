import asyncio
import json
from pathlib import Path
import tempfile
import time
import unittest

from authlib.jose import JsonWebKey, JsonWebToken
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import httpx

from capri.broker import Denied
from capri.provider import PlanProvider, AUTH


class IdentityTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        cls.jwk=JsonWebKey.import_key(cls.key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())).as_dict(is_private=True)
        cls.public=JsonWebKey.import_key(cls.key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)).as_dict()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.provider=PlanProvider(Path(self.tmp.name)/'accounts')
        async def request(method,url,**kwargs):
            if 'openid-configuration' in url:return {'jwks_uri':AUTH+'/jwks'}
            return {'keys':[self.public]}
        self.provider.request=request

    def token(self,**changes):
        now=int(time.time())
        claims={'iss':AUTH,'sub':'fixture-owner','aud':'oaiapp_fixture','iat':now,'exp':now+120,'nonce':'fixture-nonce',**changes}
        return JsonWebToken(['RS256']).encode({'alg':'RS256'},claims,self.jwk).decode()

    async def test_signed_identity_requires_current_issuer_audience_expiry_nonce(self):
        valid=await self.provider.validate_identity(self.token(),'oaiapp_fixture','fixture-nonce')
        self.assertEqual(valid['sub'],'fixture-owner')
        for changes in ({'iss':'https://evil.invalid'},{'aud':'other-client'},{'nonce':'wrong'},{'exp':int(time.time())-120}):
            with self.subTest(changes=changes),self.assertRaises(Exception):
                await self.provider.validate_identity(self.token(**changes),'oaiapp_fixture','fixture-nonce')

    async def test_signature_from_untrusted_key_is_rejected(self):
        other=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        token=JsonWebToken(['RS256']).encode({'alg':'RS256'},{'iss':AUTH,'sub':'fake','aud':'oaiapp_fixture','exp':int(time.time())+120,'iat':int(time.time()),'nonce':'fixture-nonce'},JsonWebKey.import_key(other.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))).decode()
        with self.assertRaises(Exception):await self.provider.validate_identity(token,'oaiapp_fixture','fixture-nonce')
        self.assertIsNone(self.provider.record)

    async def test_rotating_refresh_is_serialized_and_saved_atomically(self):
        self.provider.record={'subject':'fixture','client_id':'oaiapp_fixture','access_token':'expired-fixture',
                              'refresh_token':'refresh-fixture','expires_at':0,'scopes':['chatgpt.tokens.use.direct']}
        calls=[]
        async def request(method,url,**kwargs):
            calls.append(url);await asyncio.sleep(0)
            return {'access_token':'new-fixture','refresh_token':'rotated-fixture','expires_in':3600}
        self.provider.request=request
        a,b=await asyncio.gather(self.provider.access_token(),self.provider.access_token())
        self.assertEqual((a,b),('new-fixture','new-fixture'));self.assertEqual(len(calls),1)
        record=json.loads((self.provider.directory/(self.provider.partition+'.json')).read_text())
        self.assertEqual(record['refresh_token'],'rotated-fixture')
        self.assertEqual((self.provider.directory/(self.provider.partition+'.json')).stat().st_mode&0o777,0o600)

    async def test_redirects_cannot_send_bearer_to_another_host(self):
        requests=[]
        def handler(request):
            requests.append(request)
            return httpx.Response(302,headers={'Location':'https://evil.invalid'})
        self.provider.http=httpx.AsyncClient(transport=httpx.MockTransport(handler),follow_redirects=False)
        self.addAsyncCleanup(self.provider.http.aclose)
        with self.assertRaises(Denied):await PlanProvider.request(self.provider,'GET','https://api.openai.com/v1/models',headers={'Authorization':'Bearer fixture-only'})
        self.assertEqual(len(requests),1)
        self.assertEqual(str(requests[0].url.host),'api.openai.com')


class StreamTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.provider=PlanProvider(Path(self.tmp.name)/'accounts');self.provider.catalog=[{'id':'fixture-model','name':'Fixture'}];self.provider.model='fixture-model'
        async def token():return 'fixture-only'
        self.provider.access_token=token
        self.deltas=[]
    async def delta(self,text):self.deltas.append(text)
    async def serve(self,events):
        content=''.join('data: '+json.dumps(e)+'\n\n' for e in events)
        def handler(request):
            body=json.loads(request.content)
            self.assertEqual(body['store'],False);self.assertEqual(body['stream'],True)
            self.assertIsInstance(body['input'],list)
            self.assertNotIn('previous_response_id',body)
            self.assertNotIn('tools',body)
            return httpx.Response(200,content=content)
        self.provider.http=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        self.addAsyncCleanup(self.provider.http.aclose)
    async def test_terminal_completion_is_required(self):
        await self.serve([{'type':'response.output_text.delta','delta':'fixture text'},{'type':'response.completed'}])
        self.assertEqual(await self.provider.respond('persona',[{'role':'user','content':'test'}],self.delta),'fixture text')
    async def test_partial_limit_failure_is_not_success_or_a_paid_retry(self):
        await self.serve([{'type':'response.output_text.delta','delta':'partial'},{'type':'response.failed','response':{'error':{'code':'subscription_sharing_usage_limit_exceeded'}}}])
        with self.assertRaises(Denied):await self.provider.respond('persona',[],self.delta)
        self.assertEqual(self.provider.calls,1)
    async def test_interrupted_stream_is_not_completed(self):
        await self.serve([{'type':'response.output_text.delta','delta':'partial'}])
        with self.assertRaises(Denied):await self.provider.respond('persona',[],self.delta)
    async def test_unrequested_tool_call_has_no_execution_path(self):
        await self.serve([{'type':'response.function_call_arguments.done','arguments':'{"approved":true}'}])
        with self.assertRaises(Denied):await self.provider.respond('persona',[],self.delta)
