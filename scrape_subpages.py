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

routes = [
    "/developer/docs",
    "/bot",
    "/scanner",
    "/trade",
    "/trade?family=even_odd",
    "/demo"
]

def scrape_subpages():
    for route in routes:
        url = BASE_URL + route
        print(f"\n==========================================")
        print(f"[*] Crawling: {url}")
        print(f"==========================================")
        try:
            r = requests.get(url, headers=headers, timeout=15)
            print(f"Status: {r.status_code}")
            soup = BeautifulSoup(r.text, "html.parser")
            
            # Print page text summary
            text = ' '.join(soup.stripped_strings)
            print(f"Text Preview (first 500 chars):\n{text[:500]}...\n")
            
            # Search for APIs, websockets, or strategy blocks
            apis = set(re.findall(r'(/api/[a-zA-Z0-9_\-\/]+)', r.text))
            if apis:
                print(f"API endpoints found: {apis}")
                
            wss = set(re.findall(r'wss?://[^\s\'"]+', r.text))
            if wss:
                print(f"WebSockets found: {wss}")
                
            # Search for bot/strategy keywords in this page
            for kw in ["Titan", "XML", "strategy", "ap_strategy", "Blockly", "multiplier", "Martingale", "Vol 10", "Volatility"]:
                matches = len(re.findall(re.escape(kw), r.text, re.IGNORECASE))
                if matches > 0:
                    print(f"  Keyword '{kw}': {matches} hits")

        except Exception as e:
            print(f"[!] Failed to fetch {url}: {e}")

if __name__ == "__main__":
    scrape_subpages()
