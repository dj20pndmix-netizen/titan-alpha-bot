import requests
from bs4 import BeautifulSoup
import re

url = "https://mmgpredictions.com/scanner"
headers = {"User-Agent": "Mozilla/5.0"}
r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, "html.parser")
scripts = [s.get("src") for s in soup.find_all("script") if s.get("src")]

print(f"Scripts on /scanner: {len(scripts)}")

keywords = ["scanner", "prediction", "signal", "accuracy", "confidence", "recommend", "even_odd", "streak", "hot", "cold"]

for s in scripts:
    js_url = "https://mmgpredictions.com" + s if s.startswith("/") else s
    res = requests.get(js_url, headers=headers)
    found = [kw for kw in keywords if kw in res.text.lower()]
    if len(found) > 3:
        print(f"\nMatch in {js_url}: {found}")
        # search for prediction calculation or scanner endpoints
        scanner_apis = set(re.findall(r'(/api/v1/[a-zA-Z0-9_\-\/]+)', res.text))
        print("APIs in chunk:", scanner_apis)
        
        # look for formula or prediction logic
        pos = res.text.find("prediction")
        if pos != -1:
            print("Context around 'prediction':")
            print(res.text[max(0, pos - 150):min(len(res.text), pos + 350)])
