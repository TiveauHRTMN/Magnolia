import os
import base58
from solders.keypair import Keypair
from dotenv import load_dotenv

load_dotenv()

def verify():
    try:
        priv_key_str = os.getenv("SOLANA_PRIVATE_KEY")
        if not priv_key_str:
            print("❌ Fout: SOLANA_PRIVATE_KEY niet gevonden in .env")
            return
            
        # Zet de Base58 string om naar een Keypair object
        keypair = Keypair.from_bytes(base58.b58decode(priv_key_str))
        
        print(f"✅ Sleutel geverifieerd!")
        print(f"Publiek adres van deze sleutel: {keypair.pubkey()}")
        print("Komt dit overeen met wat je in Phantom ziet? Dan zijn we LIVE.")
    except Exception as e:
        print(f"❌ Fout bij het laden van de sleutel: {e}")

if __name__ == "__main__":
    verify()
