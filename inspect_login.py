import requests
from bs4 import BeautifulSoup
import re

url = "https://mmgpredictions.com/login"
headers = {"User-Agent": "Mozilla/5.0"}
r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, "html.parser")
scripts = [s.get("src") for s in soup.find_all("script") if s.get("src")]

for s in scripts:
    js_url = "https://mmgpredictions.com" + s if s.startswith("/") else s
    res = requests.get(js_url, headers=headers)
    if "/api/v1/auth/login" in res.text:
        print(f"Found login logic in {js_url}!")
        pos = res.text.find("/api/v1/auth/login")
        print(res.text[max(0, pos - 200):min(len(res.text), pos + 400)])
