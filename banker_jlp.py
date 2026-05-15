import httpx
import json
import os
import time

JLP_STATS_URL = "https://stats.jup.ag/jlp-stats"
JLP_MINT = "27G8MtK7VtTcCHkpASjSDdkWWYfoqT6ggEuKidVJidD4"
DEXSCREENER_URL = f"https://api.dexscreener.com/latest/dex/tokens/{JLP_MINT}"
CACHE_FILE = os.path.join(os.path.dirname(__file__), "jlp_cache.json")
_DEX_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)
_STATS_TIMEOUT = httpx.Timeout(connect=5.0, read=20.0, write=5.0, pool=5.0)


def _fetch_tvl_dexscreener():
    with httpx.Client(timeout=_DEX_TIMEOUT) as client:
        res = client.get(DEXSCREENER_URL)
        res.raise_for_status()
        pairs = res.json().get("pairs", [])
        if pairs:
            best = sorted(pairs, key=lambda x: x.get("liquidity", {}).get("usd", 0), reverse=True)[0]
            return best.get("liquidity", {}).get("usd", 0)
    return 0


def _fetch_apy_stats():
    with httpx.Client(timeout=_STATS_TIMEOUT) as client:
        res = client.get(JLP_STATS_URL)
        res.raise_for_status()
        data = res.json()
        return data.get("apy", 0) / 100


def _cached_apy():
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE) as f:
                return json.load(f).get("apy", 0.345)
    except Exception:
        pass
    return 0.345


def get_jlp_yield():
    print("🏦 Banker: Checking JLP (Casinohouder) yield...")

    # TVL via DexScreener (primair — betrouwbaar)
    tvl = 0
    try:
        tvl = _fetch_tvl_dexscreener()
    except Exception as e:
        print(f"⚠️ Banker: DexScreener TVL niet beschikbaar ({e}).")

    # APY via stats.jup.ag (secundair — soms down)
    apy = None
    try:
        apy = _fetch_apy_stats()
    except Exception:
        apy = _cached_apy()

    result = {"apy": apy, "tvl": tvl, "fees_24h": 0}

    # Cache opslaan zodra we verse APY hebben
    if apy != _cached_apy():
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump(result, f)
        except Exception:
            pass

    print(f"🏦 Banker: APY {apy*100:.1f}% | TVL ${tvl/1e6:.2f}M")
    return result


if __name__ == "__main__":
    y = get_jlp_yield()
    if y:
        print(f"JLP APY: {y['apy']*100:.2f}% | TVL: ${y['tvl']/1e6:.2f}M | Fees 24h: ${y['fees_24h']:.2f}")
