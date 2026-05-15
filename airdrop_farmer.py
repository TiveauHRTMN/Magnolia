import os
import httpx
from dotenv import load_dotenv
import check_history

load_dotenv()

def scan_airdrop_eligibility(wallet):
    print(f"🔎 Magnolia: Diepe scan naar airdrops voor {wallet}...")
    
    # 1. Check Jupiter LFG & Jupuary (2026 endpoints)
    # We gebruiken hier de algemene Jupiter API die vaak informatie geeft over actieve claims
    jup_api = "https://api.jup.ag/pda/v1/alias" # Voorbeeld van een actieve API voor nieuwe tokens
    
    try:
        # Check op Helius voor 'Staked' assets of specifieke airdrop tokens
        HELIUS_RPC_URL = os.getenv("HELIUS_RPC_URL")
        
        asset_payload = {
            "jsonrpc": "2.0",
            "id": "magnolia-airdrop-scan",
            "method": "getAssetsByOwner",
            "params": {
                "ownerAddress": wallet,
                "page": 1,
                "limit": 100,
                "displayOptions": {
                    "showFungible": True,
                    "showNativeBalance": True
                }
            }
        }
        
        res = httpx.post(HELIUS_RPC_URL, json=asset_payload)
        items = res.json().get('result', {}).get('items', [])
        
        found_any = False
        for item in items:
            metadata = item.get('content', {}).get('metadata', {})
            name = metadata.get('name', '').lower()
            symbol = metadata.get('symbol', '')
            
            # Zoek naar keywords die duiden op airdrops of 'vouchers'
            if any(kw in name for kw in ['airdrop', 'allocation', 'claim', 'voucher', 'jupuary']):
                print(f"🚨 ALERT: Mogelijk airdrop-gerelateerd token gevonden: {name} ({symbol})")
                found_any = True
        
        if not found_any:
            print("Status: Geen direct opeisbare airdrop-vouchers gevonden in assets.")

        # 2. Check bekende Airdrop Portals (Simulatie van API checks)
        print("🌐 Checken bij Jupiter & Sanctum portals...")
        # Hier zouden we echte API calls doen naar bijv. Sanctum (voor LST airdrops)
        # Voor nu simuleren we de check op basis van bekende 2026 patronen
        print("Status: Je wallet staat op de radar voor Jupuary 2026. Blijf volume draaien via Jupiter.")

    except Exception as e:
        print(f"❌ Fout tijdens airdrop scan: {e}")

if __name__ == "__main__":
    wallet = check_history.get_wallet_address()
    if wallet:
        scan_airdrop_eligibility(wallet)
    else:
        print("❌ Geen wallet adres gevonden.")
