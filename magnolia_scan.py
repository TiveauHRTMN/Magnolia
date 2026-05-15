import os
import json
import time
import sys
import httpx

# Magnolia Oracle
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
import policy_engine
import oracle_systemics

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
    sol_usd = analytics_engine.get_sol_usd_price() or analytics_engine.get_token_price_usd(config.SOL_MINT)
    breakdown, total_usd = analytics_engine.build_portfolio_breakdown(balance_data, sol_usd)
    snapshot = analytics_engine.record_snapshot(balance_data, sol_usd)
    risk_report = risk_engine.analyze_risk(breakdown, total_usd, sol_usd)
    pm_status = portfolio_manager.get_status_summary(breakdown, total_usd)
    pm_instructions = portfolio_manager.get_rebalancing_instructions(breakdown, total_usd)
    analytics_history = analytics_engine._load_analytics()
    systemics_report = oracle_systemics.build_systemic_report(breakdown, total_usd, analytics_history)
    bearish_bias = (
        str(oracle.get("macro_sentiment", "")).upper() == "BEARISH"
        or str(oracle.get("market_bias", "")).upper() == "BEARISH"
        or str(oracle.get("macro_regime", "")).upper() == "RISK_OFF"
        or str(oracle.get("risk_level", "")).upper() == "HIGH"
        or str(systemics_report.get("systemic_regime", "")).upper() == "DEFENSIVE"
        or float(snapshot.get("daily_pnl_usd", 0) or 0) <= -abs(config.AIRDROP_MAX_DAILY_LOSS_USD)
    )
    defensive_pm_instructions = portfolio_manager.get_defensive_rebalancing_instructions(
        breakdown,
        total_usd,
        jlp_stats=jlp_stats,
        force_usdc=bearish_bias,
    )

    context = {
        "wallet_address": wallet,
        "sol_balance": balance_data.get("sol_balance", 0),
        "tokens": balance_data.get("tokens", []),
        "live_market_data": {"SOL": sol_market_data, "trending": trending_pairs},
        "protocols_data": {
            "guardian_jito": jito_stats,
            "banker_jlp": jlp_stats,
        },
        "aladdin": {
            "portfolio_usd": total_usd,
            "sol_usd_price": sol_usd,
            "daily_pnl_usd": snapshot.get("daily_pnl_usd", 0),
            "daily_pnl_pct": snapshot.get("daily_pnl_pct", 0),
            "breakdown": breakdown,
            "risk": risk_report,
            "systemics": systemics_report,
            "portfolio_allocation": pm_status["summary_text"],
            "rebalance_needed": pm_instructions["rebalance_needed"],
            "rebalance_instructions": pm_instructions.get("instructions", []),
            "defensive_rebalance_needed": defensive_pm_instructions["rebalance_needed"],
            "defensive_rebalance_instructions": defensive_pm_instructions.get("instructions", []),
            "sol_reserve_excess": pm_status.get("sol_reserve_excess", {}),
        },
        "limits": {
            "MIN_SOL_RESERVE": config.MIN_SOL_RESERVE,
            "MAX_TRADE_SOL": config.MAX_TRADE_SOL,
        },
            "oracle": oracle or {},
            "farm_log_today": farmer_airdrop.already_farmed_today(),
            "current_focus": "Guardian (JitoSOL) + Banker (JLP) + Farmer (airdrops).",
            "regime_layer": (oracle or {}).get("regime_layer"),
        }
    context["execution_gate"] = policy_engine.get_execution_gate(context)
    return context

def analyze_and_decide(context):
    gate = context.get("execution_gate", {}) or {}
    if gate.get("only_hold"):
        if gate.get("defensive_only"):
            print(f"Hermes: Defensieve de-risking toegestaan. {gate.get('reason', '')}", flush=True)
        else:
            reason = gate.get("reason", "Execution gate closed.")
            print(f"Hermes: HOLD vooraf afgedwongen door policy. {reason}", flush=True)
            return {
                "macro_thesis": "Geen nieuwe uitvoering zolang de preflight-gate dicht staat.",
                "self_correction_audit": f"Policy preflight: {reason}",
                "action": "HOLD",
                "params": {},
                "paperclip_memory_note": "",
            }

    print(f"Hermes: Besluit nemen met {config.OPENROUTER_MODEL}...", flush=True)

    oracle = context.get("oracle", {})
    oracle_block = ""
    if oracle:
        oracle_block = f"""
ORACLE BRIEFING (GPT-5.5 Pro xhigh — geldig voor vandaag):
- Sentiment   : {oracle.get('macro_sentiment')} ({oracle.get('confidence')}% confidence)
- Regime      : {oracle.get('macro_regime')} | liquidity {oracle.get('liquidity_score')} | geopolitics {oracle.get('geopolitical_risk_score')}
- Risico      : {oracle.get('risk_level')}
- Layer       : {oracle.get('regime_layer')} | shock {oracle.get('macro_shock_score')} ({oracle.get('macro_shock_category')})
- SOL thesis  : {oracle.get('sol_thesis')}
- Hermes dir. : {oracle.get('hermes_directive')}
- Prep stand  : {oracle.get('pre_breakout_posture')}
- Post stand  : {oracle.get('post_breakout_posture')}
- Airdrop EV  : {oracle.get('airdrop_ev_score')} | {oracle.get('airdrop_directive')}
- Airdrops    : {', '.join(oracle.get('airdrop_targets', []))}
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
                f"  {i['from']} -> {i['to']}: ${i['amount_usd']} ({i['reason']})"
                for i in instrs
            )
        defensive_note = ""
        if aladdin.get("defensive_rebalance_needed"):
            dinstr = aladdin.get("defensive_rebalance_instructions", [])
            defensive_note = "\nDEFENSIVE DE-RISK:\n" + "\n".join(
                f"  {i['from']} -> {i['to']}: ${i['amount_usd']} ({i['reason']})"
                for i in dinstr
            )
        risk = aladdin.get("risk", {})
        systemics = aladdin.get("systemics", {})
        aladdin_block = f"""
ALADDIN PORTFOLIO INTELLIGENCE:
- Portfolio waarde : ${aladdin.get('portfolio_usd', 0):.2f} | SOL ${aladdin.get('sol_usd_price', 0):.2f}
- Dagelijkse P&L  : ${aladdin.get('daily_pnl_usd', 0):+.4f} ({aladdin.get('daily_pnl_pct', 0):+.2f}%)
- Risk level       : {risk.get('risk_level', 'UNKNOWN')} | SOL-exposure {risk.get('sol_exposure_pct', 0)*100:.1f}%
- Systemics        : {systemics.get('systemic_regime', 'UNKNOWN')} | SOL beta {systemics.get('sol_beta', 0)} | max new risk USD {systemics.get('risk_budget', {}).get('max_new_risk_usd', 0)}
- Alerts           : {', '.join(risk.get('alerts', [])) or 'geen'}
- Allocatie:
{aladdin.get('portfolio_allocation', '')}
{rebalance_note}
{defensive_note}
"""

    prompt = f"""
Je bent Hermes — portfolio manager van Magnolia Oracle.
Missie: superieur schalen met weinig. Elk besluit bouwt het financiële imperium.
{oracle_block}{aladdin_block}
LIVE MARKTDATA:
{json.dumps(context, indent=2)}

UITVOERINGSREGELS:
- Als execution_gate.only_hold true is: action MOET HOLD zijn. Geen SWAP of DEPOSIT_KAMINO voorstellen.
- Als execution_gate.defensive_only true is: action mag alleen SWAP zijn van SOL naar USDC of JLP, met kleinste nuttige hoeveelheid; geen JitoSOL en geen deposit.
- Als execution_gate.pre_breakout true is: action mag alleen SWAP zijn naar JitoSOL, met kleinste nuttige hoeveelheid; geen Kamino, geen brede risk-on.
- Als execution_gate.momentum_rotation true is: idle USDC mag klein roteren naar SOL, JitoSOL of JLP; kies de route die het beste past bij live momentum, liquiditeit en carry.
- Als Oracle trade_permission false is en geen defensive/pre_breakout gate actief is: action MOET HOLD zijn tot de trigger expliciet bevestigd is.
- Volg Oracle-richting tenzij live data er duidelijk tegenin gaat.
- Respecteer Oracle Systemics: bij DEFENSIVE/BALANCED regime kleiner traden of HOLD kiezen.
- Bij bearish/defensive omstandigheden: reduceer SOL-beta eerst naar USDC; gebruik JLP alleen als carry gezond is en dat expliciet als veiligere parkeerplek telt.
- Bij sterke SOL-upmove en duidelijke momentum_rotation: gebruik idle USDC liever voor SOL/JitoSOL/JLP dan voor extra cash, zolang reserve en quote goed blijven.
- Bij PREPARE_BREAKOUT: houd cashbuffer intact maar positioneer klein richting JitoSOL zodat de wallet al klaarstaat voor bevestiging.
- Bij BULLISH + confidence >= {config.MIN_ORACLE_CONFIDENCE_FOR_TRADE}% + RISK_ON mag je AGGRESSIVE_COMPOUND voorstellen; gebruik dan zinvolle sizing, niet automatisch minimum.
- Bij BEARISH/RISK_OFF/HIGH risk: defensief handelen, bij voorkeur richting USDC of HOLD.
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
        print(f"Magnolia Oracle: data verwerken met {config.OPENROUTER_MODEL} via OpenRouter...", flush=True)
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
                        "messages": [{"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"},
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
                        "response_format": {"type": "json_object"},
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

def execute_decision(decision, context):
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
        policy_engine.record_trade_event({
            "agent_action": action,
            "status": "blocked",
            "reason": audit_msg,
            "decision": decision,
        })
        return

    is_policy_approved, policy_reason = policy_engine.validate_decision(decision, context)
    if not is_policy_approved:
        print(f"🛑 Policy Veto: {policy_reason}", flush=True)
        policy_engine.record_trade_event({
            "agent_action": action,
            "status": "blocked",
            "reason": policy_reason,
            "decision": decision,
        })
        return

    if action == "HOLD":
        print(f"Magnolia: HOLD goedgekeurd door policy. {policy_reason}", flush=True)
        return

    if not policy_engine.should_execute_live():
        print(f"Magnolia: DRY RUN — {action} niet uitgevoerd. {policy_reason}", flush=True)
        policy_engine.record_trade_event({
            "agent_action": action,
            "status": "dry_run",
            "reason": policy_reason,
            "decision": decision,
            "portfolio_usd": context.get("aladdin", {}).get("portfolio_usd", 0),
        })
        return

    if action == "SWAP":
        params = decision.get("params", {})
        try:
            amount_sol = float(params.get('amount_sol', 0.01))
        except (ValueError, TypeError):
            amount_sol = 0.01

        amount_units = int(params.get("amount_units") or int(min(amount_sol, config.MAX_TRADE_SOL) * 1_000_000_000))
        target_from = params.get('from', config.SOL_MINT)
        target_to = params.get('to', config.USDC_MINT)
        amount_label = params.get("amount_source", amount_sol)
            
        swap_params = {
            "from": target_from,
            "to": target_to,
            "amount_lamports": amount_units
        }
        
        is_approved, reason = paperclip_optimizer.evaluate_trade(swap_params, context.get("sol_balance", 0))
        
        if is_approved:
            print(f"🔄 Magnolia: LIVE SWAP gestart ({amount_label} {config.ALLOWED_TRADE_MINTS.get(target_from, target_from)})...", flush=True)
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
                        hermes_logger.log_action("Magnolia", "god_mode_trade", f"Magnolia Oracle trade succesvol: {amount_sol} {target_from[:4]} -> {target_to[:4]}. Sig: {sig}")
                        policy_engine.record_trade_event({
                            "agent_action": action,
                            "status": "executed",
                            "signature": sig,
                            "from": target_from,
                            "to": target_to,
                            "amount_sol": amount_sol,
                            "amount_source": amount_label,
                            "amount_units": amount_units,
                            "decision": decision,
                        })
                    else:
                        print("🚨 PEV FAILED: Target balans onveranderd of 0 na executie.", flush=True)
                        fleet_orchestrator.paperclip.remember(f"FAILED SWAP: PEV Protocol getriggerd. Balans bleef leeg na swap {sig}.")
                        hermes_logger.log_action("Magnolia", "god_mode_trade_failed", f"PEV FAILED. Geen tokens ontvangen voor sig: {sig}")
                        policy_engine.record_trade_event({
                            "agent_action": action,
                            "status": "failed",
                            "signature": sig,
                            "reason": "PEV target balance check failed",
                            "decision": decision,
                        })
                        
                        # Hard stop op de huidige executie-thread
                        print("🛑 PEV Protocol blokkeert verdere acties. Systeem wacht op handmatig groen licht.", flush=True)
                        sys.exit(1)
            except Exception as e:
                print(f"⚠️ Executiefout: {e}.", flush=True)
                policy_engine.record_trade_event({
                    "agent_action": action,
                    "status": "failed",
                    "reason": str(e),
                    "decision": decision,
                })
        else:
            print(f"🛑 Paperclip Veto: {reason}", flush=True)
            policy_engine.record_trade_event({
                "agent_action": action,
                "status": "blocked",
                "reason": reason,
                "decision": decision,
            })

    elif action == "DEPOSIT_KAMINO":
        try:
            result = kamino_vault.deposit_usdc(config.DEPOSIT_THRESHOLD_USDC)
            if result:
                policy_engine.record_trade_event({
                    "agent_action": action,
                    "status": "executed",
                    "signature": result,
                    "amount_usdc": config.DEPOSIT_THRESHOLD_USDC,
                    "decision": decision,
                })
            else:
                policy_engine.record_trade_event({
                    "agent_action": action,
                    "status": "failed",
                    "reason": "Kamino deposit returned no signature",
                    "decision": decision,
                })
        except Exception as e:
            print(f"⚠️ Kamino executiefout: {e}.", flush=True)
            policy_engine.record_trade_event({
                "agent_action": action,
                "status": "failed",
                "reason": str(e),
                "decision": decision,
            })

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


def run_oracle_loop():
    import daily_report
    iteration = 0
    print(f"Magnolia Oracle gestart — {time.strftime('%Y-%m-%d %H:%M')}", flush=True)

    while True:
        print("\n" + "="*45, flush=True)
        print("--- MAGNOLIA ORACLE — GUARDIAN + BANKER + FARMER ---", flush=True)
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
                        oracle_airdrop_ev_score=oracle.get("airdrop_ev_score"),
                        daily_pnl_usd=context.get("aladdin", {}).get("daily_pnl_usd", 0),
                    )

                # Dagelijks rapport om 07:00
                if _should_send_report():
                    print("Magnolia: Dagelijks rapport versturen...", flush=True)
                    daily_report.send_report()

                if iteration % 5 == 0:
                    aladdin = context.get("aladdin", {})
                    hermes_logger.log_action(
                        "Magnolia", "system_check",
                        f"Online. Portfolio ${aladdin.get('portfolio_usd', 0):.2f} | P&L ${aladdin.get('daily_pnl_usd', 0):+.4f}",
                        status="active",
                    )

                decision = analyze_and_decide(context)
                if decision:
                    execute_decision(decision, context)
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
    run_oracle_loop()
