"""Small CDP client for owned presentation browsers; no personal profile access."""
import asyncio,json
class CDP:
    def __init__(self, websocket):
        self.websocket=websocket;self.sequence=0;self.pending={};self.exceptions=[]
    async def pump(self):
        async for raw in self.websocket:
            event=json.loads(raw)
            if 'id' in event:
                future=self.pending.pop(event['id'],None)
                if future and not future.done():
                    if 'error' in event:future.set_exception(RuntimeError(str(event['error'])))
                    else:future.set_result(event.get('result',{}))
            elif event.get('method')=='Runtime.exceptionThrown':self.exceptions.append(event['params']['exceptionDetails'])
    async def call(self,method,params=None):
        self.sequence+=1;sequence=self.sequence;future=asyncio.get_running_loop().create_future();self.pending[sequence]=future
        await self.websocket.send(json.dumps({'id':sequence,'method':method,'params':params or {}}))
        return await asyncio.wait_for(future,45)
    async def evaluate(self,expression):
        result=await self.call('Runtime.evaluate',{'expression':expression,'awaitPromise':True,'returnByValue':True})
        if 'exceptionDetails' in result:raise RuntimeError(str(result['exceptionDetails']))
        return result.get('result',{}).get('value')
