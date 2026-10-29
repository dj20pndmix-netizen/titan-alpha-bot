import requests

s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0"})
s.post("https://mmgpredictions.com/api/v1/auth/demo", json={})

for fam in ["even_odd", "over_under", "match_diff"]:
    res = s.get(f"https://mmgpredictions.com/api/v1/scanner/?family={fam}")
    print(f"\n--- Family: {fam} (Status {res.status_code}) ---")
    data = res.json()
    print("Best market:", data.get("best", {}).get("symbol"))
    print("Trade label:", data.get("best", {}).get("trade_label"))
    print("Contract type:", data.get("best", {}).get("contract_type"))
    print("AI Score:", data.get("best", {}).get("ai_score"))
    print("Win Rate:", data.get("best", {}).get("win_rate"))
    print("Recent Rate:", data.get("best", {}).get("recent_rate"))
    print("Pattern:", data.get("best", {}).get("pattern"))
