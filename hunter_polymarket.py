import httpx
import json

GAMMA_API_URL = "https://gamma-api.polymarket.com/markets"

# Drempel voor hype-detectie; Oracle kan dit bijsturen via hunter_directive
DEFAULT_HYPE_THRESHOLD = 0.58


def scan_polymarket_opportunities(limit=10, oracle_bias=None, hunter_directive=None):
    """
    Scans Polymarket op hype-gedreven markten. Protocol 3: The Hunter.

    oracle_bias: "NO" | "YES" | "AVOID" — Oracle-richting voor vandaag.
    hunter_directive: vrije tekst die als context wordt meegestuurd naar de vloot.
    """
    if oracle_bias == "AVOID":
        print("🦅 Hunter: Oracle zegt AVOID — Polymarket scan overgeslagen.", flush=True)
        return []

    print(f"🦅 Hunter: Scannen op hype-markten (Oracle bias: {oracle_bias or 'geen'})...", flush=True)
    if hunter_directive:
        print(f"🦅 Hunter directive: {hunter_directive[:120]}", flush=True)

    # Bij NO-bias iets hogere drempel: Oracle verwacht irrationeel optimisme
    hype_threshold = DEFAULT_HYPE_THRESHOLD
    if oracle_bias == "NO":
        hype_threshold = 0.62

    params = {"active": "true", "closed": "false", "limit": limit}

    try:
        with httpx.Client(timeout=15.0) as client:
            res = client.get(GAMMA_API_URL, params=params)
            res.raise_for_status()
            markets = res.json()

            opportunities = []
            for market in markets:
                outcomes = json.loads(market.get("outcomes", "[]"))

                if len(outcomes) != 2:
                    continue

                raw_prices = market.get("outcomePrices", "[0,0]")
                prices = json.loads(raw_prices) if isinstance(raw_prices, str) else raw_prices
                yes_price = float(prices[0]) if len(prices) > 0 else 0
                no_price = float(prices[1]) if len(prices) > 1 else 0

                # Bij AVOID-bias voor specifieke sectoren: simpel doorgeven, Hermes filtert
                opp = {
                    "question": market.get("question"),
                    "slug": market.get("slug"),
                    "yes_price": yes_price,
                    "no_price": no_price,
                    "volume_24h": market.get("volume24h"),
                    "liquidity": market.get("liquidity"),
                    "end_date": market.get("endDate"),
                    "hype_flag": yes_price >= hype_threshold,
                    "oracle_bias": oracle_bias,
                }
                opportunities.append(opp)

            # Sorteer: hype-targets eerst (Oracle-gefilterd)
            opportunities.sort(key=lambda x: (x["hype_flag"], x["yes_price"]), reverse=True)
            return opportunities

    except Exception as e:
        print(f"❌ Hunter: Polymarket scan gefaald: {e}", flush=True)
        return []


if __name__ == "__main__":
    opps = scan_polymarket_opportunities()
    for o in opps[:10]:
        flag = "HYPE" if o["hype_flag"] else "     "
        print(f"[{flag}] {o['question'][:60]} | Yes: {o['yes_price']:.2f} | No: {o['no_price']:.2f}")
