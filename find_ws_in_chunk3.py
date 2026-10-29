import requests
import re

url = "https://mmgpredictions.com/_next/static/immutable/chunks/3c2saou8cdmnh.js"
headers = {"User-Agent": "Mozilla/5.0"}
resp = requests.get(url, headers=headers)
text = resp.text

pos = [m.start() for m in re.finditer(r'/api/v1/feed/ws', text)]
for p in pos:
    print("--- WS at", p, "---")
    print(text[max(0, p - 200):min(len(text), p + 400)])
