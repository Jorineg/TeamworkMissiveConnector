# Setup Guide

Complete guide to setting up the Teamwork & Missive Connector.

## Prerequisites

- Python 3.9 or later
- Airtable account (or PostgreSQL database)
- Teamwork account with API access
- Missive account with API access
- ngrok account (for local development)

## Quick Setup (5 Minutes)

### Step 1: Install Dependencies (1 min)

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

### Step 2: Configure Environment (2 min)

```bash
cp .env.example .env
# Edit .env with your credentials
```

**Required settings:**

```env
# ngrok (get from: https://dashboard.ngrok.com/get-started/your-authtoken)
NGROK_AUTHTOKEN=your_token_here

# Teamwork (get from: Settings > API & Webhooks)
TEAMWORK_BASE_URL=https://yourcompany.teamwork.com
TEAMWORK_API_KEY=your_key_here

# Missive (get from: Settings > API)
MISSIVE_API_TOKEN=your_token_here

# Airtable (get from: https://airtable.com/create/tokens)
AIRTABLE_API_KEY=your_key_here
AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX
```

**For Airtable Personal Access Token:**
1. Go to: https://airtable.com/create/tokens
2. Click "Create new token"
3. Add scopes: `schema.bases:write`, `data.records:write`, `data.records:read`
4. Select your base
5. Copy token to `.env`

### Step 3: Run (2 min)

```bash
# On macOS/Linux
./scripts/run_local.sh

# On Windows
scripts\run_local.bat
```

**That's it!** The system will automatically:
- ✅ Create Airtable tables with all required fields
- ✅ Start ngrok tunnel
- ✅ Configure Teamwork webhooks (4 event types)
- ✅ Configure Missive webhook
- ✅ Perform initial backfill
- ✅ Start processing events

### What You'll See

```
2025-10-15 01:00:00 - INFO - Checking Airtable tables...
2025-10-15 01:00:01 - INFO - Creating table: Emails
2025-10-15 01:00:02 - INFO - ✓ Created table 'Emails' with 16 fields
2025-10-15 01:00:02 - INFO - Creating table: Tasks
2025-10-15 01:00:03 - INFO - ✓ Created table 'Tasks' with 18 fields
2025-10-15 01:00:03 - INFO - ✓ Airtable setup complete

2025-10-15 01:00:04 - INFO - Starting ngrok tunnel on port 5000...
2025-10-15 01:00:06 - INFO - ✓ ngrok tunnel established: https://abc123.ngrok-free.app

2025-10-15 01:00:07 - INFO - Configuring Teamwork webhooks...
2025-10-15 01:00:08 - INFO - ✓ Created webhook for: task.created
2025-10-15 01:00:08 - INFO - ✓ Created webhook for: task.updated
2025-10-15 01:00:08 - INFO - ✓ Created webhook for: task.deleted
2025-10-15 01:00:08 - INFO - ✓ Created webhook for: task.completed
2025-10-15 01:00:08 - INFO - ✓ Teamwork webhooks configured

2025-10-15 01:00:09 - INFO - Configuring Missive webhook...
2025-10-15 01:00:10 - INFO - ✓ Created Missive webhook
2025-10-15 01:00:10 - INFO - ✓ All webhooks configured successfully

2025-10-15 01:00:11 - INFO - Starting backfill operation...
2025-10-15 01:00:12 - INFO - Found 5 tasks to backfill
2025-10-15 01:00:13 - INFO - Found 0 conversations to backfill
2025-10-15 01:00:13 - INFO - ✓ Backfill completed

2025-10-15 01:00:14 - INFO - Startup operations completed successfully
2025-10-15 01:00:14 - INFO - Keep this process running to maintain ngrok tunnel
```

## Automated Setup Features

### Airtable Table Creation

**What it does:**
- Checks if Emails and Tasks tables exist
- Creates them via API if missing
- Configures all required fields with correct types

**Emails Table (16 fields):**
- Email ID, Thread ID, Subject, From, To, Cc, Bcc
- Body Text, Body HTML, Sent At, Received At
- Labels, Deleted, Deleted At, Source Links, Attachments

**Tasks Table (18 fields):**
- Task ID, Project ID, Title, Description, Status
- tagIds, tags, assigneeUserIds, assignees
- createdById, createdBy, updatedById, updatedBy
- Due At, Updated At, Deleted, Deleted At, Source Links

**Requirements:**
- Personal Access Token with `schema.bases:write` scope
- Base creator role

### Teamwork Webhook Management

**What it does:**
- Deletes old webhooks from previous runs
- Creates 4 new webhooks for current ngrok URL
- Stores webhook IDs in `data/teamwork_webhook_ids.json`
- Subscribes to: task.created, task.updated, task.deleted, task.completed

**On each restart:**
1. Load stored webhook IDs
2. Delete all old webhooks
3. Create new webhooks with current URL
4. Save new IDs for next time

**Result:** Always exactly 4 webhooks, no stale URLs

### Missive Webhook Management

**What it does:**
- Loads stored webhook ID from `data/missive_webhook_id.json`
- Deletes old webhook (if exists)
- Creates new webhook with current ngrok URL
- Stores new ID for next deletion

**Why delete & recreate:**
- ngrok URL changes on every restart
- Missive API doesn't support webhook URL updates
- This ensures no duplicate or stale webhooks

### ID-to-Name Mapping

**On startup:**
- Fetches all people from Teamwork API
- Fetches all tags from Teamwork API
- Caches in `data/teamwork_people.json` and `data/teamwork_tags.json`

**When processing tasks:**
- Replaces person IDs with names (assignees, creator, updater)
- Replaces tag IDs with tag names
- Stores both IDs and names in separate Airtable columns

**Every 60 seconds:**
- Refreshes mappings to catch new people/tags

## Manual Testing

### Test Teamwork Integration

1. Create a new task in Teamwork
2. Wait 5-10 seconds
3. Check your Airtable Tasks table
4. You should see the new task with:
   - Task details
   - Tag names (not IDs)
   - Assignee names (not IDs)

### Test Missive Integration

1. Send an email to your Missive inbox
2. Wait 5-10 seconds
3. Check your Airtable Emails table
4. You should see the email with attachments (if any)

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

For production deployment without ngrok:

### Option 1: Linux Server with systemd

1. Deploy to server with public IP or domain
2. Update `.env`:
   ```env
   # Remove ngrok token
   # NGROK_AUTHTOKEN=...
   
   # Add your domain
   PUBLIC_URL=https://yourdomain.com
   ```

3. Create systemd service:
   ```bash
   sudo nano /etc/systemd/system/teamwork-missive.service
   ```
   
   ```ini
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

4. Start service:
   ```bash
   sudo systemctl enable teamwork-missive
   sudo systemctl start teamwork-missive
   ```

5. Start worker separately or use supervisor for both processes

### Option 2: Docker

Create `Dockerfile`:
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

## Switching to PostgreSQL

### Step 1: Set Up Database

```bash
# Install PostgreSQL
sudo apt-get install postgresql

# Create database
sudo -u postgres createdb teamwork_missive

# Create user
sudo -u postgres psql
CREATE USER youruser WITH PASSWORD 'yourpassword';
GRANT ALL PRIVILEGES ON DATABASE teamwork_missive TO youruser;
```

### Step 2: Update Configuration

Edit `.env`:
```env
DB_BACKEND=postgres
PG_DSN=postgresql://youruser:yourpassword@localhost:5432/teamwork_missive
```

### Step 3: Restart Application

```bash
# Tables will be created automatically on first run
./scripts/run_local.sh
```

## Troubleshooting

### Airtable: "Permission denied"
- Check token has `schema.bases:write` scope
- Ensure you're the base creator
- Verify base ID is correct

### Airtable: Tables not created
- Check logs for specific error
- Verify API token is valid
- Manually create tables if needed (see field list above)

### Teamwork: Webhooks fail with 404
- Webhooks API requires Pro plan or higher
- If not available, manually configure webhooks:
  1. Go to Settings > API & Webhooks
  2. Add webhook with displayed URL
  3. Select all 4 event types

### Teamwork: Webhooks fail with 401
- Check `TEAMWORK_API_KEY` in `.env`
- Verify API key is correct
- Regenerate API key if needed

### Missive: Webhook creation fails
- Verify `MISSIVE_API_TOKEN` is valid
- Check token hasn't expired
- Regenerate if needed

### ngrok: Tunnel fails to start
- Verify `NGROK_AUTHTOKEN` in `.env`
- Check ngrok service status at dashboard.ngrok.com
- Free tier allows 1 tunnel at a time

### Webhooks not arriving
- Check ngrok tunnel is active: http://localhost:4040
- Verify webhook configuration succeeded (check logs)
- Test webhook with ngrok inspector

### Queue not processing
- Check worker is running: `ps aux | grep dispatcher`
- Check worker logs in `logs/app.log`
- Inspect spool directories: `ls data/queue/spool/*/`

### Database errors
- Verify all API keys in `.env`
- Check Airtable base ID and table names
- Ensure tables were created successfully

### Events being missed
- The periodic backfill (every 60s) should catch missed events
- Check logs for backfill execution
- Verify checkpoint files are updating: `cat data/checkpoints/*.json`

## Advanced Configuration

### Environment Variables

See `.env.example` for all available options.

**Key settings:**
- `DB_BACKEND`: `airtable` or `postgres`
- `LOG_LEVEL`: `DEBUG`, `INFO`, `WARNING`, `ERROR`
- `BACKFILL_OVERLAP_SECONDS`: Overlap window (default: 120)
- `SPOOL_RETRY_SECONDS`: Retry interval (default: 300)

### Checkpoint Management

Checkpoints are stored in `data/checkpoints/`:
- `teamwork.json` - Last processed Teamwork event
- `missive.json` - Last processed Missive event

Format:
```json
{
  "source": "teamwork",
  "last_event_time": "2025-10-15T12:34:56.789Z",
  "last_cursor": null
}
```

To reset (re-process all recent events):
```bash
rm data/checkpoints/*.json
```

### Queue Management

Queue files are in `data/queue/spool/`:
- `teamwork/` - Teamwork events
- `missive/` - Missive events

Each event is stored as:
- `{id}.evt` - Pending event
- `{id}.retry` - Failed event (will retry)

To clear queue:
```bash
rm -rf data/queue/spool/*/
```

## File Locations

- **Configuration**: `.env`
- **Logs**: `logs/app.log`
- **Queue**: `data/queue/spool/`
- **Checkpoints**: `data/checkpoints/`
- **Webhook IDs**: `data/teamwork_webhook_ids.json`, `data/missive_webhook_id.json`
- **Mappings**: `data/teamwork_people.json`, `data/teamwork_tags.json`

## Getting Help

- **ARCHITECTURE.md**: System architecture and design
- **docs/api_notes.md**: API quirks and field mappings
- **issues.md**: Known issues and resolutions
- **Logs**: Check `logs/app.log` for errors

## Summary

Setup time comparison:

| Task | Manual | Automated |
|------|--------|-----------|
| Create Airtable tables | 15+ minutes | **Automatic** ✅ |
| Configure Teamwork webhooks | 5+ minutes | **Automatic** ✅ |
| Configure Missive webhook | 3+ minutes | **Automatic** ✅ |
| Update on ngrok restart | Manual each time | **Automatic** ✅ |
| **Total setup time** | **~30 minutes** | **~5 minutes** |

The automated setup reduces setup time by 80% and eliminates configuration errors.
