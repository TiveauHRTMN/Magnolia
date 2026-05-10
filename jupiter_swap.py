import os
import httpx
import base64
import base58
import json
import time
from dotenv import load_dotenv, find_dotenv
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction

# Forceer reload van de lokale .env
load_dotenv(find_dotenv(), override=True)

HELIUS_RPC_URL = os.getenv("HELIUS_RPC_URL")
PRIV_KEY = os.getenv("SOLANA_PRIVATE_KEY")

# Vercel AI Gateway Endpoint (System Instruction Audit)
VERCEL_GATEWAY_URL = "https://gateway.ai.vercel.com/v1/tiveauhrtmns-projects/magnolia/ai-gateway"

# Alternatieve Jupiter API (betere DNS bereikbaarheid)
JUP_BASE_URL = "https://public.jupiterapi.com"

def get_keypair():
    if not PRIV_KEY: return None
    try:
        clean_key = PRIV_KEY.strip().replace(" ", "").replace("\"", "").replace("'", "")
        if "jouw_" in clean_key: return None
        return Keypair.from_base58_string(clean_key)
    except:
        try:
            decoded = base58.b58decode(clean_key)
            return Keypair.from_bytes(decoded)
        except: return None

def send_rpc_request(client, method, params):
    """
    MAGNOLIA AUDIT GATEWAY INTEGRATIE
    Routeert RPC requests via Vercel Gateway voor het monitoren van retries en logging.
    Met veilige fallback naar directe Helius RPC om fleet-downtime te voorkomen.
    """
    payload = {
        "jsonrpc": "2.0", 
        "id": "magnolia-audit", 
        "method": method, 
        "params": params
    }
    
    # Beveiliging: Headers gescheiden. Geen private keys meesturen, alleen metadata.
    headers = {
        "Content-Type": "application/json",
        "x-magnolia-module": "farmer-execution",
        "x-rpc-target": HELIUS_RPC_URL # Vertel gateway waar het heen moet als custom provider
    }

    try:
        # 1. Probeer via Vercel Gateway (Audit & Retry Monitoring)
        res = client.post(VERCEL_GATEWAY_URL, json=payload, headers=headers)
        res.raise_for_status()
        return res.json()
    except Exception as gateway_err:
        # 2. Fallback: Als Gateway nog niet JSON-RPC compatibel is ingesteld, bypass.
        # print(f"⚠️ Gateway Audit Bypass: {gateway_err}. Directe RPC route...")
        res = client.post(HELIUS_RPC_URL, json=payload)
        res.raise_for_status()
        return res.json()

def swap(input_mint, output_mint, amount_lamports, slippage_bps=50):
    keypair = get_keypair()
    if not keypair:
        print("❌ Fout: Geen key.")
        return

    try:
        # 1. Get Quote
        print(f"🔄 Magnolia vraagt quote aan via Public Jupiter API...")
        quote_url = f"{JUP_BASE_URL}/quote"
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount_lamports),
            "slippageBps": slippage_bps
        }
        
        with httpx.Client(timeout=30.0) as client:
            res = client.get(quote_url, params=params)
            if res.status_code != 200:
                print(f"❌ Jupiter Quote Error: {res.status_code} - {res.text}")
                return None
            quote_data = res.json()
            
            if "outAmount" not in quote_data:
                print(f"❌ Quote mislukt: {quote_data}")
                return

            print(f"✅ Quote ontvangen: {quote_data['outAmount']} tokens.")

            # 2. Get Swap Transaction
            swap_url = f"{JUP_BASE_URL}/swap"
            payload = {
                "quoteResponse": quote_data,
                "userPublicKey": str(keypair.pubkey()),
                "wrapAndUnwrapSol": True,
                "dynamicComputeUnitLimit": True,
                "prioritizationFeeLamports": 100000 
            }
            
            res = client.post(swap_url, json=payload)
            if res.status_code != 200:
                print(f"❌ Jupiter Swap API Error: {res.status_code} - {res.text}")
                return None
                
            swap_data = res.json()
            
            # 3. Sign & Send
            raw_tx = base64.b64decode(swap_data['swapTransaction'])
            tx = VersionedTransaction.from_bytes(raw_tx)
            
            signed_tx = VersionedTransaction(tx.message, [keypair])
            
            print("🚀 Verzenden naar Solana (Via Vercel AI Gateway)...")
            encoded_tx = base64.b64encode(bytes(signed_tx)).decode('utf-8')
            
            send_params = [
                encoded_tx, 
                {"encoding": "base64", "skipPreflight": False, "maxRetries": 5}
            ]
            
            # MAGNOLIA AUDIT GATEWAY CALL
            result = send_rpc_request(client, "sendTransaction", send_params)
            
            if "result" in result:
                sig = result['result']
                print(f"🔥 Transactie verzonden: {sig}")
                
                # PEV Protocol: Verificatie loop via Gateway
                print("⏳ Wachten op on-chain bevestiging (Monitoring via Gateway)...")
                for i in range(15):
                    time.sleep(3)
                    status_data = send_rpc_request(client, "getSignatureStatuses", [[sig]])
                    status = status_data.get("result", {}).get("value", [None])[0]
                    
                    if status and status.get("confirmationStatus") in ["confirmed", "finalized"]:
                        print(f"✅ BEVESTIGD op slot {status.get('slot')}")
                        return sig
                    print(".", end="", flush=True)
                
                print("\n⚠️ Geen bevestiging binnen 45s. Check Solscan.")
                return sig
            else:
                print(f"❌ Transactie mislukt op RPC/Gateway: {result}")

    except Exception as e:
        print(f"❌ Syndicaat Executiefout: {e}")
    return None
