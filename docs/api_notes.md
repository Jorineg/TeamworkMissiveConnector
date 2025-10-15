# API Notes and Quirks

This document contains notes about the Teamwork and Missive APIs based on implementation experience.

## Teamwork API

### Base Information
- **Authentication**: HTTP Basic Auth with API key as username (password empty)
- **Base URL**: `https://{your-domain}.teamwork.com`
- **Documentation**: https://developer.teamwork.com/

### API Endpoints Used

#### Get Tasks
- **Endpoint**: `GET /projects/api/v3/tasks.json`
- **Parameters**:
  - `updatedAfter`: ISO 8601 UTC with seconds, e.g. `2025-10-15T22:12:53Z`
  - `includeCompletedTasks`: `true` to include completed/deleted
  - `includeArchivedProjects`: `true` to include tasks from archived projects
  - `page`: Page number (starts at 1)
  - `pageSize`: Items per page (default 50, max 500)

#### Get Single Task
- **Endpoint**: `GET /projects/api/v3/tasks/{taskId}.json`
- **Returns**: Full task details including tags, assignees, dates

### Webhook Events
- `task.created`
- `task.updated`
- `task.deleted`
- `task.completed`

### Field Mappings

| Teamwork Field | Our Model | Notes |
|----------------|-----------|-------|
| `id` | `task_id` | String representation |
| `name` | `title` | Task name/title |
| `description` | `description` | HTML or plain text |
| `status` | `status` | Task status |
| `projectId` | `project_id` | Parent project |
| `tags` | `tags` | Array of tag objects |
| `assignees` | `assignees` | Array of user objects |
| `dueDate` | `due_at` | ISO 8601 datetime |
| `updatedAt` | `updated_at` | ISO 8601 datetime |
| `completed` | `deleted` | We treat completed as soft-deleted |
| `completedAt` | `deleted_at` | When completed/deleted |

### Quirks & Notes

1. **Date Format**:
   - Query param `updatedAfter` accepts ISO 8601 (`YYYY-MM-DDTHH:MM:SSZ`)
   - Responses also use ISO 8601

2. **Completed vs Deleted**:
   - Completed tasks are still accessible but have `completed: true`
   - Hard-deleted tasks may not be retrievable
   - We treat both as `deleted: true` in our model

3. **Tags Format**:
   - Tags are objects with `id`, `name`, `color`
   - We extract just the `name` field

4. **Assignees Format**:
   - Assignees are user objects with `id`, `firstName`, `lastName`, `fullName`
   - We use `fullName` for display

5. **Rate Limits**:
   - 200 requests per minute per IP
   - Response header: `X-RateLimit-Remaining`
   - 429 response includes `Retry-After` header

## Missive API

### Base Information
- **Authentication**: Bearer token
- **Base URL**: `https://public.missiveapp.com/v1`
- **Documentation**: https://missiveapp.com/developer/rest

### API Endpoints Used

#### Get Conversations
- **Endpoint**: `GET /conversations`
- **Parameters**:
  - `updated_after`: Unix timestamp (seconds since epoch)
  - `limit`: Items per page (default 25, max 100)
  - `cursor`: Pagination cursor from previous response

#### Get Conversation Messages
- **Endpoint**: `GET /conversations/{conversationId}/messages`
- **Returns**: All messages in a conversation

### Webhook Events
- `conversation.created`
- `conversation.updated`
- `message.received`
- `message.sent`
- `conversation.trashed`

### Field Mappings

| Missive Field | Our Model | Notes |
|---------------|-----------|-------|
| `id` | `email_id` | Message ID |
| `conversation.id` | `thread_id` | Conversation/thread ID |
| `subject` | `subject` | Email subject |
| `from_field` | `from_address` | Sender email address |
| `to_fields` | `to_addresses` | Array of recipient emails |
| `body` | `body_text` | Plain text body |
| `body_html` | `body_html` | HTML body |
| `delivered_at` | `sent_at` | When email was sent |
| `received_at` | `received_at` | When email was received |
| `labels` | `labels` | Array of label objects |
| `trashed` | `deleted` | Soft-deleted flag |
| `trashed_at` | `deleted_at` | When trashed |
| `attachments` | `attachments` | Array of attachment objects |

### Quirks & Notes

1. **Address Format**:
   - Addresses can be objects: `{name: "John Doe", address: "john@example.com"}`
   - Or just strings: `"john@example.com"`
   - We normalize to always extract the email address

2. **Conversation vs Message**:
   - A conversation contains multiple messages
   - Webhooks may include full message data or just IDs
   - We fetch full message data if not in webhook payload

3. **Attachments**:
   - Attachment URLs may require authentication
   - URLs might be time-limited
   - For Airtable, provide URL directly (Airtable fetches and re-hosts)
   - For PostgreSQL, download and store in S3/similar

4. **Trashed vs Deleted**:
   - `trashed: true` means moved to trash (soft delete)
   - Hard deletes are not exposed via API
   - We treat trashed as deleted

5. **Labels/Tags**:
   - Labels are objects with `id`, `name`, `color`
   - We extract just the `name` field

6. **Rate Limits**:
   - Not explicitly documented
   - Assume reasonable limits for your volume
   - Implement 429 retry logic

7. **Cursor Pagination**:
   - Use `cursor` from response for next page
   - More reliable than offset pagination
   - `null` cursor means no more pages

## Airtable API

### Attachments

When setting an attachment field in Airtable:

```python
{
    "Attachments": [
        {
            "url": "https://example.com/file.pdf",
            "filename": "optional-filename.pdf"  # optional
        }
    ]
}
```

**Important**:
- URL must be publicly accessible (or use signed URL)
- Airtable fetches the file and re-hosts it
- After upload, Airtable returns its own URLs
- Max file size: 20 MB per attachment via API
- Max 10 attachments per field

### Rate Limits
- 5 requests per second per base
- 1,000 records per request for batch operations
- We use single record operations, well within limits

## PostgreSQL Schema

For future reference when migrating from Airtable:

```sql
-- Emails table
CREATE TABLE emails (
    id SERIAL PRIMARY KEY,
    email_id VARCHAR(255) UNIQUE NOT NULL,
    thread_id VARCHAR(255),
    subject TEXT,
    from_address VARCHAR(500),
    to_addresses TEXT[],
    cc_addresses TEXT[],
    bcc_addresses TEXT[],
    body_text TEXT,
    body_html TEXT,
    sent_at TIMESTAMP,
    received_at TIMESTAMP,
    labels TEXT[],
    deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP,
    source_links JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Attachments (for PostgreSQL)
CREATE TABLE attachments (
    id SERIAL PRIMARY KEY,
    email_id VARCHAR(255) REFERENCES emails(email_id),
    filename VARCHAR(500),
    content_type VARCHAR(255),
    byte_size INTEGER,
    source_url TEXT,
    checksum VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Tasks table
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(255) UNIQUE NOT NULL,
    project_id VARCHAR(255),
    title TEXT,
    description TEXT,
    status VARCHAR(100),
    tags TEXT[],
    assignees TEXT[],
    due_at TIMESTAMP,
    updated_at TIMESTAMP,
    deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP,
    source_links JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Checkpoints
CREATE TABLE checkpoints (
    source VARCHAR(50) PRIMARY KEY,
    last_event_time TIMESTAMP NOT NULL,
    last_cursor TEXT,
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## Testing Tips

### Testing Webhooks Locally

1. Use ngrok inspector: http://localhost:4040
2. View request/response details
3. Replay requests
4. Check for errors

### Simulating Events

**Teamwork**:
- Create/update/complete a task in Teamwork UI
- Webhook should arrive within seconds

**Missive**:
- Send an email to your Missive inbox
- Reply to a conversation
- Add a label
- Move to trash

### Checking Event Processing

```bash
# Check queue
python scripts/check_queue.py

# Watch logs
tail -f logs/app.log

# Verify in database
# For Airtable: Check base in browser
# For PostgreSQL: psql and SELECT queries
```

