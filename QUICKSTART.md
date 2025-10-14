# Quick Start Guide

Get the Teamwork & Missive Connector running in 5 minutes.

## Prerequisites

- Python 3.9+
- Airtable account
- Teamwork account
- Missive account
- ngrok account (free tier works)

## Step 1: Install (2 minutes)

```bash
# Clone or download this repository
cd TeamworkMissiveConnector

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Configure (2 minutes)

```bash
# Copy example config
cp .env.example .env

# Edit .env with your credentials
nano .env  # or use your preferred editor
```

**Minimum required settings:**

```env
# ngrok (get from: https://dashboard.ngrok.com/get-started/your-authtoken)
NGROK_AUTHTOKEN=your_token_here

# Teamwork (get from: Settings > API & Webhooks)
TEAMWORK_BASE_URL=https://yourcompany.teamwork.com
TEAMWORK_API_KEY=your_key_here

# Missive (get from: Settings > API)
MISSIVE_API_TOKEN=your_token_here

# Airtable (get key from: https://airtable.com/create/tokens)
AIRTABLE_API_KEY=your_key_here
AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX
```

## Step 3: Set Up Airtable (1 minute)

Create a new base with two tables:

### Emails Table
Add these fields (or use the template in SETUP.md):
- Email ID (Single line text)
- Subject (Single line text)
- From (Single line text)
- Body Text (Long text)
- Attachments (Attachment)
- Deleted (Checkbox)

### Tasks Table
Add these fields:
- Task ID (Single line text)
- Title (Single line text)
- Description (Long text)
- Status (Single select)
- Deleted (Checkbox)

**Tip**: See SETUP.md for complete field list.

## Step 4: Run (30 seconds)

### On macOS/Linux:
```bash
./scripts/run_local.sh
```

### On Windows:
```bash
# Option 1: Use the batch script (opens 3 windows automatically)
scripts\run_local.bat

# Option 2: Manual (run in 3 separate terminals)
# Terminal 1
python -m src.startup

# Terminal 2 (new terminal)
python -m src.app

# Terminal 3 (new terminal)
python -m src.workers.dispatcher
```

You'll see output like:
```
======================================================================
WEBHOOK URLS - Configure these in Teamwork and Missive:
======================================================================
Teamwork: https://abc123.ngrok.io/webhook/teamwork
Missive:  https://abc123.ngrok.io/webhook/missive
======================================================================
```

## Step 5: Configure Webhooks (1 minute)

### Teamwork
1. Go to **Settings** > **API & Webhooks**
2. Click **Add Webhook**
3. Paste the Teamwork URL from Step 4
4. Select events: `task.created`, `task.updated`, `task.deleted`
5. Save

### Missive
1. Go to **Settings** > **Integrations** > **Webhooks**
2. Click **Add Webhook**
3. Paste the Missive URL from Step 4
4. Select events: `conversation.created`, `message.received`
5. Save

## Done! 🎉

The connector is now running and syncing data:

- ✓ Webhooks are receiving events
- ✓ Events are being queued
- ✓ Worker is processing events
- ✓ Data is being stored in Airtable

## Verify It's Working

### Test 1: Create a task in Teamwork
1. Create a new task in Teamwork
2. Wait 5-10 seconds
3. Check your Airtable Tasks table
4. You should see the new task!

### Test 2: Send an email to Missive
1. Send an email to your Missive inbox
2. Wait 5-10 seconds
3. Check your Airtable Emails table
4. You should see the new email!

## Monitor

```bash
# Check logs
tail -f logs/app.log

# Check queue status
python scripts/check_queue.py

# Validate configuration
python scripts/validate_config.py
```

## Troubleshooting

### Webhooks not arriving?
- Check ngrok is running: http://localhost:4040
- Verify webhook URLs in Teamwork/Missive
- Check Flask app is running on port 5000

### Nothing in Airtable?
- Check worker is running: `ps aux | grep dispatcher`
- Check logs: `tail -f logs/app.log`
- Verify Airtable API key and base ID

### Still stuck?
See SETUP.md and ARCHITECTURE.md for detailed information.

## Next Steps

- **Production deployment**: See SETUP.md for deploying without ngrok
- **Switch to PostgreSQL**: Change `DB_BACKEND=postgres` in .env
- **Customize**: Modify handlers in `src/workers/handlers/`
- **Monitor**: Set up logging/alerting for production use

## Common Commands

```bash
# Start everything
./scripts/run_local.sh

# Check queue
python scripts/check_queue.py

# Manual backfill
python scripts/manual_backfill.py

# Validate config
python scripts/validate_config.py

# View logs
tail -f logs/app.log

# Stop everything
# Press Ctrl+C in the terminal where you ran run_local.sh
```

## File Locations

- **Config**: `.env`
- **Logs**: `logs/app.log`
- **Queue**: `data/queue/inbox.jsonl`
- **Checkpoints**: `data/checkpoints/`
- **Dead Letter Queue**: `data/queue/dlq.jsonl`

## Getting Help

- **SETUP.md**: Detailed setup instructions
- **ARCHITECTURE.md**: System architecture and design
- **docs/api_notes.md**: API quirks and field mappings
- **Logs**: Check `logs/app.log` for errors

---

**Happy syncing!** 🚀

