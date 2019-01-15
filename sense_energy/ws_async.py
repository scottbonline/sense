import asyncio
import json
import websockets
from .sense_exceptions import SenseAPITimeoutException

data = 0
async def get_realtime_stream(url, callback):
    """ Reads realtime data from websocket"""
    global data
    # hello, features, [updates,] data
    async with websockets.connect(url) as ws:
        while True:
            message = await ws.recv()
            result = json.loads(message)
            if result.get('type') == 'realtime_update':
                data = result['payload']
                if callback: callback(data)
                else: return
    
def get_realtime(url, timeout):
    global data
    try:
        data = 0
        asyncio.get_event_loop().run_until_complete(
            asyncio.wait_for(get_realtime_stream(url, None), timeout))
        return data
    except asyncio.TimeoutError:
        raise SenseAPITimeoutException("API websocket timed out")
                
def get_realtime_future(url, timeout, callback):
    return get_realtime_stream(url, callback)
