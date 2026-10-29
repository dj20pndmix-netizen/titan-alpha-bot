import sys
sys.stdout.reconfigure(encoding='utf-8')
import requests
import re
import json

BASE_URL = "https://mmgpredictions.com"
headers = {"User-Agent": "Mozilla/5.0"}

# Let's inspect the cashier, login, and developer routes
routes = ["/login", "/cashier", "/developer", "/developer/docs"]

for route in routes:
    r = requests.get(BASE_URL + route, headers=headers)
    print(f"\n================ Route: {route} (Status {r.status_code}) ================")
    # Extract scripts
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "html.parser")
    scripts = [s.get("src") for s in soup.find_all("script") if s.get("src")]
    print(f"Scripts on {route}: {len(scripts)}")
    
    # Search for cashier/real/deposit endpoints
    apis = set(re.findall(r'(/api/v1/[a-zA-Z0-9_\-\/]+)', r.text))
    if apis:
        print("APIs in HTML:", apis)

# Search inside bot_engine_chunk.js for real wallet handling
with open(r"c:\my strategy\bot_engine_chunk.js", "r", encoding="utf-8") as f:
    text = f.read()

print("\n--- Searching bot_engine_chunk.js for 'real' wallet and 'login' ---")
real_matches = [m.start() for m in re.finditer(r'walletKind|loginid|"real"|\'real\'', text)]
print(f"Found {len(real_matches)} references to walletKind / real")

for p in real_matches[:6]:
    print(f"\n[Position {p}]:")
    print(text[max(0, p - 150):min(len(text), p + 250)])
