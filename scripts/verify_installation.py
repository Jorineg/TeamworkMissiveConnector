#!/usr/bin/env python3
"""Verify that the installation is complete and all files are present."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'


def check_file(path: Path, required: bool = True) -> bool:
    """Check if a file exists."""
    if path.exists():
        print(f"  {GREEN}✓{RESET} {path}")
        return True
    else:
        if required:
            print(f"  {RED}✗{RESET} {path} (MISSING)")
        else:
            print(f"  {YELLOW}○{RESET} {path} (optional, not found)")
        return not required


def check_directory(path: Path) -> bool:
    """Check if a directory exists."""
    if path.exists():
        print(f"  {GREEN}✓{RESET} {path}/")
        return True
    else:
        print(f"  {RED}✗{RESET} {path}/ (MISSING)")
        return False


def main():
    project_root = Path(__file__).parent.parent
    print(f"\nVerifying installation in: {project_root}\n")
    print("=" * 70)
    
    all_ok = True
    
    # Check core Python files
    print("\n[Core Application Files]")
    all_ok &= check_file(project_root / "src" / "__init__.py")
    all_ok &= check_file(project_root / "src" / "app.py")
    all_ok &= check_file(project_root / "src" / "settings.py")
    all_ok &= check_file(project_root / "src" / "logging_conf.py")
    all_ok &= check_file(project_root / "src" / "startup.py")
    
    # Check queue module
    print("\n[Queue System]")
    all_ok &= check_directory(project_root / "src" / "queue")
    all_ok &= check_file(project_root / "src" / "queue" / "__init__.py")
    all_ok &= check_file(project_root / "src" / "queue" / "file_queue.py")
    all_ok &= check_file(project_root / "src" / "queue" / "models.py")
    
    # Check workers
    print("\n[Workers]")
    all_ok &= check_directory(project_root / "src" / "workers")
    all_ok &= check_file(project_root / "src" / "workers" / "__init__.py")
    all_ok &= check_file(project_root / "src" / "workers" / "dispatcher.py")
    all_ok &= check_directory(project_root / "src" / "workers" / "handlers")
    all_ok &= check_file(project_root / "src" / "workers" / "handlers" / "__init__.py")
    all_ok &= check_file(project_root / "src" / "workers" / "handlers" / "missive_events.py")
    all_ok &= check_file(project_root / "src" / "workers" / "handlers" / "teamwork_events.py")
    
    # Check connectors
    print("\n[API Connectors]")
    all_ok &= check_directory(project_root / "src" / "connectors")
    all_ok &= check_file(project_root / "src" / "connectors" / "__init__.py")
    all_ok &= check_file(project_root / "src" / "connectors" / "missive_client.py")
    all_ok &= check_file(project_root / "src" / "connectors" / "teamwork_client.py")
    
    # Check database
    print("\n[Database Layer]")
    all_ok &= check_directory(project_root / "src" / "db")
    all_ok &= check_file(project_root / "src" / "db" / "__init__.py")
    all_ok &= check_file(project_root / "src" / "db" / "interface.py")
    all_ok &= check_file(project_root / "src" / "db" / "models.py")
    all_ok &= check_file(project_root / "src" / "db" / "airtable_impl.py")
    all_ok &= check_file(project_root / "src" / "db" / "postgres_impl.py")
    
    # Check HTTP
    print("\n[HTTP/Webhooks]")
    all_ok &= check_directory(project_root / "src" / "http")
    all_ok &= check_file(project_root / "src" / "http" / "__init__.py")
    all_ok &= check_file(project_root / "src" / "http" / "security.py")
    
    # Check scripts
    print("\n[Scripts]")
    all_ok &= check_directory(project_root / "scripts")
    all_ok &= check_file(project_root / "scripts" / "run_local.sh")
    all_ok &= check_file(project_root / "scripts" / "run_worker_only.sh")
    all_ok &= check_file(project_root / "scripts" / "check_queue.py")
    all_ok &= check_file(project_root / "scripts" / "manual_backfill.py")
    all_ok &= check_file(project_root / "scripts" / "validate_config.py")
    all_ok &= check_file(project_root / "scripts" / "verify_installation.py")
    
    # Check documentation
    print("\n[Documentation]")
    all_ok &= check_file(project_root / "README.md")
    all_ok &= check_file(project_root / "QUICKSTART.md")
    all_ok &= check_file(project_root / "SETUP.md")
    all_ok &= check_file(project_root / "ARCHITECTURE.md")
    all_ok &= check_file(project_root / "PROJECT_SUMMARY.md")
    all_ok &= check_directory(project_root / "docs")
    all_ok &= check_file(project_root / "docs" / "api_notes.md")
    
    # Check config files
    print("\n[Configuration]")
    all_ok &= check_file(project_root / "requirements.txt")
    check_file(project_root / ".env.example")
    check_file(project_root / ".env", required=False)
    all_ok &= check_file(project_root / "LICENSE")
    
    # Check Python imports
    print("\n[Python Import Check]")
    try:
        import flask
        print(f"  {GREEN}✓{RESET} flask")
    except ImportError:
        print(f"  {RED}✗{RESET} flask (not installed)")
        all_ok = False
    
    try:
        import requests
        print(f"  {GREEN}✓{RESET} requests")
    except ImportError:
        print(f"  {RED}✗{RESET} requests (not installed)")
        all_ok = False
    
    try:
        import pyngrok
        print(f"  {GREEN}✓{RESET} pyngrok")
    except ImportError:
        print(f"  {RED}✗{RESET} pyngrok (not installed)")
        all_ok = False
    
    try:
        import pyairtable
        print(f"  {GREEN}✓{RESET} pyairtable")
    except ImportError:
        print(f"  {RED}✗{RESET} pyairtable (not installed)")
        all_ok = False
    
    try:
        import psycopg2
        print(f"  {GREEN}✓{RESET} psycopg2")
    except ImportError:
        print(f"  {RED}✗{RESET} psycopg2 (not installed)")
        all_ok = False
    
    try:
        import portalocker
        print(f"  {GREEN}✓{RESET} portalocker")
    except ImportError:
        print(f"  {RED}✗{RESET} portalocker (not installed)")
        all_ok = False
    
    try:
        from dotenv import load_dotenv
        print(f"  {GREEN}✓{RESET} python-dotenv")
    except ImportError:
        print(f"  {RED}✗{RESET} python-dotenv (not installed)")
        all_ok = False
    
    # Check Python modules can be imported
    print("\n[Module Import Check]")
    try:
        from src import settings
        print(f"  {GREEN}✓{RESET} src.settings")
    except Exception as e:
        print(f"  {RED}✗{RESET} src.settings: {e}")
        all_ok = False
    
    try:
        from src.queue.file_queue import FileQueue
        print(f"  {GREEN}✓{RESET} src.queue.file_queue")
    except Exception as e:
        print(f"  {RED}✗{RESET} src.queue.file_queue: {e}")
        all_ok = False
    
    try:
        from src.db.interface import DatabaseInterface
        print(f"  {GREEN}✓{RESET} src.db.interface")
    except Exception as e:
        print(f"  {RED}✗{RESET} src.db.interface: {e}")
        all_ok = False
    
    # Final result
    print("\n" + "=" * 70)
    if all_ok:
        print(f"\n{GREEN}[SUCCESS] Installation verification passed!{RESET}")
        print("\nNext steps:")
        print("  1. Copy .env.example to .env")
        print("  2. Configure your API keys in .env")
        print("  3. Run: python scripts/validate_config.py")
        print("  4. Run: ./scripts/run_local.sh")
        print("\nSee QUICKSTART.md for detailed instructions.")
        return 0
    else:
        print(f"\n{RED}[FAILED] Installation verification failed!{RESET}")
        print("\nPlease fix the missing files or install missing packages:")
        print("  pip install -r requirements.txt")
        return 1


if __name__ == "__main__":
    sys.exit(main())

