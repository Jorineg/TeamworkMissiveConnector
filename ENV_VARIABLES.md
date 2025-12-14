# Environment Variables Reference

This document provides a comprehensive list of all environment variables used by the Teamwork & Missive Connector.

## Quick Reference Table

| Variable | Required? | Default | Purpose | Details |
|----------|-----------|---------|---------|---------|
| [`TEAMWORK_BASE_URL`](#teamwork_base_url) | ✅ Yes | - | Teamwork instance URL | [↓](#teamwork_base_url) |
| [`TEAMWORK_API_KEY`](#teamwork_api_key) | ✅ Yes | - | Teamwork authentication | [↓](#teamwork_api_key) |
| [`TEAMWORK_WEBHOOK_SECRET`](#teamwork_webhook_secret) | ❌ No | Empty | Webhook signature validation | [↓](#teamwork_webhook_secret) |
| [`TEAMWORK_PROCESS_AFTER`](#teamwork_process_after) | ❌ No | None | Filter tasks by created date | [↓](#teamwork_process_after) |
| [`INCLUDE_COMPLETED_TASKS_ON_INITIAL_SYNC`](#include_completed_tasks_on_initial_sync) | ❌ No | `true` | Include completed tasks on initial sync | [↓](#include_completed_tasks_on_initial_sync) |
| [`MISSIVE_API_TOKEN`](#missive_api_token) | ✅ Yes | - | Missive authentication | [↓](#missive_api_token) |
| [`MISSIVE_WEBHOOK_SECRET`](#missive_webhook_secret) | ❌ No | Empty | Webhook signature validation | [↓](#missive_webhook_secret) |
| [`MISSIVE_PROCESS_AFTER`](#missive_process_after) | ❌ No | None | Filter emails by received date | [↓](#missive_process_after) |
| [`CRAFT_BASE_URL`](#craft_base_url) | ❌ No | - | Craft Multi-Document API URL | [↓](#craft_base_url) |
| [`PG_DSN`](#pg_dsn) | ✅ Yes | - | PostgreSQL connection | [↓](#pg_dsn) |
| [`NGROK_AUTHTOKEN`](#ngrok_authtoken) | ⚠️ If webhooks | - | ngrok tunnel (local dev) | [↓](#ngrok_authtoken) |
| [`DISABLE_WEBHOOKS`](#disable_webhooks) | ❌ No | `false` | Enable/disable webhooks | [↓](#disable_webhooks) |
| [`APP_PORT`](#app_port) | ❌ No | `5000` | Flask application port | [↓](#app_port) |
| [`LOG_LEVEL`](#log_level) | ❌ No | `INFO` | Logging verbosity | [↓](#log_level) |
| [`TIMEZONE`](#timezone) | ❌ No | `Europe/Berlin` | Timestamp timezone | [↓](#timezone) |
| [`BETTERSTACK_SOURCE_TOKEN`](#betterstack_source_token) | ❌ No | - | Betterstack cloud logging | [↓](#betterstack_source_token) |
| [`BETTERSTACK_INGEST_HOST`](#betterstack_ingest_host) | ❌ No | - | Custom Betterstack host | [↓](#betterstack_ingest_host) |
| [`PERIODIC_BACKFILL_INTERVAL`](#periodic_backfill_interval) | ❌ No | `5`/`60` | Polling interval (seconds) | [↓](#periodic_backfill_interval) |
| [`BACKFILL_OVERLAP_SECONDS`](#backfill_overlap_seconds) | ❌ No | `120` | Checkpoint overlap window | [↓](#backfill_overlap_seconds) |
| [`MAX_QUEUE_ATTEMPTS`](#max_queue_attempts) | ❌ No | `3` | Max retry attempts | [↓](#max_queue_attempts) |

**Legend:**
- ✅ Always required
- ⚠️ Conditionally required
- ❌ Optional

---

## Required Variables

### `TEAMWORK_BASE_URL`
- **Description**: Your Teamwork installation URL
- **Format**: URL without trailing slash
- **Example**: `https://yourcompany.teamwork.com`

### `TEAMWORK_API_KEY`
- **Description**: API key for Teamwork authentication
- **Format**: String
- **Example**: `twp_abc123xyz...`
- **How to get**: Teamwork → Settings → API & Webhooks → API Key

### `MISSIVE_API_TOKEN`
- **Description**: API token for Missive authentication
- **Format**: String (long alphanumeric)
- **Example**: `abc123xyz456...`
- **How to get**: Missive → Settings → API → Create Token

### `PG_DSN`
- **Description**: PostgreSQL connection string
- **Format**: PostgreSQL connection URI
- **Example**: `postgresql://username:password@localhost:5432/teamwork_missive`
- **Components**:
  - `username`: PostgreSQL user
  - `password`: User's password
  - `localhost:5432`: Host and port
  - `teamwork_missive`: Database name

---

## Optional Variables

### Application Settings

#### `APP_PORT`
- **Description**: Port number for the Flask application
- **Default**: `5000`
- **Example**: `8080`

#### `LOG_LEVEL`
- **Description**: Logging verbosity level
- **Default**: `INFO`
- **Options**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

#### `TIMEZONE`
- **Description**: IANA timezone name for timestamp display
- **Default**: `Europe/Berlin`
- **Examples**: `America/New_York`, `Asia/Tokyo`, `UTC`

#### `BETTERSTACK_SOURCE_TOKEN`
- **Description**: Source token for Betterstack cloud logging
- **Default**: Not set (logging disabled)
- **How to get**: https://logs.betterstack.com/ → Settings → Sources → Create Source

#### `BETTERSTACK_INGEST_HOST`
- **Description**: Custom ingestion host for Betterstack
- **Default**: Not set (uses `in.logs.betterstack.com`)

### Webhook Settings

#### `NGROK_AUTHTOKEN`
- **Description**: Authentication token for ngrok tunnel (local development)
- **Required for**: Webhook mode in local development
- **How to get**: https://dashboard.ngrok.com/get-started/your-authtoken
- **Not needed**: When using `DISABLE_WEBHOOKS=true`

#### `TEAMWORK_WEBHOOK_SECRET`
- **Description**: Secret for validating Teamwork webhook signatures
- **Default**: Empty (no validation)

#### `MISSIVE_WEBHOOK_SECRET`
- **Description**: Secret for validating Missive webhook signatures
- **Default**: Empty (no validation)

#### `DISABLE_WEBHOOKS`
- **Description**: Switch to polling-only mode
- **Default**: `false`
- **Options**: `true`, `false`, `1`, `0`, `yes`, `no`
- **Effect**:
  - `true`: No webhooks, frequent polling (default 5s interval)
  - `false`: Webhooks enabled with backup polling (default 60s interval)

### Craft Settings

#### `CRAFT_BASE_URL`
- **Description**: Base URL for the Craft Multi-Document API
- **Default**: Not set (Craft integration disabled)
- **Format**: URL (without trailing slash)
- **Example**: `https://connect.craft.do/links/FLzEdbunAos/api/v1`
- **Note**: Craft doesn't support webhooks, uses polling

### Backfill & Polling Settings

#### `PERIODIC_BACKFILL_INTERVAL`
- **Description**: Interval in seconds for periodic polling/backfill
- **Default**:
  - `5` when `DISABLE_WEBHOOKS=true`
  - `60` when `DISABLE_WEBHOOKS=false`
- **Considerations**:
  - Lower values = More real-time, more API calls
  - Higher values = Fewer API calls, slower updates

#### `BACKFILL_OVERLAP_SECONDS`
- **Description**: Time overlap window when fetching updates
- **Default**: `120` (2 minutes)
- **Purpose**: Prevents missed events due to clock skew

### Database Resilience Settings

#### `DB_CONNECT_TIMEOUT`
- **Description**: Connection timeout in seconds
- **Default**: `10`

#### `DB_RECONNECT_DELAY`
- **Description**: Initial delay between reconnect attempts
- **Default**: `5`

#### `DB_MAX_RECONNECT_DELAY`
- **Description**: Maximum delay with exponential backoff
- **Default**: `60`

#### `DB_OPERATION_RETRIES`
- **Description**: Retries for individual database operations
- **Default**: `3`

### Queue Settings

#### `MAX_QUEUE_ATTEMPTS`
- **Description**: Maximum retry attempts for failed queue items
- **Default**: `3`

#### `SPOOL_RETRY_SECONDS`
- **Description**: Wait time before retrying failed items
- **Default**: `60`

---

## Date Filtering

Filter old data from being synced.

### `TEAMWORK_PROCESS_AFTER`
- **Description**: Only process tasks created on or after this date
- **Default**: Not set (process all)
- **Format**: `DD.MM.YYYY`
- **Example**: `01.01.2020`
- **Behavior**: Tasks created before this date are skipped

### `INCLUDE_COMPLETED_TASKS_ON_INITIAL_SYNC`
- **Description**: Include completed tasks during initial sync
- **Default**: `true`
- **Format**: Boolean
- **Note**: Subsequent syncs always include completed tasks

### `MISSIVE_PROCESS_AFTER`
- **Description**: Only process emails received on or after this date
- **Default**: Not set (last 30 days on first run)
- **Format**: `DD.MM.YYYY`
- **Example**: `01.01.2020`

---

## Example Configurations

### Minimal Setup (Webhook Mode)
```env
TEAMWORK_BASE_URL=https://yourcompany.teamwork.com
TEAMWORK_API_KEY=your_key_here
MISSIVE_API_TOKEN=your_token_here
PG_DSN=postgresql://user:pass@localhost:5432/database
NGROK_AUTHTOKEN=your_token_here
```

### Minimal Setup (Polling-Only Mode)
```env
TEAMWORK_BASE_URL=https://yourcompany.teamwork.com
TEAMWORK_API_KEY=your_key_here
MISSIVE_API_TOKEN=your_token_here
PG_DSN=postgresql://user:pass@localhost:5432/database
DISABLE_WEBHOOKS=true
```

### Production Setup
```env
TEAMWORK_BASE_URL=https://yourcompany.teamwork.com
TEAMWORK_API_KEY=your_key_here
MISSIVE_API_TOKEN=your_token_here
PG_DSN=postgresql://user:pass@localhost:5432/database

# Optional integrations
CRAFT_BASE_URL=https://connect.craft.do/links/YOUR_LINK_ID/api/v1

# Settings
TIMEZONE=America/New_York
LOG_LEVEL=INFO
PERIODIC_BACKFILL_INTERVAL=60

# Cloud logging
BETTERSTACK_SOURCE_TOKEN=your_betterstack_token_here
```

### Setup with Date Filtering
```env
TEAMWORK_BASE_URL=https://yourcompany.teamwork.com
TEAMWORK_API_KEY=your_key_here
MISSIVE_API_TOKEN=your_token_here
PG_DSN=postgresql://user:pass@localhost:5432/database

# Only sync data from 2020 onwards
TEAMWORK_PROCESS_AFTER=01.01.2020
MISSIVE_PROCESS_AFTER=01.01.2020

# Only sync active tasks on initial sync
INCLUDE_COMPLETED_TASKS_ON_INITIAL_SYNC=false

DISABLE_WEBHOOKS=true
```

---

## Troubleshooting

### Invalid Date Format Error
- Ensure format is exactly `DD.MM.YYYY`
- Use leading zeros: `01.01.2020` not `1.1.2020`
- Use dots (`.`), not slashes or dashes

### Webhooks Not Working
1. Check `NGROK_AUTHTOKEN` is set
2. Verify ngrok tunnel is running
3. Consider using `DISABLE_WEBHOOKS=true`

### Database Connection Issues
- Verify `PG_DSN` format and credentials
- Check logs for specific error messages

---

## See Also

- [README.md](README.md) - Project overview and quick start
- [SETUP.md](SETUP.md) - Detailed setup instructions
- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical architecture details
