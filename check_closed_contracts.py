import requests

s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0"})
s.post("https://mmgpredictions.com/api/v1/auth/demo", json={})

res = s.get("https://mmgpredictions.com/api/v1/contracts/?status=closed&limit=10")
print("Status:", res.status_code)
print("Data:", res.text[:500])
