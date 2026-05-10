import os
from dotenv import load_dotenv

# Laad de .env file vanuit de huidige map
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# API Keys
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
HELIUS_RPC_URL = os.getenv("HELIUS_RPC_URL")

# Mints
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SOL_MINT = "So11111111111111111111111111111111111111112"

# Strategy Settings (God Mode)
MIN_SOL_RESERVE = 0.010 # Verlaagd naar 0.010 op verzoek voor maximale handelsvrijheid
MAX_TRADE_SOL = 0.1 # Maximale blootstelling per enkele trade
DEPOSIT_THRESHOLD_USDC = 2.0 # Minder snel vastzetten in yield, houd liquide voor trading

# Model Settings — alles via OpenRouter
OPENROUTER_MODEL = "nousresearch/hermes-4-70b"   # Hermes 4 70B — dagelijkse besluitvorming
DEEPSEEK_FLASH_MODEL = "deepseek/deepseek-v4-flash"  # DeepSeek V4 Flash — snelle fallback
DEEPSEEK_PRO_MODEL = "deepseek/deepseek-v4-pro"      # DeepSeek V4 Pro — Oracle fallback
ORACLE_MODEL = "anthropic/claude-opus-4.7"            # Opus 4.7 — eenmalige ochtendvoorspelling
ORACLE_CONFIDENCE_THRESHOLD = 70                      # Min. confidence voor directe actie
