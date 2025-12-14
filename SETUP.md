# Setup Guide

Complete guide to setting up the Teamwork & Missive Connector.

For a complete reference of all environment variables, see **[ENV_VARIABLES.md](ENV_VARIABLES.md)**.

## What You'll Need

Before starting, make sure you have:

- **Python 3.9 or later** installed on your computer
  - Check by opening Terminal/Command Prompt and typing: `python --version` or `python3 --version`
  - If not installed, download from [python.org](https://www.python.org/downloads/)
- **PostgreSQL database** with connection credentials
- **Teamwork account** with API access
  - You'll need admin or project manager permissions to get an API key
- **Missive account** with API access
  - You'll need the API token from your Missive settings
- **ngrok account** (only needed if using webhook mode for local development)
  - Free tier works fine - sign up at [ngrok.com](https://ngrok.com)

## Operation Modes

This connector supports two operation modes:

1. **Webhook Mode (Default)** - Real-time sync using webhooks with periodic backfill as backup
   - Requires: ngrok (local dev) or public URL (production)
   - Updates: Near-instant (< 5 seconds)
   - API calls: Minimal (only on events)
   - Best for: Production environments, real-time requirements

2. **Polling-Only Mode** - Frequent periodic polling without webhooks
   - Requires: No public URL or ngrok needed
   - Updates: Configurable delay (5 seconds default)
   - API calls: Frequent (every polling interval)
   - Best for: Testing, firewalled environments, simple setups

## Quick Setup

### Step 1: Install Dependencies

Open Terminal (macOS/Linux) or Command Prompt (Windows) and navigate to the project folder:

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate  # On Windows

# Install required packages
pip install -r requirements.txt
```

### Step 2: Configure Environment

Create a new file named `.env` in the project folder:

**Webhook Mode (Real-time sync):**
```env
# Required: Teamwork (get from: Settings > API & Webhooks)
TEAMWORK_BASE_URL=https://yourcompany.teamwork.com
TEAMWORK_API_KEY=your_key_here

# Required: Missive (get from: Settings > API)
MISSIVE_API_TOKEN=your_token_here

# Required: PostgreSQL
PG_DSN=postgresql://user:pass@host:5432/database

# Required for webhook mode: ngrok (get from: https://dashboard.ngrok.com)
NGROK_AUTHTOKEN=your_token_here

# Optional: Craft integration
# CRAFT_BASE_URL=https://connect.craft.do/links/YOUR_ID/api/v1

# Optional: Timezone (defaults to Europe/Berlin)
TIMEZONE=Europe/Berlin
```

**Polling-Only Mode (No webhooks):**
```env
# Required: Teamwork
TEAMWORK_BASE_URL=https://yourcompany.teamwork.com
TEAMWORK_API_KEY=your_key_here

# Required: Missive
MISSIVE_API_TOKEN=your_token_here

# Required: PostgreSQL
PG_DSN=postgresql://user:pass@host:5432/database

# Disable webhooks - use polling instead
DISABLE_WEBHOOKS=true

# Optional: Polling interval (default 5s when webhooks disabled)
# PERIODIC_BACKFILL_INTERVAL=5
```

### Step 3: Run

**On macOS/Linux:**
```bash
./scripts/run_local.sh
```

**On Windows:**
```
scripts\run_local.bat
```

## What You'll See

**Webhook Mode:**
```
2025-10-15 01:00:00 - INFO - Connecting to PostgreSQL database
2025-10-15 01:00:01 - INFO - Database connection established successfully
2025-10-15 01:00:02 - INFO - Starting ngrok tunnel on port 5000...
2025-10-15 01:00:04 - INFO - ✓ ngrok tunnel established: https://abc123.ngrok-free.app
2025-10-15 01:00:05 - INFO - Configuring Teamwork webhooks...
2025-10-15 01:00:06 - INFO - ✓ Teamwork webhooks configured
2025-10-15 01:00:07 - INFO - Configuring Missive webhook...
2025-10-15 01:00:08 - INFO - ✓ All webhooks configured successfully
2025-10-15 01:00:09 - INFO - Starting backfill operation...
2025-10-15 01:00:10 - INFO - ✓ Backfill completed
2025-10-15 01:00:11 - INFO - Startup operations completed successfully
```

**Polling-Only Mode:**
```
2025-10-15 01:00:00 - INFO - Connecting to PostgreSQL database
2025-10-15 01:00:01 - INFO - Database connection established successfully
2025-10-15 01:00:02 - INFO - Webhooks disabled. Skipping ngrok setup.
======================================================================
POLLING MODE ACTIVE
======================================================================
Periodic backfill interval: 5 seconds
No webhooks will be configured. System relies on periodic polling.
======================================================================
2025-10-15 01:00:03 - INFO - Starting backfill operation...
2025-10-15 01:00:04 - INFO - ✓ Backfill completed
2025-10-15 01:00:05 - INFO - Starting periodic backfill (every 5 seconds)...
```

## Monitoring

### Check Logs
```bash
tail -f logs/app.log
```

### Check Queue Status
```bash
python scripts/check_queue.py
```

### Manual Backfill
```bash
python scripts/manual_backfill.py
```

### Validate Configuration
```bash
python scripts/validate_config.py
```

## Production Deployment

### Option 1: Linux Server with systemd

1. Deploy to server with public IP or domain
2. Set up a reverse proxy (nginx/Apache) to forward to `localhost:5000`
3. Create systemd service:

```ini
# /etc/systemd/system/teamwork-missive.service
[Unit]
Description=Teamwork Missive Connector
After=network.target

[Service]
Type=simple
User=yourusername
WorkingDirectory=/path/to/TeamworkMissiveConnector
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python -m src.app
Restart=always

[Install]
WantedBy=multi-user.target
```

4. Enable and start:
```bash
sudo systemctl enable teamwork-missive
sudo systemctl start teamwork-missive
```

### Option 2: Docker

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "src.app"]
```

Build and run:
```bash
docker build -t teamwork-missive-connector .
docker run -d --env-file .env teamwork-missive-connector
```

## Troubleshooting

### Webhooks not arriving
1. Check ngrok inspector: http://localhost:4040
2. Verify webhook URLs in Teamwork/Missive
3. Try polling-only mode: `DISABLE_WEBHOOKS=true`

### Database connection issues
1. Verify `PG_DSN` format and credentials
2. Check PostgreSQL is running and accessible
3. Check logs for specific error messages

### Queue not processing
1. Check logs: `tail -f logs/app.log`
2. Run queue status: `python scripts/check_queue.py`
3. Restart the application

### Events being missed
- Webhook mode: Periodic backfill (60s) catches missed events
- Polling mode: Polling (5s) is the primary mechanism
- Check logs for backfill execution

## Choosing Between Modes

**Use Webhook Mode if:**
- You need real-time updates (< 5 second latency)
- You can expose a public URL
- You're deploying to production

**Use Polling-Only Mode if:**
- You're testing or developing
- You're behind a strict firewall
- 5-60 second update delay is acceptable

**Switching:**
```env
# Polling-only
DISABLE_WEBHOOKS=true

# Webhook mode
DISABLE_WEBHOOKS=false
```

## File Locations

- **Configuration**: `.env`
- **Logs**: `logs/app.log`
- **Webhook IDs**: `data/teamwork_webhook_ids.json`, `data/missive_webhook_id.json`
- **Mappings**: `data/teamwork_people.json`, `data/teamwork_tags.json`

## Getting Help

1. **Check logs**: `logs/app.log`
2. **Read docs**: `ARCHITECTURE.md`, `docs/api_notes.md`
3. **Validate config**: `python scripts/validate_config.py`
