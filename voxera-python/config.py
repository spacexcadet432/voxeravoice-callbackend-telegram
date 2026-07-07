import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env file
load_dotenv(dotenv_path=BASE_DIR / ".env")

# API Keys and tokens
RETELL_API_KEY = os.getenv("RETELL_API_KEY", "").strip()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Polling Interval (default to 30 seconds)
try:
    POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))
except ValueError:
    POLL_INTERVAL_SECONDS = 30

# Timezone (default to Asia/Kolkata)
TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata").strip()

# Storage file location (relative to script directory)
PROCESSED_CALLS_FILE = BASE_DIR / os.getenv("PROCESSED_CALLS_FILE", "processed_calls.json")

# Start Fetch Date for filtering historical calls
from datetime import datetime
START_FETCH_DATE_RAW = os.getenv("START_FETCH_DATE", "").strip()
START_FETCH_DATE = None

if START_FETCH_DATE_RAW:
    try:
        START_FETCH_DATE = datetime.fromisoformat(START_FETCH_DATE_RAW)
        if START_FETCH_DATE.tzinfo is None:
            raise ValueError("Datetime must include timezone offset (e.g. +05:30 or Z)")
    except Exception as e:
        print(f"[ERROR] Invalid START_FETCH_DATE '{START_FETCH_DATE_RAW}': {e}. Defaulting to process all calls.")
        START_FETCH_DATE = None

# Target Agent ID for filtering calls
TARGET_AGENT_ID = os.getenv("TARGET_AGENT_ID", "").strip()

# Backward compatibility: allow TARGET_AGENT_NAME from older deployments
if not TARGET_AGENT_ID:
    TARGET_AGENT_ID = os.getenv("TARGET_AGENT_NAME", "").strip()


def validate_config() -> bool:
    """
    Validates that the essential environment variables are set.
    Prints informative messages on console.
    """
    is_valid = True
    if not RETELL_API_KEY:
        print("[WARNING] RETELL_API_KEY is not set in environment.")
        is_valid = False
    if not TELEGRAM_BOT_TOKEN:
        print("[WARNING] TELEGRAM_BOT_TOKEN is not set in environment.")
        is_valid = False
    if not TELEGRAM_CHAT_ID:
        print("[WARNING] TELEGRAM_CHAT_ID is not set in environment.")
        is_valid = False
    return is_valid
