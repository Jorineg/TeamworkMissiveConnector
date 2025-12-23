# Architecture Documentation

This document describes the architecture of the Teamwork & Missive Connector system.

## High-Level Architecture

### Webhook Mode (Default - DISABLE_WEBHOOKS=false)

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│  Teamwork   │       │   Missive   │       │    Craft    │
│  Webhooks   │       │  Webhooks   │       │   (Poll)    │
└──────┬──────┘       └──────┬──────┘       └──────┬──────┘
       │                     │                     │
       │    ┌─────────┐      │                     │
       └────►  ngrok  ◄──────┘                     │
            └────┬────┘                            │
                 │                                 │
         ┌───────▼────────┐                        │
         │  Flask App     │◄───────────────────────┘
         │  (Webhooks)    │◄────┐
         └───────┬────────┘     │
                 │               │ Periodic
         ┌───────▼────────┐     │ Backfill
         │ PostgreSQL     │     │ (60s)
         │ Queue          │     │
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
         │   PostgreSQL   │
         │   Database     │
         └────────────────┘
```

### Polling-Only Mode (DISABLE_WEBHOOKS=true)

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│  Teamwork   │       │   Missive   │       │    Craft    │
│     API     │       │     API     │       │     API     │
└──────▲──────┘       └──────▲──────┘       └──────▲──────┘
       │                     │                     │
       │   Periodic Polling  │                     │
       │      (5s default)   │                     │
       │                     │                     │
   ┌───┴─────────────────────┴─────────────────────┴───┐
   │              Periodic Backfill Timer              │
   └───────────────────────┬───────────────────────────┘
                           │
                   ┌───────▼────────┐
                   │ PostgreSQL     │
                   │ Queue          │
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
                   │   PostgreSQL   │
                   │   Database     │
                   └────────────────┘
```

## Operation Modes

### 1. Webhook Mode (Default)
**Configuration**: `DISABLE_WEBHOOKS=false` (default)

**How it works**:
- ngrok tunnel provides public URL for local development
- Webhooks automatically configured in Teamwork and Missive
- Real-time event notifications arrive immediately
- Periodic backfill runs every 60 seconds (default) as safety net

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

**Advantages**:
- No public URL or webhook setup required
- Works behind strict firewalls
- Simpler deployment (no ngrok needed)

**Trade-offs**:
- Higher API rate limit usage
- Updates delayed by polling interval (5s default)
- More frequent API calls

## Components

### 1. Webhook Receivers (`src/app.py`)

**Purpose**: Receive and validate incoming webhooks from Teamwork and Missive.

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
- Resilient: Automatic database reconnection

### 2. PostgreSQL Queue (`src/queue/postgres_queue.py`)

**Purpose**: Reliable, crash-safe event queue stored in PostgreSQL.

**Implementation**:
- Table: `teamworkmissiveconnector.queue_items`
- Status tracking: pending → processing → completed/failed
- Batch dequeue for efficiency
- Automatic retry with failure tracking

**Guarantees**:
- At-least-once delivery
- Survives crashes
- No events lost
- Transactional consistency

### 3. Worker Dispatcher (`src/workers/dispatcher.py`)

**Purpose**: Process queued events in the background.

**Responsibilities**:
- Dequeue items in batches
- Route to appropriate handler
- Mark items completed/failed
- Handle database reconnection

**Key Features**:
- Single-threaded (sufficient for load)
- Graceful shutdown on SIGINT/SIGTERM
- Continuous processing loop
- Database resilience with automatic reconnect

### 4. Event Handlers

#### Teamwork Handler (`src/workers/handlers/teamwork_events.py`)

**Purpose**: Parse and normalize Teamwork events.

**Responsibilities**:
- Extract task ID from various payload formats
- Fetch full task data from API with included resources
- Upsert related entities (companies, users, teams, tags, projects, tasklists)
- Parse task fields (tags, assignees, dates)
- Handle deletion events
- Convert to canonical `Task` model

#### Missive Handler (`src/workers/handlers/missive_events.py`)

**Purpose**: Parse and normalize Missive events.

**Responsibilities**:
- Extract conversation/message IDs
- Fetch full conversation and message data
- Parse email fields (addresses, body, attachments)
- Handle deletion/trash events
- Process comments
- Convert to canonical `Email` model

#### Craft Handler (`src/workers/handlers/craft_events.py`)

**Purpose**: Parse and sync Craft documents.

**Responsibilities**:
- Fetch document content as markdown
- Handle document metadata
- Upsert to `craft_documents` table

### 5. API Clients

#### Teamwork Client (`src/connectors/teamwork_client.py`)

**Features**:
- HTTP Basic Auth
- Pagination support
- Rate limit handling (429 → retry with backoff)
- Server error retry (5xx → exponential backoff)
- Fetch tasks with included resources

#### Missive Client (`src/connectors/missive_client.py`)

**Features**:
- Bearer token auth
- Cursor-based pagination
- Rate limit handling
- Server error retry
- Fetch conversations, messages, comments

#### Craft Client (`src/connectors/craft_client.py`)

**Features**:
- Multi-Document API support
- Markdown content retrieval
- Metadata fetching
- No webhooks (polling only)

### 6. Database Implementation (`src/db/postgres_impl.py`)

**Purpose**: PostgreSQL-specific database operations.

**Features**:
- Upsert operations for all entity types
- Relational structure with proper foreign keys
- Junction table management (tags, assignees)
- Checkpoint storage
- Connection resilience

**Schema**: Uses `teamwork`, `missive`, `teamworkmissiveconnector`, and `public` schemas.

### 7. Startup & Backfill (`src/startup.py`)

**Purpose**: Initialize system and catch up on missed events.

**Responsibilities**:
- Start ngrok tunnel (local dev)
- Display webhook URLs
- Perform backfill for all sources (Teamwork, Missive, Craft)

**Backfill Logic**:
1. Load last checkpoint (timestamp)
2. Subtract overlap window (default 120s) to handle clock skew
3. Fetch all items updated since overlap time
4. Enqueue each item
5. Update checkpoint with latest timestamp

**First Run**: If no checkpoint exists, backfill based on `*_PROCESS_AFTER` settings or defaults.

## Data Flow

### Webhook Event Flow

1. **Receive**: Teamwork/Missive → ngrok → Flask app
2. **Validate**: Check signature (if configured)
3. **Enqueue**: Insert into `queue_items` table
4. **Respond**: Return 200 OK to webhook sender
5. **Dequeue**: Worker reads from queue
6. **Route**: Dispatcher routes to handler
7. **Parse**: Handler normalizes event data
8. **Enrich**: Fetch full object from API if needed
9. **Store**: Upsert to database tables
10. **Complete**: Mark queue item as completed

### Backfill Flow

1. **Start**: Application startup or periodic timer
2. **Load**: Get last checkpoint from database
3. **Fetch**: API query for items updated since checkpoint - overlap
4. **Enqueue**: Each item added to queue
5. **Process**: Normal queue processing handles items
6. **Update**: Save new checkpoint after API success

## Reliability Features

### Idempotency
- All database writes use upserts keyed by external ID
- Safe to process same event multiple times
- Safe to receive duplicate webhooks

### At-Least-Once Delivery
- Queue items marked completed only after successful processing
- Crash during processing → item reprocessed on restart

### Overlap Window
- Backfill queries "since X - 120s" to handle:
  - Clock skew between systems
  - Race conditions (webhook arrives before API reflects change)
  - Network delays

### Database Resilience
- Lazy connection initialization
- Automatic reconnection on failure
- Exponential backoff for retries
- Health check endpoint reports database status

### Graceful Shutdown
- SIGINT/SIGTERM → finish current item, then exit
- No partial writes
- Clean queue state

## Performance Characteristics

### Expected Load
- ~30 emails/hour (Missive)
- ~60 task changes/hour (Teamwork)
- **Total: ~90 events/hour = ~1.5 events/minute**

### Resource Usage
- **CPU**: Very low (mostly I/O bound)
- **Memory**: ~50-100 MB
- **Network**: Minimal (only when processing events)

## Configuration

### Environment Variables

See [ENV_VARIABLES.md](ENV_VARIABLES.md) for complete reference.

**Key Settings**:
- `PG_DSN`: PostgreSQL connection string (required)
- `DISABLE_WEBHOOKS`: `true` for polling-only mode
- `PERIODIC_BACKFILL_INTERVAL`: Polling interval in seconds
- `BACKFILL_OVERLAP_SECONDS`: Overlap window (default: 120)

### Database Schema

**teamworkmissiveconnector schema**:
- `queue_items`: Event queue with status tracking
- `checkpoints`: Last sync timestamp per source
- `webhook_config`: Registered webhook IDs for cleanup

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
- Optional: Better Stack cloud logging

### Health Check
- `GET /health` endpoint
- Returns queue size, database status, and timestamp

### Queue Inspection
```bash
python scripts/check_queue.py
```

### Manual Operations
- Backfill: `python scripts/manual_backfill.py`
- Check logs: `tail -f logs/app.log`
