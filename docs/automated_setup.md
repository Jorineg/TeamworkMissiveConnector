# Automated Setup Features

This document describes the automated setup features that make deployment easier.

## Overview

The connector now includes **fully automated setup**:

1. ✅ **Airtable table creation** - Automatically creates tables via API
2. ✅ **Teamwork webhook automation** - Automatically creates/updates webhooks via API
3. ✅ **Missive webhook automation** - Automatically creates webhooks via API (deletes old on restart)

## How It Works

When you run `python -m src.startup`, the system automatically:

### 1. Creates Airtable Tables

**What it does:**
- Checks if the Emails and Tasks tables exist in your Airtable base
- **Automatically creates them via API if they don't exist**
- Creates all required fields with correct types

**Success output:**
```
2025-10-14 23:49:35 - INFO - Checking Airtable tables...
2025-10-14 23:49:35 - INFO - Creating table: Emails
2025-10-14 23:49:36 - INFO - ✓ Created table 'Emails'
2025-10-14 23:49:36 - INFO - Creating table: Tasks
2025-10-14 23:49:37 - INFO - ✓ Created table 'Tasks'
2025-10-14 23:49:37 - INFO - ✓ Airtable setup complete
```

**API Requirements:**
- Personal access token with `schema.bases:write` scope
- Base creator role
- Available on all Airtable plans

### 2. Configures Teamwork Webhooks

**What it does:**
- Automatically retrieves the ngrok public URL
- Checks for existing Teamwork webhooks
- Creates new webhooks or updates existing ones
- Subscribes to these events:
  - `task.created`
  - `task.updated`
  - `task.deleted`
  - `task.completed`

**Success output:**
```
2025-10-14 23:49:35 - INFO - Setting up Teamwork webhooks to: https://abc123.ngrok-free.app/webhook/teamwork
2025-10-14 23:49:36 - INFO - ✓ Created webhook for event: task.created
2025-10-14 23:49:36 - INFO - ✓ Created webhook for event: task.updated
2025-10-14 23:49:36 - INFO - ✓ Created webhook for event: task.deleted
2025-10-14 23:49:36 - INFO - ✓ Created webhook for event: task.completed
2025-10-14 23:49:36 - INFO - ✓ Teamwork webhooks configured successfully
```

**Failure fallback:**
If automatic setup fails (e.g., API not available on your Teamwork plan), it prints manual setup instructions:
```
======================================================================
TEAMWORK WEBHOOK SETUP (Manual)
======================================================================

Automatic setup failed. Please configure manually:

1. Go to: https://yourcompany.teamwork.com/settings/webhooks
2. Click 'Add Webhook'
3. Enter URL: https://abc123.ngrok-free.app/webhook/teamwork
4. Select these events:
   - task.created
   - task.updated
   - task.deleted
   - task.completed
5. Click 'Save'
```

**API Details:**
- Uses Teamwork v1 API: `/projects/api/v1/webhooks.json`
- Requires HTTP Basic Auth with your API key
- Works with Teamwork Pro and higher plans

### 3. Configures Missive Webhooks

**What it does:**
- Checks for existing Missive webhook (stored ID from previous run)
- **Deletes the old webhook** (if exists)
- **Creates a new webhook** with the current ngrok URL
- Stores the webhook ID for next run

**Success output:**
```
2025-10-14 23:49:37 - INFO - Configuring Missive webhook...
2025-10-14 23:49:37 - INFO - Setting up Missive webhook to: https://abc123.ngrok-free.app/webhook/missive
2025-10-14 23:49:37 - INFO - Deleting old Missive webhook: d75aecb6-96a2-4b5f-afa6-19d1916052ea
2025-10-14 23:49:38 - INFO - ✓ Deleted old Missive webhook
2025-10-14 23:49:38 - INFO - ✓ Created Missive webhook for event: incoming_email
2025-10-14 23:49:38 - INFO - ✓ Missive webhook configured successfully
```

**Why delete & recreate:**
- Missive API doesn't support updating webhook URLs
- ngrok URL changes on every restart
- Deleting old webhooks prevents duplicates
- Webhook ID stored in: `data/missive_webhook_id.json`

**API Details:**
- Uses Missive API v1: `/v1/hooks`
- Subscribes to: `incoming_email`
- Stores webhook ID for deletion on next run

## Complete Startup Flow

```
1. Validate configuration (.env)
   ↓
2. Create Airtable tables (if not exist)
   ↓
3. Start ngrok tunnel
   ↓
4. Get public URL
   ↓
5. Configure Teamwork webhooks (automatic)
   ↓
6. Delete old Missive webhook (if exists)
   ↓
7. Create new Missive webhook (automatic)
   ↓
8. Perform backfill (catch missed events)
   ↓
9. Keep running (maintain ngrok tunnel)
```

## API Requirements

### Teamwork API
- **Endpoint**: `GET/POST/PUT /projects/api/v1/webhooks.json`
- **Auth**: HTTP Basic (API key as username)
- **Plan**: Pro or higher (webhooks not available on free tier)
- **Rate Limit**: 200 requests/minute

### Missive API
- **Endpoint**: `POST/DELETE /v1/hooks`
- **Auth**: Bearer token
- **Webhook Creation**: Fully supported ✅
- **Webhook Update**: Not supported (must delete & recreate)
- **ID Storage**: Saved to `data/missive_webhook_id.json`

### Airtable API
- **Endpoint**: `POST /v0/meta/bases/{baseId}/tables`
- **Auth**: Bearer token (Personal access token)
- **Scope Required**: `schema.bases:write`
- **Table Creation**: Fully supported ✅
- **Field Types**: All standard types supported

## Benefits

### Before (Manual Setup)
1. Create Airtable tables manually (15+ clicks)
2. Copy field names exactly (error-prone)
3. Configure Teamwork webhooks in UI
4. Configure Missive webhooks in UI
5. Update webhook URLs every ngrok restart
6. Risk of typos and misconfiguration

### After (Automated Setup)
1. Run `python -m src.startup`
2. **Everything configured automatically** 🎉
3. Airtable tables created ✅
4. Teamwork webhooks configured ✅
5. Missive webhooks configured ✅
6. Automatic updates on ngrok restart ✅

## Troubleshooting

### Airtable verification fails
**Problem:** Table doesn't exist or wrong name
**Solution:** Follow printed instructions to create table via Airtable UI

### Teamwork webhooks fail with 404
**Problem:** Your Teamwork plan doesn't support webhooks API
**Solution:** Follow manual setup instructions printed by the system

### Teamwork webhooks fail with 401
**Problem:** API key invalid or insufficient permissions
**Solution:** Check `TEAMWORK_API_KEY` in `.env`, regenerate if needed

### ngrok URL keeps changing
**Problem:** Each restart generates new URL, webhooks become stale
**Solution:** 
- For development: Re-run startup script (Teamwork auto-updates)
- For production: Use stable domain instead of ngrok

## Production Deployment

For production (without ngrok):

1. Deploy to server with static domain
2. Update `.env` to remove `NGROK_AUTHTOKEN`
3. Set Teamwork webhook URL to: `https://yourdomain.com/webhook/teamwork`
4. Set Missive webhook URL to: `https://yourdomain.com/webhook/missive`
5. Run startup once to verify Airtable
6. Webhooks remain stable (no ngrok restarts)

## Code Structure

```
src/
├── db/
│   └── airtable_setup.py       # Airtable verification & instructions
├── webhooks/
│   ├── teamwork_webhooks.py    # Teamwork webhook automation
│   └── missive_webhooks.py     # Missive manual instructions
└── startup.py                   # Orchestrates all setup
```

## Future Enhancements

Possible improvements:
- [ ] Airtable base template for one-click table creation
- [ ] Webhook health checks and automatic repair
- [ ] Email notification when webhooks fail
- [ ] Dashboard showing webhook status
- [ ] Automatic Missive webhook management if API support is added

## Summary

The automated setup significantly reduces manual configuration:

| Task | Before | After |
|------|--------|-------|
| Airtable tables | Manual creation (15+ clicks) | **Fully automated** ✅ |
| Teamwork webhooks | Manual UI setup | **Fully automated** ✅ |
| Missive webhooks | Manual UI setup | **Fully automated** ✅ |
| ngrok URL updates | Manual update both | **Auto-updates both** ✅ |
| Setup errors | Silent failures | **Clear logging** ✅ |

**Result**: Zero manual setup! Just run one command! 🎉

