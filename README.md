# Teamwork & Missive Connector

A reliable Python-based connector system that synchronizes data from Teamwork (tasks) and Missive (emails) into your database (Airtable initially, with PostgreSQL support for future migration).

## 📚 Documentation

- **[SETUP.md](SETUP.md)** - Complete setup guide with step-by-step instructions
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Technical architecture and design decisions
- **[docs/label_categorization.md](docs/label_categorization.md)** - Label and tag categorization feature

## Features

- **Fully automated setup** - Tables and webhooks created automatically
- **Dual operation modes**:
  - **Webhook mode** (default): Real-time sync with periodic backfill (60s) as backup
  - **Polling-only mode**: No webhooks, relies on frequent polling (5s default)
- **Persistent spool queue** ensures no events are lost
- **Attachment handling** from Missive emails (uploads to Airtable)
- **Soft deletion** support with `deleted` flag
- **ID-to-name mapping** for tags and people (cached locally)
- **Label/tag categorization** - Automatically organize tags/labels into custom categories (e.g., customers, cost groups, rooms)
- **Database abstraction** for easy migration from Airtable to PostgreSQL

## Quick Start

### 1. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file with your configuration:

**For webhook mode (default, real-time sync):**
```env
# Teamwork
TEAMWORK_BASE_URL=https://yourcompany.teamwork.com
TEAMWORK_API_KEY=your_key_here

# Missive
MISSIVE_API_TOKEN=your_token_here

# Airtable
AIRTABLE_API_KEY=your_key_here
AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX

# ngrok (for local dev with webhooks)
NGROK_AUTHTOKEN=your_token_here

# Optional: Timezone (defaults to Europe/Berlin)
TIMEZONE=Europe/Berlin
```

**For polling-only mode (no webhooks, simpler setup):**
```env
# Teamwork
TEAMWORK_BASE_URL=https://yourcompany.teamwork.com
TEAMWORK_API_KEY=your_key_here

# Missive
MISSIVE_API_TOKEN=your_token_here

# Airtable
AIRTABLE_API_KEY=your_key_here
AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX

# Disable webhooks, use polling instead
DISABLE_WEBHOOKS=true

# Optional: Polling interval in seconds (default: 5 when webhooks disabled)
PERIODIC_BACKFILL_INTERVAL=5

# Optional: Timezone (defaults to Europe/Berlin)
TIMEZONE=Europe/Berlin
```

### 3. Run

```bash
# On macOS/Linux
./scripts/run_local.sh

# On Windows
scripts\run_local.bat
```

**That's it!** The system will automatically:
- ✅ Create Airtable tables (if needed)
- ✅ Set up ngrok tunnel
- ✅ Configure Teamwork webhooks
- ✅ Configure Missive webhooks
- ✅ Perform initial backfill
- ✅ Start processing events

## Project Structure

```
TeamworkMissiveConnector/
├── src/
│   ├── app.py                      # Flask webhook endpoints + periodic backfill
│   ├── startup.py                  # Automated setup & ngrok tunnel
│   ├── connectors/
│   │   ├── missive_client.py       # Missive API client
│   │   ├── teamwork_client.py      # Teamwork API client
│   │   └── teamwork_mappings.py    # ID-to-name mappings
│   ├── queue/
│   │   └── spool_queue.py          # Spool directory queue
│   ├── workers/
│   │   ├── dispatcher.py           # Queue processor
│   │   └── handlers/               # Event handlers
│   ├── db/
│   │   ├── interface.py            # Abstract database interface
│   │   ├── airtable_impl.py        # Airtable implementation
│   │   └── postgres_impl.py        # PostgreSQL implementation
│   └── webhooks/
│       ├── teamwork_webhooks.py    # Webhook management
│       └── missive_webhooks.py
├── data/                           # Queue, checkpoints, mappings (created at runtime)
├── logs/                           # Application logs
└── scripts/                        # Helper scripts
```

## Key Features Explained

### Automated Setup
On startup, the system automatically:
- Creates Airtable tables via API (with all required fields)
- Configures Teamwork webhooks via API (creates/updates as needed)
- Configures Missive webhooks via API (deletes old, creates new)
- Stores webhook IDs for cleanup on next run

### Periodic Backfill / Polling
The system runs periodic polling to query APIs for updates:
- **Webhook mode**: Every 60 seconds (default) as a safety net for missed webhooks
- **Polling-only mode**: Every 5 seconds (default) as the primary sync mechanism
- Queries APIs for recently updated items using checkpoint-based incremental fetching
- Updates cached mappings for tags and people
- Configurable via `PERIODIC_BACKFILL_INTERVAL` environment variable

### ID-to-Name Mapping
- Fetches all people and tags from Teamwork on startup
- Caches in `data/teamwork_people.json` and `data/teamwork_tags.json`
- Replaces IDs with names when storing tasks in Airtable
- Stores both IDs (for programmatic use) and names (for readability)

### Label/Tag Categorization
- Configure custom categories in `data/label_categories.json`
- Automatically sort tags/labels into category columns (e.g., "Kunden", "Kostengruppe", "Räume")
- Supports exact matches and wildcard patterns (`*` for multiple chars, `?` for single char)
- Creates category columns in Airtable automatically
- See [docs/label_categorization.md](docs/label_categorization.md) for detailed configuration

### Reliability
- **Idempotent upserts** - Safe to process same event multiple times
- **Persistent spool queue** - One file per event, survives crashes
- **Retry logic** - Exponential backoff, moves to retry queue
- **Overlap window** - Queries API with time buffer to handle clock skew

## Monitoring

```bash
# Check logs
tail -f logs/app.log

# Check queue status
python scripts/check_queue.py

# Manual backfill
python scripts/manual_backfill.py

# Validate configuration
python scripts/validate_config.py
```

## Database Migration (Airtable → PostgreSQL)

1. Create PostgreSQL database
2. Update `.env`: `DB_BACKEND=postgres` and set `PG_DSN`
3. Restart application (tables created automatically)

## Troubleshooting

### Webhooks not arriving
- Check ngrok tunnel: `http://localhost:4040`
- Verify webhook configuration succeeded in startup logs
- Check Flask app is running on port 5000

### Queue not processing
- Check worker is running: `ps aux | grep dispatcher`
- Check worker logs in `logs/app.log`
- Inspect spool: `ls data/queue/spool/*/`

### Database errors
- Verify API keys in `.env`
- Check Airtable base ID and table names
- Ensure tables were created successfully (check startup logs)

## License

MIT

