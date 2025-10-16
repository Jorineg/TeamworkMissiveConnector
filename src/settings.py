"""Configuration management for the connector system."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
(DATA_DIR / "queue").mkdir(exist_ok=True)
(DATA_DIR / "checkpoints").mkdir(exist_ok=True)

# Application settings
APP_PORT = int(os.getenv("APP_PORT", "5000"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ngrok settings
NGROK_AUTHTOKEN = os.getenv("NGROK_AUTHTOKEN")

# Teamwork settings
TEAMWORK_BASE_URL = os.getenv("TEAMWORK_BASE_URL", "").rstrip("/")
TEAMWORK_API_KEY = os.getenv("TEAMWORK_API_KEY")
TEAMWORK_WEBHOOK_SECRET = os.getenv("TEAMWORK_WEBHOOK_SECRET", "")

# Missive settings
MISSIVE_API_TOKEN = os.getenv("MISSIVE_API_TOKEN")
MISSIVE_WEBHOOK_SECRET = os.getenv("MISSIVE_WEBHOOK_SECRET", "")
MISSIVE_BACKFILL_DAYS = int(os.getenv("MISSIVE_BACKFILL_DAYS", "30"))

# Database settings
DB_BACKEND = os.getenv("DB_BACKEND", "airtable")

# Airtable settings
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_EMAILS_TABLE = os.getenv("AIRTABLE_EMAILS_TABLE", "Emails")
AIRTABLE_TASKS_TABLE = os.getenv("AIRTABLE_TASKS_TABLE", "Tasks")

# Timezone settings
TIMEZONE = os.getenv("TIMEZONE", "Europe/Berlin")

# PostgreSQL settings
PG_DSN = os.getenv("PG_DSN")

# Queue settings
QUEUE_DIR = DATA_DIR / "queue"
CHECKPOINT_DIR = DATA_DIR / "checkpoints"
MAX_QUEUE_ATTEMPTS = int(os.getenv("MAX_QUEUE_ATTEMPTS", "3"))
BACKFILL_OVERLAP_SECONDS = int(os.getenv("BACKFILL_OVERLAP_SECONDS", "120"))

# File paths
QUEUE_INBOX_FILE = QUEUE_DIR / "inbox.jsonl"
QUEUE_OFFSET_FILE = QUEUE_DIR / "offset.json"
QUEUE_DLQ_FILE = QUEUE_DIR / "dlq.jsonl"

# Spool queue settings
SPOOL_BASE_DIR = QUEUE_DIR / "spool"
SPOOL_TEAMWORK_DIR = SPOOL_BASE_DIR / "teamwork"
SPOOL_MISSIVE_DIR = SPOOL_BASE_DIR / "missive"
SPOOL_RETRY_SECONDS = int(os.getenv("SPOOL_RETRY_SECONDS", "60"))


def validate_config():
    """Validate that required configuration is present."""
    errors = []
    
    if not TEAMWORK_BASE_URL:
        errors.append("TEAMWORK_BASE_URL is required")
    if not TEAMWORK_API_KEY:
        errors.append("TEAMWORK_API_KEY is required")
    if not MISSIVE_API_TOKEN:
        errors.append("MISSIVE_API_TOKEN is required")
    
    if DB_BACKEND == "airtable":
        if not AIRTABLE_API_KEY:
            errors.append("AIRTABLE_API_KEY is required when DB_BACKEND=airtable")
        if not AIRTABLE_BASE_ID:
            errors.append("AIRTABLE_BASE_ID is required when DB_BACKEND=airtable")
    elif DB_BACKEND == "postgres":
        if not PG_DSN:
            errors.append("PG_DSN is required when DB_BACKEND=postgres")
    else:
        errors.append(f"Invalid DB_BACKEND: {DB_BACKEND} (must be 'airtable' or 'postgres')")
    
    if errors:
        raise ValueError("Configuration errors:\n  " + "\n  ".join(errors))


if __name__ == "__main__":
    try:
        validate_config()
        print("✓ Configuration is valid")
    except ValueError as e:
        print(f"✗ {e}")

