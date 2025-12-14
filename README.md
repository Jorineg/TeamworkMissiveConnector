# Teamwork & Missive Connector

A reliable Python-based connector that synchronizes data from Teamwork (tasks), Missive (emails), and Craft (documents) into PostgreSQL.

## 📚 Documentation

- **[SETUP.md](SETUP.md)** - Complete setup guide with step-by-step instructions
- **[ENV_VARIABLES.md](ENV_VARIABLES.md)** - Complete environment variables reference
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Technical architecture and design decisions

## Features

- **Dual operation modes**:
  - **Webhook mode** (default): Real-time sync with periodic backfill (60s) as backup
  - **Polling-only mode**: No webhooks, relies on frequent polling (5s default)
- **PostgreSQL queue**: Persistent, crash-safe event queue
- **Database resilience**: Lazy connection with automatic reconnect
- **ID-to-name mapping**: Tags and users resolved to human-readable names
- **Date filtering**: Skip old data via `TEAMWORK_PROCESS_AFTER` and `MISSIVE_PROCESS_AFTER`
- **Auto-categorization**: Database triggers extract locations, cost groups, and task types from tags/labels

## Quick Start

### 1. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file:

```env
# Required
TEAMWORK_BASE_URL=https://yourcompany.teamwork.com
TEAMWORK_API_KEY=your_key_here
MISSIVE_API_TOKEN=your_token_here
PG_DSN=postgresql://user:pass@host:5432/database

# Optional: Craft integration
CRAFT_BASE_URL=https://connect.craft.do/links/YOUR_ID/api/v1

# Optional: Polling-only mode (no webhooks)
DISABLE_WEBHOOKS=true

# Optional: ngrok for local webhook development
NGROK_AUTHTOKEN=your_token_here

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
- ✅ Connect to PostgreSQL
- ✅ Set up ngrok tunnel (if webhooks enabled)
- ✅ Configure webhooks (if enabled)
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
│   │   └── craft_client.py         # Craft API client
│   ├── queue/
│   │   ├── postgres_queue.py       # PostgreSQL-based queue
│   │   └── models.py               # Queue item models
│   ├── workers/
│   │   ├── dispatcher.py           # Queue processor
│   │   └── handlers/               # Event handlers
│   ├── db/
│   │   ├── interface.py            # Database interface
│   │   ├── postgres_impl.py        # PostgreSQL implementation
│   │   └── models.py               # Domain models
│   └── webhooks/
│       ├── teamwork_webhooks.py    # Webhook management
│       └── missive_webhooks.py
├── data/                           # Runtime data (mappings cache)
├── logs/                           # Application logs
└── scripts/                        # Helper scripts
```

## Key Features

### Periodic Backfill / Polling
- **Webhook mode**: Every 60 seconds (default) as a safety net
- **Polling-only mode**: Every 5 seconds (default) as primary sync
- Configurable via `PERIODIC_BACKFILL_INTERVAL`

### ID-to-Name Mapping
- Fetches all people and tags from Teamwork on startup
- Caches in `data/teamwork_people.json` and `data/teamwork_tags.json`
- Replaces IDs with names when storing tasks

### Auto-Categorization (Database Triggers)
The database automatically extracts and categorizes data via triggers:
- **Locations**: Extracted from tags/labels matching location patterns
- **Cost Groups**: Extracted from tags/labels matching Kostengruppe patterns (DIN 276)
- **Task Types**: Classified based on tag patterns
- **Project Linking**: Conversations auto-linked to projects based on labels

### Reliability
- **Idempotent upserts**: Safe to process same event multiple times
- **At-least-once delivery**: Events reprocessed on crash
- **Overlap window**: Queries API with 120s buffer to handle clock skew
- **Graceful shutdown**: Finishes current item before exit

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

## Troubleshooting

### Webhooks not arriving
- Check ngrok tunnel: `http://localhost:4040`
- Verify webhook configuration in startup logs
- Consider using `DISABLE_WEBHOOKS=true` as alternative

### Queue not processing
- Check worker is running: `ps aux | grep dispatcher`
- Check worker logs in `logs/app.log`

### Database connection issues
- Verify `PG_DSN` format and credentials
- Check logs for specific error messages

## License

MIT
