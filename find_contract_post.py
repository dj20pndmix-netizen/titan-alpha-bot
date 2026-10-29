import re

with open(r"c:\my strategy\bot_engine_chunk.js", "r", encoding="utf-8") as f:
    text = f.read()

# Look for POST /api/v1/contracts
pos = [m.start() for m in re.finditer(r'/api/v1/contracts/?', text)]
for p in pos:
    print("--- Found at", p, "---")
    print(text[max(0, p - 300):min(len(text), p + 400)])
