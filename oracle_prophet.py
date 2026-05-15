"""
Magnolia Oracle — dagelijkse macro-voorspelling voor Magnolia Oracle.
Draait eenmaal per ochtend. Model via config.ORACLE_MODEL (OpenRouter).
Slaat voorspelling op in oracle_cache.json (TTL: 20 uur).
"""
import os
import json
import html
import httpx
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

import config
import kiloclaw_scraper
import guardian_jito
import banker_jlp
import oracle_systemics

CACHE_FILE = os.path.join(os.path.dirname(__file__), "oracle_cache.json")
CACHE_HISTORY_FILE = os.path.join(os.path.dirname(__file__), "oracle_history.json")
TRADE_JOURNAL_FILE = os.path.join(os.path.dirname(__file__), "trade_journal.json")
ANALYTICS_FILE = os.path.join(os.path.dirname(__file__), "analytics.json")
MACRO_CONTEXT_FILE = os.path.join(os.path.dirname(__file__), "macro_context.json")
SCORECARD_FILE = os.path.join(os.path.dirname(__file__), "oracle_scorecard.json")
CAPITAL_PLAN_FILE = os.path.join(os.path.dirname(__file__), "capital_plan.json")
REBALANCE_REQUEST_FILE = os.path.join(os.path.dirname(__file__), "oracle_rebalance_request.json")
LAST_RAW_RESPONSE_FILE = os.path.join(os.path.dirname(__file__), "oracle_last_raw_response.txt")
LAST_PRIMARY_RESPONSE_FILE = os.path.join(os.path.dirname(__file__), "oracle_last_primary_response.json")
CACHE_TTL_HOURS = 20
SCORE_HORIZONS_HOURS = (6, 24, 72)
MAX_ABS_SOL_RETURN_FOR_SCORE = 25.0


def is_cache_fresh():
    _hydrate_local_cache_from_supabase()
    if not os.path.exists(CACHE_FILE):
        return False
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            cache = json.load(f)
        for required_key in ("regime_layer", "macro_shock_score", "pre_breakout_posture", "post_breakout_posture"):
            if required_key not in cache:
                return False
        saved_at = datetime.fromisoformat(cache.get("saved_at", "2000-01-01"))
        if os.path.exists(REBALANCE_REQUEST_FILE):
            try:
                with open(REBALANCE_REQUEST_FILE, encoding="utf-8") as f:
                    request = json.load(f)
                request_at = datetime.fromisoformat(request.get("created_at", "2000-01-01"))
                if request_at.tzinfo is not None:
                    request_at = request_at.astimezone().replace(tzinfo=None)
                if request_at > saved_at:
                    return False
            except Exception:
                pass
        now = datetime.now()
        age_hours = (datetime.now() - saved_at).total_seconds() / 3600
        today_gate = now.replace(hour=config.ORACLE_DAILY_RUN_HOUR, minute=0, second=0, microsecond=0)
        required_gate = today_gate if now >= today_gate else today_gate - timedelta(days=1)
        return age_hours < CACHE_TTL_HOURS and saved_at >= required_gate
    except Exception:
        return False


def load_cache():
    with open(CACHE_FILE, encoding="utf-8") as f:
        cache = json.load(f)
    try:
        scorecard = _load_json(SCORECARD_FILE, {})
        normalized = _normalize_prediction(
            cache,
            cache.get("date", datetime.now().strftime("%Y-%m-%d")),
            scorecard.get("summary", {}) if isinstance(scorecard, dict) else {},
        )
        _save_json(CACHE_FILE, normalized)
        return normalized
    except Exception:
        return cache


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


# Supabase persistente Oracle-cache (overleeft Railway-restarts)
SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
SUPABASE_CACHE_ID = "magnolia_oracle"


def _supabase_load_cache():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        url = f"{SUPABASE_URL}/rest/v1/oracle_cache?id=eq.{SUPABASE_CACHE_ID}&select=payload&limit=1"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        res = httpx.get(url, headers=headers, timeout=10.0)
        if res.status_code != 200:
            return None
        rows = res.json()
        if not rows:
            return None
        payload = rows[0].get("payload")
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _supabase_save_cache(payload):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
    try:
        url = f"{SUPABASE_URL}/rest/v1/oracle_cache"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        }
        body = {
            "id": SUPABASE_CACHE_ID,
            "payload": payload,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        res = httpx.post(url, headers=headers, json=body, timeout=10.0)
        return res.status_code in (200, 201, 204)
    except Exception:
        return False


def _hydrate_local_cache_from_supabase():
    remote = _supabase_load_cache()
    if not remote:
        return False
    try:
        local_saved_at = None
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, encoding="utf-8") as f:
                local = json.load(f)
            local_saved_at = local.get("saved_at")
        remote_saved_at = remote.get("saved_at")
        if local_saved_at and remote_saved_at and remote_saved_at <= local_saved_at:
            return False
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(remote, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def _get_latest_analytics():
    analytics = _load_json(ANALYTICS_FILE, {})
    if not analytics:
        return {}
    latest_key = sorted(analytics.keys())[-1]
    return {"date": latest_key, **analytics[latest_key]}


def _get_systemics_report(latest_analytics=None):
    analytics = _load_json(ANALYTICS_FILE, {})
    latest = latest_analytics or _get_latest_analytics()
    breakdown = latest.get("breakdown", {}) if isinstance(latest, dict) else {}
    total_usd = float(latest.get("portfolio_usd", 0) or 0) if isinstance(latest, dict) else 0
    if not breakdown or total_usd <= 0:
        return {}
    return oracle_systemics.build_systemic_report(breakdown, total_usd, analytics)


def _parse_snapshot_datetime(date_key, timestamp):
    raw_time = timestamp or "23:59"
    try:
        return datetime.fromisoformat(f"{date_key}T{raw_time}")
    except Exception:
        return datetime.fromisoformat(f"{date_key}T23:59")


def _analytics_snapshots():
    analytics = _load_json(ANALYTICS_FILE, {})
    if not isinstance(analytics, dict):
        return []

    snapshots = []
    for date_key, payload in analytics.items():
        if not isinstance(payload, dict):
            continue
        try:
            snapshot_at = _parse_snapshot_datetime(date_key, payload.get("timestamp"))
        except Exception:
            continue
        snapshots.append(
            {
                "date": date_key,
                "snapshot_at": snapshot_at,
                "portfolio_usd": payload.get("portfolio_usd"),
                "daily_pnl_pct": payload.get("daily_pnl_pct"),
                "sol_usd_price": payload.get("sol_usd_price"),
            }
        )
    return sorted(snapshots, key=lambda item: item["snapshot_at"])


def _summarize_trades(limit=8):
    journal = _load_json(TRADE_JOURNAL_FILE, [])
    if not isinstance(journal, list):
        return {"recent": [], "counts": {}}

    recent = journal[-limit:]
    counts = {}
    for entry in journal:
        status = entry.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1

    return {
        "recent": [
            {
                "timestamp": item.get("timestamp"),
                "status": item.get("status"),
                "action": item.get("agent_action"),
                "reason": item.get("reason"),
                "from": item.get("from"),
                "to": item.get("to"),
                "amount_sol": item.get("amount_sol"),
                "amount_source": item.get("amount_source"),
                "signature": item.get("signature"),
            }
            for item in recent
        ],
        "counts": counts,
    }


def _load_macro_context():
    macro = _load_json(MACRO_CONTEXT_FILE, {})
    if not isinstance(macro, dict):
        return {}
    sources = macro.get("sources", [])
    notes = macro.get("oracle_notes", [])
    economic_watchlist = macro.get("economic_watchlist", [])
    geopolitical_watchlist = macro.get("geopolitical_watchlist", [])
    return {
        "sources": sources[:3] if isinstance(sources, list) else [],
        "oracle_notes": notes[:5] if isinstance(notes, list) else [],
        "economic_watchlist": economic_watchlist[:8] if isinstance(economic_watchlist, list) else [],
        "geopolitical_watchlist": geopolitical_watchlist[:8] if isinstance(geopolitical_watchlist, list) else [],
    }


def _load_capital_plan():
    plan = _load_json(CAPITAL_PLAN_FILE, {})
    if not isinstance(plan, dict):
        return {}
    return {
        "wallet": plan.get("wallet"),
        "base_capital_usd": plan.get("base_capital_usd"),
        "monthly_contribution_usd": plan.get("monthly_contribution_usd"),
        "monthly_contribution_eur": plan.get("monthly_contribution_eur"),
        "monthly_contribution_usd_estimate": plan.get("monthly_contribution_usd_estimate"),
        "occasional_injections": bool(plan.get("occasional_injections", False)),
        "user_manual_trading": bool(plan.get("user_manual_trading", False)),
        "funding_policy": plan.get("funding_policy"),
        "capital_policy": plan.get("capital_policy", [])[:5]
        if isinstance(plan.get("capital_policy"), list)
        else [],
    }


def _load_rebalance_request():
    request = _load_json(REBALANCE_REQUEST_FILE, {})
    return request if isinstance(request, dict) else {}


def _score_macro_shock(macro_context):
    """
    Heuristische severity-score voor macro-, geopolitieke en health shocks.
    Houdt rekening met headlines, watchlists en Oracle-notes.
    """
    if not isinstance(macro_context, dict):
        return {"score": 0, "category": "none", "hits": []}

    texts = []
    for key in ("oracle_notes", "economic_watchlist", "geopolitical_watchlist"):
        value = macro_context.get(key, [])
        if isinstance(value, list):
            texts.extend(str(item) for item in value)
    sources = macro_context.get("sources", [])
    if isinstance(sources, list):
        for source in sources[:3]:
            if isinstance(source, dict):
                texts.append(str(source.get("summary", "")))
                texts.append(str(source.get("name", "")))

    keyword_weights = {
        "invasion": 24,
        "strike": 20,
        "attack": 18,
        "war": 24,
        "conflict": 16,
        "sanction": 16,
        "missile": 18,
        "nuclear": 20,
        "outbreak": 20,
        "epidemic": 22,
        "pandemic": 22,
        "hanta": 24,
        "virus": 14,
        "fed": 8,
        "rate": 8,
        "inflation": 10,
        "recession": 14,
        "liquidity": 12,
        "debt": 10,
        "tariff": 10,
        "shutdown": 8,
    }

    hits = []
    score = 0
    for text in texts:
        lower = str(text).lower()
        for keyword, weight in keyword_weights.items():
            if keyword in lower and keyword not in hits:
                hits.append(keyword)
                score += weight

    score = max(0, min(100, score))
    if any(item in hits for item in ("invasion", "strike", "attack", "war", "conflict", "sanction", "missile", "nuclear")):
        category = "geopolitical"
    elif any(item in hits for item in ("outbreak", "epidemic", "pandemic", "hanta", "virus")):
        category = "health"
    elif hits:
        category = "macro"
    else:
        category = "none"
    return {"score": score, "category": category, "hits": hits[:8]}


def _derive_regime_layer(prediction, feedback):
    macro_context = feedback.get("macro_context", {}) if isinstance(feedback, dict) else {}
    systemics = feedback.get("systemics_report", {}) if isinstance(feedback, dict) else {}
    latest_portfolio = feedback.get("latest_portfolio", {}) if isinstance(feedback, dict) else {}
    shock = _score_macro_shock(macro_context)

    sentiment = str(prediction.get("macro_sentiment", "NEUTRAL")).upper()
    regime = str(prediction.get("macro_regime", "TRANSITION")).upper()
    risk_level = str(prediction.get("risk_level", "HIGH")).upper()
    trade_permission = bool(prediction.get("trade_permission", True))
    confidence = int(prediction.get("confidence", 0) or 0)
    geopolitics = int(prediction.get("geopolitical_risk_score", 50) or 50)
    systemic_regime = str(systemics.get("systemic_regime", "BALANCED")).upper()
    sol_beta = float(systemics.get("sol_beta") or 0)
    daily_pnl_pct = float(latest_portfolio.get("daily_pnl_pct") or 0)

    if (
        shock["score"] >= 70
        or geopolitics >= 70
        or risk_level == "HIGH"
        or systemic_regime == "DEFENSIVE"
        or sentiment == "BEARISH"
        or regime == "RISK_OFF"
        or daily_pnl_pct <= -2.0
    ):
        layer = "DEFENSIVE"
        pre_breakout = "Park SOL-excess in USDC; geen airdrop-frictie; wacht op macroverbetering."
        post_breakout = "Pas na macro- en liquiditeitsherstel opnieuw naar carry of breakout-accumulatie."
    elif (
        sentiment == "BULLISH"
        and confidence >= max(config.ORACLE_CONFIDENCE_THRESHOLD - 10, 55)
        and shock["score"] < 65
        and geopolitics < 65
        and systemic_regime in {"EXPANSIVE", "BALANCED"}
        and sol_beta <= 0.8
    ):
        if trade_permission and confidence >= config.ORACLE_CONFIDENCE_THRESHOLD and regime == "RISK_ON":
            layer = "RISK_ON"
            pre_breakout = "Scale only with confirmation; no need to front-run."
            post_breakout = "Confirmation already active; let Hermes scale within policy."
        else:
            layer = "PREPARE_BREAKOUT"
            pre_breakout = "Houd reserve, maar positioneer klein richting JitoSOL zodat de wallet klaarstaat voor bevestiging."
            post_breakout = "Bij bevestigde breakout mag Hermes versnellen, maar alleen vanuit de voorbereidende stand."
    else:
        layer = "TRANSITION"
        pre_breakout = "Behoud flexibiliteit; geen grote risk-on, geen zware defensieve churn."
        post_breakout = "Eerst prijs/volume of macrobevestiging; dan pas allocatie verhogen."

    return {
        "regime_layer": layer,
        "macro_shock_score": shock["score"],
        "macro_shock_category": shock["category"],
        "macro_shock_hits": shock["hits"],
        "pre_breakout_posture": pre_breakout,
        "post_breakout_posture": post_breakout,
        "regime_layer_reason": (
            f"sentiment={sentiment}, regime={regime}, risk={risk_level}, "
            f"confidence={confidence}, geopolitics={geopolitics}, shock={shock['score']}, "
            f"systemics={systemic_regime}, sol_beta={sol_beta:.2f}, pnl_pct={daily_pnl_pct:+.2f}%"
        ),
    }


def _get_prediction_market_signals():
    if config.POLYMARKET_DATA_MODE != "read_only":
        return {
            "mode": config.POLYMARKET_DATA_MODE,
            "execution": "disabled",
            "markets": [],
        }


def _get_airdrop_scorecard():
    try:
        import farmer_airdrop

        return farmer_airdrop.build_airdrop_scorecard()
    except Exception as e:
        return {"error": str(e)}

    try:
        import hunter_polymarket

        markets = hunter_polymarket.scan_polymarket_opportunities(limit=8)
        return {
            "mode": "read_only",
            "execution": "disabled",
            "use": "market-implied sentiment only; never a trade route",
            "markets": markets[:8],
        }
    except Exception as e:
        return {
            "mode": "read_only",
            "execution": "disabled",
            "error": str(e),
            "markets": [],
        }


def _sentiment_direction(sentiment):
    sentiment = str(sentiment or "").upper()
    if sentiment == "BULLISH":
        return 1
    if sentiment == "BEARISH":
        return -1
    return 0


def _direction_score(direction, sol_return_pct):
    if direction == 0:
        if abs(sol_return_pct) <= 1.0:
            return 1.0
        if abs(sol_return_pct) <= 2.0:
            return 0.5
        return 0.0
    if direction > 0:
        if sol_return_pct >= 0.5:
            return 1.0
        if sol_return_pct >= -0.5:
            return 0.5
        return 0.0
    if sol_return_pct <= -0.5:
        return 1.0
    if sol_return_pct <= 0.5:
        return 0.5
    return 0.0


def _build_oracle_scorecard(history, snapshots):
    scorecard = []
    skipped_outliers = 0
    if not isinstance(history, list) or not snapshots:
        return {"records": [], "summary": {}}

    for prediction in history[-60:]:
        saved_at = prediction.get("saved_at")
        baseline = prediction.get("oracle_inputs_snapshot", {})
        baseline_price = baseline.get("sol_usd_price")
        if not saved_at:
            continue
        try:
            prediction_at = datetime.fromisoformat(saved_at)
        except Exception:
            continue

        if not baseline_price:
            baseline_snapshot = next(
                (snap for snap in reversed(snapshots) if snap["snapshot_at"] <= prediction_at),
                None,
            )
            baseline_price = baseline_snapshot.get("sol_usd_price") if baseline_snapshot else None
        if not baseline_price:
            continue
        try:
            baseline_price = float(baseline_price)
        except Exception:
            continue

        direction = _sentiment_direction(prediction.get("macro_sentiment"))
        confidence = float(prediction.get("confidence", 0) or 0)
        for horizon in SCORE_HORIZONS_HOURS:
            target_at = prediction_at + timedelta(hours=horizon)
            outcome = next((snap for snap in snapshots if snap["snapshot_at"] >= target_at), None)
            if not outcome or not outcome.get("sol_usd_price"):
                continue
            try:
                outcome_price = float(outcome["sol_usd_price"])
            except Exception:
                continue

            sol_return_pct = ((outcome_price - baseline_price) / baseline_price) * 100
            if abs(sol_return_pct) > MAX_ABS_SOL_RETURN_FOR_SCORE:
                skipped_outliers += 1
                continue
            direction_score = _direction_score(direction, sol_return_pct)
            confidence_score = max(0.0, 100.0 - abs(confidence - (direction_score * 100.0)))
            scorecard.append(
                {
                    "prediction_saved_at": saved_at,
                    "horizon_hours": horizon,
                    "outcome_date": outcome["date"],
                    "macro_sentiment": prediction.get("macro_sentiment"),
                    "confidence": confidence,
                    "baseline_sol_usd": round(baseline_price, 4),
                    "outcome_sol_usd": round(outcome_price, 4),
                    "sol_return_pct": round(sol_return_pct, 3),
                    "direction_score": round(direction_score, 3),
                    "confidence_score": round(confidence_score, 1),
                }
            )

    if not scorecard:
        return {"records": [], "summary": {"skipped_outliers": skipped_outliers} if skipped_outliers else {}}

    recent = scorecard[-12:]
    avg_direction = sum(item["direction_score"] for item in recent) / len(recent)
    avg_confidence = sum(item["confidence_score"] for item in recent) / len(recent)
    summary = {
        "sample_size": len(recent),
        "avg_direction_score": round(avg_direction, 3),
        "avg_confidence_score": round(avg_confidence, 1),
        "skipped_outliers": skipped_outliers,
        "last_records": recent[-5:],
    }
    return {"records": scorecard[-120:], "summary": summary}


def refresh_oracle_scorecard():
    history = _load_json(CACHE_HISTORY_FILE, [])
    scorecard = _build_oracle_scorecard(history, _analytics_snapshots())
    _save_json(SCORECARD_FILE, scorecard)
    return scorecard


def _clamp_int(value, minimum, maximum, default=0):
    try:
        value = int(value)
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


def _text_contains_trigger_language(prediction):
    parts = [
        prediction.get("sol_thesis", ""),
        prediction.get("sol_entry_zone", ""),
        prediction.get("hermes_directive", ""),
        prediction.get("oracle_summary", ""),
    ]
    for key in ("hermes_trigger_rules", "no_trade_conditions", "invalidation_points"):
        value = prediction.get(key, [])
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        else:
            parts.append(str(value))
    text = " ".join(str(part).lower() for part in parts)
    return any(
        marker in text
        for marker in (
            "wacht",
            "wait",
            "if ",
            "then",
            "trigger",
            "boven",
            "below",
            "onder",
            "breakout",
            "uitbraak",
            "4h",
            "slot",
            "close",
            "bevestig",
            "confirm",
        )
    )


def _normalize_prediction(prediction, analysis_date, scorecard_summary=None):
    prediction.setdefault("date", analysis_date)
    prediction["macro_sentiment"] = str(prediction.get("macro_sentiment", "NEUTRAL")).upper()
    if prediction["macro_sentiment"] not in {"BULLISH", "BEARISH", "NEUTRAL"}:
        prediction["macro_sentiment"] = "NEUTRAL"

    prediction["macro_regime"] = str(prediction.get("macro_regime", "TRANSITION")).upper()
    if prediction["macro_regime"] not in {"RISK_ON", "RISK_OFF", "TRANSITION"}:
        prediction["macro_regime"] = "TRANSITION"

    prediction["risk_level"] = str(prediction.get("risk_level", "HIGH")).upper()
    if prediction["risk_level"] not in {"LOW", "MEDIUM", "HIGH"}:
        prediction["risk_level"] = "HIGH"

    prediction["confidence"] = _clamp_int(prediction.get("confidence"), 0, 100, 50)
    prediction["liquidity_score"] = _clamp_int(prediction.get("liquidity_score"), -100, 100, 0)
    prediction["geopolitical_risk_score"] = _clamp_int(
        prediction.get("geopolitical_risk_score"), 0, 100, 50
    )
    prediction["airdrop_ev_score"] = _clamp_int(prediction.get("airdrop_ev_score"), 0, 100, 50)

    prediction.setdefault("sol_entry_zone", "Geen duidelijke entry-zone.")
    if not isinstance(prediction.get("scenario_analysis"), dict):
        prediction["scenario_analysis"] = {}
    prediction["scenario_analysis"].setdefault("base_case", "Geen base case opgegeven.")
    prediction["scenario_analysis"].setdefault("bull_case", "Geen bull case opgegeven.")
    prediction["scenario_analysis"].setdefault("bear_case", "Geen bear case opgegeven.")

    for key in ("invalidation_points", "no_trade_conditions", "hermes_trigger_rules"):
        if not isinstance(prediction.get(key), list):
            prediction[key] = []

    prediction.setdefault("hermes_directive", "HOLD tenzij live marktdata de thesis bevestigt.")
    prediction.setdefault("airdrop_directive", "Farm alleen echte, fee-efficiënte protocolactiviteit.")
    prediction.setdefault("airdrop_targets", ["Jupiter", "Sanctum", "Kamino"])
    prediction.setdefault("key_catalysts", [])
    prediction.setdefault("high_conviction_sectors", [])
    prediction.setdefault("avoid_sectors", [])
    prediction.setdefault("blacklist_tokens", [])
    prediction.setdefault("oracle_summary", "")
    scorecard_summary = scorecard_summary or {}
    sample_size = int(scorecard_summary.get("sample_size") or 0)
    avg_direction = float(scorecard_summary.get("avg_direction_score") or 0)
    if sample_size >= 2 and avg_direction < 0.4 and prediction["confidence"] > 55:
        prediction["confidence"] = max(45, prediction["confidence"] - 15)
        prediction["oracle_summary"] = (
            f"Scorecard penalty actief: recente direction score {avg_direction} over "
            f"{sample_size} metingen. " + prediction.get("oracle_summary", "")
        ).strip()

    prediction.setdefault("market_bias", prediction["macro_sentiment"])
    prediction.setdefault("execution_mode", prediction["macro_regime"])
    prediction.setdefault("trigger_required", False)
    prediction.setdefault("trade_permission", True)
    prediction.setdefault("trade_permission_reason", "Oracle permits execution under policy limits.")
    prediction.setdefault("regime_layer", "TRANSITION")
    prediction.setdefault("macro_shock_score", 0)
    prediction.setdefault("macro_shock_category", "none")
    prediction.setdefault("macro_shock_hits", [])
    prediction.setdefault("pre_breakout_posture", "Behoud flexibiliteit; wacht op bevestiging.")
    prediction.setdefault("post_breakout_posture", "Schaal op zodra de bevestiging er is.")
    prediction.setdefault("regime_layer_reason", "")

    conditional_bullish = (
        prediction["macro_sentiment"] == "BULLISH"
        and prediction["macro_regime"] == "RISK_ON"
        and _text_contains_trigger_language(prediction)
    )
    if conditional_bullish:
        prediction["market_bias"] = "BULLISH"
        prediction["execution_mode"] = "CONDITIONAL_RISK_ON"
        prediction["trigger_required"] = True
        prediction["trade_permission"] = False
        prediction["trade_permission_reason"] = "Bullish thesis is conditional; wait for explicit trigger confirmation."
        prediction["macro_sentiment"] = "NEUTRAL"
        prediction["macro_regime"] = "TRANSITION"
        prediction["confidence"] = min(prediction["confidence"], 55)
        if not str(prediction["hermes_directive"]).startswith("HOLD until trigger"):
            prediction["hermes_directive"] = "HOLD until trigger confirmation. " + str(prediction["hermes_directive"])
    return prediction


def _html(value):
    return html.escape(str(value if value is not None else ""))


def _list_html(items):
    if not isinstance(items, list) or not items:
        return "<li>Geen</li>"
    return "".join(f"<li>{_html(item)}</li>" for item in items[:8])


def send_oracle_email(prediction, feedback=None):
    if not config.ORACLE_EMAIL_ENABLED:
        print("Magnolia Oracle: e-mail staat uit.", flush=True)
        return False
    if not config.RESEND_API_KEY:
        print("Magnolia Oracle: RESEND_API_KEY ontbreekt. E-mail niet verstuurd.", flush=True)
        return False

    feedback = feedback or {}
    systemics = feedback.get("systemics_report", {}) if isinstance(feedback, dict) else {}
    airdrop = feedback.get("airdrop_scorecard", {}) if isinstance(feedback, dict) else {}
    risk_budget = systemics.get("risk_budget", {}) if isinstance(systemics, dict) else {}

    scenario = prediction.get("scenario_analysis", {})
    if not isinstance(scenario, dict):
        scenario = {}

    subject = (
        f"Magnolia Oracle - {prediction.get('macro_sentiment')} "
        f"{prediction.get('confidence')}% | {prediction.get('macro_regime')} | "
        f"{prediction.get('date')}"
    )

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:680px;margin:auto;color:#111;">
      <div style="background:#0d1117;color:#fff;padding:18px 22px;border-radius:8px 8px 0 0;">
        <h1 style="margin:0;font-size:20px;">Magnolia Oracle</h1>
        <p style="margin:6px 0 0;color:#8b949e;">Dagelijkse briefing - {_html(prediction.get('date'))}</p>
      </div>
      <div style="border:1px solid #d0d7de;border-top:0;padding:18px 22px;">
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
          <tr><td><strong>Sentiment</strong></td><td>{_html(prediction.get('macro_sentiment'))} ({_html(prediction.get('confidence'))}%)</td></tr>
          <tr><td><strong>Regime</strong></td><td>{_html(prediction.get('macro_regime'))}</td></tr>
          <tr><td><strong>Risk</strong></td><td>{_html(prediction.get('risk_level'))}</td></tr>
          <tr><td><strong>Liquidity</strong></td><td>{_html(prediction.get('liquidity_score'))}</td></tr>
          <tr><td><strong>Geopolitics</strong></td><td>{_html(prediction.get('geopolitical_risk_score'))}</td></tr>
          <tr><td><strong>Airdrop EV</strong></td><td>{_html(prediction.get('airdrop_ev_score'))}</td></tr>
          <tr><td><strong>Systemics</strong></td><td>{_html(systemics.get('systemic_regime'))} | SOL beta {_html(systemics.get('sol_beta'))} | max new risk USD {_html(risk_budget.get('max_new_risk_usd'))}</td></tr>
        </table>

        <h3>SOL Thesis</h3>
        <p>{_html(prediction.get('sol_thesis'))}</p>
        <p><strong>Entry zone:</strong> {_html(prediction.get('sol_entry_zone'))}</p>

        <h3>Scenario's</h3>
        <p><strong>Base:</strong> {_html(scenario.get('base_case'))}</p>
        <p><strong>Bull:</strong> {_html(scenario.get('bull_case'))}</p>
        <p><strong>Bear:</strong> {_html(scenario.get('bear_case'))}</p>

        <h3>Hermes</h3>
        <p>{_html(prediction.get('hermes_directive'))}</p>
        <ul>{_list_html(prediction.get('hermes_trigger_rules'))}</ul>

        <h3>No-Trade / Invalidation</h3>
        <ul>{_list_html(prediction.get('no_trade_conditions'))}</ul>
        <ul>{_list_html(prediction.get('invalidation_points'))}</ul>

        <h3>Airdrops</h3>
        <p>{_html(prediction.get('airdrop_directive'))}</p>
        <p>Streak: {_html(airdrop.get('current_streak_days'))} dagen | Weekkosten: USD {_html(airdrop.get('estimated_weekly_cost_usd'))} / {_html(airdrop.get('weekly_budget_usd'))}</p>

        <h3>Summary</h3>
        <p>{_html(prediction.get('oracle_summary'))}</p>

        <p style="margin-top:22px;color:#57606a;font-size:12px;">Model: {_html(prediction.get('model_used'))}</p>
      </div>
    </div>
    """

    try:
        res = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"},
            json={
                "from": "Magnolia Oracle <onboarding@resend.dev>",
                "to": [config.REPORT_TO],
                "subject": subject,
                "html": html_body,
            },
            timeout=20.0,
        )
        if res.status_code == 200:
            print(f"Magnolia Oracle: e-mail verstuurd naar {config.REPORT_TO}.", flush=True)
            return True
        print(f"Magnolia Oracle: e-mail fout {res.status_code}: {res.text}", flush=True)
        return False
    except Exception as e:
        print(f"Magnolia Oracle: e-mail fout: {e}", flush=True)
        return False


def build_oracle_feedback():
    history = _load_json(CACHE_HISTORY_FILE, [])
    latest_oracle = history[-1] if history else {}
    latest_analytics = _get_latest_analytics()
    trade_summary = _summarize_trades()
    macro_context = _load_macro_context()
    capital_plan = _load_capital_plan()
    rebalance_request = _load_rebalance_request()
    airdrop_scorecard = _get_airdrop_scorecard()
    systemics_report = _get_systemics_report(latest_analytics)
    scorecard = refresh_oracle_scorecard()

    lessons = []
    if latest_analytics:
        pnl = float(latest_analytics.get("daily_pnl_usd", 0) or 0)
        pnl_pct = float(latest_analytics.get("daily_pnl_pct", 0) or 0)
        lessons.append(
            f"Latest portfolio snapshot {latest_analytics.get('date')}: ${latest_analytics.get('portfolio_usd', 0):.2f}, "
            f"PnL ${pnl:+.4f} ({pnl_pct:+.2f}%)."
        )

    if trade_summary["counts"]:
        parts = ", ".join(f"{k}:{v}" for k, v in sorted(trade_summary["counts"].items()))
        lessons.append(f"Trade outcomes this run: {parts}.")

    if latest_oracle:
        lessons.append(
            f"Previous Oracle: {latest_oracle.get('date')} {latest_oracle.get('macro_sentiment')} "
            f"confidence {latest_oracle.get('confidence')} risk {latest_oracle.get('risk_level')}."
        )

    if scorecard.get("summary", {}).get("sample_size"):
        summary = scorecard["summary"]
        lessons.append(
            f"Oracle scorecard: direction {summary.get('avg_direction_score')} "
            f"confidence {summary.get('avg_confidence_score')} over {summary.get('sample_size')} recent outcomes."
        )
        if float(summary.get("avg_direction_score") or 0) < 0.4:
            lessons.append(
                "Oracle correction: recent direction score is poor; lower confidence and prefer NEUTRAL/TRANSITION unless triggers are already confirmed."
            )
    elif scorecard.get("summary", {}).get("skipped_outliers"):
        lessons.append(
            f"Oracle scorecard: skipped {scorecard['summary']['skipped_outliers']} unreliable analytics outliers."
        )

    if macro_context.get("sources"):
        primary_source = macro_context["sources"][0]
        lessons.append(
            f"Macro source: {primary_source.get('name')} ({primary_source.get('date')}) "
            f"{primary_source.get('summary')}."
        )

    if macro_context.get("oracle_notes"):
        lessons.extend([f"Macro note: {note}" for note in macro_context["oracle_notes"]])

    if macro_context.get("economic_watchlist"):
        lessons.append(
            "Economic watchlist: " + ", ".join(macro_context["economic_watchlist"][:5]) + "."
        )

    if macro_context.get("geopolitical_watchlist"):
        lessons.append(
            "Geopolitical watchlist: " + ", ".join(macro_context["geopolitical_watchlist"][:5]) + "."
        )

    if capital_plan:
        lessons.append(
            f"Capital plan: {capital_plan.get('wallet')} wallet starts near "
            f"USD {capital_plan.get('base_capital_usd')} with monthly EUR "
            f"{capital_plan.get('monthly_contribution_eur')} contributions; "
            f"manual trading by user is {capital_plan.get('user_manual_trading')}. "
            "Size trades from confirmed capital only."
        )

    if rebalance_request:
        lessons.append(
            "Pocket rebalance request: manual capital event detected; do not score as P&L; "
            "decide whether to restore target pockets under policy."
        )

    if airdrop_scorecard and "error" not in airdrop_scorecard:
        lessons.append(
            f"Airdrop scorecard: {airdrop_scorecard.get('active_days')} active days, "
            f"streak {airdrop_scorecard.get('current_streak_days')} days, "
            f"counts {airdrop_scorecard.get('target_counts')}."
        )

    if systemics_report:
        lessons.append(
            f"Oracle Systemics: regime {systemics_report.get('systemic_regime')}, "
            f"SOL beta {systemics_report.get('sol_beta')}, "
            f"max new risk USD {systemics_report.get('risk_budget', {}).get('max_new_risk_usd')}."
        )

    return {
        "previous_oracle": latest_oracle,
        "latest_portfolio": latest_analytics,
        "trade_summary": trade_summary,
        "macro_context": macro_context,
        "capital_plan": capital_plan,
        "rebalance_request": rebalance_request,
        "airdrop_scorecard": airdrop_scorecard,
        "systemics_report": systemics_report,
        "scorecard_summary": scorecard.get("summary", {}),
        "lessons": lessons,
    }


def gather_oracle_inputs():
    print("The Oracle: marktdata verzamelen...", flush=True)
    sol_data = kiloclaw_scraper.claw_market_data(config.SOL_MINT)
    trending = kiloclaw_scraper.scan_trending_pairs()
    jito = guardian_jito.get_jito_yield()
    jlp = banker_jlp.get_jlp_yield()
    prediction_markets = _get_prediction_market_signals()

    return {
        "sol_market": sol_data,
        "trending_pairs": trending[:10] if trending else [],
        "jito_yield": jito,
        "jlp_yield": jlp,
        "prediction_markets": prediction_markets,
        "analysis_date": datetime.now().strftime("%Y-%m-%d"),
        "analysis_time_utc": datetime.now(timezone.utc).strftime("%H:%M UTC"),
        "feedback": build_oracle_feedback(),
    }


def run_oracle():
    if is_cache_fresh():
        print("The Oracle: dagrun-cache geladen.", flush=True)
        return load_cache()

    print(f"The Oracle: Activeren... {config.ORACLE_MODEL} consulteren...", flush=True)
    inputs = gather_oracle_inputs()
    feedback = inputs.get("feedback", {})
    macro_context = feedback.get("macro_context", {})
    capital_plan = feedback.get("capital_plan", {})
    rebalance_request = feedback.get("rebalance_request", {})
    airdrop_scorecard = feedback.get("airdrop_scorecard", {})
    systemics_report = feedback.get("systemics_report", {})
    market_payload = {key: value for key, value in inputs.items() if key != "feedback"}
    feedback_payload = {
        key: value
        for key, value in feedback.items()
        if key not in {"macro_context", "capital_plan", "rebalance_request", "airdrop_scorecard", "systemics_report"}
    }

    prompt = f"""
Je bent Magnolia Oracle — het strategische brein van Magnolia Oracle.
Vandaag is het {inputs['analysis_date']}, {inputs['analysis_time_utc']}.

Marktdata:
{json.dumps(market_payload, indent=2)}

FEEDBACKLUS VAN DE VOORGAANDE RUNS:
{json.dumps(feedback_payload, indent=2)}

MACRO-LENS:
{json.dumps(macro_context, indent=2)}

KAPITAALPLAN:
{json.dumps(capital_plan, indent=2)}

POCKET HERSTELVRAAG:
{json.dumps(rebalance_request, indent=2)}

AIRDROP SCORECARD:
{json.dumps(airdrop_scorecard, indent=2)}

ORACLE SYSTEMICS:
{json.dumps(systemics_report, indent=2)}

MACRO-INTERPRETATIE:
- Gebruik economische data als regimefilter voor risk-on / risk-off.
- Scheid marktbeeld van uitvoerbaarheid: een bullish marktbeeld zonder bevestigde trigger is NEUTRAL/TRANSITION voor execution.
- Als je woorden gebruikt als wacht, IF/THEN, breakout, 4H-slot, entry zone of bevestiging, zet trade_permission op false en execution_mode op CONDITIONAL_RISK_ON.
- Gebruik BULLISH/RISK_ON alleen wanneer de trigger al actief is en Hermes direct mag handelen binnen policy.
- Gebruik geopolitieke stress als correctie op modelconfidence, vooral voor crypto en equities.
- Geef voorkeur aan liquiditeit, kredietcondities en USD-trend boven narratief.
- Gebruik maandelijkse inleg als groeipad, niet als excuus om huidig kapitaal te overtraden.
- Als er een pocket herstelvraag is door handmatige storting/swap: behandel dit als kapitaalnormalisatie, niet als alpha. Geef alleen herstelacties als ze policy-compliant zijn; anders HOLD en geef de exacte trigger.
- Als macro bearish, risk-off, confidence laag of systeem defensief is: verlaag SOL-beta eerst naar USDC; gebruik JLP alleen als carry duidelijk beter is dan cash en de markt niet verder breekt.
- Gebruik prediction-market data alleen als read-only sentimentbron; geef geen Polymarket-orders, toegangsstappen of omzeilingsadvies.
- Gebruik Jupuary 2027 als optionele upside: prioriteer echte Jupiter fee-paying usage, JUP governance/staking alleen als kosten/lock-up logisch zijn, en behandel JLP-holdings als ecosystem exposure maar niet als bewezen standalone eligibility.
- Airdrop farming mag nooit SOL-reserve, slippage-policy of portfolio-overleving breken.
- Gebruik Oracle Systemics als harde risicolaag: verlaag trade-size bij DEFENSIVE/BALANCED regime, hoge SOL beta, drawdown, VaR of grote scenarioverliezen.
- Ken een expliciete regime_layer toe: DEFENSIVE, TRANSITION, PREPARE_BREAKOUT of RISK_ON.
- Vul macro_shock_score, macro_shock_category, pre_breakout_posture en post_breakout_posture in op basis van macro/news/geopolitiek.
- PREPARE_BREAKOUT betekent: nog niet vol risk-on, maar wel de wallet alvast in een positionele stand zetten voor een mogelijke breakout.

Jouw taak: geef een dagelijkse macro-voorspelling voor de cryptomarkt.
De vloot bestaat uit drie protocollen:
- Guardian (JitoSOL staking yield)
- Banker (JLP yield)
- Farmer (dagelijkse micro-interacties voor airdrop eligibility: Jupiter, Sanctum, Kamino)

Wees concreet. Geen platitudes. Alleen wiskundige en narratieve patronen.

KRITISCH: Antwoord UITSLUITEND in dit exacte JSON-formaat, niets anders:
{{
    "date": "{inputs['analysis_date']}",
    "macro_sentiment": "BULLISH",
    "macro_regime": "RISK_ON",
    "market_bias": "BULLISH",
    "execution_mode": "CONDITIONAL_RISK_ON",
    "trade_permission": false,
    "trade_permission_reason": "Wacht op 4H-slot boven breakoutniveau met volumeconfirmatie.",
    "trigger_required": true,
    "regime_layer": "PREPARE_BREAKOUT",
    "macro_shock_score": 25,
    "macro_shock_category": "macro",
    "macro_shock_hits": ["rate", "liquidity"],
    "pre_breakout_posture": "Houd reserve, maar positioneer klein richting JitoSOL.",
    "post_breakout_posture": "Na bevestiging mag Hermes versnellen binnen policy.",
    "confidence": 75,
    "liquidity_score": 40,
    "geopolitical_risk_score": 25,
    "airdrop_ev_score": 70,
    "sol_thesis": "Max 2 zinnen over SOL-richting vandaag.",
    "sol_entry_zone": "$95.00-$96.00",
    "risk_level": "MEDIUM",
    "scenario_analysis": {{
        "base_case": "Meest waarschijnlijke scenario en hoe Hermes daarop moet reageren.",
        "bull_case": "Wat moet gebeuren om risk-on op te schalen.",
        "bear_case": "Wat moet gebeuren om risico af te bouwen."
    }},
    "invalidation_points": ["Concreet prijs-, macro- of liquiditeitsniveau dat de thesis ongeldig maakt."],
    "no_trade_conditions": ["Conditie waaronder Hermes expliciet niets mag doen."],
    "hermes_trigger_rules": ["Concreet IF/THEN signaal voor de 15-minuten agent."],
    "hermes_directive": "Timing en aanpak voor swaps: wanneer wachten, wanneer ingrijpen.",
    "airdrop_directive": "Welke airdrop-acties vandaag nuttig zijn en welke juist te duur/onnodig zijn.",
    "airdrop_targets": ["Jupiter", "Sanctum", "Kamino"],
    "key_catalysts": ["catalyst 1", "catalyst 2"],
    "high_conviction_sectors": ["sector1"],
    "avoid_sectors": ["sector1"],
    "blacklist_tokens": [],
    "oracle_summary": "Max 3 zinnen totaalvisie voor vandaag."
}}

macro_sentiment: "BULLISH" | "BEARISH" | "NEUTRAL"
macro_regime: "RISK_ON" | "RISK_OFF" | "TRANSITION"
market_bias: directional market view, independent from execution permission
execution_mode: "RISK_ON" | "RISK_OFF" | "TRANSITION" | "CONDITIONAL_RISK_ON"
trade_permission: true only if Hermes may propose SWAP/DEPOSIT_KAMINO now
trigger_required: true when a price/volume/time trigger must happen before execution
regime_layer: "DEFENSIVE" | "TRANSITION" | "PREPARE_BREAKOUT" | "RISK_ON"
macro_shock_score: integer 0..100
macro_shock_category: "none" | "macro" | "geopolitical" | "health"
pre_breakout_posture: short instruction for the wallet before confirmation
post_breakout_posture: short instruction after confirmation
risk_level: "LOW" | "MEDIUM" | "HIGH"
liquidity_score: integer -100..100
geopolitical_risk_score: integer 0..100
airdrop_ev_score: integer 0..100
airdrop_targets: geordende lijst van ["Jupiter", "Sanctum", "Kamino"] — zet vandaag meest kansrijke protocol vooraan
"""

    content = None
    content_model_used = None

    if config.OPENROUTER_API_KEY:
        try:
            print(f"The Oracle: {config.ORACLE_MODEL} via OpenRouter consulteren...", flush=True)
            with httpx.Client(timeout=90.0) as client:
                res = client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                        "HTTP-Referer": "https://magnolia-oracle.local",
                        "X-Title": "Magnolia Oracle",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": config.ORACLE_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"},
                        "max_tokens": 16000,
                        "reasoning": {
                            "effort": config.ORACLE_REASONING_EFFORT,
                            "exclude": True,
                        },
                    },
                )
                res.raise_for_status()
                primary_response = res.json()
                _save_json(LAST_PRIMARY_RESPONSE_FILE, primary_response)
                content = primary_response["choices"][0]["message"].get("content")
                content_model_used = f"{config.ORACLE_MODEL}:{config.ORACLE_REASONING_EFFORT}"
                print(f"The Oracle: {config.ORACLE_MODEL} antwoord ontvangen.", flush=True)
        except Exception as e:
            print(f"Oracle: {config.ORACLE_MODEL} gefaald ({e}). Fallback naar DeepSeek V4 Pro...", flush=True)

    if not content and config.OPENROUTER_API_KEY:
        try:
            print(f"The Oracle: {config.DEEPSEEK_PRO_MODEL} fallback via OpenRouter...", flush=True)
            with httpx.Client(timeout=90.0) as client:
                res = client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                        "HTTP-Referer": "https://magnolia-oracle.local",
                        "X-Title": "Magnolia Oracle Fallback",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": config.DEEPSEEK_PRO_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"},
                        "max_tokens": 6000,
                    },
                )
                res.raise_for_status()
                content = res.json()["choices"][0]["message"]["content"]
                content_model_used = config.DEEPSEEK_PRO_MODEL
        except Exception as e:
            print(f"Oracle: Ook DeepSeek V4 Pro gefaald: {e}", flush=True)
            return None

    if not content:
        return None

    with open(LAST_RAW_RESPONSE_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    try:
        content = content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        if not content.startswith("{") and "{" in content:
            content = content[content.find("{") :]
        if not content.endswith("}") and "}" in content:
            content = content[: content.rfind("}") + 1]
        prediction = json.loads(content)
        prediction = _normalize_prediction(
            prediction,
            inputs["analysis_date"],
            feedback.get("scorecard_summary", {}),
        )
    except Exception as e:
        print(f"Oracle: JSON parse fout: {e}\nContent: {content[:300]}", flush=True)
        return None

    latest_portfolio = feedback.get("latest_portfolio", {})
    prediction["saved_at"] = datetime.now().isoformat()
    prediction["model_used"] = content_model_used or f"{config.ORACLE_MODEL}:{config.ORACLE_REASONING_EFFORT}"
    prediction.update(_derive_regime_layer(prediction, feedback))
    prediction["oracle_inputs_snapshot"] = {
        "portfolio_usd": latest_portfolio.get("portfolio_usd"),
        "sol_usd_price": latest_portfolio.get("sol_usd_price"),
        "daily_pnl_pct": latest_portfolio.get("daily_pnl_pct"),
    }

    history = _load_json(CACHE_HISTORY_FILE, [])
    if not isinstance(history, list):
        history = []
    history.append(prediction)
    _save_json(CACHE_HISTORY_FILE, history[-90:])

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(prediction, f, indent=2, ensure_ascii=False)

    if _supabase_save_cache(prediction):
        print("The Oracle: Cache ook naar Supabase weggeschreven (restart-bestendig).", flush=True)

    print(
        f"The Oracle: Voorspelling opgeslagen. "
        f"Sentiment: {prediction.get('macro_sentiment')} | "
        f"Confidence: {prediction.get('confidence')}% | "
        f"Risico: {prediction.get('risk_level')}",
        flush=True,
    )
    print(
        f"The Oracle: Regime layer {prediction.get('regime_layer')} | "
        f"shock {prediction.get('macro_shock_score')} ({prediction.get('macro_shock_category')})",
        flush=True,
    )

    execute_oracle_action(prediction)
    return prediction


def execute_oracle_action(prediction):
    """
    Directe actie op basis van Oracle-oordeel.
    Wordt alleen aangeroepen bij een verse voorspelling, niet vanuit cache.
    """
    if not config.ORACLE_DIRECT_ACTIONS:
        print("The Oracle: Directe acties staan uit. Hermes + policy engine nemen uitvoering over.", flush=True)
        return

    confidence = prediction.get("confidence", 0)
    sentiment = prediction.get("macro_sentiment", "NEUTRAL")
    risk = prediction.get("risk_level", "HIGH")

    print(f"\nThe Oracle: Directe actie beoordelen...", flush=True)
    print(f"  Confidence: {confidence}% | Sentiment: {sentiment} | Risico: {risk}", flush=True)

    if confidence < config.ORACLE_CONFIDENCE_THRESHOLD:
        print(
            f"The Oracle: Confidence te laag ({confidence}% < {config.ORACLE_CONFIDENCE_THRESHOLD}%). "
            f"Geen directe actie — Hermes neemt het over.",
            flush=True,
        )
        return

    # --- BULLISH SOL-positie — kleine openingszet ---
    if sentiment == "BULLISH" and risk in ["LOW", "MEDIUM"]:
        print("The Oracle: BULLISH signaal — kleine SOL-positie via Jupiter...", flush=True)
        try:
            import check_history
            import jupiter_swap
            import paperclip_optimizer

            wallet = check_history.get_wallet_address()
            if not wallet:
                print("The Oracle: Geen wallet gevonden. Swap geannuleerd.", flush=True)
                return

            balance = check_history.check_balance(wallet)
            sol_balance = balance.get("sol_balance", 0)

            amount_sol = 0.02
            amount_lamports = int(amount_sol * 1_000_000_000)

            swap_params = {
                "from": config.USDC_MINT,
                "to": config.SOL_MINT,
                "amount_lamports": amount_lamports,
            }

            is_approved, reason = paperclip_optimizer.evaluate_trade(swap_params, sol_balance)
            if is_approved:
                sig = jupiter_swap.swap(config.USDC_MINT, config.SOL_MINT, amount_lamports)
                if sig:
                    print(f"The Oracle: BULLISH swap uitgevoerd. Sig: {sig}", flush=True)
                else:
                    print("The Oracle: Swap gefaald — geen signature ontvangen.", flush=True)
            else:
                print(f"The Oracle: Paperclip blokkeert swap: {reason}", flush=True)
        except Exception as e:
            print(f"The Oracle: Swap fout: {e}", flush=True)

    else:
        print(
            f"The Oracle: Geen directe actie (sentiment={sentiment}, risk={risk}). "
            f"Hermes neemt het over in de reguliere cyclus.",
            flush=True,
        )


if __name__ == "__main__":
    result = run_oracle()
    if result:
        print("\n" + "=" * 55)
        print("     MAGNOLIA ORACLE — DAGELIJKSE BRIEFING")
        print("=" * 55)
        print(f"Datum       : {result.get('date')}")
        print(f"Sentiment   : {result.get('macro_sentiment')} ({result.get('confidence')}% confidence)")
        print(f"Regime      : {result.get('macro_regime')} | Liquidity {result.get('liquidity_score')} | Geopolitical {result.get('geopolitical_risk_score')}")
        print(f"Risico      : {result.get('risk_level')}")
        print(f"Model       : {result.get('model_used')}")
        print(f"\nSOL thesis  : {result.get('sol_thesis')}")
        print(f"Entry zone  : {result.get('sol_entry_zone')}")
        print(f"Hermes      : {result.get('hermes_directive')}")
        print(f"Pre-stand   : {result.get('pre_breakout_posture')}")
        print(f"Post-stand  : {result.get('post_breakout_posture')}")
        print(f"Farmer      : {', '.join(result.get('airdrop_targets', []))}")
        print(f"\nSectoren OK : {', '.join(result.get('high_conviction_sectors', []))}")
        print(f"Vermijden   : {', '.join(result.get('avoid_sectors', []))}")
        print(f"Catalysts   : {', '.join(result.get('key_catalysts', []))}")
        print(f"\nVisie       : {result.get('oracle_summary')}")
        print("=" * 55)
