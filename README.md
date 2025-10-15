# Teamwork & Missive Connector

A reliable Python-based connector system that synchronizes data from Teamwork (tasks) and Missive (emails) into your database (Airtable initially, with PostgreSQL support for future migration).

## Features

- **Webhook-based real-time sync** for Teamwork tasks and Missive emails
- **Startup backfill** to catch missed events during downtime
- **Persistent queue** (spool-based) ensures no events are lost
- **Attachment handling** from Missive emails (uploads to Airtable)
- **Soft deletion** support with `deleted` flag
- **Database abstraction** for easy migration from Airtable to PostgreSQL
- **Local ngrok support** for webhook testing

## Project Structure

```
TeamworkMissiveConnector/
├── src/
│   ├── app.py                      # Flask webhook endpoints
│   ├── settings.py                 # Configuration management
│   ├── logging_conf.py             # Logging setup
│   ├── startup.py                  # ngrok tunnel & backfill
│   ├── queue/
│   │   ├── spool_queue.py          # Spool directory queue implementation
│   │   └── models.py               # Queue item schemas
│   ├── workers/
│   │   ├── dispatcher.py           # Queue processor & retry logic
│   │   └── handlers/
│   │       ├── missive_events.py   # Missive event handler
│   │       └── teamwork_events.py  # Teamwork event handler
│   ├── connectors/
│   │   ├── missive_client.py       # Missive API client
│   │   └── teamwork_client.py      # Teamwork API client
│   ├── db/
│   │   ├── interface.py            # Abstract database interface
│   │   ├── airtable_impl.py        # Airtable implementation
│   │   ├── postgres_impl.py        # PostgreSQL implementation
│   │   └── models.py               # Domain models
│   └── http/
│       └── security.py             # Webhook verification
├── scripts/
│   └── run_local.sh                # Development runner
├── data/                           # Queue & checkpoints (created at runtime)
├── logs/                           # Application logs (created at runtime)
├── .env.example
├── requirements.txt
└── README.md
```

## Setup

### 1. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys and settings
```

### 3. Set Up Airtable

Create two tables in your Airtable base:

**Emails Table:**
- Email ID (Single line text, Primary)
- Thread ID (Single line text)
- Subject (Single line text)
- From (Single line text)
- To (Long text)
- Cc (Long text)
- Bcc (Long text)
- Body Text (Long text)
- Body HTML (Long text)
- Sent At (Date)
- Received At (Date)
- Labels (Multiple select)
- Deleted (Checkbox)
- Deleted At (Date)
- Source Links (Long text)
- Attachments (Attachment)

**Tasks Table:**
- Task ID (Single line text, Primary)
- Project ID (Single line text)
- Title (Single line text)
- Description (Long text)
- Status (Single select)
- Tags (Multiple select)
- Assignees (Long text)
- Due At (Date)
- Updated At (Date)
- Deleted (Checkbox)
- Deleted At (Date)
- Source Links (Long text)

### 4. Configure Webhooks

#### For Local Development (with ngrok):

```bash
# Run the application
./scripts/run_local.sh
```

The script will:
1. Start ngrok tunnel
2. Print webhook URLs
3. Start the Flask app and worker

Copy the webhook URLs and configure them in:
- **Teamwork**: Settings > API & Webhooks > Add Webhook
- **Missive**: Settings > Integrations > Webhooks > Add Webhook

#### For Production Deployment:

Update the `.env` file with your production domain and skip ngrok setup.

## Usage

### Run Locally

```bash
./scripts/run_local.sh
```

Or manually:

```bash
# Terminal 1: Run Flask app
python -m src.app

# Terminal 2: Run worker
python -m src.workers.dispatcher
```

### Monitor

Check logs in `logs/app.log` for activity and errors.

## Database Migration (Airtable → PostgreSQL)

1. Create PostgreSQL tables using the schema in `src/db/postgres_impl.py`
2. Update `.env`: `DB_BACKEND=postgres`
3. Set `PG_DSN` with your connection string
4. Restart the application

## Architecture

### Webhook Flow
1. Teamwork/Missive sends webhook → Flask endpoint
2. Endpoint validates & enqueues event → Spool queue (one file per ID)
3. Worker dequeues → processes → stores in DB
4. Checkpoint updated

### Startup Backfill
1. Read last checkpoint (timestamp + ID)
2. Query API for items changed since checkpoint - overlap
3. Enqueue all items
4. Process normally

### Reliability Features
- **Idempotent upserts** using external IDs
- **Persistent queue** with fsync
- **Retry logic** with exponential backoff
- **Dead letter queue** for poison messages
- **Overlap window** to handle clock skew

## API Rate Limits

- **Teamwork**: 200 requests/minute (more than sufficient for your volume)
- **Missive**: Generous limits, well above 30 emails/hour
- Both connectors implement exponential backoff on rate limit errors

## Troubleshooting

### Webhooks not arriving
- Check ngrok tunnel is active: `http://localhost:4040`
- Verify webhook URLs in Teamwork/Missive settings
- Check Flask app logs

### Queue not processing
- Check worker is running: `ps aux | grep dispatcher`
- Check worker logs in `logs/app.log`
- Inspect spool: `dir data/queue/spool/*`

### Database errors
- Verify API keys in `.env`
- Check Airtable base ID and table names
- Ensure tables exist with correct field names

## License

MIT

