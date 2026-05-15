"""
Oracle Systemics: merkneutrale portfolio-risicoanalyse voor Magnolia.
Levert compacte quant-context aan Magnolia Oracle en Hermes.
"""
import math

import config


SOL_BETA = {
    "SOL": 1.0,
    "JitoSOL": 1.0,
    "JLP": 0.55,
    "USDC": 0.0,
    "USDT": 0.0,
}

SHOCKS = {
    "sol_minus_30": {"SOL": -0.30, "JitoSOL": -0.30, "JLP": -0.18, "USDC": 0.0},
    "risk_off": {"SOL": -0.45, "JitoSOL": -0.45, "JLP": -0.30, "USDC": 0.0},
    "usdc_depeg": {"SOL": -0.08, "JitoSOL": -0.08, "JLP": -0.12, "USDC": -0.10},
    "jlp_stress": {"SOL": -0.20, "JitoSOL": -0.20, "JLP": -0.35, "USDC": 0.0},
}


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _portfolio_series(analytics):
    if not isinstance(analytics, dict):
        return []
    rows = []
    for day, payload in sorted(analytics.items()):
        if not isinstance(payload, dict):
            continue
        value = _safe_float(payload.get("portfolio_usd"))
        if value > 0:
            rows.append({"date": day, "portfolio_usd": value})
    return rows


def _returns(series):
    out = []
    for prev, cur in zip(series, series[1:]):
        if prev["portfolio_usd"] > 0:
            out.append((cur["portfolio_usd"] - prev["portfolio_usd"]) / prev["portfolio_usd"])
    return out


def _max_drawdown(series):
    peak = 0.0
    max_dd = 0.0
    for row in series:
        value = row["portfolio_usd"]
        peak = max(peak, value)
        if peak:
            max_dd = min(max_dd, (value - peak) / peak)
    return max_dd


def _volatility(returns):
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((item - mean) ** 2 for item in returns) / (len(returns) - 1)
    return math.sqrt(variance)


def _historical_var(returns, percentile=0.05):
    if not returns:
        return 0.0
    losses = sorted(returns)
    index = max(0, min(len(losses) - 1, int(len(losses) * percentile)))
    return min(0.0, losses[index])


def _asset_shock_loss(breakdown, shocks):
    total = sum(_safe_float(pos.get("value_usd")) for pos in breakdown.values())
    if total <= 0:
        return {"loss_usd": 0.0, "loss_pct": 0.0, "remaining_usd": 0.0}

    loss = 0.0
    for symbol, pos in breakdown.items():
        value = _safe_float(pos.get("value_usd"))
        shock = shocks.get(symbol, shocks.get(config.ALLOWED_TRADE_MINTS.get(pos.get("mint")), -0.15))
        loss += value * abs(min(0.0, shock))

    return {
        "loss_usd": round(loss, 4),
        "loss_pct": round(loss / total, 4),
        "remaining_usd": round(total - loss, 4),
    }


def _risk_budget(total_usd, drawdown, volatility, sol_beta):
    if total_usd < 50:
        base = 0.015
    elif total_usd < 250:
        base = 0.025
    else:
        base = 0.04

    penalty = 1.0
    if drawdown <= -0.15:
        penalty *= 0.5
    if volatility >= 0.08:
        penalty *= 0.6
    if sol_beta >= 0.75:
        penalty *= 0.75

    risk_usd = max(0.25, total_usd * base * penalty)
    return {
        "max_new_risk_usd": round(risk_usd, 2),
        "max_trade_pct": round((risk_usd / total_usd) if total_usd else 0, 4),
    }


def build_systemic_report(breakdown, total_usd, analytics=None):
    series = _portfolio_series(analytics or {})
    returns = _returns(series)
    drawdown = _max_drawdown(series)
    volatility = _volatility(returns)
    var_95 = _historical_var(returns, 0.05)

    total = sum(_safe_float(pos.get("value_usd")) for pos in breakdown.values())
    sol_weighted = 0.0
    for symbol, pos in breakdown.items():
        sol_weighted += _safe_float(pos.get("value_usd")) * SOL_BETA.get(symbol, 0.5)
    sol_beta = round(sol_weighted / total, 4) if total else 0.0

    scenarios = {
        name: _asset_shock_loss(breakdown, shocks)
        for name, shocks in SHOCKS.items()
    }

    risk_flags = []
    if drawdown <= -0.15:
        risk_flags.append("drawdown_control")
    if volatility >= 0.08:
        risk_flags.append("high_realized_volatility")
    if sol_beta >= 0.75:
        risk_flags.append("high_sol_beta")
    if scenarios["risk_off"]["loss_pct"] >= 0.30:
        risk_flags.append("risk_off_loss_large")

    if len(risk_flags) >= 2:
        regime = "DEFENSIVE"
    elif risk_flags:
        regime = "BALANCED"
    else:
        regime = "EXPANSIVE"

    return {
        "engine": "Oracle Systemics",
        "portfolio_usd": round(total_usd, 4),
        "sample_days": len(series),
        "realized_volatility_daily": round(volatility, 4),
        "max_drawdown_pct": round(drawdown, 4),
        "historical_var_95_pct": round(var_95, 4),
        "sol_beta": sol_beta,
        "scenario_losses": scenarios,
        "risk_budget": _risk_budget(total_usd, drawdown, volatility, sol_beta),
        "risk_flags": risk_flags,
        "systemic_regime": regime,
    }
