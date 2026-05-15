"""
Aladdin Portfolio Manager - allocatie targets en rebalancing voor Magnolia.
Bepaalt of Hermes moet rebalancen en geeft concrete instructies.
"""
import config

TARGET_ALLOCATION = {
    "JLP": 0.60,       # Growth engine - hoogste yield
    "JitoSOL": 0.25,   # Safety - stabiele staking yield
    "USDC": 0.15,      # Liquiditeit - cash voor kansen
}

REBALANCE_THRESHOLD = 0.07
MIN_PORTFOLIO_USD = 50.0


def _value_usd(position):
    return float(position.get("value_usd", 0) or 0)


def get_current_allocation(breakdown):
    """Berekent huidige allocatie als percentages."""
    total = sum(_value_usd(v) for v in breakdown.values())
    if total == 0:
        return {}
    return {k: round(_value_usd(v) / total, 4) for k, v in breakdown.items()}


def calculate_drift(current_allocation):
    """
    Vergelijkt huidige allocatie met target.
    Geeft drift per bucket terug (positief = te zwaar, negatief = te licht).
    """
    drift = {}
    for protocol, target_pct in TARGET_ALLOCATION.items():
        current_pct = current_allocation.get(protocol, 0)
        drift[protocol] = round(current_pct - target_pct, 4)
    return drift


def needs_rebalancing(drift, total_usd):
    """True als portfolio groot genoeg is en drift boven threshold zit."""
    if total_usd < MIN_PORTFOLIO_USD:
        return False
    return any(abs(v) > REBALANCE_THRESHOLD for v in drift.values())


def get_sol_reserve_excess(breakdown, reserve_sol=None):
    """
    Geeft native SOL-overschot terug boven de operationele reserve.
    Dit is een aparte reserve-check; het valt niet onder de klassieke target mix.
    """
    reserve_sol = config.MIN_SOL_RESERVE if reserve_sol is None else float(reserve_sol)
    sol_pos = breakdown.get("SOL", {}) if isinstance(breakdown, dict) else {}
    sol_balance = float(sol_pos.get("balance", 0) or 0)
    excess_sol = max(0.0, sol_balance - reserve_sol)
    return {
        "reserve_sol": round(reserve_sol, 6),
        "sol_balance": round(sol_balance, 6),
        "excess_sol": round(excess_sol, 6),
        "excess_sol_usd": round(excess_sol * float(sol_pos.get("value_usd", 0) / sol_balance), 4)
        if sol_balance > 0 and sol_pos.get("value_usd")
        else 0.0,
    }


def get_rebalancing_instructions(breakdown, total_usd):
    """
    Geeft Hermes concrete rebalancing-instructies.
    Formaat: lijst van acties die Hermes kan uitvoeren.
    """
    if total_usd < MIN_PORTFOLIO_USD:
        return {
            "rebalance_needed": False,
            "reason": f"Portfolio ${total_usd:.2f} < minimum ${MIN_PORTFOLIO_USD} voor rebalancing.",
            "instructions": [],
        }

    current = get_current_allocation(breakdown)
    drift = calculate_drift(current)

    if not needs_rebalancing(drift, total_usd):
        return {
            "rebalance_needed": False,
            "reason": "Portfolio binnen target allocatie.",
            "drift": drift,
            "instructions": [],
        }

    instructions = []
    overweight = {k: v for k, v in drift.items() if v > REBALANCE_THRESHOLD}
    underweight = {k: v for k, v in drift.items() if v < -REBALANCE_THRESHOLD}

    for sell_from, sell_drift in overweight.items():
        sell_usd = round(sell_drift * total_usd, 2)
        for buy_into, buy_drift in underweight.items():
            buy_usd = round(abs(buy_drift) * total_usd, 2)
            move_usd = min(sell_usd, buy_usd)
            if move_usd > 1.0:
                instructions.append({
                    "action": "REBALANCE",
                    "from": sell_from,
                    "to": buy_into,
                    "amount_usd": move_usd,
                    "reason": f"{sell_from} {sell_drift*100:+.1f}% drift -> {buy_into} {buy_drift*100:+.1f}% drift",
                })

    return {
        "rebalance_needed": True,
        "current_allocation": current,
        "target_allocation": TARGET_ALLOCATION,
        "drift": drift,
        "instructions": instructions,
    }


def get_defensive_rebalancing_instructions(
    breakdown,
    total_usd,
    jlp_stats=None,
    reserve_sol=None,
    force_usdc=False,
):
    """
    Defensieve pocket-correctie voor kleine wallets.
    Laat SOL-overschot naar USDC of, als carry sterk genoeg is, naar JLP schuiven.
    Werkt ook onder MIN_PORTFOLIO_USD omdat kapitaalbehoud prioriteit heeft.
    """
    excess = get_sol_reserve_excess(breakdown, reserve_sol=reserve_sol)
    excess_sol = excess.get("excess_sol", 0.0)
    excess_sol_usd = excess.get("excess_sol_usd", 0.0)
    if excess_sol < 0.001 or excess_sol_usd <= 0:
        return {
            "rebalance_needed": False,
            "reason": "Geen SOL-overschot boven operationele reserve.",
            "instructions": [],
            "reserve": excess,
        }

    current = get_current_allocation(breakdown)
    usdc_pct = current.get("USDC", 0)
    usdc_target = TARGET_ALLOCATION["USDC"]

    jlp_apy = float((jlp_stats or {}).get("apy") or 0)
    jlp_tvl = float((jlp_stats or {}).get("tvl") or 0)
    jlp_carry_healthy = jlp_apy >= 0.20 and jlp_tvl >= 3_000_000

    instructions = []
    max_sol = min(excess_sol, config.BEARISH_MAX_TRADE_SOL)

    if force_usdc or usdc_pct < usdc_target or not jlp_carry_healthy:
        instructions.append({
            "action": "REBALANCE",
            "from": "SOL",
            "to": "USDC",
            "amount_usd": round(min(excess_sol_usd, total_usd * 0.10 if total_usd else excess_sol_usd), 2),
            "reason": "Bearish/defensive posture: parkeer SOL-overschot in USDC voor kapitaalbehoud.",
        })
    else:
        move_usd = round(min(excess_sol_usd, total_usd * 0.05 if total_usd else excess_sol_usd), 2)
        if move_usd > 1.0:
            instructions.append({
                "action": "REBALANCE",
                "from": "SOL",
                "to": "JLP",
                "amount_usd": move_usd,
                "reason": "Carry is healthy enough for a small defensive SOL->JLP park move.",
            })

    if not instructions:
        return {
            "rebalance_needed": False,
            "reason": "SOL overschot bestaat wel, maar onder trade-minimum.",
            "instructions": [],
            "reserve": excess,
        }

    return {
        "rebalance_needed": True,
        "reason": "Defensive SOL reserve normalization required.",
        "current_allocation": current,
        "reserve": excess,
        "instructions": instructions,
    }


def get_status_summary(breakdown, total_usd):
    """Beknopte samenvatting voor Oracle en Hermes prompts."""
    current = get_current_allocation(breakdown)
    drift = calculate_drift(current)
    rebalance = needs_rebalancing(drift, total_usd)
    excess = get_sol_reserve_excess(breakdown)

    lines = []
    for protocol, target in TARGET_ALLOCATION.items():
        actual = current.get(protocol, 0)
        d = drift.get(protocol, 0)
        flag = " <- REBALANCE" if abs(d) > REBALANCE_THRESHOLD else ""
        lines.append(f"  {protocol:<10} target {target*100:.0f}% | actueel {actual*100:.1f}% | drift {d*100:+.1f}%{flag}")
    lines.append(
        f"  {'SOL reserve':<10} reserve {excess['reserve_sol']:.3f} | actueel {excess['sol_balance']:.3f} | overschot {excess['excess_sol']:+.3f}"
    )

    return {
        "summary_text": "\n".join(lines),
        "rebalance_needed": rebalance,
        "total_usd": total_usd,
        "sol_reserve_excess": excess,
    }


if __name__ == "__main__":
    test_breakdown = {
        "JLP": {"balance": 0.18, "value_usd": 16.52, "pct": 0.60},
        "JitoSOL": {"balance": 0.046, "value_usd": 6.88, "pct": 0.25},
        "USDC": {"balance": 4.13, "value_usd": 4.13, "pct": 0.15},
    }
    total = sum(v["value_usd"] for v in test_breakdown.values())
    result = get_rebalancing_instructions(test_breakdown, total)
    status = get_status_summary(test_breakdown, total)

    print(f"Portfolio: ${total:.2f}")
    print(f"Rebalance nodig: {result['rebalance_needed']}")
    print(f"\nAllocatie:\n{status['summary_text']}")
    if result.get("instructions"):
        print("\nInstructies:")
        for i in result["instructions"]:
            print(f"  {i['from']} -> {i['to']}: ${i['amount_usd']} ({i['reason']})")
