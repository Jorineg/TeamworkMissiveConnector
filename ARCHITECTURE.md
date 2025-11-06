# Architecture Documentation

This document describes the architecture of the Teamwork & Missive Connector system.

## High-Level Architecture

### Webhook Mode (Default - DISABLE_WEBHOOKS=false)

```
┌─────────────┐       ┌─────────────┐
│  Teamwork   │       │   Missive   │
│  Webhooks   │       │  Webhooks   │
└──────┬──────┘       └──────┬──────┘
       │                     │
       │    ┌─────────┐      │
       └────►  ngrok  ◄──────┘
            └────┬────┘
                 │
         ┌───────▼────────┐
         │  Flask App     │
         │  (Webhooks)    │◄────┐
         └───────┬────────┘     │
                 │               │ Periodic
         ┌───────▼────────┐     │ Backfill
         │  Spool Queue   │     │ (60s)
         │ (Persistent)   │     │
         └───────┬────────┘     │
                 │          ┌───┴────┐
         ┌───────▼────────┐ │ Timer  │
         │    Worker      │ └───┬────┘
         │  Dispatcher    │◄────┘
         └───────┬────────┘
                 │
         ┌───────▼────────┐
         │   Handlers     │
         │ (Parse/Enrich) │
         └───────┬────────┘
                 │
         ┌───────▼────────┐
         │   Database     │
         │  (Airtable/PG) │
         └────────────────┘
```

### Polling-Only Mode (DISABLE_WEBHOOKS=true)

```
┌─────────────┐       ┌─────────────┐
│  Teamwork   │       │   Missive   │
│     API     │       │     API     │
└──────▲──────┘       └──────▲──────┘
       │                     │
       │                     │
       │   Periodic Polling  │
       │      (5s default)   │
       │                     │
   ┌───┴─────────────────────┴───┐
   │      Periodic Backfill      │
   │          Timer              │
   └───────────┬─────────────────┘
               │
       ┌───────▼────────┐
       │  Spool Queue   │
       │ (Persistent)   │
       └───────┬────────┘
               │
       ┌───────▼────────┐
       │    Worker      │
       │  Dispatcher    │
       └───────┬────────┘
               │
       ┌───────▼────────┐
       │   Handlers     │
       │ (Parse/Enrich) │
       └───────┬────────┘
               │
       ┌───────▼────────┐
       │   Database     │
       │  (Airtable/PG) │
       └────────────────┘
```

## Operation Modes

The system supports two operation modes:

### 1. Webhook Mode (Default)
**Configuration**: `DISABLE_WEBHOOKS=false` (default)

**How it works**:
- ngrok tunnel provides public URL for local development
- Webhooks automatically configured in Teamwork and Missive
- Real-time event notifications arrive immediately
- Periodic backfill runs every 60 seconds (default) as safety net
- Best for: Real-time synchronization, production environments

**Advantages**:
- Near-instant updates (events arrive within seconds)
- Lower API rate limit usage
- More efficient than constant polling
- Redundancy with periodic backfill backup

**Requirements**:
- Public URL (ngrok for local dev, or actual domain for production)
- Webhook support from Teamwork and Missive
- Open inbound network connection

### 2. Polling-Only Mode
**Configuration**: `DISABLE_WEBHOOKS=true`

**How it works**:
- No ngrok tunnel or webhooks configured
- Periodic polling queries APIs every 5 seconds (default)
- Checkpoint-based incremental fetching
- Overlap window prevents missed events
- Best for: Testing, firewalled environments, simple deployments

**Advantages**:
- No public URL or webhook setup required
- Works behind strict firewalls
- Simpler deployment (no ngrok needed)
- Still reliable with frequent polling

**Trade-offs**:
- Higher API rate limit usage
- Updates delayed by polling interval (5s default)
- More frequent API calls

**Recommended Settings**:
```env
DISABLE_WEBHOOKS=true
PERIODIC_BACKFILL_INTERVAL=5  # Adjust based on needs (1-60 seconds)
```

## Components

### 1. Webhook Receivers (`src/app.py`)

**Purpose**: Receive and validate incoming webhooks from Teamwork and Missive (when webhooks are enabled).

**Responsibilities**:
- Accept HTTP POST requests
- Verify webhook signatures (if configured)
- Extract event metadata
- Enqueue events immediately
- Return 200 OK quickly to avoid timeouts

**Key Features**:
- Non-blocking: Events are queued, not processed synchronously
- Idempotent: Safe to receive duplicate events
- Fast: Minimal processing in webhook handler
- Optional: Can be completely disabled for polling-only mode

### 2. Persistent Queue (`src/queue/spool_queue.py`)

**Purpose**: Reliable, crash-safe event queue with minimal complexity.

**Implementation**:
- Spool directories: `data/queue/spool/{teamwork,missive}/`
- One file per event ID: `<id>.evt`
- On failure: rename to `<id>.retry` and retry after `SPOOL_RETRY_SECONDS`
- Natural dedup via exclusive file creation

**Guarantees**:
- At-least-once delivery
- FIFO ordering within a source
- Survives crashes
- No events lost

### 3. Worker Dispatcher (`src/workers/dispatcher.py`)

**Purpose**: Process queued events in the background.

**Responsibilities**:
- Read from queue
- Route to appropriate handler
- Retry on failures with exponential backoff
- Move poison messages to DLQ after max attempts
- Update processing offset after success

**Key Features**:
- Single-threaded (sufficient for load)
- Graceful shutdown on SIGINT/SIGTERM
- Continuous processing loop

### 4. Event Handlers

#### Teamwork Handler (`src/workers/handlers/teamwork_events.py`)

**Purpose**: Parse and normalize Teamwork events.

**Responsibilities**:
- Extract task ID from various payload formats
- Fetch full task data from API if needed
- Parse task fields (tags, assignees, dates)
- Handle deletion events
- Convert to canonical `Task` model

#### Missive Handler (`src/workers/handlers/missive_events.py`)

**Purpose**: Parse and normalize Missive events.

**Responsibilities**:
- Extract conversation/message IDs
- Fetch full message data if needed
- Parse email fields (addresses, body, attachments)
- Handle deletion/trash events
- Convert to canonical `Email` model
- Process attachments

### 5. API Clients

#### Teamwork Client (`src/connectors/teamwork_client.py`)

**Features**:
- HTTP Basic Auth
- Pagination support
- Rate limit handling (429 → retry with backoff)
- Server error retry (5xx → exponential backoff)
- Fetch tasks updated since timestamp
- Include completed tasks (controlled by `include_completed` parameter)

#### Missive Client (`src/connectors/missive_client.py`)

**Features**:
- Bearer token auth
- Cursor-based pagination
- Rate limit handling
- Server error retry
- Fetch conversations updated since timestamp
- Download attachments

### 6. Database Abstraction (`src/db/`)

**Purpose**: Unified interface for multiple database backends.

**Interface** (`src/db/interface.py`):
```python
- upsert_email(email: Email)
- upsert_task(task: Task)
- mark_email_deleted(email_id: str)
- mark_task_deleted(task_id: str)
- get_checkpoint(source: str)
- set_checkpoint(checkpoint: Checkpoint)
```

**Implementations**:
- **Airtable** (`airtable_impl.py`): Uses pyairtable, caches record IDs
- **PostgreSQL** (`postgres_impl.py`): Uses psycopg2, creates tables automatically

**Switching databases**: Change `DB_BACKEND` in `.env`, restart application.

### 7. Startup & Backfill (`src/startup.py`)

**Purpose**: Initialize system and catch up on missed events.

**Responsibilities**:
- Start ngrok tunnel (local dev)
- Display webhook URLs
- Perform backfill for both sources
- Maintain ngrok tunnel

**Backfill Logic**:
1. Load last checkpoint (timestamp + cursor)
2. Subtract overlap window (default 120s) to handle clock skew
3. Fetch all items updated since overlap time
4. Enqueue each item
5. Update checkpoint with latest timestamp

**First Run**: If no checkpoint exists, backfill last 24 hours.

## Data Flow

### Webhook Event Flow

1. **Receive**: Teamwork/Missive → ngrok → Flask app
2. **Validate**: Check signature (if configured)
3. **Enqueue**: Create `<id>.evt` in `data/queue/spool/{source}/`
4. **Respond**: Return 200 OK to webhook sender
5. **Dequeue**: Worker reads from queue
6. **Route**: Dispatcher routes to handler (Teamwork/Missive)
7. **Parse**: Handler normalizes event data
8. **Enrich**: Fetch full object from API if needed
9. **Store**: Upsert to database via interface
10. **Checkpoint**: Update last processed timestamp
11. **Advance**: Worker advances queue offset

### Backfill Flow

1. **Start**: Application startup or manual trigger
2. **Load**: Get last checkpoint from database
3. **Fetch**: API query for items updated since checkpoint - overlap
4. **Enqueue**: Each item added to queue
5. **Process**: Normal queue processing handles items
6. **Update**: Save new checkpoint after processing

## Reliability Features

### Idempotency
- All database writes use upserts keyed by external ID
- Safe to process same event multiple times
- Safe to receive duplicate webhooks

### At-Least-Once Delivery
- Queue persisted to disk with fsync
- Offset only advanced after successful processing
- Crash during processing → item reprocessed on restart

### Overlap Window
- Backfill queries "since X - 120s" to handle:
  - Clock skew between systems
  - Race conditions (webhook arrives before API reflects change)
  - Network delays

### Retry Logic
- Failures rename to `.retry` and are retried approximately every `SPOOL_RETRY_SECONDS`
- No DLQ; failures remain visible and reattempted periodically

### Graceful Shutdown
- SIGINT/SIGTERM → finish current item, then exit
- No partial writes
- Clean offset state

## Performance Characteristics

### Expected Load
- ~30 emails/hour (Missive)
- ~60 task changes/hour (Teamwork)
- **Total: ~90 events/hour = ~1.5 events/minute**

### Resource Usage
- **CPU**: Very low (mostly I/O bound)
- **Memory**: ~50-100 MB
- **Disk**: Queue files grow slowly, compact automatically
- **Network**: Minimal (only when processing events)

### Scalability
Current implementation is single-threaded and single-process, which is more than sufficient for the expected load. If load increases 100x, consider:
- Multi-process workers reading from same queue
- Redis or RabbitMQ instead of file queue
- Database connection pooling
- Async I/O for API calls

## Configuration

### Environment Variables

**Key Settings**:
- `DB_BACKEND`: `airtable` or `postgres`
- `DISABLE_WEBHOOKS`: `true` or `false` (default: `false`)
  - When `true`: No webhooks or ngrok tunnel, relies solely on periodic polling
  - When `false`: Standard webhook-based operation with periodic backfill as backup
- `PERIODIC_BACKFILL_INTERVAL`: Polling interval in seconds
  - Default: `5` seconds when `DISABLE_WEBHOOKS=true`
  - Default: `60` seconds when `DISABLE_WEBHOOKS=false`
  - Can be overridden manually for custom intervals
- `MAX_QUEUE_ATTEMPTS`: Retry count before DLQ (default: 3)
- `BACKFILL_OVERLAP_SECONDS`: Overlap window (default: 120)
- `LOG_LEVEL`: `DEBUG`, `INFO`, `WARNING`, `ERROR`

### Checkpoints
Stored in `data/checkpoints/{source}.json`:
```json
{
  "source": "teamwork",
  "last_event_time": "2025-10-14T12:34:56.789Z",
  "last_cursor": null
}
```

### Spool Queue Files
- `data/queue/spool/teamwork/*.evt`: Pending Teamwork events
- `data/queue/spool/teamwork/*.retry`: Failed Teamwork events (will retry)
- `data/queue/spool/missive/*.evt`: Pending Missive events
- `data/queue/spool/missive/*.retry`: Failed Missive events (will retry)

## Security

### Webhook Verification
- HMAC signature verification (if secrets configured)
- Signature mismatches rejected with 401

### Credentials
- All secrets in environment variables
- Never logged or committed to git
- `.env` in `.gitignore`

### Network
- ngrok provides HTTPS automatically
- API clients enforce TLS

## Monitoring

### Logs
- JSON format in `logs/app.log`
- Structured fields: timestamp, level, source, event_id
- Console output: human-readable

### Health Check
- `GET /health` endpoint
- Returns queue size and status

### Queue Inspection
```bash
python scripts/check_queue.py
```

### Manual Operations
- Backfill: `python scripts/manual_backfill.py`
- Check logs: `tail -f logs/app.log`
- Inspect queue: `ls -la data/queue/spool/*/`
- Check queue status: `python scripts/check_queue.py`

## Future Enhancements

### Possible Improvements
1. **Metrics**: Add Prometheus metrics for queue depth, processing rate, errors
2. **Alerting**: Notify on DLQ items or processing failures
3. **Dashboard**: Web UI for queue status and recent events
4. **Async Processing**: Use `asyncio` for concurrent API calls
5. **Batch Processing**: Group database writes for efficiency
6. **Attachment Storage**: Upload Missive attachments to S3 before Airtable
7. **Webhook Registration**: Auto-register webhooks via API
8. **Health Monitoring**: Periodic health checks of services

### Migration to Production
1. Deploy on persistent server (not local laptop)
2. Use systemd/supervisor for process management
3. Set up log rotation
4. Configure monitoring/alerting
5. Use production database (PostgreSQL recommended)
6. Remove ngrok, use direct HTTPS endpoint
7. Set up backup/restore procedures

