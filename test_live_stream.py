import requests
import json
import asyncio
import websockets

BASE_URL = "https://mmgpredictions.com"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def create_demo_session():
    s = requests.Session()
    s.headers.update(headers)
    
    print("[*] Creating Demo Account via POST /api/v1/auth/demo ...")
    r = s.post(f"{BASE_URL}/api/v1/auth/demo", json={})
    print(f"Status: {r.status_code}")
    demo_data = r.json()
    print("User:", demo_data.get("user"))
    print("Wallets:", demo_data.get("wallets"))
    
    # Check session cookie
    print("Cookies:", s.cookies.get_dict())
    
    # Request ws-token
    print("[*] Requesting feed token via GET /api/v1/auth/ws-token ...")
    ws_tok_res = s.get(f"{BASE_URL}/api/v1/auth/ws-token")
    print(f"Status: {ws_tok_res.status_code}")
    print("Token Res:", ws_tok_res.text)
    
    token = ws_tok_res.json().get("token")
    return s, token, demo_data

async def listen_ticks(token):
    ws_url = f"wss://mmgpredictions.com/api/v1/feed/ws?token={token}"
    print(f"[*] Connecting to live tick stream: {ws_url} ...")
    async with websockets.connect(ws_url, ssl=True) as ws:
        print("[+] WebSocket successfully connected! Streaming 10 ticks:")
        for i in range(10):
            msg = await ws.recv()
            print(f"  [Tick {i+1}]: {msg}")

if __name__ == "__main__":
    session, token, demo_data = create_demo_session()
    if token:
        asyncio.run(listen_ticks(token))
