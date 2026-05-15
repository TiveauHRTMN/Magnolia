"""
Deterministic execution policy for Magnolia.

Agents can propose actions, but this module decides whether an action is
eligible to reach the wallet. Profit is never guaranteed; the standard here is
positive expected value with explicit downside controls.
"""
import json
import os
from datetime import date, datetime

import config
import jupiter_swap
import kiloclaw_scraper

JOURNAL_FILE = os.path.join(os.path.dirname(__file__), "trade_journal.json")


def _load_journal():
    if not os.path.exists(JOURNAL_FILE):
        return []
    try:
        with open(JOURNAL_FILE, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def record_trade_event(event):
    journal = _load_journal()
    item = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        **event,
    }
    journal.append(item)
    journal = journal[-500:]
    with open(JOURNAL_FILE, "w", encoding="utf-8") as f:
        json.dump(journal, f, indent=2, ensure_ascii=False)


def _todays_events():
    today = date.today().isoformat()
    return [e for e in _load_journal() if str(e.get("timestamp", "")).startswith(today)]


def _daily_trade_count():
    return len([e for e in _todays_events() if e.get("status") == "executed"])


def _is_defensive_de_risk(context):
    aladdin = context.get("aladdin", {}) or {}
    oracle = context.get("oracle", {}) or {}
    systemics = aladdin.get("systemics", {}) or {}
    daily_pnl = float(aladdin.get("daily_pnl_usd") or 0)
    sol_balance = float(context.get("sol_balance", 0) or 0)
    reserve = float(context.get("limits", {}).get("MIN_SOL_RESERVE", config.MIN_SOL_RESERVE) or config.MIN_SOL_RESERVE)
    has_sol_excess = sol_balance > reserve + 0.001
    momentum = _live_sol_momentum(context)

    bearish = (
        str(oracle.get("macro_sentiment", "")).upper() == "BEARISH"
        or str(oracle.get("market_bias", "")).upper() == "BEARISH"
        or str(oracle.get("macro_regime", "")).upper() == "RISK_OFF"
        or str(oracle.get("risk_level", "")).upper() == "HIGH"
        or str(systemics.get("systemic_regime", "")).upper() == "DEFENSIVE"
        or daily_pnl <= -abs(config.AIRDROP_MAX_DAILY_LOSS_USD)
    )
    strong_momentum = momentum["price_change_24h"] >= 2.5 and momentum["price_drift_pct"] >= 1.0
    return bearish and has_sol_excess and not strong_momentum


def _oracle_regime_layer(context):
    oracle = context.get("oracle", {}) or {}
    return str(oracle.get("regime_layer", "")).upper()


def _live_sol_momentum(context):
    live_market = context.get("live_market_data", {}) or {}
    sol_market = live_market.get("SOL", {}) or {}
    oracle = context.get("oracle", {}) or {}
    oracle_snapshot = oracle.get("oracle_inputs_snapshot", {}) or {}

    try:
        price_change_24h = float(sol_market.get("price_change_24h") or 0)
    except (TypeError, ValueError):
        price_change_24h = 0.0

    try:
        live_price = float(sol_market.get("price_usd") or 0)
    except (TypeError, ValueError):
        live_price = 0.0

    try:
        oracle_price = float(oracle_snapshot.get("sol_usd_price") or 0)
    except (TypeError, ValueError):
        oracle_price = 0.0

    price_drift_pct = 0.0
    if oracle_price > 0 and live_price > 0:
        price_drift_pct = abs((live_price - oracle_price) / oracle_price) * 100

    return {
        "price_change_24h": price_change_24h,
        "live_price": live_price,
        "oracle_price": oracle_price,
        "price_drift_pct": price_drift_pct,
    }


def _oracle_execution_freshness(context):
    oracle = context.get("oracle", {}) or {}
    saved_at_raw = oracle.get("saved_at")
    if not saved_at_raw:
        return False, "Oracle decision is missing a saved_at timestamp."

    try:
        saved_at = datetime.fromisoformat(saved_at_raw)
    except Exception:
        return False, f"Oracle decision timestamp is invalid: {saved_at_raw!r}."

    age_hours = (datetime.now() - saved_at).total_seconds() / 3600
    if age_hours > config.ORACLE_MAX_EXECUTION_AGE_HOURS:
        return (
            False,
            f"Oracle decision is {age_hours:.1f}h old; refresh required before execution.",
        )

    oracle_snapshot = oracle.get("oracle_inputs_snapshot", {}) or {}
    oracle_sol = oracle_snapshot.get("sol_usd_price")
    live_sol = context.get("aladdin", {}).get("sol_usd_price")
    try:
        oracle_sol = float(oracle_sol)
        live_sol = float(live_sol)
    except (TypeError, ValueError):
        return True, f"Oracle decision age {age_hours:.1f}h; price drift check unavailable."

    if oracle_sol > 0 and live_sol > 0:
        drift_pct = abs((live_sol - oracle_sol) / oracle_sol) * 100
        if drift_pct > config.ORACLE_MAX_PRICE_DRIFT_PCT:
            return (
                False,
                f"Oracle snapshot SOL ${oracle_sol:.2f} vs live ${live_sol:.2f} drift {drift_pct:.1f}% exceeds {config.ORACLE_MAX_PRICE_DRIFT_PCT:.1f}%.",
            )

    return True, f"Oracle decision age {age_hours:.1f}h and price drift within limits."


def _is_pre_breakout_staging(context):
    oracle = context.get("oracle", {}) or {}
    aladdin = context.get("aladdin", {}) or {}
    systemics = aladdin.get("systemics", {}) or {}
    layer = _oracle_regime_layer(context)
    if layer != "PREPARE_BREAKOUT":
        return False
    if str(oracle.get("macro_sentiment", "")).upper() == "BEARISH":
        return False
    if str(systemics.get("systemic_regime", "")).upper() == "DEFENSIVE":
        return False
    if float(aladdin.get("daily_pnl_usd") or 0) <= -abs(config.AIRDROP_MAX_DAILY_LOSS_USD):
        return False
    return True


def _is_momentum_rotation(context):
    oracle = context.get("oracle", {}) or {}
    aladdin = context.get("aladdin", {}) or {}
    systemics = aladdin.get("systemics", {}) or {}
    momentum = _live_sol_momentum(context)

    if momentum["price_change_24h"] < 2.5:
        return False
    if momentum["price_drift_pct"] < 1.0:
        return False
    if str(oracle.get("macro_sentiment", "")).upper() == "BEARISH":
        return False
    if str(systemics.get("systemic_regime", "")).upper() == "DEFENSIVE":
        return False
    return True


def _is_defensive_swap(decision, context):
    if not _is_defensive_de_risk(context):
        return False
    if not isinstance(decision, dict):
        return False

    params = decision.get("params")
    if not isinstance(params, dict):
        return False

    from_mint = params.get("from")
    to_mint = params.get("to")
    if from_mint != config.SOL_MINT:
        return False
    if to_mint not in {config.USDC_MINT, config.JLP_MINT}:
        return False

    if to_mint == config.USDC_MINT:
        momentum = _live_sol_momentum(context)
        if momentum["price_change_24h"] >= 2.5 or momentum["price_drift_pct"] >= config.ORACLE_MAX_PRICE_DRIFT_PCT:
            return False

    try:
        amount_sol = float(params.get("amount_sol", 0) or 0)
    except (TypeError, ValueError):
        return False
    if amount_sol <= 0:
        return False

    if to_mint == config.JLP_MINT:
        jlp = context.get("protocols_data", {}).get("banker_jlp", {}) or {}
        apy = float(jlp.get("apy") or 0)
        tvl = float(jlp.get("tvl") or 0)
        if apy < 0.20 or tvl < 3_000_000:
            return False

    return True


def _is_pre_breakout_swap(decision, context):
    if not _is_pre_breakout_staging(context):
        return False
    if not isinstance(decision, dict):
        return False

    params = decision.get("params")
    if not isinstance(params, dict):
        return False

    from_mint = params.get("from")
    to_mint = params.get("to")
    if from_mint not in {config.SOL_MINT, config.USDC_MINT}:
        return False
    if to_mint != config.JITOSOL_MINT:
        return False

    try:
        amount_sol = float(params.get("amount_sol", 0) or 0)
    except (TypeError, ValueError):
        return False
    if amount_sol <= 0:
        return False

    oracle = context.get("oracle", {}) or {}
    confidence = int(oracle.get("confidence") or 0)
    if confidence < 55:
        return False

    return True


def get_execution_gate(context):
    """
    Cheap preflight gate for the agent loop.

    This runs before Hermes is asked for a decision, so known hard blocks do not
    create noisy SWAP/DEPOSIT proposals that policy will reject anyway.
    """
    trade_count = _daily_trade_count()
    base = {
        "daily_trade_count": trade_count,
        "max_daily_trades": config.MAX_DAILY_TRADES,
    }

    if os.path.exists(config.PAUSE_FILE):
        return {**base, "can_trade": False, "only_hold": True, "reason": "Pause file present; execution disabled."}

    aladdin = context.get("aladdin", {}) or {}
    risk = aladdin.get("risk", {}) or {}
    oracle = context.get("oracle", {}) or {}
    daily_pnl = float(aladdin.get("daily_pnl_usd") or 0)

    oracle_fresh, oracle_fresh_reason = _oracle_execution_freshness(context)
    if not oracle_fresh:
        return {
            **base,
            "can_trade": False,
            "only_hold": True,
            "reason": oracle_fresh_reason,
        }

    defensive_only = _is_defensive_de_risk(context)
    pre_breakout = _is_pre_breakout_staging(context)

    if defensive_only:
        return {
            **base,
            "can_trade": True,
            "only_hold": False,
            "defensive_only": True,
            "reason": "Defensive pocket de-risking allowed; only SOL reserve normalization is permitted.",
        }

    if pre_breakout:
        return {
            **base,
            "can_trade": True,
            "only_hold": False,
            "pre_breakout": True,
            "reason": "Pre-breakout staging allowed; only small JitoSOL prep is permitted.",
        }

    if _is_momentum_rotation(context):
        return {
            **base,
            "can_trade": True,
            "only_hold": False,
            "momentum_rotation": True,
            "reason": "Momentum rotation allowed; idle capital may rotate toward SOL, JitoSOL, or JLP.",
        }

    if trade_count >= config.MAX_DAILY_TRADES:
        return {**base, "can_trade": False, "only_hold": True, "reason": "Daily trade limit reached."}

    if daily_pnl <= -abs(config.MAX_DAILY_LOSS_USD):
        return {**base, "can_trade": False, "only_hold": True, "reason": "Daily loss limit reached."}

    if risk.get("risk_level") == "HIGH":
        return {**base, "can_trade": False, "only_hold": True, "reason": "Risk engine is HIGH; block new capital deployment."}

    if not oracle.get("trade_permission", True):
        reason = oracle.get("trade_permission_reason") or "Oracle requires trigger confirmation before execution."
        return {**base, "can_trade": False, "only_hold": True, "reason": reason}

    if int(oracle.get("confidence") or 0) < config.MIN_ORACLE_CONFIDENCE_FOR_TRADE:
        return {**base, "can_trade": False, "only_hold": True, "reason": "Oracle confidence below trade threshold."}

    return {**base, "can_trade": True, "only_hold": False, "reason": "Execution gate open."}


def _normalize_action(action):
    if not isinstance(action, str):
        return "HOLD"
    return action.strip().upper()


def _is_known_mint(mint):
    return mint in config.ALLOWED_TRADE_MINTS


def _token_balance(tokens, mint):
    for token in tokens or []:
        if token.get("mint") == mint:
            try:
                return float(token.get("balance", 0) or 0)
            except (TypeError, ValueError):
                return 0
    return 0


def _breakdown_position(context, mint):
    breakdown = context.get("aladdin", {}).get("breakdown", {})
    for symbol, position in breakdown.items():
        if position.get("mint") == mint:
            return symbol, position
    return None, None


def _native_units(amount_tokens, mint):
    decimals = config.TOKEN_DECIMALS.get(mint)
    if decimals is None:
        raise ValueError(f"No decimals configured for {mint}")
    return int(float(amount_tokens) * (10 ** decimals))


def _execution_profile(context):
    oracle = context.get("oracle", {}) or {}
    systemics = context.get("aladdin", {}).get("systemics", {}) or {}
    sentiment = str(oracle.get("macro_sentiment", "NEUTRAL")).upper()
    regime = str(oracle.get("macro_regime", "TRANSITION")).upper()
    risk_level = str(oracle.get("risk_level", "HIGH")).upper()
    systemic_regime = str(systemics.get("systemic_regime", "BALANCED")).upper()
    regime_layer = _oracle_regime_layer(context)
    confidence = int(oracle.get("confidence") or 0)
    liquidity = int(oracle.get("liquidity_score") or 0)
    geopolitics = int(oracle.get("geopolitical_risk_score") or 50)

    if regime_layer == "DEFENSIVE":
        return {
            "mode": "DEFENSIVE",
            "max_trade_sol": min(config.BEARISH_MAX_TRADE_SOL, config.MAX_TRADE_SOL),
            "prefer_usdc": True,
        }
    if regime_layer == "PREPARE_BREAKOUT":
        return {
            "mode": "PREPARE_BREAKOUT",
            "max_trade_sol": min(config.DEFENSIVE_MAX_TRADE_SOL, config.MAX_TRADE_SOL),
            "prefer_usdc": False,
        }

    defensive = (
        sentiment == "BEARISH"
        or regime == "RISK_OFF"
        or risk_level == "HIGH"
        or systemic_regime == "DEFENSIVE"
        or geopolitics >= 70
    )
    aggressive = (
        sentiment == "BULLISH"
        and confidence >= config.MIN_ORACLE_CONFIDENCE_FOR_TRADE
        and regime == "RISK_ON"
        and risk_level in {"LOW", "MEDIUM"}
        and systemic_regime in {"EXPANSIVE", "BALANCED"}
        and liquidity >= 0
        and geopolitics < 60
    )

    if defensive:
        return {
            "mode": "DEFENSIVE",
            "max_trade_sol": min(config.BEARISH_MAX_TRADE_SOL, config.MAX_TRADE_SOL),
            "prefer_usdc": True,
        }
    if aggressive:
        return {
            "mode": "AGGRESSIVE_COMPOUND",
            "max_trade_sol": min(config.AGGRESSIVE_MAX_TRADE_SOL, config.MAX_TRADE_SOL),
            "prefer_usdc": False,
        }
    if systemic_regime == "BALANCED":
        max_trade = min(config.BALANCED_MAX_TRADE_SOL, config.MAX_TRADE_SOL)
    else:
        max_trade = min(config.DEFENSIVE_MAX_TRADE_SOL, config.MAX_TRADE_SOL)
    return {"mode": "BALANCED", "max_trade_sol": max_trade, "prefer_usdc": False}


def _normalize_swap_amount(params, context):
    from_mint = params["from"]
    requested_sol_equiv = float(params["amount_sol"])
    profile = _execution_profile(context)
    max_trade_sol = profile["max_trade_sol"]

    if from_mint == config.SOL_MINT:
        sol_balance = float(context.get("sol_balance", 0) or 0)
        spendable_sol = max(0, sol_balance - config.MIN_SOL_RESERVE)
        if spendable_sol < 0.001:
            return False, "Spendable SOL is below minimum trade size."
        amount_sol = min(requested_sol_equiv, max_trade_sol, spendable_sol)
        params["amount_sol"] = round(amount_sol, 6)
        params["amount_units"] = _native_units(params["amount_sol"], from_mint)
        params["amount_source"] = params["amount_sol"]
        return True, f"Amount set to {params['amount_sol']} SOL under {profile['mode']}."

    symbol, position = _breakdown_position(context, from_mint)
    if not position:
        return False, "Source token is not present in portfolio breakdown."

    source_balance = _token_balance(context.get("tokens", []), from_mint)
    if source_balance <= 0:
        return False, "Source token balance is zero."

    sol_usd = float(context.get("aladdin", {}).get("sol_usd_price") or 0)
    token_balance = float(position.get("balance") or 0)
    token_value_usd = float(position.get("value_usd") or 0)
    if sol_usd <= 0 or token_balance <= 0 or token_value_usd <= 0:
        return False, "Cannot price source token for SOL-equivalent sizing."

    desired_usd = min(requested_sol_equiv, max_trade_sol) * sol_usd
    token_price_usd = token_value_usd / token_balance
    desired_tokens = desired_usd / token_price_usd
    amount_tokens = min(desired_tokens, source_balance)

    if amount_tokens <= 0:
        return False, "Computed source token amount is zero."

    params["amount_source"] = round(amount_tokens, 8)
    params["amount_units"] = _native_units(amount_tokens, from_mint)
    return True, f"Amount set to {params['amount_source']} {symbol} from {requested_sol_equiv} SOL-equivalent intent under {profile['mode']}."


def _market_liquidity_ok(mint):
    if mint == config.USDC_MINT:
        return True, "USDC liquidity treated as sufficient."
    data = kiloclaw_scraper.claw_market_data(mint)
    if data.get("error"):
        return False, f"No market data for {config.ALLOWED_TRADE_MINTS.get(mint, mint)}."
    liquidity = float(data.get("liquidity_usd") or 0)
    if liquidity < config.MIN_LIQUIDITY_USD:
        return False, f"Liquidity ${liquidity:.0f} below minimum ${config.MIN_LIQUIDITY_USD:.0f}."
    return True, f"Liquidity ${liquidity:.0f} OK."


def _quote_quality_ok(from_mint, to_mint, amount_lamports):
    try:
        quote = jupiter_swap.get_quote(from_mint, to_mint, amount_lamports)
    except Exception as e:
        return False, f"Jupiter quote unavailable: {e}"

    if "outAmount" not in quote:
        return False, f"Jupiter quote missing outAmount: {quote}"

    try:
        price_impact_pct = abs(float(quote.get("priceImpactPct") or 0))
    except (TypeError, ValueError):
        price_impact_pct = 0

    if price_impact_pct > config.MAX_PRICE_IMPACT_PCT:
        return False, f"Price impact {price_impact_pct:.3f}% exceeds {config.MAX_PRICE_IMPACT_PCT:.3f}%."

    route_plan = quote.get("routePlan", [])
    if not route_plan:
        return False, "Jupiter returned no route plan."

    return True, f"Quote OK, price impact {price_impact_pct:.3f}%."


def validate_decision(decision, context):
    if os.path.exists(config.PAUSE_FILE):
        return False, "Pause file present; execution disabled."

    if not isinstance(decision, dict):
        return False, "Decision is not a JSON object."

    action = _normalize_action(decision.get("action"))
    decision["action"] = action

    defensive_swap = _is_defensive_swap(decision, context)
    pre_breakout_swap = _is_pre_breakout_swap(decision, context)

    if action == "HOLD":
        return True, "Hold decision accepted."

    if action not in {"SWAP", "DEPOSIT_KAMINO"}:
        return False, f"Unknown action {action}."

    aladdin = context.get("aladdin", {})
    risk = aladdin.get("risk", {})
    oracle = context.get("oracle", {})

    if risk.get("risk_level") == "HIGH" and not (defensive_swap or pre_breakout_swap):
        return False, "Risk engine is HIGH; block new capital deployment."

    if int(oracle.get("confidence") or 0) < config.MIN_ORACLE_CONFIDENCE_FOR_TRADE and not (defensive_swap or pre_breakout_swap):
        return False, "Oracle confidence below trade threshold."

    if not oracle.get("trade_permission", True) and not (defensive_swap or pre_breakout_swap):
        return False, oracle.get("trade_permission_reason") or "Oracle requires trigger confirmation before execution."

    if float(aladdin.get("daily_pnl_usd") or 0) <= -abs(config.MAX_DAILY_LOSS_USD) and not (defensive_swap or pre_breakout_swap):
        return False, "Daily loss limit reached."

    if _daily_trade_count() >= config.MAX_DAILY_TRADES and not (defensive_swap or pre_breakout_swap):
        return False, "Daily trade limit reached."

    profile = _execution_profile(context)

    if action == "DEPOSIT_KAMINO":
        usdc_balance = _token_balance(context.get("tokens", []), config.USDC_MINT)
        if usdc_balance < config.DEPOSIT_THRESHOLD_USDC:
            return False, f"USDC {usdc_balance:.4f} below Kamino deposit threshold."
        return True, f"Kamino deposit policy accepted under {profile['mode']}."

    params = decision.get("params")
    if not isinstance(params, dict):
        return False, "SWAP params missing."

    from_mint = params.get("from")
    to_mint = params.get("to")
    if not _is_known_mint(from_mint) or not _is_known_mint(to_mint):
        return False, "Mint outside Magnolia allowed universe."
    if from_mint == to_mint:
        return False, "Swap source and target are identical."
    momentum_rotation = bool(context.get("execution_gate", {}).get("momentum_rotation"))

    if defensive_swap and from_mint == config.SOL_MINT and to_mint == config.USDC_MINT:
        pass
    elif defensive_swap and from_mint == config.SOL_MINT and to_mint == config.JLP_MINT:
        pass
    elif pre_breakout_swap and from_mint in {config.SOL_MINT, config.USDC_MINT} and to_mint == config.JITOSOL_MINT:
        pass
    elif momentum_rotation and from_mint == config.USDC_MINT and to_mint in {config.SOL_MINT, config.JITOSOL_MINT, config.JLP_MINT}:
        pass
    elif profile["prefer_usdc"] and to_mint != config.USDC_MINT:
        return False, "Defensive profile only allows swaps toward USDC."

    try:
        amount_sol = float(params.get("amount_sol", 0))
    except (TypeError, ValueError):
        return False, "Invalid amount_sol."

    if amount_sol <= 0:
        return False, "Swap amount must be positive."
    if amount_sol > profile["max_trade_sol"]:
        params["amount_sol"] = profile["max_trade_sol"]

    ok, amount_reason = _normalize_swap_amount(params, context)
    if not ok:
        return False, amount_reason

    ok, reason = _market_liquidity_ok(to_mint)
    if not ok:
        return False, reason

    ok, quote_reason = _quote_quality_ok(from_mint, to_mint, int(params["amount_units"]))
    if not ok:
        return False, quote_reason

    if defensive_swap and to_mint == config.JLP_MINT:
        jlp = context.get("protocols_data", {}).get("banker_jlp", {}) or {}
        apy = float(jlp.get("apy") or 0)
        tvl = float(jlp.get("tvl") or 0)
        if apy < 0.20 or tvl < 3_000_000:
            return False, "Defensive SOL->JLP correction requires healthy carry conditions."

    if pre_breakout_swap:
        oracle = context.get("oracle", {}) or {}
        if str(oracle.get("macro_sentiment", "")).upper() == "BEARISH":
            return False, "Pre-breakout staging is disabled during bearish sentiment."
        if str(context.get("aladdin", {}).get("systemics", {}).get("systemic_regime", "")).upper() == "DEFENSIVE":
            return False, "Pre-breakout staging is disabled under defensive systemics."

    return True, f"Policy accepted: {amount_reason} {reason} {quote_reason}"


def should_execute_live():
    return config.MAGNOLIA_MODE == "live"
