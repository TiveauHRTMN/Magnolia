import jupiter_swap
import time
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

def retry_swap_and_confirm():
    # 0.005 SOL
    amount = 5000000 
    sig = jupiter_swap.swap(
        'So11111111111111111111111111111111111111112', 
        'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v', 
        amount
    )
    
    if sig:
        print(f"⏳ Hermes: Wachten op bevestiging van {sig}...")
        rpc = os.getenv("HELIUS_RPC_URL")
        for i in range(20):
            time.sleep(3)
            try:
                payload = {
                    "jsonrpc": "2.0", 
                    "id": 1, 
                    "method": "getSignatureStatuses", 
                    "params": [[sig]]
                }
                res = httpx.post(rpc, json=payload)
                data = res.json()
                status = data.get("result", {}).get("value", [None])[0]
                
                if status:
                    conf_status = status.get("confirmationStatus")
                    err = status.get("err")
                    if err:
                        print(f"❌ Hermes: Transactie gefaald op-chain: {err}")
                        return False
                    if conf_status in ["confirmed", "finalized"]:
                        print(f"✅ Hermes: BEVESTIGD! Status: {conf_status}")
                        return True
                print(".", end="", flush=True)
            except Exception as e:
                print(f"⚠️ Error check status: {e}")
        
        print("\n⚠️ Hermes: Timeout bij wachten op bevestiging. De transactie kan nog steeds lukken, maar we hebben geen bevestiging.")
        return False
    else:
        print("❌ Hermes: Kon geen transactie versturen.")
        return False

if __name__ == "__main__":
    retry_swap_and_confirm()
