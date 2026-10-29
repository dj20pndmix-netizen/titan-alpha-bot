import asyncio
import json
import websockets

WS_URL = "wss://mmgpredictions.com/api/v1/feed/public"

async def test_public_feed():
    print(f"Connecting to {WS_URL}...")
    try:
        async with websockets.connect(WS_URL, ssl=True) as ws:
            print("Connected! Listening for messages (timeout 10s)...")
            for _ in range(5):
                msg = await asyncio.wait_for(ws.recv(), timeout=10)
                print(f"[RECV]: {msg[:200]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_public_feed())
