import httpx
import json

GAMMA_API_URL = "https://gamma-api.polymarket.com/markets"

def get_detailed_hunter_report():
    print("🦅 Hunter: Analyzing Polymarket for 'Anti-Insanity' opportunities...")
    params = {"active": "true", "closed": "false", "limit": 20}
    
    try:
        with httpx.Client(timeout=15.0) as client:
            res = client.get(GAMMA_API_URL, params=params)
            res.raise_for_status()
            markets = res.json()
            
            print(f"{'QUESTION':<60} | {'YES':<6} | {'NO':<6} | {'VOLUME':<10}")
            print("-" * 90)
            
            for m in markets:
                outcomes_str = m.get('outcomes', '[]')
                try:
                    outcomes = json.loads(outcomes_str) if isinstance(outcomes_str, str) else outcomes_str
                except:
                    outcomes = []
                    
                prices_raw = m.get('outcomePrices', [])
                try:
                    prices = json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw
                except:
                    prices = prices_raw
                
                if len(outcomes) == 2 and prices:
                    q = m.get('question', 'Unknown')
                    if len(q) > 57: q = q[:57] + "..."
                    
                    yes = prices[0] if len(prices) > 0 else "0"
                    no = prices[1] if len(prices) > 1 else "0"
                    vol = m.get('volume', '0')
                    
                    try:
                        v_float = float(vol) if vol else 0
                    except:
                        v_float = 0
                        
                    if v_float > 100:
                        # Format prices to be readable
                        try:
                            yes_val = f"{float(yes):.2f}"
                            no_val = f"{float(no):.2f}"
                        except:
                            yes_val = str(yes)
                            no_val = str(no)
                            
                        print(f"{q:<60} | {yes_val:<6} | {no_val:<6} | ${v_float/1e6:>7.2f}M")
                        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    get_detailed_hunter_report()
