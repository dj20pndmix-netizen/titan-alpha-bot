import requests
import re

url = "https://mmgpredictions.com/_next/static/immutable/chunks/3c2saou8cdmnh.js"
headers = {"User-Agent": "Mozilla/5.0"}
resp = requests.get(url, headers=headers)
text = resp.text

# Look for /demo or guest or spinning up demo
matches = re.findall(r'(/api/v1/[a-zA-Z0-9_\-\/]+)', text)
print("All endpoints in chunk3:", set(matches))
