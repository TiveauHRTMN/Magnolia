import os
import json
import time
import sys
import httpx

# Het Syndicaat
import config
import check_history
import jupiter_swap
import kiloclaw_scraper
import paperclip_optimizer
import hermes_logger
import kamino_vault
import guardian_jito
import banker_jlp
import fleet_orchestrator
import oracle_prophet
import farmer_airdrop
import analytics_engine
import risk_engine
import portfolio_manager

def get_market_context():
    wallet = check_history.get_wallet_address()
    if not wallet:
        return {"error": "Geen geldige wallet gevonden."}

    # THE ORACLE — eenmalige ochtendvoorspelling (cache-aware, 20u TTL)
    print("Market: The Oracle raadplegen...", flush=True)
    oracle = oracle_prophet.run_oracle()

    print("Market: Balansgegevens ophalen...", flush=True)
    balance_data = check_history.check_balance(wallet)

    print("Market: Kiloclaw marktanalyse starten...", flush=True)
    sol_market_data = kiloclaw_scraper.claw_market_data(config.SOL_MINT)
    trending_pairs = kiloclaw_scraper.scan_trending_pairs()

    print("Market: Guardian + Banker activeren...", flush=True)
    jito_stats = guardian_jito.get_jito_yield()
    jlp_stats = banker_jlp.get_jlp_yield()

    # ALADDIN — Analytics, Risk, Portfolio Manager
    print("Market: Aladdin suite activeren...", flush=True)
    sol_eur = analytics_engine.get_sol_eur_price() or 150.0
    breakdown, total_eur = analytics_engine.build_portfolio_breakdown(balance_data, sol_eur)
    snapshot = analytics_engine.record_snapshot(balance_data, sol_eur)
    risk_report = risk_engine.analyze_risk(breakdown, total_eur, sol_eur)
    pm_status = portfolio_manager.get_status_summary(breakdown, total_eur)
    pm_instructions = portfolio_manager.get_rebalancing_instructions(breakdown, total_eur)

    return {
        "wallet_address": wallet,
        "sol_balance": balance_data.get("sol_balance", 0),
        "tokens": balance_data.get("tokens", []),
        "live_market_data": {"SOL": sol_market_data, "trending": trending_pairs},
        "protocols_data": {
            "guardian_jito": jito_stats,
            "banker_jlp": jlp_stats,
        },
        "aladdin": {
            "portfolio_eur": total_eur,
            "sol_eur_price": sol_eur,
            "daily_pnl_eur": snapshot.get("daily_pnl_eur", 0),
            "daily_pnl_pct": snapshot.get("daily_pnl_pct", 0),
            "breakdown": breakdown,
            "risk": risk_report,
            "portfolio_allocation": pm_status["summary_text"],
            "rebalance_needed": pm_instructions["rebalance_needed"],
            "rebalance_instructions": pm_instructions.get("instructions", []),
        },
        "limits": {
            "MIN_SOL_RESERVE": config.MIN_SOL_RESERVE,
            "MAX_TRADE_SOL": config.MAX_TRADE_SOL,
        },
        "oracle": oracle or {},
        "farm_log_today": farmer_airdrop.already_farmed_today(),
        "current_focus": "Guardian (JitoSOL) + Banker (JLP) + Farmer (airdrops).",
    }

def analyze_and_decide(context):
    print(f"Hermes: Besluit nemen met {config.OPENROUTER_MODEL}...", flush=True)

    oracle = context.get("oracle", {})
    oracle_block = ""
    if oracle:
        oracle_block = f"""
ORACLE BRIEFING (Opus 4.7 — geldig voor vandaag):
- Sentiment   : {oracle.get('macro_sentiment')} ({oracle.get('confidence')}% confidence)
- Risico      : {oracle.get('risk_level')}
- SOL thesis  : {oracle.get('sol_thesis')}
- Hermes dir. : {oracle.get('hermes_directive')}
- Sectoren OK : {', '.join(oracle.get('high_conviction_sectors', []))}
- Vermijden   : {', '.join(oracle.get('avoid_sectors', []))}
- Visie       : {oracle.get('oracle_summary')}

Volg de Oracle-briefing tenzij live marktdata er direct tegenin gaat.
"""

    aladdin = context.get("aladdin", {})
    aladdin_block = ""
    if aladdin:
        rebalance_note = ""
        if aladdin.get("rebalance_needed"):
            instrs = aladdin.get("rebalance_instructions", [])
            rebalance_note = "\nREBALANCE VEREIST:\n" + "\n".join(
                f"  {i['from']} → {i['to']}: €{i['amount_eur']} ({i['reason']})"
                for i in instrs
            )
        risk = aladdin.get("risk", {})
        aladdin_block = f"""
ALADDIN PORTFOLIO INTELLIGENCE:
- Portfolio waarde : €{aladdin.get('portfolio_eur', 0):.2f} | SOL €{aladdin.get('sol_eur_price', 0):.2f}
- Dagelijkse P&L  : €{aladdin.get('daily_pnl_eur', 0):+.4f} ({aladdin.get('daily_pnl_pct', 0):+.2f}%)
- Risk level       : {risk.get('risk_level', 'UNKNOWN')} | SOL-exposure {risk.get('sol_exposure_pct', 0)*100:.1f}%
- Alerts           : {', '.join(risk.get('alerts', [])) or 'geen'}
- Allocatie:
{aladdin.get('portfolio_allocation', '')}
{rebalance_note}
"""

    prompt = f"""
Je bent Hermes — portfolio manager van het Magnolia Syndicaat.
Missie: superieur schalen met weinig. Elk besluit bouwt het financiële imperium.
{oracle_block}{aladdin_block}
LIVE MARKTDATA:
{json.dumps(context, indent=2)}

UITVOERINGSREGELS:
- Volg Oracle-richting tenzij live data er duidelijk tegenin gaat.
- Prioriteer rebalancing als Aladdin dit aangeeft.
- Alleen moves met wiskundig voordeel (ROI > netwerkkosten).
- DEPOSIT_KAMINO als USDC > {config.DEPOSIT_THRESHOLD_USDC} USDC en yield aantrekkelijk.
- Geen emotie — alleen getallen, allocatie en compound.

Antwoord ALTIJD en ALLEEN in JSON formaat:
{{
    "macro_thesis": "Portfolio-visie in 1 zin — bouwt dit het imperium?",
    "self_correction_audit": "Volg ik Oracle + Aladdin of wijk ik af en waarom?",
    "action": "SWAP" | "HOLD" | "DEPOSIT_KAMINO",
    "params": {{
        "from": "MINT_ADDRESS",
        "to": "MINT_ADDRESS",
        "amount_sol": 0.05
    }},
    "paperclip_memory_note": "Wat moet Paperclip onthouden van deze move?"
}}
"""


    content = None

    if config.OPENROUTER_API_KEY:
        print(f"Magnolia: Syndicaat-data verwerken met {config.OPENROUTER_MODEL} via OpenRouter...", flush=True)
        try:
            with httpx.Client(timeout=45.0) as client:
                res = client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": config.OPENROUTER_MODEL,
                        "messages": [{"role": "user", "content": prompt}]
                    }
                )
                res.raise_for_status()
                data = res.json()
                content = data['choices'][0]['message']['content']
        except Exception as e:
            print(f"⚠️ Hermes gefaald ({e}). Fallback naar DeepSeek V4 Flash...", flush=True)

    if not content and config.OPENROUTER_API_KEY:
        print(f"Magnolia: Fallback — {config.DEEPSEEK_FLASH_MODEL} via OpenRouter...", flush=True)
        try:
            with httpx.Client(timeout=45.0) as client:
                res = client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": config.DEEPSEEK_FLASH_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                res.raise_for_status()
                content = res.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"❌ DeepSeek Fallback gefaald: {e}", flush=True)
            return None

    if not content:
        return None

    try:
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        return json.loads(content)
    except Exception as e:
        print(f"❌ JSON Parse Fout: {e}\nContent was: {content}", flush=True)
        return None

def execute_decision(decision, current_sol_balance, tokens):
    if not decision: return
        
    action = decision.get("action")
    print(f"\n🧠 God Mode Thesis: {decision.get('macro_thesis')}", flush=True)
    print(f"⚖️ Audit: {decision.get('self_correction_audit')}", flush=True)
    print(f"⚖️ Action: {action}", flush=True)

    note = decision.get("paperclip_memory_note", "")
    if note:
        fleet_orchestrator.paperclip.remember(note)
    
    is_safe, audit_msg = fleet_orchestrator.paperclip.audit(decision)
    if not is_safe:
        print(f"🛑 Paperclip Veto: {audit_msg}", flush=True)
        return

    if action == "SWAP":
        params = decision.get("params", {})
        try:
            amount_sol = float(params.get('amount_sol', 0.01))
            if amount_sol > config.MAX_TRADE_SOL:
                amount_sol = config.MAX_TRADE_SOL
        except (ValueError, TypeError):
            amount_sol = 0.01
            
        amount_lamports = int(amount_sol * 1_000_000_000)
        target_from = params.get('from', config.SOL_MINT)
        target_to = params.get('to', config.USDC_MINT)
            
        swap_params = {
            "from": target_from,
            "to": target_to,
            "amount_lamports": amount_lamports
        }
        
        is_approved, reason = paperclip_optimizer.evaluate_trade(swap_params, current_sol_balance)
        
        if is_approved:
            print(f"🔄 Magnolia: LIVE SWAP gestart ({amount_sol} SOL)...", flush=True)
            try:
                # 1. Execute swap
                sig = jupiter_swap.swap(swap_params.get('from'), swap_params.get('to'), swap_params.get('amount_lamports'))
                
                if sig:
                    # 2. PEV Protocol: Activeer 30-seconde cooldown en verificatie
                    print(f"⏳ PEV Protocol Geactiveerd: 30 seconden cooldown voor {sig}...", flush=True)
                    time.sleep(30)
                    
                    # 3. Balance ophalen
                    wallet = check_history.get_wallet_address()
                    new_balance = check_history.check_balance(wallet)
                    
                    target_found = False
                    if target_to == config.SOL_MINT:
                        if new_balance.get("sol_balance", 0) > 0: target_found = True
                    else:
                        for t in new_balance.get('tokens', []):
                            if t.get('mint') == target_to and t.get('balance', 0) > 0:
                                target_found = True
                                break
                                
                    # 4. Resultaat beoordelen en loggen
                    if target_found:
                        print("✅ PEV PASSED: Target balans is succesvol geüpdatet.", flush=True)
                        hermes_logger.log_action("Magnolia", "god_mode_trade", f"Syndicaat trade succesvol: {amount_sol} {target_from[:4]} -> {target_to[:4]}. Sig: {sig}")
                    else:
                        print("🚨 PEV FAILED: Target balans onveranderd of 0 na executie.", flush=True)
                        fleet_orchestrator.paperclip.remember(f"FAILED SWAP: PEV Protocol getriggerd. Balans bleef leeg na swap {sig}.")
                        hermes_logger.log_action("Magnolia", "god_mode_trade_failed", f"PEV FAILED. Geen tokens ontvangen voor sig: {sig}")
                        
                        # Hard stop op de huidige executie-thread
                        print("🛑 PEV Protocol blokkeert verdere acties. Systeem wacht op handmatig groen licht.", flush=True)
                        sys.exit(1)
            except Exception as e:
                print(f"⚠️ Executiefout: {e}.", flush=True)
        else:
            print(f"🛑 Paperclip Veto: {reason}", flush=True)

def _should_send_report():
    """Verstuurt rapport eenmaal per dag om 07:00."""
    now = time.localtime()
    if now.tm_hour != 7:
        return False
    flag = os.path.join(os.path.dirname(__file__), ".report_sent_today")
    today = time.strftime("%Y-%m-%d")
    if os.path.exists(flag):
        with open(flag) as f:
            if f.read().strip() == today:
                return False
    with open(flag, "w") as f:
        f.write(today)
    return True


def run_syndicate():
    import daily_report
    iteration = 0
    print(f"Magnolia Syndicaat gestart — {time.strftime('%Y-%m-%d %H:%M')}", flush=True)

    while True:
        print("\n" + "="*45, flush=True)
        print("--- MAGNOLIA SYNDICAAT — GUARDIAN + BANKER + FARMER ---", flush=True)
        print("="*45, flush=True)

        try:
            context = get_market_context()
            if "error" not in context:
                sol_bal = context.get('sol_balance', 0)

                # Farmer: eenmaal per dag
                if not farmer_airdrop.already_farmed_today():
                    oracle = context.get("oracle", {})
                    farmer_airdrop.run_farmer(
                        oracle_targets=oracle.get("airdrop_targets"),
                        sol_balance=sol_bal,
                    )

                # Dagelijks rapport om 07:00
                if _should_send_report():
                    print("Magnolia: Dagelijks rapport versturen...", flush=True)
                    daily_report.send_report()

                if iteration % 5 == 0:
                    aladdin = context.get("aladdin", {})
                    hermes_logger.log_action(
                        "Magnolia", "system_check",
                        f"Online. Portfolio €{aladdin.get('portfolio_eur', 0):.2f} | P&L €{aladdin.get('daily_pnl_eur', 0):+.4f}",
                        status="active",
                    )

                decision = analyze_and_decide(context)
                if decision:
                    execute_decision(decision, sol_bal, context.get('tokens', []))
                else:
                    print("Magnolia: HOLD — geen besluit mogelijk.", flush=True)

            iteration += 1

        except SystemExit:
            print("Magnolia: PEV Protocol hard stop. Herstart over 60 minuten.", flush=True)
            time.sleep(3600)

        except Exception as e:
            print(f"Magnolia: Fout in cyclus ({e}). Herstart over 5 minuten.", flush=True)
            time.sleep(300)

        print(f"\nMagnolia rust (15m)... [{time.strftime('%H:%M')}]", flush=True)
        time.sleep(900)


if __name__ == "__main__":
    run_syndicate()
