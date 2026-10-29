import re

with open(r"c:\my strategy\bot_engine_chunk.js", "r", encoding="utf-8") as f:
    text = f.read()

# Search for stake_cents or payout or contract payload fields
matches = re.findall(r'\{[^{}]*stake_cents[^{}]*\}', text)
print("stake_cents matches:", matches)

matches_family = re.findall(r'\{[^{}]*family:[^{}]*stake[^{}]*\}', text)
print("family+stake matches:", matches_family)

# Look for the exact definition of open({ ... })
pos = text.find('open:async')
if pos != -1:
    print("\n--- Context of open:async ---")
    print(text[pos:pos+400])

# Look for calls to open(
calls = re.findall(r'open\(\{([^\}]+)\}\)', text)
for c in set(calls):
    print("Call to open:", c)
