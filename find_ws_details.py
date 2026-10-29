import re

with open(r"c:\my strategy\bot_engine_chunk.js", "r", encoding="utf-8") as f:
    text = f.read()

pos = [m.start() for m in re.finditer(r'/api/v1/feed/ws', text)]
for p in pos:
    print("--- WS at", p, "---")
    print(text[max(0, p - 200):min(len(text), p + 300)])

pos_token = [m.start() for m in re.finditer(r'ws-token', text)]
for p in pos_token:
    print("--- ws-token at", p, "---")
    print(text[max(0, p - 100):min(len(text), p + 300)])
