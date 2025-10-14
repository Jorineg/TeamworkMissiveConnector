# Setup Guide

This guide will walk you through setting up the Teamwork & Missive Connector.

## Prerequisites

- Python 3.9 or later
- Airtable account (or PostgreSQL database)
- Teamwork account with API access
- Missive account with API access
- ngrok account (for local development)

## Step 1: Install Dependencies

### Create Virtual Environment

```bash
# On macOS/Linux
python3 -m venv venv
source venv/bin/activate

# On Windows
python -m venv venv
venv\Scripts\activate
```

### Install Packages

```bash
pip install -r requirements.txt
```

## Step 2: Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials:

### Required Settings

#### ngrok (for local development)
- `NGROK_AUTHTOKEN`: Get from https://dashboard.ngrok.com/get-started/your-authtoken

#### Teamwork
- `TEAMWORK_BASE_URL`: Your Teamwork domain (e.g., `https://mycompany.teamwork.com`)
- `TEAMWORK_API_KEY`: Get from Teamwork Settings > API & Webhooks

#### Missive
- `MISSIVE_API_TOKEN`: Get from Missive Settings > API

#### Airtable
- `AIRTABLE_API_KEY`: Get from https://airtable.com/create/tokens
- `AIRTABLE_BASE_ID`: Found in your base URL (starts with `app...`)
- `AIRTABLE_EMAILS_TABLE`: Name of your emails table (default: `Emails`)
- `AIRTABLE_TASKS_TABLE`: Name of your tasks table (default: `Tasks`)

## Step 3: Set Up Airtable

Create a new base in Airtable with two tables:

### Emails Table

Create fields:
- **Email ID** (Single line text) - Primary field
- **Thread ID** (Single line text)
- **Subject** (Single line text)
- **From** (Single line text)
- **To** (Long text)
- **Cc** (Long text)
- **Bcc** (Long text)
- **Body Text** (Long text)
- **Body HTML** (Long text)
- **Sent At** (Date)
- **Received At** (Date)
- **Labels** (Multiple select)
- **Deleted** (Checkbox)
- **Deleted At** (Date)
- **Source Links** (Long text)
- **Attachments** (Attachment)

### Tasks Table

Create fields:
- **Task ID** (Single line text) - Primary field
- **Project ID** (Single line text)
- **Title** (Single line text)
- **Description** (Long text)
- **Status** (Single select)
- **Tags** (Multiple select)
- **Assignees** (Long text)
- **Due At** (Date)
- **Updated At** (Date)
- **Deleted** (Checkbox)
- **Deleted At** (Date)
- **Source Links** (Long text)

## Step 4: Test Configuration

```bash
python -m src.settings
```

This will validate your configuration and report any errors.

## Step 5: Run the Application

### For Local Development (with ngrok)

```bash
# On macOS/Linux
./scripts/run_local.sh

# On Windows
python -m src.startup
# Then in separate terminals:
python -m src.app
python -m src.workers.dispatcher
```

The script will:
1. Start ngrok tunnel
2. Display webhook URLs
3. Perform initial backfill
4. Start Flask webhook server
5. Start worker dispatcher

### Configure Webhooks

After starting the application, you'll see webhook URLs like:
```
Teamwork: https://abc123.ngrok.io/webhook/teamwork
Missive:  https://abc123.ngrok.io/webhook/missive
```

#### Configure Teamwork Webhook
1. Go to Teamwork Settings > API & Webhooks
2. Click "Add Webhook"
3. Enter the webhook URL
4. Select events: Task created, Task updated, Task deleted
5. Save

#### Configure Missive Webhook
1. Go to Missive Settings > Integrations > Webhooks
2. Click "Add Webhook"
3. Enter the webhook URL
4. Select events: Conversation created, Message received, Conversation updated
5. Save

## Step 6: Monitor

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

## Production Deployment

For production deployment without ngrok:

1. Deploy to a server with a public IP or domain
2. Update webhook URLs to point to your server
3. Remove `NGROK_AUTHTOKEN` from `.env`
4. Run:
   ```bash
   ./scripts/run_worker_only.sh
   ```

Or use a process manager like systemd or supervisor.

## Switching to PostgreSQL

1. Set up PostgreSQL database
2. Update `.env`:
   ```
   DB_BACKEND=postgres
   PG_DSN=postgresql://user:password@localhost:5432/dbname
   ```
3. Restart the application

The tables will be created automatically on first run.

## Troubleshooting

### Webhooks not arriving
- Check ngrok tunnel is active: `http://localhost:4040`
- Verify webhook URLs in Teamwork/Missive settings
- Check Flask app logs

### Queue not processing
- Check worker is running: `ps aux | grep dispatcher`
- Check worker logs in `logs/app.log`
- Inspect queue file: `cat data/queue/inbox.jsonl`

### Database errors
- Verify API keys in `.env`
- Check Airtable base ID and table names
- Ensure tables exist with correct field names

### Rate limiting
The connectors implement automatic retry with exponential backoff. If you hit rate limits frequently, check your API usage.

