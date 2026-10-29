import requests
import json
import asyncio
import websockets

BASE_URL = "https://mmgpredictions.com"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_demo_token():
    s = requests.Session()
    s.headers.update(headers)
    r = s.post(f"{BASE_URL}/api/v1/auth/demo", json={})
    tok_res = s.get(f"{BASE_URL}/api/v1/auth/ws-token")
    token = tok_res.json().get("token")
    return token

async def stream_live_ticks():
    token = get_demo_token()
    ws_url = f"wss://api.mmgtrades.site/api/v1/feed/ws?token={token}&symbols=volatility_10"
    print(f"Connecting to: {ws_url} ...")
    
    async with websockets.connect(ws_url, ssl=True) as ws:
        print("[+] CONNECTED! Capturing live Volatility 10 ticks:")
        for i in range(10):
            raw = await ws.recv()
            data = json.loads(raw)
            print(f"  Tick {i+1}: {data}")

if __name__ == "__main__":
    asyncio.run(stream_live_ticks())
