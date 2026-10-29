import sys
sys.stdout.reconfigure(encoding='utf-8')
import requests
from bs4 import BeautifulSoup
import re
import json

BASE_URL = "https://mmgpredictions.com"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Fetch /bot page and find all script chunks
r = requests.get(BASE_URL + "/bot", headers=headers)
soup = BeautifulSoup(r.text, "html.parser")
scripts = [s.get("src") for s in soup.find_all("script") if s.get("src")]

print(f"Found {len(scripts)} scripts on /bot")

keywords = [
    "ap_strategy",
    "TITAN",
    "TITAN_ALPHA",
    "Blockly",
    "ap_buy_evenodd",
    "/api/v1/contracts",
    "/api/v1/feed/ws",
    "consec_losses",
    "last_digit"
]

matching_chunks = {}

for s in scripts:
    url = BASE_URL + s if s.startswith("/") else s
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        found = []
        for kw in keywords:
            if kw in resp.text:
                found.append(kw)
        if found:
            print(f"Matched {found} in {url}")
            matching_chunks[url] = resp.text
    except Exception as e:
        pass

# Let's search inside the matched chunks for contract request payload structure
for url, content in matching_chunks.items():
    print(f"\n--- Snippets from {url} ---")
    # Search for contract posting
    contract_matches = re.findall(r'(/api/v1/contracts[^\s\'"`]*)', content)
    print("Contract endpoints:", set(contract_matches))
    
    # Search for block definitions
    block_defs = re.findall(r'Blockly\.Blocks\[[\'"][^\'"]+[\'"]\]', content)
    if block_defs:
        print("Blockly definitions found:", block_defs[:15])

    # Search for payload objects sent to /api/v1/contracts
    payload_samples = re.findall(r'\{[^{}]*family:[^{}]*\}', content)
    if payload_samples:
        print("Payload samples:", payload_samples[:5])
