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
| [`AIRTABLE_API_KEY`](#airtable_api_key) | ⚠️ If Airtable | - | Airtable authentication | [↓](#airtable_api_key) |
| [`AIRTABLE_BASE_ID`](#airtable_base_id) | ⚠️ If Airtable | - | Airtable base identifier | [↓](#airtable_base_id) |
| [`AIRTABLE_EMAILS_TABLE`](#airtable_emails_table) | ❌ No | `Emails` | Emails table name | [↓](#airtable_emails_table) |
| [`AIRTABLE_TASKS_TABLE`](#airtable_tasks_table) | ❌ No | `Tasks` | Tasks table name | [↓](#airtable_tasks_table) |
| [`DB_BACKEND`](#db_backend) | ❌ No | `airtable` | Database choice | [↓](#db_backend) |
| [`PG_DSN`](#pg_dsn) | ⚠️ If Postgres | - | PostgreSQL connection | [↓](#pg_dsn) |
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
| [`SPOOL_RETRY_SECONDS`](#spool_retry_seconds) | ❌ No | `60` | Retry wait time | [↓](#spool_retry_seconds) |

**Legend:**
- ✅ Always required
- ⚠️ Conditionally required
- ❌ Optional

---

## Table of Contents

- [Required Variables](#required-variables)
- [Optional Variables](#optional-variables)
- [Database Configuration](#database-configuration)
- [Queue Settings](#queue-settings)
- [Date Filtering](#date-filtering)
- [Example Configurations](#example-configurations)
- [Troubleshooting](#troubleshooting)

---

## Required Variables

These variables must be set for the connector to function:

### `TEAMWORK_BASE_URL`
- **Description**: Your Teamwork installation URL
- **Format**: URL without trailing slash
- **Example**: `https://yourcompany.teamwork.com`
- **How to get**: This is your Teamwork instance URL

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

### `AIRTABLE_API_KEY`
- **Description**: Personal Access Token for Airtable (when using Airtable as database)
- **Format**: String starting with `pat`
- **Example**: `patAbc123Xyz456...`
- **How to get**: https://airtable.com/create/tokens
- **Required scopes**:
  - `schema.bases:write` (to create tables)
  - `data.records:write` (to write data)
  - `data.records:read` (to read data)

### `AIRTABLE_BASE_ID`
- **Description**: ID of your Airtable base (when using Airtable as database)
- **Format**: String starting with `app`
- **Example**: `appAbc123Xyz456`
- **How to get**: Visible in the URL when you open your base: `https://airtable.com/appXXXXXXXXXXXXXX/...`

---

## Optional Variables

### Application Settings

#### `APP_PORT`
- **Description**: Port number for the Flask application
- **Default**: `5000`
- **Example**: `8080`
- **When to change**: If port 5000 is already in use on your system

#### `LOG_LEVEL`
- **Description**: Logging verbosity level
- **Default**: `INFO`
- **Options**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **Example**: `DEBUG`
- **When to use DEBUG**: When troubleshooting issues

#### `TIMEZONE`
- **Description**: IANA timezone name for timestamp display
- **Default**: `Europe/Berlin`
- **Format**: IANA timezone identifier
- **Examples**: 
  - `America/New_York`
  - `Asia/Tokyo`
  - `UTC`
  - `Europe/London`
- **Note**: Affects how timestamps are displayed in Airtable

#### `BETTERSTACK_SOURCE_TOKEN`
- **Description**: Source token for Betterstack cloud logging
- **Default**: Not set (Betterstack logging disabled)
- **Format**: String
- **Example**: `your_betterstack_source_token_here`
- **How to get**: https://logs.betterstack.com/ → Settings → Sources → Create Source
- **When to use**: 
  - Production deployments for centralized logging
  - When you want cloud-based log monitoring and alerts
  - To aggregate logs from multiple instances
- **Note**: If not set, application logs only to console and local files

#### `BETTERSTACK_INGEST_HOST`
- **Description**: Custom ingestion host for Betterstack logging
- **Default**: Not set (uses default `in.logs.betterstack.com`)
- **Format**: Hostname string (without protocol)
- **Example**: `custom.logs.betterstack.com`
- **When to use**: 
  - When using a custom Betterstack endpoint
  - For self-hosted Betterstack instances
- **Note**: Only relevant if `BETTERSTACK_SOURCE_TOKEN` is set

### Webhook Settings

#### `NGROK_AUTHTOKEN`
- **Description**: Authentication token for ngrok tunnel (local development only)
- **Required for**: Webhook mode in local development
- **Format**: String
- **Example**: `2abc123XYZ...`
- **How to get**: https://dashboard.ngrok.com/get-started/your-authtoken
- **When NOT needed**: 
  - When using polling-only mode (`DISABLE_WEBHOOKS=true`)
  - In production with a public domain

#### `TEAMWORK_WEBHOOK_SECRET`
- **Description**: Secret for validating Teamwork webhook signatures
- **Default**: Empty (no validation)
- **Format**: String
- **Example**: `my_secret_key_123`
- **Note**: Currently optional as signature validation is not enforced

#### `MISSIVE_WEBHOOK_SECRET`
- **Description**: Secret for validating Missive webhook signatures
- **Default**: Empty (no validation)
- **Format**: String
- **Example**: `my_secret_key_456`
- **Note**: Currently optional as signature validation is not enforced

#### `DISABLE_WEBHOOKS`
- **Description**: Switch to polling-only mode (no webhooks)
- **Default**: `false`
- **Options**: `true`, `false`, `1`, `0`, `yes`, `no`
- **Example**: `true`
- **When to use**:
  - Testing and development
  - Firewalled environments
  - When you can't use ngrok
  - When simpler setup is preferred
- **Effect**: 
  - `true`: No webhooks, frequent polling (default 5s interval)
  - `false`: Webhooks enabled with backup polling (default 60s interval)

### Backfill & Polling Settings

#### `PERIODIC_BACKFILL_INTERVAL`
- **Description**: Interval in seconds for periodic polling/backfill
- **Default**: 
  - `5` when `DISABLE_WEBHOOKS=true`
  - `60` when `DISABLE_WEBHOOKS=false`
- **Format**: Integer (seconds)
- **Examples**: `10`, `30`, `120`
- **Considerations**:
  - **Lower values** = More real-time updates, more API calls
  - **Higher values** = Fewer API calls, slower updates
  - **Webhook mode**: Acts as safety net for missed webhooks
  - **Polling mode**: Acts as primary sync mechanism

#### `BACKFILL_OVERLAP_SECONDS`
- **Description**: Time overlap window when fetching updates
- **Default**: `120` (2 minutes)
- **Format**: Integer (seconds)
- **Example**: `180`
- **Purpose**: Prevents missed events due to clock skew or race conditions
- **How it works**: When resuming from checkpoint, fetches items updated since (checkpoint - overlap)

---

## Database Configuration

### `DB_BACKEND`
- **Description**: Which database backend to use
- **Default**: `airtable`
- **Options**: `airtable`, `postgres`
- **Example**: `postgres`
- **When to change**: When migrating from Airtable to PostgreSQL

### `PG_DSN`
- **Description**: PostgreSQL connection string (required when `DB_BACKEND=postgres`)
- **Format**: PostgreSQL connection URI
- **Example**: `postgresql://username:password@localhost:5432/teamwork_missive`
- **Components**:
  - `username`: PostgreSQL user
  - `password`: User's password
  - `localhost:5432`: Host and port (default PostgreSQL port)
  - `teamwork_missive`: Database name

### `AIRTABLE_EMAILS_TABLE`
- **Description**: Name of the Emails table in Airtable
- **Default**: `Emails`
- **Example**: `EmailData`
- **When to change**: If you want custom table names

### `AIRTABLE_TASKS_TABLE`
- **Description**: Name of the Tasks table in Airtable
- **Default**: `Tasks`
- **Example**: `TeamworkTasks`
- **When to change**: If you want custom table names

---

## Queue Settings

### `MAX_QUEUE_ATTEMPTS`
- **Description**: Maximum retry attempts for failed queue items
- **Default**: `3`
- **Format**: Integer
- **Example**: `5`
- **Behavior**: After max attempts, items are moved to retry queue with `.retry` extension

### `SPOOL_RETRY_SECONDS`
- **Description**: Wait time before retrying failed items
- **Default**: `60`
- **Format**: Integer (seconds)
- **Example**: `120`
- **Note**: Failed items are retried after this interval

---

## Date Filtering

These variables allow you to filter out old data from being synced to your database.

### `TEAMWORK_PROCESS_AFTER`
- **Description**: Only process Teamwork tasks created on or after this date
- **Default**: Not set (process all tasks)
- **Format**: `DD.MM.YYYY`
- **Example**: `23.04.2010`
- **Behavior**:
  - Tasks created **before** this date are **skipped** (marked as handled, not synced to database)
  - Tasks created **on or after** this date are **synced normally**
  - If not set, all tasks are processed
- **Use case**: 
  - Skip historical data you don't need
  - Reduce database size
  - Speed up initial sync
  - Focus on recent projects only

### `INCLUDE_COMPLETED_TASKS_ON_INITIAL_SYNC`
- **Description**: Control whether completed tasks are included during the initial sync
- **Default**: `true`
- **Format**: Boolean (`true`, `false`, `1`, `0`, `yes`, `no`)
- **Example**: `false`
- **Behavior**:
  - When `true`: Completed tasks are included during the first sync (default)
  - When `false`: Only active tasks are synced during the first sync
  - **Important**: This setting only affects the **initial sync** (when no checkpoint exists)
  - Subsequent syncs **always include completed tasks** to capture task status changes
- **Use case**: 
  - Set to `false` if you only want to track active tasks
  - Reduces initial sync time and database size
  - Useful when you don't need historical completed task data
- **API mapping**: Controls the `includeCompletedTasks` parameter in Teamwork API

### `MISSIVE_PROCESS_AFTER`
- **Description**: Only process Missive emails received on or after this date
- **Default**: Not set (fetches last 30 days on first run)
- **Format**: `DD.MM.YYYY`
- **Example**: `01.01.2020`
- **Behavior**:
  - On **first run**: API fetches conversations from this date onwards (reduces API calls)
  - On **subsequent runs**: Uses checkpoint-based incremental fetching
  - Emails received **before** this date are **not fetched** from API
  - Additional filtering in handler ensures no old emails are synced
  - If not set, defaults to last 30 days on first run
- **Use case**: 
  - Skip old email history
  - Reduce API calls and database size
  - Speed up initial sync significantly
  - Focus on recent communications only

**Important Notes on Date Filtering:**
- **Teamwork**: 
  - Initial backfill fetches tasks from the last 15 years via API
  - Tasks created before `TEAMWORK_PROCESS_AFTER` are filtered after fetch (not saved to database)
  - Use `INCLUDE_COMPLETED_TASKS_ON_INITIAL_SYNC=false` to exclude completed tasks during initial sync
  - Subsequent syncs always include completed tasks to track status changes
  - Ensures checkpoint advances properly
- **Missive**: 
  - Initial backfill only fetches conversations from `MISSIVE_PROCESS_AFTER` date onwards (or last 30 days if not set)
  - Significantly reduces API calls on first run
  - Additional handler-level filtering provides safety net
  - Subsequent runs use checkpoint-based incremental fetching
- Filtering is based on:
  - **Teamwork**: Task `createdAt` field
  - **Missive**: Message `delivered_at` or `created_at` field
- Date format is strict: Must be `DD.MM.YYYY` (e.g., `23.04.2010`, not `23/04/2010` or `2010-04-23`)

---

## Example Configurations

### Minimal Setup (Webhook Mode)
```env
# Required
TEAMWORK_BASE_URL=https://yourcompany.teamwork.com
TEAMWORK_API_KEY=your_key_here
MISSIVE_API_TOKEN=your_token_here
AIRTABLE_API_KEY=your_key_here
AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX
NGROK_AUTHTOKEN=your_token_here
```

### Minimal Setup (Polling-Only Mode)
```env
# Required
TEAMWORK_BASE_URL=https://yourcompany.teamwork.com
TEAMWORK_API_KEY=your_key_here
MISSIVE_API_TOKEN=your_token_here
AIRTABLE_API_KEY=your_key_here
AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX

# Disable webhooks
DISABLE_WEBHOOKS=true
```

### Production Setup with PostgreSQL
```env
# Required
TEAMWORK_BASE_URL=https://yourcompany.teamwork.com
TEAMWORK_API_KEY=your_key_here
MISSIVE_API_TOKEN=your_token_here

# Database
DB_BACKEND=postgres
PG_DSN=postgresql://user:pass@localhost:5432/teamwork_missive

# Optional
TIMEZONE=America/New_York
LOG_LEVEL=INFO
PERIODIC_BACKFILL_INTERVAL=60

# Betterstack logging (optional)
BETTERSTACK_SOURCE_TOKEN=your_betterstack_token_here
```

### Setup with Date Filtering
```env
# Required
TEAMWORK_BASE_URL=https://yourcompany.teamwork.com
TEAMWORK_API_KEY=your_key_here
MISSIVE_API_TOKEN=your_token_here
AIRTABLE_API_KEY=your_key_here
AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX

# Date Filtering - only sync data from 2020 onwards
TEAMWORK_PROCESS_AFTER=01.01.2020
MISSIVE_PROCESS_AFTER=01.01.2020

# Only sync active tasks on initial sync
INCLUDE_COMPLETED_TASKS_ON_INITIAL_SYNC=false

# Disable webhooks for simpler setup
DISABLE_WEBHOOKS=true
```

### Development Setup with Debug Logging
```env
# Required
TEAMWORK_BASE_URL=https://yourcompany.teamwork.com
TEAMWORK_API_KEY=your_key_here
MISSIVE_API_TOKEN=your_token_here
AIRTABLE_API_KEY=your_key_here
AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX

# Development settings
LOG_LEVEL=DEBUG
DISABLE_WEBHOOKS=true
PERIODIC_BACKFILL_INTERVAL=10
```

---

## Troubleshooting

### Invalid Date Format Error
If you see errors about date parsing when using `TEAMWORK_PROCESS_AFTER` or `MISSIVE_PROCESS_AFTER`:
- Ensure format is exactly `DD.MM.YYYY`
- Use leading zeros for single digits: `01.01.2020` not `1.1.2020`
- Use dots (`.`), not slashes (`/`) or dashes (`-`)

### All Items Being Filtered
If all your items are being filtered out:
- Check that your threshold date is not in the future
- Verify the date format is correct
- Check logs for "filtered" messages to confirm filtering is working
- Try removing the filter variables temporarily to test

### Webhooks Not Working
If webhooks aren't arriving:
1. Check `NGROK_AUTHTOKEN` is set correctly
2. Verify ngrok tunnel is running (check startup logs)
3. Consider using `DISABLE_WEBHOOKS=true` as alternative

### Database Connection Issues
If you can't connect to the database:
- **Airtable**: Verify `AIRTABLE_API_KEY` has correct scopes
- **PostgreSQL**: Check `PG_DSN` format and credentials
- Check logs for specific error messages

---

## See Also

- [README.md](README.md) - Project overview and quick start
- [SETUP.md](SETUP.md) - Detailed setup instructions
- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical architecture details
- [docs/label_categorization.md](docs/label_categorization.md) - Label categorization feature

