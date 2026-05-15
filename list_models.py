"""Lijst beschikbare modellen via OpenRouter."""
import os
import httpx
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    print("OPENROUTER_API_KEY niet gevonden in .env")
    exit(1)

res = httpx.get(
    "https://openrouter.ai/api/v1/models",
    headers={"Authorization": f"Bearer {api_key}"},
    timeout=15,
)
res.raise_for_status()
models = res.json().get("data", [])

print(f"{len(models)} modellen beschikbaar via OpenRouter:\n")
for m in sorted(models, key=lambda x: x.get("id", "")):
    ctx = m.get("context_length", "?")
    print(f"  {m['id']:<55} ctx: {ctx}")
