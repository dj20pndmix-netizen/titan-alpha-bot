import re

with open(r"c:\my strategy\bot_engine_chunk.js", "r", encoding="utf-8") as f:
    text = f.read()

pos = [m.start() for m in re.finditer(r'ap_buy_evenodd', text)]
for p in pos:
    print("--- ap_buy_evenodd at", p, "---")
    print(text[max(0, p - 200):min(len(text), p + 400)])
