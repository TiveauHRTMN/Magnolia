"""
The Oracle — Dagelijkse macro-voorspelling voor het Magnolia Syndicaat.
Draait eenmaal per ochtend. Gebruikt Opus 4.7 via OpenRouter.
Slaat voorspelling op in oracle_cache.json (TTL: 20 uur).
"""
import os
import json
import httpx
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

import config
import kiloclaw_scraper
import guardian_jito
import banker_jlp

CACHE_FILE = os.path.join(os.path.dirname(__file__), "oracle_cache.json")
CACHE_TTL_HOURS = 20


def is_cache_fresh():
    if not os.path.exists(CACHE_FILE):
        return False
    try:
        with open(CACHE_FILE) as f:
            cache = json.load(f)
        saved_at = datetime.fromisoformat(cache.get("saved_at", "2000-01-01"))
        age_hours = (datetime.now() - saved_at).total_seconds() / 3600
        return age_hours < CACHE_TTL_HOURS
    except Exception:
        return False


def load_cache():
    with open(CACHE_FILE) as f:
        return json.load(f)


def gather_oracle_inputs():
    print("The Oracle: marktdata verzamelen...", flush=True)
    sol_data = kiloclaw_scraper.claw_market_data(config.SOL_MINT)
    trending = kiloclaw_scraper.scan_trending_pairs()
    jito = guardian_jito.get_jito_yield()
    jlp = banker_jlp.get_jlp_yield()

    return {
        "sol_market": sol_data,
        "trending_pairs": trending[:10] if trending else [],
        "jito_yield": jito,
        "jlp_yield": jlp,
        "analysis_date": datetime.now().strftime("%Y-%m-%d"),
        "analysis_time_utc": datetime.now(timezone.utc).strftime("%H:%M UTC"),
    }


def run_oracle():
    if is_cache_fresh():
        print("The Oracle: vandaag al actief geweest — cache geladen.", flush=True)
        return load_cache()

    print("The Oracle: Activeren... Opus 4.7 consulteren...", flush=True)
    inputs = gather_oracle_inputs()

    prompt = f"""
Je bent The Oracle — het strategische brein van het Magnolia Syndicaat.
Vandaag is het {inputs['analysis_date']}, {inputs['analysis_time_utc']}.

Marktdata:
{json.dumps(inputs, indent=2)}

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
    "confidence": 75,
    "sol_thesis": "Max 2 zinnen over SOL-richting vandaag.",
    "risk_level": "MEDIUM",
    "hermes_directive": "Timing en aanpak voor swaps: wanneer wachten, wanneer ingrijpen.",
    "airdrop_targets": ["Jupiter", "Sanctum", "Kamino"],
    "key_catalysts": ["catalyst 1", "catalyst 2"],
    "high_conviction_sectors": ["sector1"],
    "avoid_sectors": ["sector1"],
    "blacklist_tokens": [],
    "oracle_summary": "Max 3 zinnen totaalvisie voor vandaag."
}}

macro_sentiment: "BULLISH" | "BEARISH" | "NEUTRAL"
risk_level: "LOW" | "MEDIUM" | "HIGH"
airdrop_targets: geordende lijst van ["Jupiter", "Sanctum", "Kamino"] — zet vandaag meest kansrijke protocol vooraan
"""

    content = None

    if config.OPENROUTER_API_KEY:
        try:
            print(f"The Oracle: {config.ORACLE_MODEL} via OpenRouter consulteren...", flush=True)
            with httpx.Client(timeout=90.0) as client:
                res = client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                        "HTTP-Referer": "https://magnolia-syndicate.local",
                        "X-Title": "Magnolia Oracle",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": config.ORACLE_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"},
                    },
                )
                res.raise_for_status()
                content = res.json()["choices"][0]["message"]["content"]
                print("The Oracle: Opus 4.7 antwoord ontvangen.", flush=True)
        except Exception as e:
            print(f"Oracle: Opus gefaald ({e}). Fallback naar DeepSeek V4 Pro...", flush=True)

    if not content and config.OPENROUTER_API_KEY:
        try:
            print(f"The Oracle: {config.DEEPSEEK_PRO_MODEL} fallback via OpenRouter...", flush=True)
            with httpx.Client(timeout=90.0) as client:
                res = client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                        "HTTP-Referer": "https://magnolia-syndicate.local",
                        "X-Title": "Magnolia Oracle Fallback",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": config.DEEPSEEK_PRO_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"},
                    },
                )
                res.raise_for_status()
                content = res.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"Oracle: Ook DeepSeek V4 Pro gefaald: {e}", flush=True)
            return None

    if not content:
        return None

    try:
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        prediction = json.loads(content)
    except Exception as e:
        print(f"Oracle: JSON parse fout: {e}\nContent: {content[:300]}", flush=True)
        return None

    prediction["saved_at"] = datetime.now().isoformat()
    prediction["model_used"] = config.ORACLE_MODEL

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(prediction, f, indent=2, ensure_ascii=False)

    print(
        f"The Oracle: Voorspelling opgeslagen. "
        f"Sentiment: {prediction.get('macro_sentiment')} | "
        f"Confidence: {prediction.get('confidence')}% | "
        f"Risico: {prediction.get('risk_level')}",
        flush=True,
    )

    execute_oracle_action(prediction)
    return prediction


def execute_oracle_action(prediction):
    """
    Directe actie op basis van Oracle-oordeel.
    Wordt alleen aangeroepen bij een verse voorspelling, niet vanuit cache.
    """
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
        print("     THE ORACLE — DAGELIJKSE BRIEFING")
        print("=" * 55)
        print(f"Datum       : {result.get('date')}")
        print(f"Sentiment   : {result.get('macro_sentiment')} ({result.get('confidence')}% confidence)")
        print(f"Risico      : {result.get('risk_level')}")
        print(f"Model       : {result.get('model_used')}")
        print(f"\nSOL thesis  : {result.get('sol_thesis')}")
        print(f"Hermes      : {result.get('hermes_directive')}")
        print(f"Farmer      : {', '.join(result.get('airdrop_targets', []))}")
        print(f"\nSectoren OK : {', '.join(result.get('high_conviction_sectors', []))}")
        print(f"Vermijden   : {', '.join(result.get('avoid_sectors', []))}")
        print(f"Catalysts   : {', '.join(result.get('key_catalysts', []))}")
        print(f"\nVisie       : {result.get('oracle_summary')}")
        print("=" * 55)
