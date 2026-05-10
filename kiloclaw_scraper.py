import httpx

def claw_market_data(token_address="So11111111111111111111111111111111111111112"):
    """Kiloclaw scheurt door de DexScreener API op zoek naar harde data."""
    print(f"🦅 Kiloclaw: Zoeken naar marktsentiment voor {token_address}...")
    
    url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
    
    try:
        res = httpx.get(url, timeout=10.0)
        data = res.json()
        pairs = data.get('pairs', [])
        
        if not pairs:
            return {"error": "Geen data gevonden door Kiloclaw."}
            
        # Pak de meest liquide pair
        best_pair = sorted(pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0), reverse=True)[0]
        
        market_data = {
            "token": best_pair.get('baseToken', {}).get('symbol'),
            "mint": best_pair.get('baseToken', {}).get('address'),
            "price_usd": best_pair.get('priceUsd'),
            "liquidity_usd": best_pair.get('liquidity', {}).get('usd'),
            "volume_24h": best_pair.get('volume', {}).get('h24'),
            "price_change_24h": best_pair.get('priceChange', {}).get('h24'),
            "dex": best_pair.get('dexId')
        }
        
        return market_data
        
    except Exception as e:
        print(f"❌ Kiloclaw miste zijn doel: {e}")
        return {"error": str(e)}

def scan_trending_pairs():
    """Panopticon Vision: Zoekt naar hoog-volume Solana pairs."""
    print("🦅 Kiloclaw: Activeert Panopticon Vision (Trending Solana Pairs)...")
    url = "https://api.dexscreener.com/latest/dex/search?q=solana%20meme"
    try:
        res = httpx.get(url, timeout=10.0)
        data = res.json()
        pairs = data.get('pairs', [])
        
        # Filter op Solana netwerk en hoge liquiditeit
        sol_pairs = [p for p in pairs if p.get('chainId') == 'solana' and p.get('liquidity', {}).get('usd', 0) > 50000]
        
        # Sorteer op 24h volume
        top_pairs = sorted(sol_pairs, key=lambda x: x.get('volume', {}).get('h24', 0), reverse=True)[:5]
        
        trending = []
        for p in top_pairs:
            trending.append({
                "symbol": p.get('baseToken', {}).get('symbol'),
                "mint": p.get('baseToken', {}).get('address'),
                "price_change_24h": p.get('priceChange', {}).get('h24'),
                "volume_24h": p.get('volume', {}).get('h24')
            })
        return trending
    except Exception as e:
        print(f"❌ Panopticon Fout: {e}")
        return []

if __name__ == "__main__":
    print(claw_market_data())
    print(scan_trending_pairs())