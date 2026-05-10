"""
Magnolia — Dagelijks institutioneel portfolio rapport.
Verstuurd via Resend. Bevat Aladdin analytics, risk, compound curve.
"""
import os
import httpx
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

import check_history
import analytics_engine
import risk_engine
import portfolio_manager
import guardian_jito
import banker_jlp
import farmer_airdrop

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
REPORT_TO = "rwnhrtmn@gmail.com"


def build_report():
    wallet = check_history.get_wallet_address()
    balance = check_history.check_balance(wallet)
    sol_eur = analytics_engine.get_sol_eur_price() or 150.0

    breakdown, total_eur = analytics_engine.build_portfolio_breakdown(balance, sol_eur)
    today_snap = analytics_engine.get_today()
    curve = analytics_engine.get_compound_curve()
    total_pnl = analytics_engine.get_total_pnl()

    risk = risk_engine.analyze_risk(breakdown, total_eur, sol_eur)
    pm = portfolio_manager.get_status_summary(breakdown, total_eur)

    jito = guardian_jito.get_jito_yield() or {}
    jlp = banker_jlp.get_jlp_yield() or {}

    farm_log = farmer_airdrop.get_farm_history()
    farm_today = farm_log.get(date.today().isoformat(), {})

    pnl_eur = today_snap.get("daily_pnl_eur", 0) if today_snap else 0
    pnl_pct = today_snap.get("daily_pnl_pct", 0) if today_snap else 0
    pnl_color = "#27ae60" if pnl_eur >= 0 else "#e74c3c"

    # Compound curve tabel (laatste 7 dagen)
    curve_rows = ""
    for entry in curve[-7:]:
        p = entry["pnl_eur"]
        color = "#27ae60" if p >= 0 else "#e74c3c"
        curve_rows += f"""
        <tr>
            <td style="padding:4px 8px;">{entry['date']}</td>
            <td style="padding:4px 8px; text-align:right;">€{entry['portfolio_eur']:.2f}</td>
            <td style="padding:4px 8px; text-align:right; color:{color};">€{p:+.4f}</td>
        </tr>"""

    # Allocatie rijen
    alloc_rows = ""
    for symbol, pos in breakdown.items():
        alloc_rows += f"""
        <tr>
            <td style="padding:4px 8px;">{symbol}</td>
            <td style="padding:4px 8px; text-align:right;">{pos['balance']:.4f}</td>
            <td style="padding:4px 8px; text-align:right;">€{pos['value_eur']:.2f}</td>
            <td style="padding:4px 8px; text-align:right;">{pos.get('pct',0)*100:.1f}%</td>
        </tr>"""

    risk_color = {"LOW": "#27ae60", "MEDIUM": "#f39c12", "HIGH": "#e74c3c"}.get(risk["risk_level"], "#888")
    is_sunday = datetime.now().weekday() == 6

    weekly_block = ""
    if is_sunday:
        weekly_block = f"""
        <div style="margin-top:20px; background:#fff3cd; padding:15px; border-radius:8px; border:1px solid #ffeeba;">
            <h3 style="color:#856404; margin:0 0 8px;">📅 Weekly Recap</h3>
            <p style="margin:0;">Portfolio groei deze week: <strong>€{sum(e['pnl_eur'] for e in curve[-7:]):+.4f}</strong></p>
            <p style="margin:4px 0 0;">Totale P&L since inception: <strong>€{total_pnl:+.4f}</strong></p>
        </div>"""

    alerts_block = ""
    if risk["alerts"]:
        alert_items = "".join(f"<li>{a}</li>" for a in risk["alerts"])
        alerts_block = f"""
        <div style="margin-top:16px; background:#fdecea; padding:12px; border-radius:8px; border:1px solid #f5c6cb;">
            <strong>⚠️ Risk Alerts</strong>
            <ul style="margin:8px 0 0; padding-left:20px;">{alert_items}</ul>
        </div>"""

    html = f"""
    <div style="font-family:'Helvetica Neue',Arial,sans-serif; max-width:640px; margin:auto; color:#1a1a1a;">

        <div style="background:#0d1117; padding:20px 24px; border-radius:10px 10px 0 0;">
            <h1 style="color:#fff; margin:0; font-size:18px; letter-spacing:1px;">MAGNOLIA SYNDICAAT</h1>
            <p style="color:#8b949e; margin:4px 0 0; font-size:13px;">Portfolio Report — {datetime.now().strftime('%d %b %Y, %H:%M')}</p>
        </div>

        <div style="background:#161b22; padding:20px 24px; display:flex; gap:16px;">
            <div style="flex:1; background:#21262d; padding:16px; border-radius:8px; text-align:center;">
                <p style="color:#8b949e; font-size:12px; margin:0;">PORTFOLIO WAARDE</p>
                <p style="color:#fff; font-size:28px; font-weight:bold; margin:4px 0;">€{total_eur:.2f}</p>
                <p style="color:{pnl_color}; font-size:14px; margin:0;">€{pnl_eur:+.4f} ({pnl_pct:+.2f}%) vandaag</p>
            </div>
            <div style="flex:1; background:#21262d; padding:16px; border-radius:8px; text-align:center;">
                <p style="color:#8b949e; font-size:12px; margin:0;">RISK LEVEL</p>
                <p style="color:{risk_color}; font-size:28px; font-weight:bold; margin:4px 0;">{risk['risk_level']}</p>
                <p style="color:#8b949e; font-size:12px; margin:0;">SOL exposure {risk['sol_exposure_pct']*100:.1f}%</p>
            </div>
            <div style="flex:1; background:#21262d; padding:16px; border-radius:8px; text-align:center;">
                <p style="color:#8b949e; font-size:12px; margin:0;">SOL PRIJS</p>
                <p style="color:#fff; font-size:28px; font-weight:bold; margin:4px 0;">€{sol_eur:.2f}</p>
                <p style="color:#8b949e; font-size:12px; margin:0;">JLP APY {jlp.get('apy',0)*100:.1f}% | jitoSOL APY {jito.get('apy',0)*100:.2f}%</p>
            </div>
        </div>

        <div style="background:#fff; padding:20px 24px;">

            <h3 style="color:#333; margin:0 0 12px;">Portefeuille Breakdown</h3>
            <table style="width:100%; border-collapse:collapse; font-size:14px;">
                <thead>
                    <tr style="background:#f6f8fa;">
                        <th style="padding:6px 8px; text-align:left;">Asset</th>
                        <th style="padding:6px 8px; text-align:right;">Balans</th>
                        <th style="padding:6px 8px; text-align:right;">Waarde</th>
                        <th style="padding:6px 8px; text-align:right;">Allocatie</th>
                    </tr>
                </thead>
                <tbody>{alloc_rows}</tbody>
            </table>

            <h3 style="color:#333; margin:20px 0 12px;">Compound Curve (7 dagen)</h3>
            <table style="width:100%; border-collapse:collapse; font-size:14px;">
                <thead>
                    <tr style="background:#f6f8fa;">
                        <th style="padding:6px 8px; text-align:left;">Datum</th>
                        <th style="padding:6px 8px; text-align:right;">Portfolio</th>
                        <th style="padding:6px 8px; text-align:right;">P&L</th>
                    </tr>
                </thead>
                <tbody>{curve_rows}</tbody>
            </table>
            <p style="font-size:13px; color:#555; margin-top:8px;">Totale P&L since inception: <strong>€{total_pnl:+.4f}</strong></p>

            <h3 style="color:#333; margin:20px 0 12px;">Farmer Status</h3>
            <p style="font-size:14px; color:#555; margin:0;">
                Vandaag gefarmed: <strong>{'Ja — ' + ', '.join(farm_today.keys()) if farm_today else 'Nog niet'}</strong>
            </p>

            {alerts_block}
            {weekly_block}

            <p style="margin-top:24px; text-align:center; font-style:italic; color:#888; font-size:13px;">
                "Superieur schalen met weinig — elke euro werkt 24/7."
            </p>
        </div>

        <div style="background:#0d1117; padding:12px 24px; border-radius:0 0 10px 10px; text-align:center;">
            <p style="color:#484f58; font-size:12px; margin:0;">Magnolia Syndicaat · Powered by Opus 4.7 + Hermes 4 70B</p>
        </div>

    </div>
    """

    return html, total_eur, pnl_eur


def send_report():
    if not RESEND_API_KEY:
        print("RESEND_API_KEY niet gevonden. Rapport niet verstuurd.")
        return False

    html, total_eur, pnl_eur = build_report()
    subject_emoji = "📈" if pnl_eur >= 0 else "📉"
    is_sunday = datetime.now().weekday() == 6
    subject = f"{'WEEKLY · ' if is_sunday else ''}{subject_emoji} Magnolia — €{total_eur:.2f} | P&L €{pnl_eur:+.4f} · {datetime.now().strftime('%d %b')}"

    res = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
        json={
            "from": "Magnolia <onboarding@resend.dev>",
            "to": [REPORT_TO],
            "subject": subject,
            "html": html,
        },
    )
    if res.status_code == 200:
        print(f"Rapport verstuurd naar {REPORT_TO}.", flush=True)
        return True
    print(f"Rapport fout: {res.status_code} {res.text}", flush=True)
    return False


if __name__ == "__main__":
    send_report()
