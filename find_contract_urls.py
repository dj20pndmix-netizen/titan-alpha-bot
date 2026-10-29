import requests
import re

with open(r"c:\my strategy\bot_engine_chunk.js", "r", encoding="utf-8") as f:
    text = f.read()

# Search for /api/v1/contracts/ with variables
matches = re.findall(r'(/api/v1/contracts/[^"\'`]*)', text)
print("Contract URLs in JS:", set(matches))
