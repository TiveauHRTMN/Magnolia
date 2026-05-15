import os
import httpx
import time
from dotenv import load_dotenv
import base58
from solders.keypair import Keypair

load_dotenv()

HELIUS_RPC_URL = os.getenv("HELIUS_RPC_URL")
PRIV_KEY = os.getenv("SOLANA_PRIVATE_KEY")

def get_wallet_address():
    if not PRIV_KEY or "jouw_" in PRIV_KEY:
        return None
    try:
        if PRIV_KEY.startswith("["):
            import json
            key_data = json.loads(PRIV_KEY)
            keypair = Keypair.from_bytes(bytes(key_data))
        else:
            keypair = Keypair.from_bytes(base58.b58decode(PRIV_KEY))
        return str(keypair.pubkey())
    except:
        return None

def monitor():
    wallet = get_wallet_address()
    if not wallet:
        print("❌ Geen geldige wallet gevonden om te monitoren.")
        return

    print(f"👀 Magnolia start met monitoren van {wallet}...")
    last_signature = None

    while True:
        try:
            # Check voor nieuwe transacties via Helius Enhanced Transaction API
            payload = {
                "jsonrpc": "2.0",
                "id": "magnolia-monitor",
                "method": "getSignaturesForAddress",
                "params": [
                    wallet,
                    {"limit": 1}
                ]
            }
            
            response = httpx.post(HELIUS_RPC_URL, json=payload)
            result = response.json().get('result', [])
            
            if result:
                current_sig = result[0].get('signature')
                
                if last_signature is None:
                    last_signature = current_sig
                    print(f"📍 Huidige laatste transactie: {last_signature}")
                
                if current_sig != last_signature:
                    print(f"🔔 NIEUWE ACTIVITEIT GEDETECTEERD!")
                    print(f"Transactie: https://solscan.io/tx/{current_sig}")
                    last_signature = current_sig
                    # Hier kun je Magnolia acties laten ondernemen, 
                    # bijv. een melding sturen of de balans opnieuw checken.
            
        except Exception as e:
            print(f"⚠️ Monitor fout: {e}")
        
        # Wacht 30 seconden voor de volgende check (vriendelijk voor je API limits)
        time.sleep(30)

if __name__ == "__main__":
    monitor()
