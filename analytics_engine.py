"""
Aladdin Analytics - dagelijkse P&L tracking en compound curve voor Magnolia.
USD is de enige waardemunt in runtime, logs en snapshots.
"""
import os
import json
import httpx
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import config
import kiloclaw_scraper

ANALYTICS_FILE = os.path.join(os.path.dirname(__file__), "analytics.json")


def get_token_price_usd(mint):
    data = kiloclaw_scraper.claw_market_data(mint)
    try:
        return float(data.get("price_usd", 0) or 0)
    except Exception:
        return 0.0


def get_sol_usd_price():
    price = get_token_price_usd(config.SOL_MINT)
    if price > 0:
        return price

    try:
        res = httpx.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "solana", "vs_currencies": "usd"},
            timeout=10.0,
        )
        return float(res.json()["solana"]["usd"])
    except Exception:
        return None


def build_portfolio_breakdown(balance_data, sol_usd):
    """
    Berekent USD-waarde per positie op basis van token-balansen.
    Herkent JLP, JitoSOL en USDC automatisch op mint-adres.
    """
    breakdown = {}
    total_usd = 0.0

    tokens = balance_data.get("tokens", [])
    sol_balance = balance_data.get("sol_balance", 0)

    if sol_balance > 0.001 and sol_usd > 0:
        value = sol_balance * sol_usd
        breakdown["SOL"] = {
            "balance": sol_balance,
            "value_usd": round(value, 4),
            "mint": config.SOL_MINT,
        }
        total_usd += value

    for token in tokens:
        mint = token.get("mint", "")
        symbol = token.get("symbol", "UNK")
        balance = token.get("balance", 0)
        if balance <= 0:
            continue

        if mint == config.USDC_MINT:
            value = balance
            breakdown["USDC"] = {"balance": balance, "value_usd": round(value, 4), "mint": mint}
        else:
            price_usd = get_token_price_usd(mint)
            value = balance * price_usd if price_usd > 0 else 0
            breakdown[symbol] = {"balance": balance, "value_usd": round(value, 4), "mint": mint}

        total_usd += value

    if total_usd > 0:
        for k in breakdown:
            breakdown[k]["pct"] = round(breakdown[k]["value_usd"] / total_usd, 4)

    return breakdown, round(total_usd, 4)


def _load_analytics():
    if not os.path.exists(ANALYTICS_FILE):
        return {}
    try:
        with open(ANALYTICS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def record_snapshot(balance_data, sol_usd):
    breakdown, total_usd = build_portfolio_breakdown(balance_data, sol_usd)
    analytics = _load_analytics()
    today = date.today().isoformat()
    previous_dates = sorted(d for d in analytics.keys() if d < today)
    yesterday = previous_dates[-1] if previous_dates else None

    yesterday_usd = analytics.get(yesterday, {}).get("portfolio_usd", total_usd) if yesterday else total_usd
    pnl_usd = round(total_usd - yesterday_usd, 4)
    pnl_pct = round((pnl_usd / yesterday_usd) * 100, 4) if yesterday_usd else 0

    analytics[today] = {
        "portfolio_usd": total_usd,
        "sol_usd_price": sol_usd,
        "breakdown": breakdown,
        "daily_pnl_usd": pnl_usd,
        "daily_pnl_pct": pnl_pct,
        "timestamp": datetime.now().strftime("%H:%M"),
    }

    with open(ANALYTICS_FILE, "w", encoding="utf-8") as f:
        json.dump(analytics, f, indent=2, ensure_ascii=False)

    print(
        f"Analytics: Portfolio ${total_usd:.4f} | P&L vandaag: ${pnl_usd:+.4f} ({pnl_pct:+.2f}%) | SOL ${sol_usd:.2f}",
        flush=True,
    )
    return analytics[today]


def get_today():
    return _load_analytics().get(date.today().isoformat())


def get_compound_curve():
    """Geeft volledige groeigeschiedenis terug voor rapportage."""
    analytics = _load_analytics()
    return [
        {"date": d, "portfolio_usd": v["portfolio_usd"], "pnl_usd": v.get("daily_pnl_usd", 0)}
        for d, v in sorted(analytics.items())
        if isinstance(v, dict) and "portfolio_usd" in v
    ]


def get_total_pnl():
    curve = get_compound_curve()
    if len(curve) < 2:
        return 0
    return round(sum(d["pnl_usd"] for d in curve), 4)


if __name__ == "__main__":
    import check_history

    wallet = check_history.get_wallet_address()
    balance = check_history.check_balance(wallet)
    sol_usd = get_sol_usd_price() or get_token_price_usd(config.SOL_MINT)
    snapshot = record_snapshot(balance, sol_usd)

    curve = get_compound_curve()
    print(f"\nCompound curve ({len(curve)} dagen):")
    for entry in curve[-7:]:
        print(f"  {entry['date']}: ${entry['portfolio_usd']:.2f} ({entry['pnl_usd']:+.4f})")
    print(f"\nTotale P&L: ${get_total_pnl():.4f}")
