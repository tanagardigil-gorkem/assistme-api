# MyDay + Tasks Frontend Implementation Instructions

## Endpoints

1. `GET /api/v1/dashboard/daily-feed`
- Primary dashboard call. Includes `myday`.

2. `GET /api/v1/dashboard/myday`
- Returns the same `myday` object.
- Supports date range filtering:
  - `start_date`: `YYYY-MM-DD` (optional)
  - `end_date`: `YYYY-MM-DD` (optional)
  - `timezone`: IANA tz string (required)
- If no dates are provided, the backend defaults to today in `timezone`.

3. `POST /api/v1/tasks`
- Create a task.

4. `GET /api/v1/tasks`
- List tasks with filters:
  - `start_date`, `end_date` (`YYYY-MM-DD`)
  - `timezone` (default `UTC`)
  - `status` (`scheduled`, `completed`, `delayed`, `skipped`)
  - `tags` (repeatable query param)
  - `include_unscheduled` (default `false`)

5. `GET /api/v1/tasks/{task_id}`
- Fetch a single task.

6. `PATCH /api/v1/tasks/{task_id}`
- Update a task.

7. `DELETE /api/v1/tasks/{task_id}`
- Delete a task.

## Response Shape (MyDay)

`myday` is a `DashboardMyDayResponse`:
- `day`: date string (`YYYY-MM-DD`) representing the local day for the schedule.
- `timezone`: IANA tz string (e.g., `America/Los_Angeles`).
- `generated_at`: ISO 8601 datetime with timezone.
- `title`: string, default `"Generated Day"`.
- `subtitle`: string or null, default `"AI-Optimized Schedule"`.
- `flow_label`: string or null, e.g. `"BEST FLOW DETECTED"`.
- `tasks`: array of `TaskItem`.

## Task Shape (Generic)

`TaskItem` is used for both MyDay and Tasks list.

Fields:
- `id`: UUID string.
- `topic`: short title.
- `description`: string or null, max 2 paragraphs (split by blank lines).
- `tags`: array of strings (preset + custom).
- `badge`: string or null for UI pill (e.g. `"AI BRIEFING"`, `"HIGH ENERGY"`).
- `status`: enum.
- `scheduled_start`: ISO datetime or null.
- `scheduled_end`: ISO datetime or null.
- `is_all_day`: boolean.
- `scheduled_date`: date string (`YYYY-MM-DD`) when `is_all_day` is true.
- `delayed_until`: ISO datetime or null (required when status is `delayed`).
- `completed_at`: ISO datetime or null (required when status is `completed`).
- `source_type`: enum (`manual`, `generated`, `email`, `calendar`, `integration`, `other`).
- `source_id`: string or null.
- `source_metadata`: object or null.

`TaskResponse` (used in `/tasks` endpoints) adds:
- `user_id`: UUID string.
- `created_at`: ISO datetime.
- `updated_at`: ISO datetime.

## Enums

Preset tag suggestions (not enforced by backend):
- `briefing`, `family`, `payment`, `bill`, `email`, `work`, `focus`, `health`, `errand`, `home`, `admin`, `learning`

`TaskStatus` values:
- `scheduled`, `completed`, `delayed`, `skipped`

`TaskSourceType` values:
- `manual`, `generated`, `email`, `calendar`, `integration`, `other`

## MyDay Display Rules

1. Use `myday.title`, `subtitle`, and `flow_label` for the header block.
2. For each task:
- Primary line: `topic`.
- Secondary line: `description` (if present), max 2 paragraphs.
- Show `badge` as a pill on the right.
- Render time from `scheduled_start` / `scheduled_end` in the local `timezone`.
- If `is_all_day` is true, display `scheduled_date` as an all-day chip.
3. Status handling:
- `completed`: show completed styling and optionally `completed_at` time.
- `delayed`: show delayed styling and display `delayed_until`.
- `skipped`: show muted styling.
- `scheduled`: normal styling.

## Ordering

- Backend returns tasks in display order for MyDay. Do not re-sort unless UX requires it.

## Tasks Menu (New)

Add a new top-level menu item: `Tasks`.

Behavior:
- Route to a dedicated Tasks screen.
- Use `GET /api/v1/tasks` to fetch and display tasks.
- Provide date range filters (start/end date), status filter, and tag filter.
- Provide a Create Task action (POST) and inline edit (PATCH) if desired.

Empty states:
- No tasks in range: show a friendly empty state with a CTA to create a task.
- No results with filters: show a clear “no matches” message and a reset filters action.

## Example `myday` JSON

```json
{
  "day": "2026-02-03",
  "timezone": "America/Los_Angeles",
  "generated_at": "2026-02-03T16:00:00Z",
  "title": "Generated Day",
  "subtitle": "AI-Optimized Schedule",
  "flow_label": "BEST FLOW DETECTED",
  "tasks": [
    {
      "id": "9f4f5d7c-3f43-4ab9-9e1a-2d95e6a0af7c",
      "topic": "Coffee & AI Briefing",
      "description": "Summary of 14 emails and 3 curated news updates.",
      "tags": ["briefing", "email"],
      "badge": "AI BRIEFING",
      "status": "scheduled",
      "scheduled_start": "2026-02-03T08:00:00-08:00",
      "scheduled_end": "2026-02-03T08:30:00-08:00",
      "is_all_day": false,
      "scheduled_date": null,
      "delayed_until": null,
      "completed_at": null,
      "source_type": "generated",
      "source_id": "myday:2026-02-03:briefing",
      "source_metadata": null
    }
  ]
}
```
