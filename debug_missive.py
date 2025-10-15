"""Debug script for Missive API issue."""
from datetime import datetime, timezone, timedelta
from src.connectors.missive_client import MissiveClient

# Create client
client = MissiveClient()

# Test with a more reasonable time (e.g., last 7 days)
now = datetime.now(tz=timezone.utc)
seven_days_ago = now - timedelta(days=7)

print(f"Testing with timestamp: {seven_days_ago}")
print(f"Unix timestamp: {int(seven_days_ago.timestamp())}")
print(f"Current time: {now}")

# Make the request
print("\nMaking request...")
conversations = client.get_conversations_updated_since(seven_days_ago)
print(f"Got {len(conversations)} conversations")

if conversations:
    print("\nFirst conversation:")
    first = conversations[0]
    print(f"  ID: {first.get('id')}")
    print(f"  Subject: {first.get('latest_message_subject')}")
    print(f"  Last activity: {datetime.fromtimestamp(first.get('last_activity_at', 0), tz=timezone.utc)}")

