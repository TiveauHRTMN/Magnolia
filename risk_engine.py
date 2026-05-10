"""
Aladdin Risk Engine — Portfolio risico analyse voor Magnolia.
Berekent: concentratie-risico, SOL-correlatie, stress tests, liquiditeit.
"""
import config

# SOL-correlatie per protocol (hoeveel van de waarde beweegt mee met SOL-prijs)
SOL_CORRELATION = {
    "JLP": 0.55,      # JLP bevat ~55% SOL-gecorreleerde assets
    "JitoSOL": 1.00,  # 100% SOL
    "SOL": 1.00,
    "USDC": 0.00,
    "USDT": 0.00,
}

STRESS_SCENARIOS = {
    "mild": -0.20,
    "moderate": -0.40,
    "severe": -0.60,
    "extreme": -0.80,
}

RISK_THRESHOLDS = {
    "concentration_max": 0.85,   # alarm als 1 protocol >85%
    "sol_exposure_max": 0.80,    # alarm als >80% SOL-gecorreleerd
    "severe_drawdown_max": 0.55, # alarm als severe scenario >55% verlies
}


def get_sol_exposure(breakdown):
    """Hoeveel % van de portfolio beweegt mee met SOL-prijs."""
    total = sum(v["value_eur"] for v in breakdown.values())
    if total == 0:
        return 0
    sol_correlated = sum(
        v["value_eur"] * SOL_CORRELATION.get(k, 0.5)
        for k, v in breakdown.items()
    )
    return round(sol_correlated / total, 4)


def get_concentration_risk(breakdown):
    """Geeft het meest geconcentreerde protocol terug."""
    if not breakdown:
        return None, 0
    top = max(breakdown.items(), key=lambda x: x[1].get("pct", 0))
    return top[0], top[1].get("pct", 0)


def stress_test(breakdown, sol_drop_pct):
    """
    Berekent portefeuillewaarde als SOL met sol_drop_pct daalt.
    sol_drop_pct: bijv. -0.50 voor -50%
    """
    total_loss = 0
    for symbol, pos in breakdown.items():
        correlation = SOL_CORRELATION.get(symbol, 0.5)
        loss = pos["value_eur"] * correlation * abs(sol_drop_pct)
        total_loss += loss
    return round(total_loss, 4)


def analyze_risk(breakdown, total_eur, sol_eur_price=None):
    """
    Volledig risico-rapport voor Magnolia.
    Geeft risk_level: LOW | MEDIUM | HIGH terug.
    """
    if not breakdown or total_eur == 0:
        return {"risk_level": "UNKNOWN", "alerts": []}

    alerts = []
    sol_exposure = get_sol_exposure(breakdown)
    top_protocol, top_pct = get_concentration_risk(breakdown)

    # Concentratie-risico
    if top_pct > RISK_THRESHOLDS["concentration_max"]:
        alerts.append(f"CONCENTRATIE: {top_protocol} is {top_pct*100:.1f}% van portfolio")

    # SOL-correlatie risico
    if sol_exposure > RISK_THRESHOLDS["sol_exposure_max"]:
        alerts.append(f"SOL-EXPOSURE: {sol_exposure*100:.1f}% gecorreleerd aan SOL-prijs")

    # Stress tests
    stress_results = {}
    for scenario, drop in STRESS_SCENARIOS.items():
        loss_eur = stress_test(breakdown, drop)
        loss_pct = loss_eur / total_eur if total_eur else 0
        stress_results[scenario] = {
            "sol_drop": f"{drop*100:.0f}%",
            "portfolio_loss_eur": loss_eur,
            "portfolio_loss_pct": round(loss_pct, 4),
            "portfolio_remaining_eur": round(total_eur - loss_eur, 4),
        }
        if scenario == "severe" and loss_pct > RISK_THRESHOLDS["severe_drawdown_max"]:
            alerts.append(f"STRESS: Severe scenario ({drop*100:.0f}% SOL) kost {loss_pct*100:.1f}% portfolio")

    # Risk level bepalen
    if len(alerts) >= 2:
        risk_level = "HIGH"
    elif len(alerts) == 1:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "risk_level": risk_level,
        "sol_exposure_pct": sol_exposure,
        "top_concentration": {"protocol": top_protocol, "pct": top_pct},
        "stress_tests": stress_results,
        "alerts": alerts,
        "sol_eur_price": sol_eur_price,
        "total_portfolio_eur": total_eur,
    }


if __name__ == "__main__":
    # Test met gesimuleerde portfolio
    test_breakdown = {
        "JLP":     {"balance": 0.18, "value_eur": 16.52, "pct": 0.60},
        "JitoSOL": {"balance": 0.046, "value_eur": 6.88, "pct": 0.25},
        "USDC":    {"balance": 4.13, "value_eur": 4.13, "pct": 0.15},
    }
    report = analyze_risk(test_breakdown, 27.53, sol_eur_price=150.0)
    print(f"Risk level : {report['risk_level']}")
    print(f"SOL exposure: {report['sol_exposure_pct']*100:.1f}%")
    print(f"Alerts     : {report['alerts'] or 'geen'}")
    print("\nStress tests:")
    for s, r in report["stress_tests"].items():
        print(f"  {s:10} SOL {r['sol_drop']:>4}: verlies €{r['portfolio_loss_eur']:.2f} ({r['portfolio_loss_pct']*100:.1f}%) | resterend €{r['portfolio_remaining_eur']:.2f}")
