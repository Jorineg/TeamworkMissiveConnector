# Label and Tag Categorization

## Overview

The label and tag categorization feature automatically organizes email labels (from Missive) and task tags (from Teamwork) into configurable categories. This allows you to structure your tags/labels into meaningful groups like customers, cost groups, buildings, projects, etc.

## Configuration

### 1. Create the Mapping File

Create a JSON file at `data/label_categories.json` with your category definitions:

```json
{
  "Kunden": ["Kunde1", "Kunde2", "Kunde3"],
  "Räume": "R_*",
  "Kostengruppe": "KGR_*",
  "Gebäude": ["Building_A", "Building_B", "Building_*"],
  "Projekt": "PRJ_*"
}
```

An example file is provided at `data/label_categories.json.example` that you can copy and customize.

### 2. Mapping Format

Each key in the JSON object represents a **category name** that will become a column in your Airtable tables. The value can be:

- **A list of exact matches**: `["Kunde1", "Kunde2", "Kunde3"]`
  - Tags/labels must match exactly (case-sensitive)
  
- **A single wildcard pattern**: `"R_*"`
  - Use as a string instead of a list
  
- **A list mixing exact matches and patterns**: `["Building_A", "Building_*"]`
  - Can combine both types

### 3. Wildcard Syntax

The categorization system supports simple wildcard patterns:

- `*` - Matches zero or more characters
  - `"R_*"` matches `R_`, `R_101`, `R_Room_A`, etc.
  - `"*_Project"` matches `ABC_Project`, `_Project`, etc.
  
- `?` - Matches exactly one character
  - `"R_?"` matches `R_1`, `R_A`, but not `R_10`
  - `"KGR_???"` matches `KGR_100`, `KGR_ABC`, but not `KGR_1` or `KGR_1000`

All other characters are matched literally and are case-sensitive.

### Example Patterns

```json
{
  "Kostengruppe": "KGR_*",          // Matches: KGR_100, KGR_200_Special
  "Räume": ["R_*", "Room_*"],       // Matches: R_101, Room_A, Room_Conference
  "Kunden": ["Kunde1", "Kunde2"],   // Exact matches only
  "Projekt": "PRJ_????",            // Matches: PRJ_2024, PRJ_ABCD (exactly 4 chars)
  "Gebäude": "Building_?",          // Matches: Building_A, Building_1 (single char)
  "Mixed": ["Exact_Name", "Prefix_*", "???_Suffix"]  // Multiple patterns
}
```

## Behavior

### Startup

When the application starts:

1. The `label_categories.json` file is loaded
2. For each category defined in the file:
   - A column is created in the **Emails** table (if it doesn't exist)
   - A column is created in the **Tasks** table (if it doesn't exist)
3. Column type is `multilineText` to support comma-separated values

### Processing

When emails or tasks are processed:

1. All labels/tags are read from the item
2. Each label/tag is matched against all category patterns
3. Matching labels/tags are grouped by category
4. Each category column receives its matching labels/tags as a comma-separated string

### Multiple Matches

- A single tag/label can match **multiple categories** and will appear in all matching columns
- Within each category, **multiple tags/labels** can match and are stored as comma-separated values

### Example

Given this mapping:
```json
{
  "Kostengruppe": "KGR_*",
  "Räume": "R_*",
  "Kunden": ["Kunde1", "Kunde2"]
}
```

And a task with tags: `["KGR_100", "KGR_200", "R_101", "Kunde1", "Other"]`

The Airtable record will have:
- **Kostengruppe**: `KGR_100, KGR_200`
- **Räume**: `R_101`
- **Kunden**: `Kunde1`
- **tags**: `KGR_100, KGR_200, R_101, Kunde1, Other` (original tags preserved)

## Important Notes

### New Items Only

- Categorization is applied only to **newly processed** emails and tasks
- Existing items in the database are **not updated** when the mapping file changes
- This prevents accidentally modifying historical data

### No Retroactive Updates

If you change the `label_categories.json` file:
- Only new/updated emails and tasks will use the new mapping
- To reprocess existing items, you would need to manually trigger a backfill

### Column Persistence

- Once created, category columns remain in Airtable even if removed from the mapping file
- This is intentional to preserve data integrity
- You can manually delete columns in Airtable if needed

### Case Sensitivity

- All pattern matching is **case-sensitive**
- `"R_*"` will not match `"r_101"`
- Ensure your patterns match the actual casing used in your tags/labels

### Performance

- Pattern matching is performed in-memory and is very fast
- The mapping file is loaded once at startup
- To reload the mapping without restarting, you would need to restart the application

## Troubleshooting

### Categories Not Appearing

1. Check that `data/label_categories.json` exists and is valid JSON
2. Review application logs for errors during startup
3. Verify Airtable API key has schema modification permissions (`schema.bases:write`)

### Tags Not Being Categorized

1. Verify the pattern syntax (remember `*` and `?` wildcards)
2. Check case sensitivity (patterns are case-sensitive)
3. Look at the `tags` or `Labels Text` column to see raw values
4. Enable debug logging to see categorization results

### Missing Columns in Airtable

1. Ensure the application has `schema.bases:write` scope for the Airtable API
2. Check logs for any errors during table setup
3. Verify the base ID and table names are correct in configuration

## Advanced Usage

### Reloading Mappings

Currently, the mapping file is loaded at startup. To reload:
1. Modify `data/label_categories.json`
2. Restart the application

### Custom Location

The default location is `data/label_categories.json`. To use a different location, modify the `LabelCategories` initialization in the code.

### Disabling Categorization

To disable categorization:
1. Delete or rename `data/label_categories.json`
2. The system will continue to work normally, just without categorization

### Testing Patterns

You can test your patterns by:
1. Creating a small test mapping
2. Adding test tags/labels in Teamwork/Missive
3. Checking the Airtable columns after processing

## Implementation Details

### Files Modified

- `src/connectors/label_categories.py` - Core categorization logic
- `src/db/airtable_setup.py` - Dynamic column creation
- `src/startup.py` - Integration with startup process
- `src/db/models.py` - Added `categorized_labels` and `categorized_tags` fields
- `src/db/airtable_impl.py` - Storage of categorized data
- `src/workers/handlers/missive_events.py` - Categorize email labels
- `src/workers/handlers/teamwork_events.py` - Categorize task tags

### Data Flow

```
1. Load label_categories.json at startup
2. Create category columns in Airtable
3. When processing email/task:
   a. Extract labels/tags
   b. Apply pattern matching
   c. Group into categories
   d. Store in appropriate columns
```

