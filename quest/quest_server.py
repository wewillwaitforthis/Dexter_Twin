#in  terminal 
# adb reverse tcp:8001 tcp:8001
# adb reverse tcp:8765 tcp:8765

#useful:
#adb reverse --list 
#adb reverse --remove tcp:XXXX

import asyncio, json, threading, http.server, functools
from websockets.asyncio.server import serve   # pip install websockets

latest = {}   # {"right": {"pos":[x,y,z], "grip":bool, "stick_x":float, "a":int, "b":int}, "left": {"pos":[x,y,z], "grip":bool, "stick_x":float, "a":int, "b":int}}

async def _handler(ws):
    async for msg in ws:
        latest.clear()
        latest.update(json.loads(msg))

async def _ws_main():
    async with serve(_handler, "0.0.0.0", 8765):
        await asyncio.Future()

def _http_main():
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=".")
    http.server.ThreadingHTTPServer(("0.0.0.0", 8001), h).serve_forever()

def start():
    threading.Thread(target=lambda: asyncio.run(_ws_main()), daemon=True).start()
    threading.Thread(target=_http_main, daemon=True).start()

if __name__ == "__main__":
    import time
    start()
    print("serving page on :8000, websocket on :8765")
    while True:
        time.sleep(0.5)
        print(latest.get("right"))