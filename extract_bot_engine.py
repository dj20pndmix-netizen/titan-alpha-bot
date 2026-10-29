import sys
sys.stdout.reconfigure(encoding='utf-8')
import requests
import re
import json

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

chunk_url = "https://mmgpredictions.com/_next/static/immutable/chunks/2zm_9i6m6pm7j.js"
resp = requests.get(chunk_url, headers=headers)
text = resp.text

with open(r"c:\my strategy\bot_engine_chunk.js", "w", encoding="utf-8") as f:
    f.write(text)

print("Downloaded chunk. Size:", len(text))

# Search for symbols/markets
symbols = set(re.findall(r'(?:R_\d+|1HZ\d+V|VOL\d+|V\d+)', text))
print("Symbols / Markets found:", symbols)

# Search for contract families
families = set(re.findall(r'family:[ ]*[\'"]([a-zA-Z0-9_\-]+)[\'"]', text))
print("Contract families found:", families)

# Search for XML block execution functions
blocks = set(re.findall(r'ap_[a-zA-Z0-9_]+', text))
print("All ap_ blocks supported by the engine:", blocks)

# Search for the contract POST fetch call
matches = re.findall(r'fetch\([^\)]*contracts[^\)]*\)', text)
for m in matches[:5]:
    print("Contract fetch call:", m)

# Look for context around /api/v1/contracts
idx = text.find("/api/v1/contracts/")
if idx != -1:
    snippet = text[max(0, idx - 300):min(len(text), idx + 500)]
    print("\n--- Context around /api/v1/contracts/ ---")
    print(snippet)

# Search for WS message format
ws_idx = text.find("/api/v1/feed/ws")
if ws_idx != -1:
    snippet = text[max(0, ws_idx - 200):min(len(text), ws_idx + 400)]
    print("\n--- Context around WS Feed ---")
    print(snippet)
