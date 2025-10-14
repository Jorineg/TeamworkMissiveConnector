# ✨ Fully Automated Setup

## TL;DR

**Zero manual configuration needed!** Just run:

```bash
python -m src.startup
```

Everything else happens automatically:
- ✅ Airtable tables created
- ✅ Teamwork webhooks configured
- ✅ Missive webhooks configured
- ✅ Auto-updates when ngrok restarts

## What Gets Automated

### 1. Airtable Tables 🗄️

**Creates tables automatically via API:**
- `Emails` table with 16 fields
- `Tasks` table with 12 fields
- All field types correctly configured
- Ready to receive data immediately

**Requirements:**
- Airtable Personal Access Token
- `schema.bases:write` scope
- Base creator role

### 2. Teamwork Webhooks 🔗

**Configures webhooks automatically:**
- Creates/updates webhooks via API
- Subscribes to: task.created, task.updated, task.deleted, task.completed
- Auto-updates URL when ngrok restarts

**Requirements:**
- Teamwork API key
- Pro plan or higher

### 3. Missive Webhooks 📧

**Manages webhooks automatically:**
- Deletes old webhook (from previous run)
- Creates new webhook with current URL
- Stores webhook ID for next deletion
- No duplicate webhooks

**Requirements:**
- Missive API token

## Quick Start

### Step 1: Configure API Keys

```bash
cp .env.example .env
# Edit .env with your API tokens
```

Required in `.env`:
```env
# Airtable
AIRTABLE_API_KEY=patXXXXXXXXXXXXXX
AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX

# Teamwork
TEAMWORK_BASE_URL=https://yourcompany.teamwork.com
TEAMWORK_API_KEY=tkn.v1_XXXXXXXX

# Missive
MISSIVE_API_TOKEN=XXXXXXXX

# ngrok (for local dev)
NGROK_AUTHTOKEN=XXXXXXXX
```

### Step 2: Run

```bash
python -m src.startup
```

### Step 3: Done! ✨

Watch the logs as everything gets configured automatically.

## What You'll See

```
2025-10-14 23:49:35 - INFO - Checking Airtable tables...
2025-10-14 23:49:35 - INFO - Creating table: Emails
2025-10-14 23:49:36 - INFO - ✓ Created table 'Emails'
2025-10-14 23:49:36 - INFO - Creating table: Tasks
2025-10-14 23:49:37 - INFO - ✓ Created table 'Tasks'
2025-10-14 23:49:37 - INFO - ✓ Airtable setup complete

2025-10-14 23:49:38 - INFO - Starting ngrok tunnel on port 5000...
2025-10-14 23:49:40 - INFO - ✓ ngrok tunnel established: https://abc123.ngrok-free.app

2025-10-14 23:49:41 - INFO - Configuring Teamwork webhooks...
2025-10-14 23:49:42 - INFO - ✓ Created webhook for event: task.created
2025-10-14 23:49:42 - INFO - ✓ Created webhook for event: task.updated
2025-10-14 23:49:42 - INFO - ✓ Created webhook for event: task.deleted
2025-10-14 23:49:42 - INFO - ✓ Created webhook for event: task.completed
2025-10-14 23:49:42 - INFO - ✓ Teamwork webhooks configured successfully

2025-10-14 23:49:43 - INFO - Configuring Missive webhook...
2025-10-14 23:49:43 - INFO - Deleting old Missive webhook: d75aecb6-96a2-4b5f-afa6-19d1916052ea
2025-10-14 23:49:44 - INFO - ✓ Deleted old Missive webhook
2025-10-14 23:49:44 - INFO - ✓ Created Missive webhook for event: incoming_email
2025-10-14 23:49:44 - INFO - ✓ Missive webhook configured successfully

2025-10-14 23:49:45 - INFO - Starting backfill operation...
2025-10-14 23:49:46 - INFO - Found 3 Teamwork tasks to backfill
2025-10-14 23:49:47 - INFO - Found 0 Missive conversations to backfill
2025-10-14 23:49:47 - INFO - ✓ Backfill operation completed

2025-10-14 23:49:47 - INFO - Startup operations completed successfully
2025-10-14 23:49:47 - INFO - Keep this process running to maintain ngrok tunnel
```

## API Token Setup

### Airtable Personal Access Token

1. Go to: https://airtable.com/create/tokens
2. Click "Create new token"
3. Name it: "Teamwork Missive Connector"
4. Add scope: `schema.bases:write` (to create tables)
5. Add scope: `data.records:write` (to write records)
6. Add scope: `data.records:read` (to read records)
7. Select your base
8. Click "Create token"
9. Copy and paste into `.env` as `AIRTABLE_API_KEY`

### Teamwork API Key

1. Go to your Teamwork site: Settings > API & Webhooks
2. Copy your API key
3. Paste into `.env` as `TEAMWORK_API_KEY`

### Missive API Token

1. Go to: https://mail.missiveapp.com/#settings/api
2. Click "Generate API token"
3. Copy and paste into `.env` as `MISSIVE_API_TOKEN`

### ngrok Auth Token

1. Go to: https://dashboard.ngrok.com/get-started/your-authtoken
2. Copy your authtoken
3. Paste into `.env` as `NGROK_AUTHTOKEN`

## Technical Details

### How Missive Webhook Management Works

**Problem:** ngrok URL changes on every restart, webhooks become stale.

**Solution:** Delete-and-recreate pattern:

1. On startup, load stored webhook ID from `data/missive_webhook_id.json`
2. If ID exists, delete that webhook via `DELETE /v1/hooks/{id}`
3. Create new webhook with current URL via `POST /v1/hooks`
4. Store new webhook ID for next run
5. Result: Always exactly one active webhook, always pointing to current URL

**Why not update?**
- Missive API doesn't support webhook URL updates (no PUT endpoint)
- Delete + create is the recommended pattern

### Airtable Table Schema

**Emails Table:**
- Email ID, Thread ID, Subject
- From, To, Cc, Bcc
- Body Text, Body HTML
- Sent At, Received At
- Labels (multiple select)
- Deleted (checkbox), Deleted At
- Source Links
- Attachments

**Tasks Table:**
- Task ID, Project ID
- Title, Description
- Status (single select), Tags (multiple select)
- Assignees, Due At, Updated At
- Deleted (checkbox), Deleted At
- Source Links

## Comparison

| Setup Step | Manual | Automated |
|------------|--------|-----------|
| Create Airtable tables | 15+ clicks per table | **0 clicks** |
| Configure all fields | 30+ field configurations | **0 configurations** |
| Setup Teamwork webhooks | 10+ clicks | **0 clicks** |
| Setup Missive webhooks | 8+ clicks | **0 clicks** |
| Update on ngrok restart | Update both manually | **Auto-updates** |
| **Total time** | **~30 minutes** | **~10 seconds** |

## Troubleshooting

### Airtable: "Permission denied"
- Check your token has `schema.bases:write` scope
- Ensure you're the base creator

### Teamwork: Webhooks fail with 404
- Webhooks API requires Pro plan or higher
- Fallback: Manual instructions printed

### Missive: Webhook creation fails
- Verify API token is valid
- Check token hasn't expired

### ngrok: Tunnel fails to start
- Verify `NGROK_AUTHTOKEN` in `.env`
- Check ngrok service status

## Production Deployment

For production (stable URL, no ngrok):

1. Remove `NGROK_AUTHTOKEN` from `.env`
2. Set up webhooks once with your production URL:
   - Teamwork: API creates them
   - Missive: API creates them
3. Webhooks remain stable (no URL changes)
4. No need to delete/recreate

## Files Created

The automation stores state in:

- `data/missive_webhook_id.json` - Missive webhook ID for deletion
- `data/checkpoints/teamwork.json` - Last synced timestamp
- `data/checkpoints/missive.json` - Last synced timestamp
- `data/queue/inbox.jsonl` - Event queue
- `logs/app.log` - Application logs

## Summary

**Before:** 30+ minutes of manual clicking and configuration.

**After:** One command, 10 seconds, fully automated. ✨

**No manual steps. No UI navigation. No copy-paste. Just works.**

---

See `docs/automated_setup.md` for detailed technical documentation.

