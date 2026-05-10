import os
import httpx
from dotenv import load_dotenv, find_dotenv
import base58
from solders.keypair import Keypair

# Forceer reload van .env
load_dotenv(find_dotenv(), override=True)

HELIUS_RPC_URL = os.getenv("HELIUS_RPC_URL")
PRIV_KEY = os.getenv("SOLANA_PRIVATE_KEY")

def get_wallet_address():
    if not PRIV_KEY:
        return None
    try:
        # Schoon de key op
        clean_key = PRIV_KEY.strip().replace(" ", "").replace("\"", "").replace("'", "")
        
        # Als de key per ongeluk nog steeds de placeholder bevat, skip dan
        if "jouw_" in clean_key or len(clean_key) < 40:
            return None

        if clean_key.startswith("["):
            import json
            key_data = json.loads(clean_key)
            keypair = Keypair.from_bytes(bytes(key_data))
        else:
            keypair = Keypair.from_bytes(base58.b58decode(clean_key))
        return str(keypair.pubkey())
    except Exception as e:
        print(f"DEBUG: Fout bij laden key: {e}")
        return None

def check_balance(wallet_address):
    data = {"sol_balance": 0, "tokens": []}
    
    payload = {
        "jsonrpc": "2.0",
        "id": "magnolia-check",
        "method": "getBalance",
        "params": [wallet_address]
    }
    
    try:
        # 1. SOL Balans
        response = httpx.post(HELIUS_RPC_URL, json=payload)
        res_json = response.json()
        sol_balance = res_json['result']['value'] / 1_000_000_000
        data["sol_balance"] = sol_balance
        print(f"💰 SOL Balans: {sol_balance:.4f} SOL")

        # 2. Assets (Tokens/NFTs)
        asset_payload = {
            "jsonrpc": "2.0",
            "id": "magnolia-assets",
            "method": "getAssetsByOwner",
            "params": {
                "ownerAddress": wallet_address,
                "page": 1,
                "limit": 100,
                "displayOptions": {"showFungible": True}
            }
        }
        
        asset_response = httpx.post(HELIUS_RPC_URL, json=asset_payload)
        assets = asset_response.json().get('result', {}).get('items', [])
        
        for asset in assets:
            token_info = asset.get('token_info', {})
            balance = token_info.get('balance', 0)
            if balance > 0:
                symbol = asset.get('content', {}).get('metadata', {}).get('symbol', 'UNK')
                decimals = token_info.get('decimals', 0)
                real_balance = float(balance) / (10 ** decimals) if decimals else balance
                data["tokens"].append({"symbol": symbol, "balance": real_balance, "mint": asset.get('id')})
                print(f"- {symbol}: {real_balance}")
        
        return data

    except Exception as e:
        print(f"❌ Fout bij ophalen data: {e}")
        return data

if __name__ == "__main__":
    wallet = get_wallet_address()
    if wallet:
        print(f"DEBUG: Wallet Address: {wallet}")
        check_balance(wallet)
    else:
        print("❌ Kon wallet adres niet bepalen. Controleer je SOLANA_PRIVATE_KEY.")
