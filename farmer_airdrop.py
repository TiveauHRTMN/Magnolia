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
from datetime import date, datetime, timedelta
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

import config
import check_history
import jupiter_swap
import kamino_vault
import policy_engine

FARM_LOG = os.path.join(os.path.dirname(__file__), "farm_log.json")
AIRDROP_SCORECARD = os.path.join(os.path.dirname(__file__), "airdrop_scorecard.json")

# Micro-bedragen — gas-efficiënt, tellen wel mee voor eligibility
JUPITER_SWAP_SOL = 0.003
SANCTUM_STAKE_SOL = 0.003
KAMINO_DEPOSIT_USDC = 0.5
ESTIMATED_FARM_COST_USD = {
    "Jupiter": 0.08,
    "Sanctum": 0.08,
    "Kamino": 0.05,
}

JITOSOL_MINT = "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn"

ALL_TARGETS = ["Jupiter", "Sanctum", "Kamino"]
TARGET_ACTION_PREFIXES = {
    "Jupiter": ("Jupiter_",),
    "Sanctum": ("Sanctum_",),
    "Kamino": ("Kamino_",),
}


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


def _record_skip(action, reason):
    log = _load_log()
    today = date.today().isoformat()
    if today not in log:
        log[today] = {}
    log[today][action] = {
        "result": "skipped",
        "reason": str(reason),
        "time": datetime.now().strftime("%H:%M"),
    }
    _save_log(log)


def _target_completed_on(day_actions, target):
    prefixes = TARGET_ACTION_PREFIXES.get(target, ())
    return any(
        action.startswith(prefixes)
        and day_actions.get(action, {}).get("result") != "skipped"
        for action in day_actions
    )


def _target_completed_today(target):
    today_actions = _load_log().get(date.today().isoformat(), {})
    return _target_completed_on(today_actions, target)


def already_farmed_today():
    today_actions = _load_log().get(date.today().isoformat(), {})
    return all(_target_completed_on(today_actions, target) for target in ALL_TARGETS)


def get_farm_history(days=7):
    log = _load_log()
    return {k: v for k, v in log.items() if k >= date.today().isoformat()[:7]}


def _week_start(today=None):
    today = today or date.today()
    return today - timedelta(days=today.weekday())


def _estimate_weekly_cost(log=None):
    log = log or _load_log()
    start = _week_start()
    total = 0.0
    for day, actions in log.items():
        try:
            day_date = date.fromisoformat(day)
        except Exception:
            continue
        if day_date < start or not isinstance(actions, dict):
            continue
        for action, payload in actions.items():
            if isinstance(payload, dict) and payload.get("result") == "skipped":
                continue
            for target, prefixes in TARGET_ACTION_PREFIXES.items():
                if action.startswith(prefixes):
                    total += ESTIMATED_FARM_COST_USD.get(target, 0)
                    break
    return round(total, 4)


def _budget_allows(target, oracle_airdrop_ev_score=None):
    spent = _estimate_weekly_cost()
    planned = ESTIMATED_FARM_COST_USD.get(target, 0)
    budget = config.AIRDROP_WEEKLY_BUDGET_USD
    if spent + planned <= budget:
        return True, f"weekly budget ok USD {spent:.2f}+{planned:.2f}/{budget:.2f}"
    if (
        oracle_airdrop_ev_score is not None
        and oracle_airdrop_ev_score >= config.AIRDROP_MIN_EV_SCORE_FOR_EXTRA_SPEND
        and spent + planned <= budget * 1.5
    ):
        return True, f"high EV override USD {spent:.2f}+{planned:.2f}/{budget:.2f}"
    return False, f"weekly airdrop budget capped USD {spent:.2f}+{planned:.2f}>{budget:.2f}"


def build_airdrop_scorecard():
    log = _load_log()
    target_counts = {target: 0 for target in ALL_TARGETS}
    total_actions = 0
    active_days = 0
    current_streak = 0

    for day, actions in sorted(log.items()):
        if not isinstance(actions, dict):
            continue
        completed_today = False
        for target in ALL_TARGETS:
            if _target_completed_on(actions, target):
                target_counts[target] += 1
                completed_today = True
        if completed_today:
            active_days += 1
            total_actions += len(actions)

    cursor = date.today()
    while True:
        actions = log.get(cursor.isoformat(), {})
        if not isinstance(actions, dict) or not any(
            _target_completed_on(actions, target) for target in ALL_TARGETS
        ):
            break
        current_streak += 1
        cursor = date.fromordinal(cursor.toordinal() - 1)

    scorecard = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "active_days": active_days,
        "current_streak_days": current_streak,
        "total_actions": total_actions,
        "target_counts": target_counts,
        "weekly_budget_usd": config.AIRDROP_WEEKLY_BUDGET_USD,
        "estimated_weekly_cost_usd": _estimate_weekly_cost(log),
        "today_completed": {
            target: _target_completed_today(target)
            for target in ALL_TARGETS
        },
        "notes": [
            "Jupiter activity is useful Jupuary footprint only when it is genuine fee-paying usage.",
            "JLP holding is Jupiter ecosystem exposure, but not a verified standalone Jupuary eligibility criterion.",
            "Prefer consistent low-cost interactions over wasteful volume farming.",
        ],
    }
    with open(AIRDROP_SCORECARD, "w", encoding="utf-8") as f:
        json.dump(scorecard, f, indent=2, ensure_ascii=False)
    return scorecard


# --- Protocol acties ---

def farm_jupiter(sol_balance):
    """Micro-swap SOL→USDC voor Jupiter volume (Jupuary eligibility)."""
    required = JUPITER_SWAP_SOL + config.MIN_SOL_RESERVE
    if sol_balance < required:
        print(f"Farmer: Onvoldoende SOL voor Jupiter ({sol_balance:.4f} < {required:.4f}). Skip.", flush=True)
        return False

    amount_lamports = int(JUPITER_SWAP_SOL * 1_000_000_000)
    print(f"Farmer: Jupiter — {JUPITER_SWAP_SOL} SOL→USDC...", flush=True)
    if not policy_engine.should_execute_live():
        print("Farmer: DRY RUN — Jupiter swap niet uitgevoerd.", flush=True)
        _record("Jupiter_SOL_USDC_DRY_RUN", "dry_run")
        return True
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
    if not policy_engine.should_execute_live():
        print("Farmer: DRY RUN — Sanctum swap niet uitgevoerd.", flush=True)
        _record("Sanctum_jitoSOL_DRY_RUN", "dry_run")
        return True
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
    if not policy_engine.should_execute_live():
        print("Farmer: DRY RUN — Kamino deposit niet uitgevoerd.", flush=True)
        _record("Kamino_USDC_DRY_RUN", "dry_run")
        return True
    result = kamino_vault.deposit_usdc(KAMINO_DEPOSIT_USDC)
    if result:
        print(f"Farmer: Kamino OK.", flush=True)
        _record("Kamino_USDC", result)
        return True
    print("Farmer: Kamino deposit gefaald.", flush=True)
    return False


# --- Hoofd-runner ---

def run_farmer(oracle_targets=None, sol_balance=0.0, oracle_airdrop_ev_score=None, daily_pnl_usd=0.0):
    """
    Dagelijkse farm-run. Eenmaal per dag, daarna skip via log-check.
    oracle_targets: lijst van protocollen die Oracle vandaag prioriteert.
    """
    if already_farmed_today():
        print("Farmer: Vandaag al gefarmed. Skip.", flush=True)
        build_airdrop_scorecard()
        return

    try:
        daily_pnl_usd = float(daily_pnl_usd or 0)
    except (TypeError, ValueError):
        daily_pnl_usd = 0.0
    if daily_pnl_usd <= -abs(config.AIRDROP_MAX_DAILY_LOSS_USD):
        print(
            f"Farmer: Pauze — daily P&L ${daily_pnl_usd:+.4f} onder "
            f"airdrop-loss grens ${-abs(config.AIRDROP_MAX_DAILY_LOSS_USD):+.2f}.",
            flush=True,
        )
        _record_skip(
            "AIRDROP_DAILY_LOSS_PAUSE",
            f"daily P&L ${daily_pnl_usd:+.4f} <= ${-abs(config.AIRDROP_MAX_DAILY_LOSS_USD):+.2f}",
        )
        build_airdrop_scorecard()
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
        if _target_completed_today(target):
            print(f"Farmer: {target} vandaag al voltooid. Skip.", flush=True)
            results[target] = True
            continue
        budget_ok, budget_reason = _budget_allows(target, oracle_airdrop_ev_score)
        if not budget_ok:
            print(f"Farmer: {target} overgeslagen - {budget_reason}.", flush=True)
            _record_skip(f"{target}_BUDGET_SKIP", budget_reason)
            results[target] = False
            continue
        print(f"Farmer: Budgetcheck {target}: {budget_reason}.", flush=True)
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
    build_airdrop_scorecard()


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
