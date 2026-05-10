import httpx
import json
import os

JLP_STATS_URL = "https://stats.jup.ag/jlp-stats"
CACHE_FILE = os.path.join(os.path.dirname(__file__), "jlp_cache.json")

def get_jlp_yield():
    """
    Retrieves the current JLP (Jupiter Liquidity Provider) yield and stats.
    Uses a local cache if the API times out.
    """
    print("🏦 Banker: Checking JLP (Casinohouder) yield...")
    
    try:
        with httpx.Client(timeout=10.0) as client: # Kortere timeout voor snelheid
            res = client.get(JLP_STATS_URL)
            res.raise_for_status()
            data = res.json()
            
            result = {
                "apy": data.get("apy", 0) / 100,
                "tvl": data.get("aum", 0),
                "fees_24h": 0 
            }
            
            # Sla op in cache
            with open(CACHE_FILE, "w") as f:
                json.dump(result, f)
                
            return result
            
    except Exception as e:
        print(f"❌ Banker: JLP API traag of onbereikbaar ({e}). Fallback naar cache...")
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, "r") as f:
                    return json.load(f)
        except Exception as cache_e:
            print(f"❌ Banker: Ook cache faalde: {cache_e}")
            
        return {"apy": 0.345, "tvl": 0, "fees_24h": 0} # Nood-fallback

if __name__ == "__main__":
    y = get_jlp_yield()
    if y:
        print(f"JLP APY: {y['apy']*100:.2f}% | TVL: ${y['tvl']/1e6:.2f}M | Fees 24h: ${y['fees_24h']:.2f}")
