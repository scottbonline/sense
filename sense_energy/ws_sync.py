import json
from websocket import create_connection
from websocket._exceptions import WebSocketTimeoutException

from .sense_exceptions import SenseAPITimeoutException

def get_realtime_stream(url, timeout):
    """ Reads realtime data from websocket
        Continues until loop broken"""
    ws = 0
    try:
        ws = create_connection(url, timeout=timeout)
        while True: # hello, features, [updates,] data
            result = json.loads(ws.recv())
            if result.get('type') == 'realtime_update':
                yield result['payload']
    except WebSocketTimeoutException:
        raise SenseAPITimeoutException("API websocket timed out")
    finally:
        if ws: ws.close()

def get_realtime(url, timeout):
    return next(get_realtime_stream(url, timeout))

def get_realtime_future(url, timeout, callback):
    raise NotImplementedError("Not available in Python < 3.6")
