# Relational Database Schema

## Overview

The database has been refactored to use a fully relational structure with proper foreign keys and junction tables for many-to-many relationships. This provides better data integrity, easier querying, and automatic normalization of data.

## Teamwork Tables

### Core Entity Tables

#### `tw_companies`
Stores Teamwork company information.

**Key Fields:**
- `id` (INTEGER, PK): Company ID
- `name`: Company name
- Contact info: `email_one`, `email_two`, `email_three`, `phone`, `fax`
- Address: `address_one`, `address_two`, `city`, `state`, `zip`, `country_code`
- `logo_url`, `website`, `status`
- `industry_id` (INTEGER): Industry category
- `can_see_private`, `is_owner` (BOOLEAN): Access flags
- `private_notes`, `private_notes_text`, `profile_text` (TEXT): Notes and profile
- `created_at`, `updated_at` (TIMESTAMP): Timestamps from API
- `raw_data` (JSONB): Full API response
- `db_created_at`, `db_updated_at` (TIMESTAMP): Database tracking timestamps

**Indexes:**
- `idx_tw_companies_name`

---

#### `tw_users`
Stores Teamwork user/people information.

**Key Fields:**
- `id` (INTEGER, PK): User ID
- `first_name`, `last_name`, `email`
- `company_id` (FK → `tw_companies.id`)
- `company_role_id` (INTEGER): Company role
- `avatar_url`, `title`, `timezone`
- Boolean flags: `is_admin`, `is_client_user`, `is_placeholder_resource`, `is_service_account`, `deleted`
- Access flags: `can_add_projects`, `can_access_portfolio`, `can_manage_portfolio`
- `user_cost`, `user_rate`, `length_of_day` (DECIMAL)
- `last_login`, `created_at`, `updated_at` (TIMESTAMP)
- `raw_data` (JSONB): Full API response
- `db_created_at`, `db_updated_at` (TIMESTAMP): Database tracking timestamps

**Indexes:**
- `idx_tw_users_email`
- `idx_tw_users_company_id`
- `idx_tw_users_deleted`

**Foreign Keys:**
- `company_id` → `tw_companies(id)` ON DELETE SET NULL

---

#### `tw_teams`
Stores Teamwork team information.

**Key Fields:**
- `id` (INTEGER, PK): Team ID
- `name` (TEXT, NOT NULL), `handle` (TEXT)
- `team_logo`, `team_logo_color`, `team_logo_icon`
- `created_at`, `updated_at` (TIMESTAMP)
- `raw_data` (JSONB): Full API response
- `db_created_at`, `db_updated_at` (TIMESTAMP): Database tracking timestamps

**Indexes:**
- `idx_tw_teams_name`

---

#### `tw_tags`
Stores Teamwork tags.

**Key Fields:**
- `id` (INTEGER, PK): Tag ID
- `name` (TEXT, NOT NULL), `color` (VARCHAR(50))
- `project_id` (INTEGER): Optional project association
- `count` (INTEGER, DEFAULT 0): Usage count
- `raw_data` (JSONB): Full API response
- `db_created_at`, `db_updated_at` (TIMESTAMP): Database tracking timestamps

**Indexes:**
- `idx_tw_tags_name`
- `idx_tw_tags_project_id`

---

#### `tw_projects`
Stores Teamwork project information.

**Key Fields:**
- `id` (INTEGER, PK): Project ID
- `name` (TEXT, NOT NULL), `description` (TEXT)
- `company_id` (FK → `tw_companies.id`)
- `owner_id` (FK → `tw_users.id`)
- `category_id` (INTEGER): Project category
- `created_by`, `updated_by`, `completed_by` (FK → `tw_users.id`)
- `status`, `sub_status` (VARCHAR(50))
- Dates: `start_date`, `end_date` (DATE), `start_at`, `end_at`, `completed_at` (TIMESTAMP)
- `created_at`, `updated_at`, `last_worked_on` (TIMESTAMP)
- Boolean flags: `is_starred`, `is_billable`, `is_sample_project`, `is_onboarding_project`, `is_project_admin`
- `logo`, `logo_color`, `logo_icon`, `announcement`
- `show_announcement` (BOOLEAN)
- Settings: `default_privacy`, `privacy_enabled`, `harvest_timers_enabled`, `notify_everyone`, `skip_weekends`
- `raw_data` (JSONB): Full API response
- `db_created_at`, `db_updated_at` (TIMESTAMP): Database tracking timestamps

**Indexes:**
- `idx_tw_projects_name`
- `idx_tw_projects_company_id`
- `idx_tw_projects_status`

**Foreign Keys:**
- `company_id` → `tw_companies(id)` ON DELETE SET NULL
- `owner_id` → `tw_users(id)` ON DELETE SET NULL
- `completed_by`, `created_by`, `updated_by` → `tw_users(id)` ON DELETE SET NULL

---

#### `tw_tasklists`
Stores Teamwork tasklist information.

**Key Fields:**
- `id` (INTEGER, PK): Tasklist ID
- `name` (TEXT, NOT NULL), `description` (TEXT)
- `project_id` (FK → `tw_projects.id`)
- `milestone_id` (INTEGER), `status` (VARCHAR(50)), `display_order` (INTEGER)
- Boolean flags: `is_private`, `is_pinned`, `is_billable`
- `icon` (TEXT), `lockdown_id` (INTEGER)
- Dates: `calculated_start_date`, `calculated_due_date` (DATE)
- `created_at`, `updated_at` (TIMESTAMP)
- `raw_data` (JSONB): Full API response
- `db_created_at`, `db_updated_at` (TIMESTAMP): Database tracking timestamps

**Indexes:**
- `idx_tw_tasklists_name`
- `idx_tw_tasklists_project_id`

**Foreign Keys:**
- `project_id` → `tw_projects(id)` ON DELETE CASCADE

---

#### `tasks`
Stores Teamwork tasks (refactored to use foreign keys).

**Key Fields:**
- `id` (SERIAL, PK): Internal database ID
- `task_id` (VARCHAR(255), UNIQUE, NOT NULL): Teamwork task ID
- `name` (TEXT), `description` (TEXT)
- `status` (VARCHAR(100)), `priority` (VARCHAR(50)), `progress` (INTEGER)
- `project_id` (FK → `tw_projects.id`)
- `tasklist_id` (FK → `tw_tasklists.id`)
- `created_by_id` (FK → `tw_users.id`)
- `updated_by_id` (FK → `tw_users.id`)
- `parent_task` (FK → `tasks.task_id`, DEFERRABLE INITIALLY DEFERRED): Parent task ID
- Dates: `start_date`, `due_date`, `created_at`, `updated_at`, `deleted_at` (TIMESTAMP)
- `estimate_minutes`, `accumulated_estimated_minutes` (INTEGER)
- `source_links` (JSONB): Links to external sources
- `raw_data` (JSONB): Full API response
- `db_created_at`, `db_updated_at` (TIMESTAMP): Database tracking timestamps

**Indexes:**
- `idx_tasks_task_id`
- `idx_tasks_project_id`
- `idx_tasks_tasklist_id`
- `idx_tasks_parent_task`
- `idx_tasks_deleted_at`
- `idx_tasks_updated_at`

**Foreign Keys:**
- `project_id` → `tw_projects(id)` ON DELETE SET NULL
- `tasklist_id` → `tw_tasklists(id)` ON DELETE SET NULL
- `created_by_id` → `tw_users(id)` ON DELETE SET NULL
- `updated_by_id` → `tw_users(id)` ON DELETE SET NULL
- `parent_task` → `tasks(task_id)` ON DELETE SET NULL

---

### Junction Tables (Many-to-Many)

#### `task_tags`
Links tasks to tags.

**Fields:**
- `task_id` (FK → `tasks.task_id`) ON DELETE CASCADE
- `tag_id` (FK → `tw_tags.id`) ON DELETE CASCADE
- PRIMARY KEY: `(task_id, tag_id)`

**Indexes:**
- `idx_task_tags_task_id`
- `idx_task_tags_tag_id`

---

#### `task_assignees`
Links tasks to user assignees.

**Fields:**
- `task_id` (FK → `tasks.task_id`) ON DELETE CASCADE
- `user_id` (FK → `tw_users.id`) ON DELETE CASCADE
- PRIMARY KEY: `(task_id, user_id)`

**Indexes:**
- `idx_task_assignees_task_id`
- `idx_task_assignees_user_id`

---

#### `tw_user_teams`
Links users to teams.

**Fields:**
- `user_id` (FK → `tw_users.id`) ON DELETE CASCADE
- `team_id` (FK → `tw_teams.id`) ON DELETE CASCADE
- PRIMARY KEY: `(user_id, team_id)`

**Indexes:**
- `idx_tw_user_teams_user_id`
- `idx_tw_user_teams_team_id`

---

## Missive Tables

### Core Entity Tables

#### `m_contacts`
Stores email correspondents (normalized contact information).

**Key Fields:**
- `id` (SERIAL, PK): Auto-generated contact ID
- `name` (TEXT): Contact name
- `email` (VARCHAR(500), NOT NULL, UNIQUE): Email address (required)
- `db_created_at`, `db_updated_at` (TIMESTAMP): Database tracking timestamps

**Indexes:**
- `idx_m_contacts_email`

**Purpose:**
- Central repository for all email participants
- Eliminates duplicate storage of name/email pairs
- Used by messages (sender), recipients (to/cc/bcc), and conversation authors
- Separate from `m_users` (Missive team members)

---

#### `m_users`
Stores Missive user information (team members).

**Key Fields:**
- `id` (UUID, PK): User ID from Missive
- `name` (TEXT), `email` (VARCHAR(500))
- `contact_id` (FK → `m_contacts.id`): Link to contact record
- `raw_data` (JSONB): Full API response
- `db_created_at`, `db_updated_at` (TIMESTAMP): Database tracking timestamps

**Indexes:**
- `idx_m_users_email`
- `idx_m_users_contact_id`

**Foreign Keys:**
- `contact_id` → `m_contacts(id)` ON DELETE SET NULL

**Note:**
- Missive users are team members with their own UUIDs from the Missive API
- They have additional properties (permissions, team membership, etc.)
- Linked to `m_contacts` for unified contact queries

---

#### `m_teams`
Stores Missive team information.

**Key Fields:**
- `id` (UUID, PK): Team ID
- `name` (TEXT, NOT NULL)
- `organization_id` (UUID): Organization reference
- `raw_data` (JSONB): Full API response
- `db_created_at`, `db_updated_at` (TIMESTAMP): Database tracking timestamps

**Indexes:**
- `idx_m_teams_organization_id`

---

#### `m_shared_labels`
Stores Missive shared labels.

**Key Fields:**
- `id` (UUID, PK): Label ID
- `name` (TEXT, NOT NULL)
- `raw_data` (JSONB): Full API response
- `db_created_at`, `db_updated_at` (TIMESTAMP): Database tracking timestamps

**Indexes:**
- `idx_m_shared_labels_name`

---

#### `m_conversations`
Stores Missive conversations.

**Key Fields:**
- `id` (UUID, PK): Conversation ID
- `subject` (TEXT), `latest_message_subject` (TEXT)
- `team_id` (FK → `m_teams.id`)
- `organization_id` (UUID)
- `color` (VARCHAR(50))
- Counts: `attachments_count` (INTEGER, DEFAULT 0), `messages_count` (INTEGER, DEFAULT 1), `drafts_count` (INTEGER, DEFAULT 0), `tasks_count` (INTEGER, DEFAULT 0), `completed_tasks_count` (INTEGER, DEFAULT 0), `send_later_messages_count` (INTEGER, DEFAULT 0)
- `last_activity_at` (TIMESTAMP): Last activity timestamp (converted from Unix milliseconds)
- `web_url` (TEXT), `app_url` (TEXT)
- `raw_data` (JSONB): Full API response
- `db_created_at`, `db_updated_at` (TIMESTAMP): Database tracking timestamps

**Indexes:**
- `idx_m_conversations_team_id`
- `idx_m_conversations_last_activity_at`

**Foreign Keys:**
- `team_id` → `m_teams(id)` ON DELETE SET NULL

---

#### `m_messages`
Stores Missive messages (emails).

**Key Fields:**
- `id` (UUID, PK): Message ID
- `conversation_id` (FK → `m_conversations.id`)
- `subject` (TEXT), `preview` (TEXT), `body` (TEXT)
- `type` (VARCHAR(50)): Message type
- `email_message_id` (TEXT): Email message ID
- `from_contact_id` (FK → `m_contacts.id`): Message sender
- Timestamps: `delivered_at`, `created_at`, `updated_at` (TIMESTAMP, converted from Unix milliseconds)
- `raw_data` (JSONB): Full API response
- `db_created_at`, `db_updated_at` (TIMESTAMP): Database tracking timestamps

**Indexes:**
- `idx_m_messages_conversation_id`
- `idx_m_messages_email_message_id`
- `idx_m_messages_from_contact_id`
- `idx_m_messages_delivered_at`

**Foreign Keys:**
- `conversation_id` → `m_conversations(id)` ON DELETE CASCADE
- `from_contact_id` → `m_contacts(id)` ON DELETE SET NULL

---

#### `m_message_recipients`
Stores message recipients (to/cc/bcc fields, normalized).

**Key Fields:**
- `id` (SERIAL, PK): Auto-generated recipient ID
- `message_id` (FK → `m_messages.id`)
- `recipient_type` (VARCHAR(10), NOT NULL): 'to', 'cc', or 'bcc'
- `contact_id` (FK → `m_contacts.id`): Recipient contact

**Indexes:**
- `idx_m_message_recipients_message_id`
- `idx_m_message_recipients_contact_id`
- `idx_m_message_recipients_type`

**Foreign Keys:**
- `message_id` → `m_messages(id)` ON DELETE CASCADE
- `contact_id` → `m_contacts(id)` ON DELETE SET NULL

---

#### `m_attachments`
Stores Missive message attachments.

**Key Fields:**
- `id` (UUID, PK): Attachment ID
- `message_id` (FK → `m_messages.id`)
- `filename` (VARCHAR(500)), `extension` (VARCHAR(50)), `url` (TEXT)
- `media_type` (VARCHAR(100)), `sub_type` (VARCHAR(100))
- `size` (INTEGER), `width` (INTEGER), `height` (INTEGER)
- `raw_data` (JSONB): Full API response
- `db_created_at` (TIMESTAMP): Database tracking timestamp

**Indexes:**
- `idx_m_attachments_message_id`

**Foreign Keys:**
- `message_id` → `m_messages(id)` ON DELETE CASCADE

---

### Junction Tables (Many-to-Many)

#### `m_conversation_users`
Links conversations to users with per-user status flags.

**Key Fields:**
- `conversation_id` (FK → `m_conversations.id`) ON DELETE CASCADE
- `user_id` (FK → `m_users.id`) ON DELETE CASCADE
- Status flags (BOOLEAN): `unassigned` (DEFAULT TRUE), `closed` (DEFAULT FALSE), `archived` (DEFAULT FALSE), `trashed` (DEFAULT FALSE), `junked` (DEFAULT FALSE), `assigned` (DEFAULT FALSE), `flagged` (DEFAULT FALSE), `snoozed` (DEFAULT FALSE)
- PRIMARY KEY: `(conversation_id, user_id)`

**Indexes:**
- `idx_m_conversation_users_conversation_id`
- `idx_m_conversation_users_user_id`

---

#### `m_conversation_assignees`
Links conversations to assigned users.

**Key Fields:**
- `conversation_id` (FK → `m_conversations.id`) ON DELETE CASCADE
- `user_id` (FK → `m_users.id`) ON DELETE CASCADE
- PRIMARY KEY: `(conversation_id, user_id)`

**Indexes:**
- `idx_m_conversation_assignees_conversation_id`
- `idx_m_conversation_assignees_user_id`

---

#### `m_conversation_labels`
Links conversations to shared labels.

**Key Fields:**
- `conversation_id` (FK → `m_conversations.id`) ON DELETE CASCADE
- `label_id` (FK → `m_shared_labels.id`) ON DELETE CASCADE
- PRIMARY KEY: `(conversation_id, label_id)`

**Indexes:**
- `idx_m_conversation_labels_conversation_id`
- `idx_m_conversation_labels_label_id`

---

#### `m_conversation_authors`
Stores conversation authors (can be multiple per conversation).

**Key Fields:**
- `id` (SERIAL, PK): Auto-generated author link ID
- `conversation_id` (FK → `m_conversations.id`)
- `contact_id` (FK → `m_contacts.id`): Author contact

**Indexes:**
- `idx_m_conversation_authors_conversation_id`
- `idx_m_conversation_authors_contact_id`

**Foreign Keys:**
- `conversation_id` → `m_conversations(id)` ON DELETE CASCADE
- `contact_id` → `m_contacts(id)` ON DELETE SET NULL

---

## System Tables

#### `checkpoints`
Tracks sync checkpoints for incremental data synchronization.

**Key Fields:**
- `source` (VARCHAR(50), PK): Source system ('teamwork' or 'missive')
- `last_event_time` (TIMESTAMP, NOT NULL): Last processed event timestamp
- `last_cursor` (TEXT): Optional cursor for pagination
- `updated_at` (TIMESTAMP, DEFAULT NOW()): Last update time

**Note:**
- Legacy `emails` and `attachments` tables have been removed
- All email data is now in the relational structure (`m_messages`, `m_message_recipients`, `m_attachments`, etc.)

---

## Auto-Discovery and Auto-Insertion

The system automatically discovers and inserts new entities when processing events:

### Teamwork Data Flow

1. When a task event is received:
   - API response includes `included` resources (companies, users, teams, tags, projects, tasklists)
   - `TeamworkEventHandler._upsert_included_entities()` processes all entities in dependency order:
     1. Companies (no dependencies)
     2. Users (depends on companies)
     3. Teams (no dependencies)
     4. Link users to teams
     5. Tags (may depend on projects)
     6. Projects (depends on companies and users)
     7. Tasklists (depends on projects)
   - Task is then upserted with foreign key references
   - Junction tables are populated (task-tags, task-assignees)

### Missive Data Flow

1. When a conversation event is received:
   - Full conversation data is fetched from API
   - `MissiveEventHandler.process_event()`:
     - Upserts conversation (which auto-upserts team if present)
     - Populates junction tables for users, assignees, and labels
     - Extracts and creates/links authors
   - For each message:
     - Upserts message with conversation_id reference
     - Normalizes recipients into `m_message_recipients` table
     - Auto-links recipients to users by email if found
     - Upserts attachments with message_id reference

---

## Database Methods

### Teamwork Entity Methods

- `upsert_tw_company(company_data: Dict)`
- `upsert_tw_user(user_data: Dict)`
- `upsert_tw_team(team_data: Dict)`
- `upsert_tw_tag(tag_data: Dict)`
- `upsert_tw_project(project_data: Dict)`
- `upsert_tw_tasklist(tasklist_data: Dict)`
- `link_task_tags(task_id: str, tag_ids: List[int])`
- `link_task_assignees(task_id: str, user_ids: List[int])`
- `link_user_teams(user_id: int, team_ids: List[int])`

### Missive Entity Methods

- `upsert_m_user(user_data: Dict)`
- `upsert_m_team(team_data: Dict)`
- `upsert_m_shared_label(label_data: Dict)`
- `upsert_m_conversation(conversation_data: Dict)` - Auto-handles users, assignees, labels, authors
- `upsert_m_message(message_data: Dict, conversation_id: str)` - Auto-handles recipients, attachments

---

## Querying Examples

### Get all tasks for a project with full details

```sql
SELECT 
    t.task_id,
    t.name,
    t.status,
    p.name as project_name,
    c.name as company_name,
    tl.name as tasklist_name,
    cu.first_name || ' ' || cu.last_name as created_by,
    uu.first_name || ' ' || uu.last_name as updated_by
FROM tasks t
LEFT JOIN tw_projects p ON t.project_id = p.id
LEFT JOIN tw_companies c ON p.company_id = c.id
LEFT JOIN tw_tasklists tl ON t.tasklist_id = tl.id
LEFT JOIN tw_users cu ON t.created_by_id = cu.id
LEFT JOIN tw_users uu ON t.updated_by_id = uu.id
WHERE t.deleted_at IS NULL
    AND p.id = 12345;
```

### Get all tags for a task

```sql
SELECT tag.name, tag.color
FROM task_tags tt
JOIN tw_tags tag ON tt.tag_id = tag.id
WHERE tt.task_id = '67890';
```

### Get all assignees for a task

```sql
SELECT u.first_name, u.last_name, u.email
FROM task_assignees ta
JOIN tw_users u ON ta.user_id = u.id
WHERE ta.task_id = '67890';
```

### Get all messages in a conversation with sender info

```sql
SELECT 
    m.id,
    m.subject,
    sender.name as from_name,
    sender.email as from_address,
    m.body,
    m.delivered_at,
    c.subject as conversation_subject
FROM m_messages m
JOIN m_conversations c ON m.conversation_id = c.id
LEFT JOIN m_contacts sender ON m.from_contact_id = sender.id
WHERE c.id = 'uuid-here'
ORDER BY m.delivered_at DESC;
```

### Get all recipients for a message

```sql
SELECT 
    mr.recipient_type,
    c.name,
    c.email as address,
    u.id as missive_user_id
FROM m_message_recipients mr
LEFT JOIN m_contacts c ON mr.contact_id = c.id
LEFT JOIN m_users u ON c.id = u.contact_id
WHERE mr.message_id = 'uuid-here'
ORDER BY mr.recipient_type, c.name;
```

### Get conversation with labels and assignees

```sql
SELECT 
    c.*,
    string_agg(DISTINCT l.name, ', ') as labels,
    string_agg(DISTINCT u.name, ', ') as assignees
FROM m_conversations c
LEFT JOIN m_conversation_labels cl ON c.id = cl.conversation_id
LEFT JOIN m_shared_labels l ON cl.label_id = l.id
LEFT JOIN m_conversation_assignees ca ON c.id = ca.conversation_id
LEFT JOIN m_users u ON ca.user_id = u.id
WHERE c.id = 'uuid-here'
GROUP BY c.id;
```

### Get all messages from/to a specific contact

```sql
-- All messages FROM a contact
SELECT m.id, m.subject, m.delivered_at, conv.subject as conversation
FROM m_messages m
JOIN m_conversations conv ON m.conversation_id = conv.id
JOIN m_contacts c ON m.from_contact_id = c.id
WHERE c.email = 'example@example.com'
ORDER BY m.delivered_at DESC;

-- All messages TO a contact (as recipient)
SELECT m.id, m.subject, m.delivered_at, conv.subject as conversation
FROM m_messages m
JOIN m_conversations conv ON m.conversation_id = conv.id
JOIN m_message_recipients mr ON m.id = mr.message_id
JOIN m_contacts c ON mr.contact_id = c.id
WHERE c.email = 'example@example.com'
ORDER BY m.delivered_at DESC;
```

### Get task hierarchy (parent/child relationships)

```sql
-- Get all subtasks of a parent task
SELECT 
    child.task_id,
    child.name as subtask_name,
    child.status,
    parent.name as parent_task_name
FROM tasks child
JOIN tasks parent ON child.parent_task = parent.task_id
WHERE parent.task_id = '12345'
ORDER BY child.created_at;

-- Get task tree (recursive)
WITH RECURSIVE task_tree AS (
    -- Base case: root task
    SELECT task_id, name, parent_task, 0 as level
    FROM tasks
    WHERE task_id = '12345'
    
    UNION ALL
    
    -- Recursive case: children
    SELECT t.task_id, t.name, t.parent_task, tt.level + 1
    FROM tasks t
    JOIN task_tree tt ON t.parent_task = tt.task_id
)
SELECT * FROM task_tree ORDER BY level, task_id;
```

---

## Benefits

1. **Data Integrity**: Foreign keys ensure referential integrity
   - Task hierarchy enforced with `parent_task` FK
   - Orphaned records prevented through CASCADE/SET NULL rules
2. **No Duplication**: Entities and contacts stored once and referenced
   - `m_contacts` eliminates duplicate email/name pairs
   - Single source of truth for each entity
3. **Easy Updates**: Update once, reflects everywhere
   - Update contact name/email in one place
   - Company info changes propagate to all related records
4. **Efficient Queries**: Proper indexes and joins enable fast querying
   - Find all messages from/to a contact in one query
   - Traverse task hierarchies with recursive CTEs
5. **Proper DateTime Handling**: Native TIMESTAMP types instead of Unix integers
   - Use SQL date functions and comparisons
   - Automatic timezone support
   - More readable in queries
6. **Task Hierarchy Support**: Parent-child task relationships
   - Query subtasks and task trees
   - Maintain referential integrity in task hierarchies
7. **Unified Contact Management**: Separate contacts from users
   - `m_contacts` for all email correspondents
   - `m_users` for Missive team members only
   - Link users to contacts for unified queries
8. **Scalable**: Normalized structure scales better than flat denormalized data
9. **Raw Data Backup**: `raw_data` JSONB fields preserve full API responses
10. **Auto-Discovery**: New entities automatically added when discovered in API responses

---

## Schema Change Notes

- All tables have `db_created_at` and most have `db_updated_at` for tracking (exception: `m_attachments` and junction tables which only have `db_created_at` where applicable)
- `raw_data` JSONB column preserves complete API response for reference in all entity tables
- **Legacy `emails` and `attachments` tables removed** - all email data now in relational structure
- **Timestamps converted from Unix milliseconds to TIMESTAMP** - `last_activity_at`, `delivered_at`, `created_at`, `updated_at`
- **`m_contacts` table added** - centralizes all email correspondents for normalization
- **`parent_task` now a foreign key** - enforces task hierarchy integrity with DEFERRABLE constraint
- Helper methods handle complex relationships automatically (auto-upsert of related entities)
- Auto-conversion of Unix timestamps (milliseconds) to TIMESTAMP in database operations
- Foreign key validation ensures referential integrity before inserts

