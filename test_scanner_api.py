import requests

s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0"})

# Demo login to get session
s.post("https://mmgpredictions.com/api/v1/auth/demo", json={})

res = s.get("https://mmgpredictions.com/api/v1/scanner/")
print("Status:", res.status_code)
print("Data:", res.text[:1000])
