"""
Protocol 3: The Farmer — Dagelijkse airdrop eligibility farming.
Draait eenmaal per dag. Doet micro-interacties met target protocollen
om on-chain reputatie en airdrop eligibility op te bouwen.

Targets (configureerbaar via Oracle):
  - Jupiter  : Jupuary 2027 volume farming (swap SOL↔USDC)
  - Sanctum  : LST volume (SOL→jitoSOL via Jupiter route)
  - Kamino   : punten via dagelijkse USDC deposit
"""
import os
import json
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

import config
import check_history
import jupiter_swap
import kamino_vault

FARM_LOG = os.path.join(os.path.dirname(__file__), "farm_log.json")

# Micro-bedragen — gas-efficiënt, tellen wel mee voor eligibility
JUPITER_SWAP_SOL = 0.003
SANCTUM_STAKE_SOL = 0.003
KAMINO_DEPOSIT_USDC = 0.5

JITOSOL_MINT = "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn"

ALL_TARGETS = ["Jupiter", "Sanctum", "Kamino"]


# --- Log helpers ---

def _load_log():
    if not os.path.exists(FARM_LOG):
        return {}
    try:
        with open(FARM_LOG) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_log(log):
    with open(FARM_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def _record(action, result):
    log = _load_log()
    today = date.today().isoformat()
    if today not in log:
        log[today] = {}
    log[today][action] = {"result": str(result), "time": datetime.now().strftime("%H:%M")}
    _save_log(log)


def already_farmed_today():
    return date.today().isoformat() in _load_log()


def get_farm_history(days=7):
    log = _load_log()
    return {k: v for k, v in log.items() if k >= date.today().isoformat()[:7]}


# --- Protocol acties ---

def farm_jupiter(sol_balance):
    """Micro-swap SOL→USDC voor Jupiter volume (Jupuary eligibility)."""
    required = JUPITER_SWAP_SOL + config.MIN_SOL_RESERVE
    if sol_balance < required:
        print(f"Farmer: Onvoldoende SOL voor Jupiter ({sol_balance:.4f} < {required:.4f}). Skip.", flush=True)
        return False

    amount_lamports = int(JUPITER_SWAP_SOL * 1_000_000_000)
    print(f"Farmer: Jupiter — {JUPITER_SWAP_SOL} SOL→USDC...", flush=True)
    sig = jupiter_swap.swap(config.SOL_MINT, config.USDC_MINT, amount_lamports)
    if sig:
        print(f"Farmer: Jupiter OK. Sig: {sig}", flush=True)
        _record("Jupiter_SOL_USDC", sig)
        return True
    print("Farmer: Jupiter swap gefaald.", flush=True)
    return False


def farm_sanctum(sol_balance):
    """SOL→jitoSOL via Jupiter (telt als Sanctum LST interactie + extra jitoSOL yield)."""
    required = SANCTUM_STAKE_SOL + config.MIN_SOL_RESERVE
    if sol_balance < required:
        print(f"Farmer: Onvoldoende SOL voor Sanctum. Skip.", flush=True)
        return False

    amount_lamports = int(SANCTUM_STAKE_SOL * 1_000_000_000)
    print(f"Farmer: Sanctum — {SANCTUM_STAKE_SOL} SOL→jitoSOL...", flush=True)
    sig = jupiter_swap.swap(config.SOL_MINT, JITOSOL_MINT, amount_lamports)
    if sig:
        print(f"Farmer: Sanctum OK. Sig: {sig}", flush=True)
        _record("Sanctum_jitoSOL", sig)
        return True
    print("Farmer: Sanctum swap gefaald.", flush=True)
    return False


def farm_kamino():
    """Klein USDC deposit in Kamino voor punten."""
    print(f"Farmer: Kamino — {KAMINO_DEPOSIT_USDC} USDC deposit...", flush=True)
    result = kamino_vault.deposit_usdc(KAMINO_DEPOSIT_USDC)
    if result:
        print(f"Farmer: Kamino OK.", flush=True)
        _record("Kamino_USDC", result)
        return True
    print("Farmer: Kamino deposit gefaald.", flush=True)
    return False


# --- Hoofd-runner ---

def run_farmer(oracle_targets=None, sol_balance=0.0):
    """
    Dagelijkse farm-run. Eenmaal per dag, daarna skip via log-check.
    oracle_targets: lijst van protocollen die Oracle vandaag prioriteert.
    """
    if already_farmed_today():
        print("Farmer: Vandaag al gefarmed. Skip.", flush=True)
        return

    print("\n" + "=" * 45, flush=True)
    print("--- PROTOCOL 3: THE FARMER — AIRDROP RUN ---", flush=True)
    print("=" * 45, flush=True)

    # Oracle-volgorde respecteren, onbekende targets negeren
    if oracle_targets:
        ordered = [t for t in oracle_targets if t in ALL_TARGETS]
        ordered += [t for t in ALL_TARGETS if t not in ordered]
    else:
        ordered = ALL_TARGETS

    results = {}
    for target in ordered:
        if target == "Jupiter":
            results["Jupiter"] = farm_jupiter(sol_balance)
        elif target == "Sanctum":
            results["Sanctum"] = farm_sanctum(sol_balance)
        elif target == "Kamino":
            results["Kamino"] = farm_kamino()

    succeeded = [k for k, v in results.items() if v]
    skipped = [k for k, v in results.items() if not v]

    print(f"\nFarmer: Run voltooid — {date.today().isoformat()}", flush=True)
    print(f"  Succesvol   : {', '.join(succeeded) if succeeded else 'geen'}", flush=True)
    print(f"  Overgeslagen: {', '.join(skipped) if skipped else 'geen'}", flush=True)
    print("=" * 45, flush=True)


if __name__ == "__main__":
    wallet = check_history.get_wallet_address()
    if not wallet:
        print("Geen wallet gevonden.")
        exit(1)

    balance = check_history.check_balance(wallet)
    sol = balance.get("sol_balance", 0)
    print(f"Wallet : {wallet}")
    print(f"SOL    : {sol:.4f}\n")

    history = get_farm_history()
    if history:
        print("Farm history deze maand:")
        for dag, acties in sorted(history.items()):
            print(f"  {dag}: {list(acties.keys())}")
        print()

    run_farmer(sol_balance=sol)
