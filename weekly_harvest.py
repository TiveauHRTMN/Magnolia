"""
Protocol: Weekly Harvest
Ma, Woe, Vrij: Swap 0.010 SOL -> USDC via Jupiter
"""
import datetime
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from jupiter_swap import swap
from config import SOL_MINT, USDC_MINT, MIN_SOL_RESERVE
from check_history import check_balance, get_wallet_address

HARVEST_SOL = 0.010
HARVEST_LAMPORTS = int(HARVEST_SOL * 1_000_000_000)
HARVEST_DAYS = {0: "Maandag", 2: "Woensdag", 4: "Vrijdag"}  # weekday() indices

def run():
    today = datetime.datetime.now()
    weekday = today.weekday()

    if weekday not in HARVEST_DAYS:
        print(f"Vandaag is {today.strftime('%A')} — geen harvest dag. Skip.")
        return

    print(f"Harvest dag: {HARVEST_DAYS[weekday]} {today.strftime('%Y-%m-%d')}")
    print(f"Magnolia: Swap {HARVEST_SOL} SOL -> USDC...")

    wallet = get_wallet_address()
    if not wallet:
        print("Geen wallet gevonden. Abort.")
        return

    balances = check_balance(wallet)
    sol_balance = balances.get("sol", 0) if isinstance(balances, dict) else 0

    required = HARVEST_SOL + MIN_SOL_RESERVE
    if sol_balance < required:
        print(f"Onvoldoende SOL: {sol_balance:.4f} (nodig: {required:.4f}). Skip harvest.")
        return

    sig = swap(
        input_mint=SOL_MINT,
        output_mint=USDC_MINT,
        amount_lamports=HARVEST_LAMPORTS,
        slippage_bps=50
    )

    if sig:
        print(f"Harvest geslaagd: {sig}")
    else:
        print("Harvest mislukt — PEV protocol actief. Wacht op handmatig groen licht.")

if __name__ == "__main__":
    run()
