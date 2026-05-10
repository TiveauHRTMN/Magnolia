import os
import httpx
import base64
import json
from dotenv import load_dotenv, find_dotenv
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.signature import Signature
import base58

# Forceer reload van de lokale .env
load_dotenv(find_dotenv(), override=True)

HELIUS_RPC_URL = os.getenv("HELIUS_RPC_URL")
PRIV_KEY = os.getenv("SOLANA_PRIVATE_KEY")

# Kamino Main Market & Reserve Addresses
KAMINO_MARKET = "7u3HeHxYDLhnCoErrtycNokbQYbWGzLs6JSDqGAv5PfF"
USDC_RESERVE = "d4A2prbA2whesmvHaL88BH6Ewn5N4bTSU2Ze8P6Bc4Q"
KAMINO_BLINK_URL = f"https://kamino.dial.to/api/v0/lending/reserve/{KAMINO_MARKET}/{USDC_RESERVE}/deposit"

def get_keypair():
    if not PRIV_KEY: return None
    try:
        clean_key = PRIV_KEY.strip().replace(" ", "").replace("\"", "").replace("'", "")
        return Keypair.from_base58_string(clean_key)
    except:
        try:
            decoded = base58.b58decode(clean_key)
            return Keypair.from_bytes(decoded)
        except: return None

def deposit_usdc(amount_tokens):
    """
    Stort USDC in Kamino via de Blink API. 
    amount_tokens is het aantal USDC (bijv. 1.0)
    """
    keypair = get_keypair()
    if not keypair:
        print("❌ Kamino: Geen key gevonden.")
        return False

    print(f"🖇️ Kamino: Voorbereiden van storting van {amount_tokens} USDC...")
    
    try:
        # 1. Haal de transactie op van de Kamino Blink API
        payload = {
            "account": str(keypair.pubkey()),
            "type": "transaction"
        }
        params = {"amount": str(amount_tokens)}
        
        with httpx.Client(timeout=30.0) as client:
            res = client.post(KAMINO_BLINK_URL, json=payload, params=params)
            if res.status_code != 200:
                print(f"❌ Kamino API Fout: {res.status_code} - {res.text}")
                return False
                
            data = res.json()
            tx_b64 = data.get("transaction")
            if not tx_b64:
                print(f"❌ Kamino: Geen transactie ontvangen: {data}")
                return False

            # 2. Decodeer en Signeer
            raw_tx = base64.b64decode(tx_b64)
            tx = VersionedTransaction.from_bytes(raw_tx)
            
            # Sign de message
            signature = keypair.sign_message(bytes(tx.message))
            
            # Reconstruct signed transaction
            # Blink API transactions might already have some signatures or placeholders
            signatures = [Signature.default()] * tx.message.header.num_required_signatures
            signatures[0] = signature
            signed_tx = VersionedTransaction.populate(tx.message, signatures)
            
            # 3. Verzend naar Solana
            print(f"🚀 Kamino: Storting verzenden naar Solana...")
            send_payload = {
                "jsonrpc": "2.0", "id": 1, "method": "sendTransaction",
                "params": [
                    base64.b64encode(bytes(signed_tx)).decode('utf-8'), 
                    {"encoding": "base64", "skipPreflight": True}
                ]
            }
            
            final_res = client.post(HELIUS_RPC_URL, json=send_payload)
            result = final_res.json()
            
            if "result" in result:
                print(f"🔥 Kamino SUCCES! Punten farmen gestart: {result['result']}")
                return result['result']
            else:
                print(f"❌ Kamino Transactie mislukt: {result}")
                return False

    except Exception as e:
        print(f"❌ Kamino Fout: {e}")
        return False

if __name__ == "__main__":
    # Test met een heel klein bedrag als dat kan, of bekijk de logs
    # deposit_usdc(0.01)
    pass
