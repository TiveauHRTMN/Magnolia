"""
Aladdin Portfolio Manager — Allocatie targets en rebalancing voor Magnolia.
Bepaalt of Hermes moet rebalancen en geeft concrete instructies.
"""
import config

# Target allocatie — aanpassen naarmate portfolio groeit
TARGET_ALLOCATION = {
    "JLP":     0.60,   # Growth engine — hoogste yield
    "JitoSOL": 0.25,   # Safety — stabiele staking yield
    "USDC":    0.15,   # Liquiditeit — cash voor kansen
}

REBALANCE_THRESHOLD = 0.07   # Rebalance bij >7% drift van target
MIN_PORTFOLIO_EUR = 50.0     # Onder dit bedrag: geen rebalancing (gas te duur)


def get_current_allocation(breakdown):
    """Berekent huidige allocatie als percentages."""
    total = sum(v["value_eur"] for v in breakdown.values())
    if total == 0:
        return {}
    return {k: round(v["value_eur"] / total, 4) for k, v in breakdown.items()}


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


def needs_rebalancing(drift, total_eur):
    """True als portfolio groot genoeg is én drift boven threshold zit."""
    if total_eur < MIN_PORTFOLIO_EUR:
        return False
    return any(abs(v) > REBALANCE_THRESHOLD for v in drift.values())


def get_rebalancing_instructions(breakdown, total_eur):
    """
    Geeft Hermes concrete rebalancing-instructies.
    Formaat: lijst van acties die Hermes kan uitvoeren.
    """
    if total_eur < MIN_PORTFOLIO_EUR:
        return {
            "rebalance_needed": False,
            "reason": f"Portfolio €{total_eur:.2f} < minimum €{MIN_PORTFOLIO_EUR} voor rebalancing.",
            "instructions": [],
        }

    current = get_current_allocation(breakdown)
    drift = calculate_drift(current)

    if not needs_rebalancing(drift, total_eur):
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
        sell_eur = round(sell_drift * total_eur, 2)
        for buy_into, buy_drift in underweight.items():
            buy_eur = round(abs(buy_drift) * total_eur, 2)
            move_eur = min(sell_eur, buy_eur)
            if move_eur > 1.0:  # Minimum €1 om gas te rechtvaardigen
                instructions.append({
                    "action": "REBALANCE",
                    "from": sell_from,
                    "to": buy_into,
                    "amount_eur": move_eur,
                    "reason": f"{sell_from} {sell_drift*100:+.1f}% drift → {buy_into} {buy_drift*100:+.1f}% drift",
                })

    return {
        "rebalance_needed": True,
        "current_allocation": current,
        "target_allocation": TARGET_ALLOCATION,
        "drift": drift,
        "instructions": instructions,
    }


def get_status_summary(breakdown, total_eur):
    """Beknopte samenvatting voor Oracle en Hermes prompts."""
    current = get_current_allocation(breakdown)
    drift = calculate_drift(current)
    rebalance = needs_rebalancing(drift, total_eur)

    lines = []
    for protocol, target in TARGET_ALLOCATION.items():
        actual = current.get(protocol, 0)
        d = drift.get(protocol, 0)
        flag = " ← REBALANCE" if abs(d) > REBALANCE_THRESHOLD else ""
        lines.append(f"  {protocol:<10} target {target*100:.0f}% | actueel {actual*100:.1f}% | drift {d*100:+.1f}%{flag}")

    return {
        "summary_text": "\n".join(lines),
        "rebalance_needed": rebalance,
        "total_eur": total_eur,
    }


if __name__ == "__main__":
    test_breakdown = {
        "JLP":     {"balance": 0.18, "value_eur": 16.52, "pct": 0.60},
        "JitoSOL": {"balance": 0.046, "value_eur": 6.88, "pct": 0.25},
        "USDC":    {"balance": 4.13, "value_eur": 4.13, "pct": 0.15},
    }
    total = sum(v["value_eur"] for v in test_breakdown.values())
    result = get_rebalancing_instructions(test_breakdown, total)
    status = get_status_summary(test_breakdown, total)

    print(f"Portfolio: €{total:.2f}")
    print(f"Rebalance nodig: {result['rebalance_needed']}")
    print(f"\nAllocatie:\n{status['summary_text']}")
    if result.get("instructions"):
        print("\nInstructies:")
        for i in result["instructions"]:
            print(f"  {i['from']} → {i['to']}: €{i['amount_eur']} ({i['reason']})")
