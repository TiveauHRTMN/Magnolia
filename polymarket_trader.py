"""
Protocol 3: The Hunter — Polymarket Execution Layer
Vitalik methode: koop 'No' waar 'Yes' irrationeel hoog staat door media hype.
"""
import os
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

import config
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.constants import POLYGON

POLYMARKET_HOST = "https://clob.polymarket.com"
CHAIN_ID = POLYGON  # 137
PRIVATE_KEY = os.getenv("POLYGON_PRIVATE_KEY")

# Vitalik drempel: Yes > 0.58 = potentiele hype trade
HYPE_THRESHOLD = 0.58
MIN_LIQUIDITY = 500.0   # minimale liquiditeit in USDC
MAX_TRADE_USDC = 5.0    # max per trade in USDC


def get_client():
    if not config.POLYMARKET_TRADING_ENABLED:
        raise PermissionError("Polymarket trading is disabled. Use read-only signals unless access and trading are legal for you.")

    if not PRIVATE_KEY:
        raise ValueError("POLYGON_PRIVATE_KEY niet gevonden in .env")

    from py_clob_client.clob_types import ApiCreds

    api_key = os.getenv("POLYMARKET_API_KEY")
    api_secret = os.getenv("POLYMARKET_API_SECRET")
    api_passphrase = os.getenv("POLYMARKET_API_PASSPHRASE")

    # signature_type=0 = EOA (standaard Phantom wallet)
    if api_key and api_secret and api_passphrase:
        creds = ApiCreds(api_key=api_key, api_secret=api_secret, api_passphrase=api_passphrase)
        return ClobClient(POLYMARKET_HOST, key=PRIVATE_KEY, chain_id=CHAIN_ID, creds=creds, signature_type=0)

    # Maak nieuwe credentials aan en sla op in .env
    client = ClobClient(POLYMARKET_HOST, key=PRIVATE_KEY, chain_id=CHAIN_ID, signature_type=0)
    creds = client.create_or_derive_api_creds()

    env_path = os.path.join(os.path.dirname(__file__), '.env')
    with open(env_path, 'a') as f:
        f.write(f"\nPOLYMARKET_API_KEY={creds.api_key}")
        f.write(f"\nPOLYMARKET_API_SECRET={creds.api_secret}")
        f.write(f"\nPOLYMARKET_API_PASSPHRASE={creds.api_passphrase}")

    return ClobClient(POLYMARKET_HOST, key=PRIVATE_KEY, chain_id=CHAIN_ID, creds=creds, signature_type=0)


def scan_and_find_targets(limit=50):
    """Scant Polymarket en returned Hunter targets (Yes > HYPE_THRESHOLD)."""
    import httpx

    res = httpx.get(
        "https://gamma-api.polymarket.com/markets",
        params={"active": "true", "closed": "false", "limit": limit},
        timeout=15
    )
    markets = res.json()

    targets = []
    for m in markets:
        raw = m.get("outcomePrices", "[0,0]")
        prices = json.loads(raw) if isinstance(raw, str) else raw
        if len(prices) != 2:
            continue

        yes = float(prices[0])
        no = float(prices[1])

        liq = float(m.get("liquidity") or 0)
        if yes > HYPE_THRESHOLD and liq >= MIN_LIQUIDITY:
            targets.append({
                "question": m.get("question"),
                "condition_id": m.get("conditionId"),
                "slug": m.get("slug"),
                "yes_price": yes,
                "no_price": no,
                "liquidity": float(m.get("liquidity") or 0),
                "volume": float(m.get("volume") or 0),
            })

    # Sorteer op liquiditeit (veiligste exit)
    targets.sort(key=lambda x: x["liquidity"], reverse=True)
    return targets


def get_token_ids(client, condition_id):
    """Haal de token IDs op voor Yes en No van een markt."""
    try:
        market = client.get_market(condition_id)
        tokens = market.get("tokens", [])
        yes_token = next((t["token_id"] for t in tokens if t["outcome"] == "Yes"), None)
        no_token = next((t["token_id"] for t in tokens if t["outcome"] == "No"), None)
        return yes_token, no_token
    except Exception as e:
        print(f"Fout bij ophalen token IDs: {e}")
        return None, None


def place_no_trade(condition_id, no_price, size_usdc=2.0):
    """
    Koop 'No' shares via Node.js wrapper (CLOB v2 compatible).
    """
    if not config.POLYMARKET_TRADING_ENABLED:
        print("Hunter: Polymarket execution disabled. Geen order geplaatst.")
        return None

    import subprocess
    import json as _json

    if size_usdc > MAX_TRADE_USDC:
        size_usdc = MAX_TRADE_USDC
        print(f"Trade gecapped op ${MAX_TRADE_USDC}")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(script_dir, "place_order.js")

    print(f"Hunter: Koop No shares @ ${no_price:.3f} (inzet: ${size_usdc:.2f} USDC)")

    try:
        result = subprocess.run(
            ["node", script_path, condition_id, str(no_price), str(size_usdc)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = result.stdout.strip()
        if not output:
            print(f"Node error: {result.stderr.strip()}")
            return None

        resp = _json.loads(output)
        if resp.get("success"):
            order_id = resp.get("orderID")
            shares = resp.get("shares")
            print(f"Order geplaatst: {order_id} ({shares} shares)")
            return order_id
        else:
            print(f"Order mislukt: {resp.get('error')}")
            return None

    except subprocess.TimeoutExpired:
        print("Timeout bij order plaatsen.")
        return None
    except Exception as e:
        print(f"Executiefout: {e}")
        return None


def run_hunter(size_usdc=2.0, dry_run=False):
    """Hoofdflow: scan -> kies beste target -> place No trade."""
    print(f"Hunter: Scannen op hype-gedreven markten (drempel: {HYPE_THRESHOLD})...")
    targets = scan_and_find_targets()

    if not targets:
        print(f"Geen Hunter targets gevonden (geen Yes > {HYPE_THRESHOLD} met >${MIN_LIQUIDITY} liquiditeit).")
        return

    print(f"\n{len(targets)} target(s) gevonden:")
    for t in targets[:5]:
        print(f"  {t['yes_price']:.2f} Yes | ${t['liquidity']:,.0f} liq | {t['question'][:60]}")

    best = targets[0]
    print(f"\nBeste target: {best['question']}")
    print(f"  Yes: {best['yes_price']:.3f} | No: {best['no_price']:.3f}")
    print(f"  Liquiditeit: ${best['liquidity']:,.0f} | Volume: ${best['volume']:,.0f}")

    if dry_run:
        print(f"[DRY RUN] Zou {size_usdc} USDC inzetten op No. Geen order geplaatst.")
        return

    if not config.POLYMARKET_TRADING_ENABLED:
        print("[BLOCKED] Polymarket trading staat uit. Gebruik alleen read-only analyse.")
        return

    return place_no_trade(best["condition_id"], best["no_price"], size_usdc)


if __name__ == "__main__":
    size = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
    dry = "--dry" in sys.argv
    run_hunter(size_usdc=size, dry_run=dry)
