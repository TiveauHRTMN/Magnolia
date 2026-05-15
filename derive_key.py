"""
Leidt de Polygon/EVM private key af uit je Phantom herstelzin.
Draait 100% lokaal — niks gaat het internet op.
Verwijder dit script na gebruik.
"""
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

from eth_account import Account
Account.enable_unaudited_hdwallet_features()

def derive(mnemonic: str):
    mnemonic = mnemonic.strip()
    # Phantom gebruikt standaard EVM derivation path
    account = Account.from_mnemonic(mnemonic, account_path="m/44'/60'/0'/0/0")
    print(f"\nAdres:       {account.address}")
    print(f"Private key: {account.key.hex()}")
    print("\nKopieer de private key naar .env als POLYGON_PRIVATE_KEY=0x<key>")
    print("Verwijder daarna dit script.\n")

if __name__ == "__main__":
    print("Voer je Phantom herstelzin in (12 of 24 woorden):")
    mnemonic = input("> ").strip()
    derive(mnemonic)
