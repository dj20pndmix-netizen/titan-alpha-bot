import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urljoin, urlparse

BASE_URL = "https://mmgpredictions.com"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def analyze_site():
    print(f"[*] Fetching: {BASE_URL}")
    try:
        resp = requests.get(BASE_URL, headers=headers, timeout=15)
        print(f"[*] Status code: {resp.status_code}")
        print(f"[*] Final URL: {resp.url}")
    except Exception as e:
        print(f"[!] Error fetching site: {e}")
        return

    soup = BeautifulSoup(resp.text, "html.parser")
    title = soup.title.string if soup.title else "No Title"
    print(f"[*] Page Title: {title.strip()}")

    # Collect scripts
    scripts = []
    for s in soup.find_all("script"):
        src = s.get("src")
        if src:
            scripts.append(urljoin(BASE_URL, src))
        elif s.string:
            scripts.append("inline: " + s.string[:120].replace("\n", " "))

    print(f"[*] Found {len(scripts)} scripts:")
    for s in scripts[:15]:
        print(f"    - {s}")

    # Collect links
    links = set()
    for a in soup.find_all("a", href=True):
        href = urljoin(BASE_URL, a['href'])
        if urlparse(href).netloc == urlparse(BASE_URL).netloc:
            links.add(href)

    print(f"\n[*] Found {len(links)} internal links:")
    for l in sorted(list(links))[:20]:
        print(f"    - {l}")

    # Inspect for keywords like 'deriv', 'binary', 'websocket', 'api', 'bot', 'titan'
    text_content = resp.text
    keywords = ["deriv", "binary", "websocket", "wss://", "app_id", "titan", "prediction", "token", "even", "odd", "digit"]
    print("\n[*] Keyword analysis in homepage source:")
    for kw in keywords:
        matches = len(re.findall(re.escape(kw), text_content, re.IGNORECASE))
        print(f"    '{kw}': {matches} occurrences")

    # Let's inspect external JS bundles
    print("\n[*] Searching external JS files for API endpoints & WebSockets...")
    ws_endpoints = set(re.findall(r'wss://[^\s\'"]+', text_content))
    api_endpoints = set(re.findall(r'https?://[^\s\'"]+/api/[^\s\'"]+', text_content))

    for s_url in [s for s in scripts if not s.startswith("inline:")][:5]:
        try:
            print(f"    Checking JS: {s_url}")
            js_resp = requests.get(s_url, headers=headers, timeout=10)
            if js_resp.status_code == 200:
                found_ws = re.findall(r'wss://[^\s\'"]+', js_resp.text)
                for w in found_ws:
                    ws_endpoints.add(w)
                found_apis = re.findall(r'https?://[^\s\'"]+/api/[^\s\'"]+', js_resp.text)
                for a in found_apis:
                    api_endpoints.add(a)
                deriv_app_ids = re.findall(r'app_id[=:\s]+(\d+)', js_resp.text)
                if deriv_app_ids:
                    print(f"      -> Found Deriv app_ids in {s_url}: {set(deriv_app_ids)}")
        except Exception as e:
            print(f"      [!] Failed to read {s_url}: {e}")

    print("\n[*] Identified WebSocket Endpoints:")
    for w in ws_endpoints:
        print(f"    -> {w}")

    print("\n[*] Identified API Endpoints:")
    for a in api_endpoints:
        print(f"    -> {a}")

if __name__ == "__main__":
    analyze_site()
