#!/usr/bin/env python3
"""Validate configuration before running the application."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src import settings
from src.logging_conf import logger


def main():
    print("Validating configuration...")
    print("=" * 70)
    
    try:
        settings.validate_config()
        
        # Print configuration summary
        print("✓ Configuration is valid\n")
        print("Configuration Summary:")
        print("-" * 70)
        print(f"Database Backend:     {settings.DB_BACKEND}")
        print(f"App Port:             {settings.APP_PORT}")
        print(f"Log Level:            {settings.LOG_LEVEL}")
        print(f"Teamwork Base URL:    {settings.TEAMWORK_BASE_URL}")
        print(f"ngrok Configured:     {'Yes' if settings.NGROK_AUTHTOKEN else 'No'}")
        
        if settings.DB_BACKEND == "airtable":
            print(f"\nAirtable Settings:")
            print(f"  Base ID:            {settings.AIRTABLE_BASE_ID}")
            print(f"  Emails Table:       {settings.AIRTABLE_EMAILS_TABLE}")
            print(f"  Tasks Table:        {settings.AIRTABLE_TASKS_TABLE}")
        elif settings.DB_BACKEND == "postgres":
            print(f"\nPostgreSQL Settings:")
            print(f"  DSN:                {settings.PG_DSN[:30]}..." if len(settings.PG_DSN) > 30 else settings.PG_DSN)
        
        print(f"\nQueue Settings:")
        print(f"  Queue Directory:    {settings.QUEUE_DIR}")
        print(f"  Max Attempts:       {settings.MAX_QUEUE_ATTEMPTS}")
        print(f"  Overlap Window:     {settings.BACKFILL_OVERLAP_SECONDS}s")
        
        print("\n" + "=" * 70)
        print("✓ Configuration validated successfully!")
        print("You can now run the application.")
        
    except ValueError as e:
        print(f"\n✗ Configuration errors found:\n")
        print(str(e))
        print("\nPlease fix these errors in your .env file.")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

