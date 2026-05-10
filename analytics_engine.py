"""
Aladdin Analytics — Dagelijkse P&L tracking en compound curve voor Magnolia.
Slaat dagelijkse snapshots op in analytics.json.
"""
import os
import json
import httpx
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

import config
import kiloclaw_scraper

ANALYTICS_FILE = os.path.join(os.path.dirname(__file__), "analytics.json")


def get_sol_eur_price():
    try:
        res = httpx.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "solana", "vs_currencies": "eur"},
            timeout=10.0,
        )
        return res.json()["solana"]["eur"]
    except Exception:
        return None


def get_token_price_usd(mint):
    data = kiloclaw_scraper.claw_market_data(mint)
    try:
        return float(data.get("price_usd", 0) or 0)
    except Exception:
        return 0.0


def build_portfolio_breakdown(balance_data, sol_eur):
    """
    Berekent EUR-waarde per positie op basis van token-balansen.
    Herkent JLP, JitoSOL en USDC automatisch op mint-adres.
    """
    breakdown = {}
    total_eur = 0.0

    tokens = balance_data.get("tokens", [])
    sol_balance = balance_data.get("sol_balance", 0)

    # Native SOL (ongebruikt kapitaal)
    if sol_balance > 0.001:
        val = sol_balance * sol_eur
        breakdown["SOL"] = {"balance": sol_balance, "value_eur": round(val, 4), "mint": config.SOL_MINT}
        total_eur += val

    for token in tokens:
        mint = token.get("mint", "")
        symbol = token.get("symbol", "UNK")
        balance = token.get("balance", 0)
        if balance <= 0:
            continue

        if mint == config.USDC_MINT:
            # USDC: 1:1 USD, omrekenen via EUR rate
            usd_eur = 1 / (sol_eur / (get_token_price_usd(config.SOL_MINT) or sol_eur))
            val = balance * usd_eur
            breakdown["USDC"] = {"balance": balance, "value_eur": round(val, 4), "mint": mint}
        else:
            price_usd = get_token_price_usd(mint)
            sol_usd = get_token_price_usd(config.SOL_MINT) or 1
            price_eur = price_usd * (sol_eur / sol_usd) if sol_usd else 0
            val = balance * price_eur
            breakdown[symbol] = {"balance": balance, "value_eur": round(val, 4), "mint": mint}

        total_eur += val

    # Voeg percentages toe
    if total_eur > 0:
        for k in breakdown:
            breakdown[k]["pct"] = round(breakdown[k]["value_eur"] / total_eur, 4)

    return breakdown, round(total_eur, 4)


def _load_analytics():
    if not os.path.exists(ANALYTICS_FILE):
        return {}
    try:
        with open(ANALYTICS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def record_snapshot(balance_data, sol_eur):
    breakdown, total_eur = build_portfolio_breakdown(balance_data, sol_eur)
    analytics = _load_analytics()
    today = date.today().isoformat()
    yesterday = list(analytics.keys())[-1] if analytics else None

    yesterday_eur = analytics.get(yesterday, {}).get("portfolio_eur", total_eur) if yesterday else total_eur
    pnl_eur = round(total_eur - yesterday_eur, 4)
    pnl_pct = round((pnl_eur / yesterday_eur) * 100, 4) if yesterday_eur else 0

    analytics[today] = {
        "portfolio_eur": total_eur,
        "sol_eur_price": sol_eur,
        "breakdown": breakdown,
        "daily_pnl_eur": pnl_eur,
        "daily_pnl_pct": pnl_pct,
        "timestamp": datetime.now().strftime("%H:%M"),
    }

    with open(ANALYTICS_FILE, "w", encoding="utf-8") as f:
        json.dump(analytics, f, indent=2, ensure_ascii=False)

    print(
        f"Analytics: Portfolio €{total_eur} | P&L vandaag: €{pnl_eur:+.4f} ({pnl_pct:+.2f}%) | SOL €{sol_eur}",
        flush=True,
    )
    return analytics[today]


def get_today():
    return _load_analytics().get(date.today().isoformat())


def get_compound_curve():
    """Geeft volledige groeigeschiedenis terug voor rapportage."""
    analytics = _load_analytics()
    return [
        {"date": d, "portfolio_eur": v["portfolio_eur"], "pnl_eur": v.get("daily_pnl_eur", 0)}
        for d, v in sorted(analytics.items())
    ]


def get_total_pnl():
    curve = get_compound_curve()
    if len(curve) < 2:
        return 0
    return round(sum(d["pnl_eur"] for d in curve), 4)


if __name__ == "__main__":
    import check_history
    wallet = check_history.get_wallet_address()
    balance = check_history.check_balance(wallet)
    sol_eur = get_sol_eur_price() or 150.0
    snapshot = record_snapshot(balance, sol_eur)

    curve = get_compound_curve()
    print(f"\nCompound curve ({len(curve)} dagen):")
    for entry in curve[-7:]:
        print(f"  {entry['date']}: €{entry['portfolio_eur']:.2f} ({entry['pnl_eur']:+.4f})")
    print(f"\nTotale P&L: €{get_total_pnl():.4f}")
