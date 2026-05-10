import httpx

KOBE_API_URL = "https://kobe.mainnet.jito.network/api/v1/stake_pool_stats"

def get_jito_yield():
    """
    Retrieves the current JitoSOL staking yield (APY).
    This is Protocol 1: The Guardian.
    """
    print("🛡️ Guardian: Checking JitoSOL staking rewards...")
    
    params = {"bucket_type": "Daily"}
    
    try:
        with httpx.Client(timeout=15.0) as client:
            res = client.get(KOBE_API_URL, params=params)
            res.raise_for_status()
            data = res.json()
            
            stats = data.get("stake_pool_stats", [])
            if stats:
                # The latest entry is usually the most recent data point
                latest = stats[-1]
                return {
                    "apy": latest.get("apy", 0),
                    "tvl": latest.get("tvl", 0),
                    "date": latest.get("date")
                }
            return None
            
    except Exception as e:
        print(f"❌ Guardian: Jito yield check failed: {e}")
        return None

if __name__ == "__main__":
    y = get_jito_yield()
    if y:
        print(f"JitoSOL APY: {y['apy']*100:.2f}% | TVL: {y['tvl']/1e9:.2f}B SOL")
