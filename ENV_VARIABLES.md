# Environment Variables Reference

This document provides a comprehensive list of all environment variables used by the Teamwork & Missive Connector.

## Table of Contents

- [Required Variables](#required-variables)
- [Optional Variables](#optional-variables)
- [Database Configuration](#database-configuration)
- [Webhook Configuration](#webhook-configuration)
- [Advanced Configuration](#advanced-configuration)
- [Date Filtering](#date-filtering)

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

## Quick Reference Table

| Variable | Required? | Default | Purpose |
|----------|-----------|---------|---------|
| `TEAMWORK_BASE_URL` | ✅ Yes | - | Teamwork instance URL |
| `TEAMWORK_API_KEY` | ✅ Yes | - | Teamwork authentication |
| `TEAMWORK_WEBHOOK_SECRET` | ❌ No | Empty | Webhook signature validation |
| `TEAMWORK_PROCESS_AFTER` | ❌ No | None | Filter tasks by created date |
| `MISSIVE_API_TOKEN` | ✅ Yes | - | Missive authentication |
| `MISSIVE_WEBHOOK_SECRET` | ❌ No | Empty | Webhook signature validation |
| `MISSIVE_PROCESS_AFTER` | ❌ No | None | Filter emails by received date |
| `AIRTABLE_API_KEY` | ⚠️ If Airtable | - | Airtable authentication |
| `AIRTABLE_BASE_ID` | ⚠️ If Airtable | - | Airtable base identifier |
| `AIRTABLE_EMAILS_TABLE` | ❌ No | `Emails` | Emails table name |
| `AIRTABLE_TASKS_TABLE` | ❌ No | `Tasks` | Tasks table name |
| `DB_BACKEND` | ❌ No | `airtable` | Database choice |
| `PG_DSN` | ⚠️ If Postgres | - | PostgreSQL connection |
| `NGROK_AUTHTOKEN` | ⚠️ If webhooks | - | ngrok tunnel (local dev) |
| `DISABLE_WEBHOOKS` | ❌ No | `false` | Enable/disable webhooks |
| `APP_PORT` | ❌ No | `5000` | Flask application port |
| `LOG_LEVEL` | ❌ No | `INFO` | Logging verbosity |
| `TIMEZONE` | ❌ No | `Europe/Berlin` | Timestamp timezone |
| `PERIODIC_BACKFILL_INTERVAL` | ❌ No | `5`/`60` | Polling interval (seconds) |
| `BACKFILL_OVERLAP_SECONDS` | ❌ No | `120` | Checkpoint overlap window |
| `MAX_QUEUE_ATTEMPTS` | ❌ No | `3` | Max retry attempts |
| `SPOOL_RETRY_SECONDS` | ❌ No | `60` | Retry wait time |

**Legend:**
- ✅ Always required
- ⚠️ Conditionally required
- ❌ Optional

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

