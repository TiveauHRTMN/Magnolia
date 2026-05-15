import os
from dotenv import load_dotenv

# Laad de .env file vanuit de huidige map
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# API Keys
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
HELIUS_RPC_URL = os.getenv("HELIUS_RPC_URL")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
REPORT_TO = os.getenv("REPORT_TO", "rwnhrtmn@gmail.com")

# Mints
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SOL_MINT = "So11111111111111111111111111111111111111112"

# Strategy Settings (God Mode)
MIN_SOL_RESERVE = 0.010 # Verlaagd naar 0.010 op verzoek voor maximale handelsvrijheid
MAX_TRADE_SOL = 0.1 # Maximale blootstelling per enkele trade
AGGRESSIVE_MAX_TRADE_SOL = float(os.getenv("AGGRESSIVE_MAX_TRADE_SOL", "0.075"))
BALANCED_MAX_TRADE_SOL = float(os.getenv("BALANCED_MAX_TRADE_SOL", "0.035"))
DEFENSIVE_MAX_TRADE_SOL = float(os.getenv("DEFENSIVE_MAX_TRADE_SOL", "0.015"))
BEARISH_MAX_TRADE_SOL = float(os.getenv("BEARISH_MAX_TRADE_SOL", "0.02"))
DEPOSIT_THRESHOLD_USDC = 2.0 # Minder snel vastzetten in yield, houd liquide voor trading

# Execution Controls
MAGNOLIA_MODE = os.getenv("MAGNOLIA_MODE", "live").lower()  # dry_run | live
ORACLE_DIRECT_ACTIONS = os.getenv("ORACLE_DIRECT_ACTIONS", "false").lower() == "true"
POLYMARKET_TRADING_ENABLED = os.getenv("POLYMARKET_TRADING_ENABLED", "false").lower() == "true"
POLYMARKET_DATA_MODE = os.getenv("POLYMARKET_DATA_MODE", "read_only").lower()  # disabled | read_only
MAX_DAILY_TRADES = int(os.getenv("MAX_DAILY_TRADES", "3"))
MAX_DAILY_LOSS_USD = float(os.getenv("MAX_DAILY_LOSS_USD", "1.0"))
MAX_PRICE_IMPACT_PCT = float(os.getenv("MAX_PRICE_IMPACT_PCT", "0.75"))
MIN_LIQUIDITY_USD = float(os.getenv("MIN_LIQUIDITY_USD", "50000"))
MIN_ORACLE_CONFIDENCE_FOR_TRADE = int(os.getenv("MIN_ORACLE_CONFIDENCE_FOR_TRADE", "60"))
ORACLE_MAX_EXECUTION_AGE_HOURS = float(os.getenv("ORACLE_MAX_EXECUTION_AGE_HOURS", "4"))
ORACLE_MAX_PRICE_DRIFT_PCT = float(os.getenv("ORACLE_MAX_PRICE_DRIFT_PCT", "3.0"))
AIRDROP_WEEKLY_BUDGET_USD = float(os.getenv("AIRDROP_WEEKLY_BUDGET_USD", "0.60"))
AIRDROP_MIN_EV_SCORE_FOR_EXTRA_SPEND = int(os.getenv("AIRDROP_MIN_EV_SCORE_FOR_EXTRA_SPEND", "80"))
AIRDROP_MAX_DAILY_LOSS_USD = float(os.getenv("AIRDROP_MAX_DAILY_LOSS_USD", "0.25"))
PAUSE_FILE = os.path.join(os.path.dirname(__file__), ".magnolia_pause")
ORACLE_DAILY_RUN_HOUR = int(os.getenv("ORACLE_DAILY_RUN_HOUR", "9"))

JITOSOL_MINT = "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn"
JLP_MINT = "27G8MtK7VtTcCHkpASjSDdkWWYfoqT6ggEuKidVJidD4"
ALLOWED_TRADE_MINTS = {
    SOL_MINT: "SOL",
    USDC_MINT: "USDC",
    JITOSOL_MINT: "JitoSOL",
    JLP_MINT: "JLP",
}
TOKEN_DECIMALS = {
    SOL_MINT: 9,
    USDC_MINT: 6,
    JITOSOL_MINT: 9,
    JLP_MINT: 6,
}

# Model Settings — alles via OpenRouter
OPENROUTER_MODEL = "nousresearch/hermes-4-70b"   # Hermes 4 70B — dagelijkse besluitvorming
DEEPSEEK_FLASH_MODEL = "deepseek/deepseek-v4-flash"  # DeepSeek V4 Flash — snelle fallback
DEEPSEEK_PRO_MODEL = "deepseek/deepseek-v4-pro"      # DeepSeek V4 Pro — Oracle fallback
ORACLE_MODEL = "openai/gpt-5.5-pro"                   # GPT-5.5 Pro — eenmalige ochtendvoorspelling
ORACLE_REASONING_EFFORT = "xhigh"
ORACLE_CONFIDENCE_THRESHOLD = 70                      # Min. confidence voor directe actie
ORACLE_EMAIL_ENABLED = os.getenv("ORACLE_EMAIL_ENABLED", "true").lower() == "true"
