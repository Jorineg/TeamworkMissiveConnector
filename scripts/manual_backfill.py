#!/usr/bin/env python3
"""Script to manually trigger a backfill operation."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.startup import StartupManager
from src.logging_conf import logger


def main():
    logger.info("Starting manual backfill...")
    
    manager = StartupManager()
    
    try:
        manager.perform_backfill()
        logger.info("Backfill completed successfully")
    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        manager.cleanup()


if __name__ == "__main__":
    main()

