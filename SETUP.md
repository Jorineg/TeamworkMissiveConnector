# Setup Guide

Complete guide to setting up the Teamwork & Missive Connector.

## What You'll Need

Before starting, make sure you have:

- **Python 3.9 or later** installed on your computer
  - Check by opening Terminal/Command Prompt and typing: `python --version` or `python3 --version`
  - If not installed, download from [python.org](https://www.python.org/downloads/)
- **Airtable account** (the free tier works fine)
  - Sign up at [airtable.com](https://airtable.com) if you don't have one
  - Alternative: PostgreSQL database (more advanced, requires technical knowledge)
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

Choose the setup method based on your preferred operation mode:

### Option A: Webhook Mode Setup (5 Minutes)

**Step 1: Install Dependencies (1 min)**

Open Terminal (macOS/Linux) or Command Prompt (Windows) and navigate to the project folder, then run:

```bash
# Create virtual environment (a clean Python environment for this project)
python3 -m venv venv

# Activate it
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate  # On Windows

# Install required packages
pip install -r requirements.txt
```

**What this does**: Creates an isolated Python environment and installs all necessary packages listed in `requirements.txt`.

**Step 2: Configure Environment (2 min)**

Create a new file named `.env` in the project folder (same folder as README.md) and add the following:

```env
# Teamwork (get from: Settings > API & Webhooks)
TEAMWORK_BASE_URL=https://yourcompany.teamwork.com
TEAMWORK_API_KEY=your_key_here

# Missive (get from: Settings > API)
MISSIVE_API_TOKEN=your_token_here

# Airtable (get from: https://airtable.com/create/tokens)
AIRTABLE_API_KEY=your_key_here
AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX

# ngrok (get from: https://dashboard.ngrok.com/get-started/your-authtoken)
NGROK_AUTHTOKEN=your_token_here

# Optional: Timezone (defaults to Europe/Berlin)
TIMEZONE=Europe/Berlin

# Optional: Polling interval for backup (defaults to 60s)
# PERIODIC_BACKFILL_INTERVAL=60
```

### Option B: Polling-Only Mode Setup (3 Minutes - No ngrok!)

**Step 1: Install Dependencies (1 min)**

Same as Option A - open Terminal (macOS/Linux) or Command Prompt (Windows) and navigate to the project folder, then run:

```bash
# Create virtual environment (a clean Python environment for this project)
python3 -m venv venv

# Activate it
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate  # On Windows

# Install required packages
pip install -r requirements.txt
```

**What this does**: Creates an isolated Python environment and installs all necessary packages listed in `requirements.txt`.

**Step 2: Configure Environment (2 min)**

Create a new file named `.env` in the project folder (same folder as README.md) and add the following:

```env
# Teamwork (get from: Settings > API & Webhooks)
TEAMWORK_BASE_URL=https://yourcompany.teamwork.com
TEAMWORK_API_KEY=your_key_here

# Missive (get from: Settings > API)
MISSIVE_API_TOKEN=your_token_here

# Airtable (get from: https://airtable.com/create/tokens)
AIRTABLE_API_KEY=your_key_here
AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX

# Disable webhooks - use polling instead
DISABLE_WEBHOOKS=true

# Optional: Polling interval in seconds (defaults to 5 when webhooks disabled)
# Lower = more real-time but more API calls
# Higher = less API calls but slower updates
# PERIODIC_BACKFILL_INTERVAL=5

# Optional: Timezone (defaults to Europe/Berlin)
TIMEZONE=Europe/Berlin
```

**Note**: No ngrok token needed for polling-only mode!

**How to get your Airtable Personal Access Token:**
1. Go to: https://airtable.com/create/tokens
2. Click "Create new token"
3. Give it a name (e.g., "Teamwork Missive Connector")
4. Add these three scopes (permissions):
   - `schema.bases:write` (allows creating tables)
   - `data.records:write` (allows adding/updating data)
   - `data.records:read` (allows reading data)
5. Under "Access", select the specific base you want to use
6. Click "Create token"
7. Copy the token and paste it into your `.env` file as `AIRTABLE_API_KEY`

### Step 3: Run (2 min)

**On macOS/Linux:**
- Open Terminal
- Navigate to the project folder
- Run: `./scripts/run_local.sh`

**On Windows:**
- Open Command Prompt or PowerShell
- Navigate to the project folder
- Run: `scripts\run_local.bat`

**Tip**: You can navigate to the project folder by typing `cd ` (with a space) and then dragging the folder into the terminal window.

### What You'll See

**Webhook Mode:**
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

**Polling-Only Mode:**
```
2025-10-15 01:00:00 - INFO - Checking Airtable tables...
2025-10-15 01:00:01 - INFO - Creating table: Emails
2025-10-15 01:00:02 - INFO - ✓ Created table 'Emails' with 16 fields
2025-10-15 01:00:02 - INFO - Creating table: Tasks
2025-10-15 01:00:03 - INFO - ✓ Created table 'Tasks' with 18 fields
2025-10-15 01:00:03 - INFO - ✓ Airtable setup complete

2025-10-15 01:00:04 - INFO - Webhooks disabled. Skipping ngrok setup.
======================================================================
POLLING MODE ACTIVE
======================================================================
Periodic backfill interval: 5 seconds
No webhooks will be configured. System relies on periodic polling.
======================================================================

2025-10-15 01:00:05 - INFO - Starting backfill operation...
2025-10-15 01:00:06 - INFO - Found 5 tasks to backfill
2025-10-15 01:00:07 - INFO - Found 0 conversations to backfill
2025-10-15 01:00:07 - INFO - ✓ Backfill completed

2025-10-15 01:00:08 - INFO - Startup operations completed successfully
2025-10-15 01:00:09 - INFO - Starting periodic backfill (every 5 seconds)...
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

**View the application logs:**
- Open the file `logs/app.log` in any text editor
- Or on macOS/Linux, use terminal: `tail -f logs/app.log`
- Or on Windows, use Command Prompt: `type logs\app.log`

### Check Queue Status

See how many events are waiting to be processed:

```bash
python scripts/check_queue.py
```

### Manual Backfill

Manually fetch recent updates from Teamwork and Missive:

```bash
python scripts/manual_backfill.py
```

### Validate Configuration

Check if your `.env` file is set up correctly:

```bash
python scripts/validate_config.py
```

## Production Deployment

For production deployment without ngrok:

### Option 1: Linux Server with systemd

1. Deploy to server with public IP or domain
2. Update `.env`:
   ```env
   # Remove ngrok token (not needed with public domain)
   # NGROK_AUTHTOKEN=...
   ```

3. Set up a reverse proxy (this forwards web requests to your Flask app):
   - If using nginx or Apache, configure it to send requests to `localhost:5000`
   - Consult your web server's documentation for reverse proxy setup

4. Create a systemd service file (this makes the app run automatically):
   - Open a new file in your text editor: `/etc/systemd/system/teamwork-missive.service`
   - Add this content (replace paths with your actual paths):
   
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

5. Start the service:
   - Run: `sudo systemctl enable teamwork-missive`
   - Run: `sudo systemctl start teamwork-missive`

**Note**: For production deployment, consider getting help from a system administrator if you're not familiar with Linux server management.

### Option 2: Docker

**Note**: This option requires Docker knowledge. If you're not familiar with Docker, consider Option 1 or ask for technical help.

Create a file named `Dockerfile` in the project folder:
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "src.app"]
```

Build and run (in Terminal/Command Prompt):
```bash
docker build -t teamwork-missive-connector .
docker run -d --env-file .env teamwork-missive-connector
```

## Switching to PostgreSQL

### Step 1: Set Up Database

**Install and configure PostgreSQL:**

1. Install PostgreSQL on your system (method depends on your operating system)
2. Create a new database called `teamwork_missive`
3. Create a database user with a password
4. Grant that user full access to the database

**If you're comfortable with terminal commands (Linux/macOS):**
```bash
sudo apt-get install postgresql
sudo -u postgres createdb teamwork_missive
sudo -u postgres psql
CREATE USER youruser WITH PASSWORD 'yourpassword';
GRANT ALL PRIVILEGES ON DATABASE teamwork_missive TO youruser;
```

**If you're not familiar with PostgreSQL**, consider:
- Using a managed database service (like AWS RDS, Heroku Postgres, etc.)
- Getting help from a database administrator
- Sticking with Airtable (it's simpler for non-technical users)

### Step 2: Update Configuration

Open your `.env` file in a text editor and update:
```env
DB_BACKEND=postgres
PG_DSN=postgresql://youruser:yourpassword@localhost:5432/teamwork_missive
```

### Step 3: Restart Application

Stop the current application (press `Ctrl+C` in the terminal where it's running), then start it again:

**On macOS/Linux:**
```bash
./scripts/run_local.sh
```

**On Windows:**
```
scripts\run_local.bat
```

The PostgreSQL tables will be created automatically on first run.

## Troubleshooting

### Airtable: "Permission denied"

**What this means**: Your Airtable API token doesn't have the right permissions.

**How to fix**:
1. Go back to https://airtable.com/create/tokens
2. Edit your token
3. Make sure these scopes are checked:
   - `schema.bases:write`
   - `data.records:write`
   - `data.records:read`
4. Make sure the correct base is selected under "Access"
5. Copy the token again and update your `.env` file

### Airtable: Tables not created

**What this means**: The system couldn't automatically create the Emails and Tasks tables.

**How to fix**:
1. Open `logs/app.log` to see the specific error message
2. Verify your Airtable API token is correct in the `.env` file
3. Make sure you have creator permissions on the Airtable base
4. If automatic creation keeps failing, you can manually create the tables using the field lists shown earlier in this guide

### Teamwork: Webhooks fail with 404

**What this means**: Your Teamwork plan doesn't support automatic webhook creation via API.

**How to fix**:
1. Check if you have a Pro plan or higher (webhooks require this)
2. If not, you can manually set up webhooks:
   - Go to Teamwork → Settings → API & Webhooks
   - Click "Add Webhook"
   - Use the URL shown in the terminal output
   - Select these event types: task.created, task.updated, task.deleted, task.completed
3. Alternative: Use polling-only mode (no webhooks needed) - just add `DISABLE_WEBHOOKS=true` to your `.env` file

### Teamwork: Webhooks fail with 401

**What this means**: Your Teamwork API key is incorrect or invalid.

**How to fix**:
1. Go to Teamwork → Settings → API & Webhooks
2. Find your API key (or generate a new one)
3. Copy it exactly as shown
4. Update `TEAMWORK_API_KEY` in your `.env` file
5. Restart the application

### Missive: Webhook creation fails

**What this means**: Your Missive API token is incorrect or has expired.

**How to fix**:
1. Go to Missive → Settings → API
2. Check if your token is still valid
3. If needed, generate a new token
4. Update `MISSIVE_API_TOKEN` in your `.env` file
5. Restart the application

### ngrok: Tunnel fails to start

**What this means**: ngrok couldn't create a public URL for your local development.

**How to fix**:
1. Check that `NGROK_AUTHTOKEN` in your `.env` file is correct
2. Go to https://dashboard.ngrok.com and verify your account is active
3. Note: Free tier only allows 1 tunnel at a time - make sure you don't have ngrok running elsewhere
4. Alternative: Use polling-only mode instead (add `DISABLE_WEBHOOKS=true` to `.env`)

### Webhooks not arriving

**What this means**: Teamwork/Missive is sending webhooks but they're not reaching your app.

**How to fix**:
1. Open http://localhost:4040 in your browser to see the ngrok inspector
2. Check if requests are showing up there
3. Look at `logs/app.log` to see if webhooks are being received
4. Verify the webhook URLs in Teamwork/Missive match the ngrok URL
5. As a backup, the system has automatic polling every 60 seconds that will catch any missed events

### Queue not processing

**What this means**: Events are stuck in the queue and not being saved to your database.

**How to fix**:
1. Make sure the worker process is running (it should start automatically with the main app)
2. Check `logs/app.log` for any error messages
3. Look in `data/queue/spool/teamwork/` and `data/queue/spool/missive/` - if you see many files, the queue is backed up
4. Try running `python scripts/check_queue.py` to see queue status
5. Restart the application

### Database errors

**What this means**: The system can't connect to or write to your database (Airtable or PostgreSQL).

**How to fix**:
1. Double-check all values in your `.env` file:
   - `AIRTABLE_API_KEY` - should start with "pat"
   - `AIRTABLE_BASE_ID` - should start with "app"
   - Table names match what you configured
2. Open `logs/app.log` to see the specific error
3. For Airtable: Check that tables exist and have the right field names
4. Try running `python scripts/validate_config.py` to check your configuration

### Events being missed
- **Webhook mode**: The periodic backfill (every 60s) should catch missed events
- **Polling mode**: The periodic polling (every 5s by default) is the primary mechanism
- Check logs for backfill/polling execution
- Verify checkpoint files are updating: `cat data/checkpoints/*.json`

### Choosing Between Webhook and Polling Mode

**Use Webhook Mode if:**
- You need real-time updates (< 5 second latency)
- You want to minimize API rate limit usage
- You can expose a public URL (ngrok for dev, or actual domain for production)
- You're deploying to production

**Use Polling-Only Mode if:**
- You're testing or developing
- You're behind a strict firewall with no inbound access
- You don't have ngrok or can't set up webhooks
- You prefer simpler deployment (no tunnel maintenance)
- 5-60 second update delay is acceptable
- API rate limits are not a concern

**Switching Between Modes:**
You can easily switch by changing `.env`:
```env
# Switch to polling-only
DISABLE_WEBHOOKS=true

# Switch back to webhooks
DISABLE_WEBHOOKS=false
# or just remove the line (default is false)
```

## Advanced Configuration

### Environment Variables

**Key settings:**
- `DB_BACKEND`: `airtable` or `postgres`
- `LOG_LEVEL`: `DEBUG`, `INFO`, `WARNING`, `ERROR`
- `DISABLE_WEBHOOKS`: `true` or `false` (default: `false`)
  - When `true`: No webhooks or ngrok, polling-only mode
  - When `false`: Webhook mode with periodic backfill as backup
- `PERIODIC_BACKFILL_INTERVAL`: Polling interval in seconds
  - Default: `5` when `DISABLE_WEBHOOKS=true`
  - Default: `60` when `DISABLE_WEBHOOKS=false`
  - Can be set to any value (e.g., `10`, `30`, `120`)
  - Lower values = more real-time but more API calls
  - Higher values = fewer API calls but slower updates
- `TIMEZONE`: IANA timezone name for timestamps (default: `Europe/Berlin`)
  - Examples: `Europe/Berlin`, `America/New_York`, `Asia/Tokyo`, `UTC`
  - All timestamps in Airtable will be displayed in this timezone
  - Both data storage and Airtable column configuration use this setting
- `BACKFILL_OVERLAP_SECONDS`: Overlap window (default: 120)
  - Helps prevent missed events due to clock skew or race conditions
- `SPOOL_RETRY_SECONDS`: Retry interval for failed events (default: 60)

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
- Delete all files in the `data/checkpoints/` folder
- Or on macOS/Linux terminal: `rm data/checkpoints/*.json`
- Or on Windows Command Prompt: `del data\checkpoints\*.json`

### Queue Management

Queue files are in `data/queue/spool/`:
- `teamwork/` - Teamwork events
- `missive/` - Missive events

Each event is stored as:
- `{id}.evt` - Pending event
- `{id}.retry` - Failed event (will retry)

To clear queue:
- Delete all folders inside `data/queue/spool/teamwork/` and `data/queue/spool/missive/`
- Or on macOS/Linux terminal: `rm -rf data/queue/spool/*/`
- Or on Windows: Manually delete all files in those folders using File Explorer

## File Locations

- **Configuration**: `.env`
- **Logs**: `logs/app.log`
- **Queue**: `data/queue/spool/`
- **Checkpoints**: `data/checkpoints/`
- **Webhook IDs**: `data/teamwork_webhook_ids.json`, `data/missive_webhook_id.json`
- **Mappings**: `data/teamwork_people.json`, `data/teamwork_tags.json`

## Getting Help

If you run into problems:

1. **Check the logs**: Open `logs/app.log` in a text editor to see error messages
2. **Read the documentation**:
   - **ARCHITECTURE.md**: Technical details about how the system works
   - **docs/api_notes.md**: Information about API quirks and data mappings
   - **issues.md**: Solutions to common problems
3. **Validate your configuration**: Run `python scripts/validate_config.py` to check if your `.env` file is set up correctly
4. **Need technical help?**: Consider reaching out to a developer or system administrator if you're stuck

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
