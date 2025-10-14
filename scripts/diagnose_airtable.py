"""Diagnostic script to check Airtable configuration and permissions."""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

import requests
from src import settings
from src.logging_conf import logger


def check_airtable_config():
    """Check Airtable configuration and permissions."""
    
    print("\n" + "="*60)
    print("AIRTABLE CONFIGURATION DIAGNOSTIC")
    print("="*60)
    
    # Check environment variables
    print("\n1. Checking environment variables...")
    if not settings.AIRTABLE_API_KEY:
        print("   ✗ AIRTABLE_API_KEY is not set")
        return False
    else:
        print(f"   ✓ AIRTABLE_API_KEY is set (length: {len(settings.AIRTABLE_API_KEY)})")
    
    if not settings.AIRTABLE_BASE_ID:
        print("   ✗ AIRTABLE_BASE_ID is not set")
        return False
    else:
        print(f"   ✓ AIRTABLE_BASE_ID: {settings.AIRTABLE_BASE_ID}")
    
    print(f"   ✓ AIRTABLE_EMAILS_TABLE: {settings.AIRTABLE_EMAILS_TABLE}")
    print(f"   ✓ AIRTABLE_TASKS_TABLE: {settings.AIRTABLE_TASKS_TABLE}")
    
    # Check API key format
    print("\n2. Checking API key format...")
    if settings.AIRTABLE_API_KEY.startswith("pat"):
        print("   ✓ Using Personal Access Token (recommended)")
    elif settings.AIRTABLE_API_KEY.startswith("key"):
        print("   ⚠ Using deprecated API key format - consider upgrading to Personal Access Token")
    else:
        print("   ✗ Unknown API key format")
    
    # Test API connection
    print("\n3. Testing API connection...")
    headers = {
        "Authorization": f"Bearer {settings.AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        # Try to get base schema (requires schema.bases:read scope)
        url = f"https://api.airtable.com/v0/meta/bases/{settings.AIRTABLE_BASE_ID}/tables"
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            print("   ✓ API connection successful")
            data = response.json()
            tables = data.get("tables", [])
            
            print(f"\n4. Found {len(tables)} table(s) in base:")
            table_names = []
            for table in tables:
                table_name = table.get("name", "Unknown")
                table_id = table.get("id", "Unknown")
                table_names.append(table_name)
                print(f"      - {table_name} (ID: {table_id})")
            
            # Check if our tables exist
            print("\n5. Checking configured tables...")
            if settings.AIRTABLE_EMAILS_TABLE in table_names:
                print(f"   ✓ '{settings.AIRTABLE_EMAILS_TABLE}' table exists")
            else:
                print(f"   ✗ '{settings.AIRTABLE_EMAILS_TABLE}' table NOT FOUND")
                print(f"      Available tables: {', '.join(table_names)}")
            
            if settings.AIRTABLE_TASKS_TABLE in table_names:
                print(f"   ✓ '{settings.AIRTABLE_TASKS_TABLE}' table exists")
            else:
                print(f"   ✗ '{settings.AIRTABLE_TASKS_TABLE}' table NOT FOUND")
                print(f"      Available tables: {', '.join(table_names)}")
            
            # Test reading from Tasks table
            print("\n6. Testing read access to Tasks table...")
            try:
                test_url = f"https://api.airtable.com/v0/{settings.AIRTABLE_BASE_ID}/{settings.AIRTABLE_TASKS_TABLE}"
                test_response = requests.get(test_url, headers=headers, params={"maxRecords": 1}, timeout=10)
                
                if test_response.status_code == 200:
                    print("   ✓ Read access to Tasks table successful")
                else:
                    print(f"   ✗ Read access failed: {test_response.status_code} - {test_response.text}")
            except Exception as e:
                print(f"   ✗ Read access test failed: {e}")
            
            return True
            
        elif response.status_code == 401:
            print("   ✗ Authentication failed - invalid API key")
            print(f"      Response: {response.text}")
            return False
        elif response.status_code == 403:
            print("   ✗ Access forbidden - API key lacks required permissions")
            print(f"      Response: {response.text}")
            print("\n   Required scopes for Personal Access Token:")
            print("      - schema.bases:read (to list tables)")
            print("      - data.records:read (to read records)")
            print("      - data.records:write (to create/update records)")
            return False
        elif response.status_code == 404:
            print("   ✗ Base not found - check AIRTABLE_BASE_ID")
            print(f"      Base ID: {settings.AIRTABLE_BASE_ID}")
            return False
        else:
            print(f"   ✗ Unexpected response: {response.status_code}")
            print(f"      Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("   ✗ Request timed out")
        return False
    except requests.exceptions.RequestException as e:
        print(f"   ✗ Network error: {e}")
        return False
    except Exception as e:
        print(f"   ✗ Unexpected error: {e}")
        return False


def suggest_fixes():
    """Suggest how to fix common issues."""
    print("\n" + "="*60)
    print("TROUBLESHOOTING STEPS")
    print("="*60)
    print("""
If you're seeing 403 Forbidden errors, try these steps:

1. CREATE A NEW PERSONAL ACCESS TOKEN (PAT):
   - Go to https://airtable.com/create/tokens
   - Click "Create new token"
   - Give it a name (e.g., "Teamwork Connector")
   - Add the following scopes:
     * data.records:read
     * data.records:write
     * schema.bases:read (optional, for diagnostics)
   - Add access to your specific base
   - Copy the token and update your .env file

2. UPDATE YOUR .env FILE:
   - Set AIRTABLE_API_KEY=pat...your_token...
   - Verify AIRTABLE_BASE_ID matches your base
   - Ensure AIRTABLE_EMAILS_TABLE and AIRTABLE_TASKS_TABLE
     match the exact table names in Airtable (case-sensitive!)

3. IF TABLES DON'T EXIST:
   - Run: python scripts/setup_airtable_tables.py
   - Or manually create tables in Airtable with these names:
     * {emails_table}
     * {tasks_table}

4. RESTART THE APPLICATION after updating .env
""".format(
        emails_table=settings.AIRTABLE_EMAILS_TABLE,
        tasks_table=settings.AIRTABLE_TASKS_TABLE
    ))


if __name__ == "__main__":
    success = check_airtable_config()
    
    if not success:
        suggest_fixes()
        print("\n" + "="*60)
        print("RESULT: Configuration issues found")
        print("="*60 + "\n")
        sys.exit(1)
    else:
        print("\n" + "="*60)
        print("RESULT: Configuration looks good!")
        print("="*60 + "\n")
        sys.exit(0)

