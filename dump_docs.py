import sys
sys.stdout.reconfigure(encoding='utf-8')
import requests
from bs4 import BeautifulSoup

url = "https://mmgpredictions.com/developer/docs"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, "html.parser")

# Find main content
main = soup.find("main") or soup.find("article") or soup.body
with open(r"c:\my strategy\docs_dump.txt", "w", encoding="utf-8") as f:
    f.write(main.get_text(separator="\n", strip=True))

print("Dumped docs. Length:", len(main.get_text()))
with open(r"c:\my strategy\docs_dump.txt", "r", encoding="utf-8") as f:
    for line in f.readlines()[:80]:
        print(line.strip())
