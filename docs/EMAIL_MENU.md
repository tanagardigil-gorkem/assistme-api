# Email Menu (New UI)

This document describes how the new Email menu UI should fetch cached emails and
summaries from the backend, trigger background refresh, and bind results to the
provided mock layout.

---

**Backend Endpoints Used**
- `GET /api/v1/integrations/{integration_id}/emails`
- `POST /api/v1/integrations/{integration_id}/emails/sync`
- `PATCH /api/v1/integrations/{integration_id}` (enable/disable, config)
- `POST /api/v1/integrations/{integration_id}/execute` (optional, advanced actions)

---

**Backend Requirements**
- Gmail OAuth credentials must be configured.
- Set `ASSISTME_OPENAI_API_KEY` (or `OPENAI_API_KEY`) to enable summaries.
- Important: the backend uses the integration's stored OAuth tokens to call Gmail.
  The frontend does not pass Gmail access tokens. In current dev mode, no JWT is sent.

---

**Email Response Schema (cached-first)**
The endpoint always returns cached data immediately. If `refresh=true` or cached data is stale,
the backend queues a background sync and returns `sync_status=syncing`.

```json
{
  "items": [
    {
      "id": "message-id",
      "thread_id": "thread-id",
      "subject": "Weekly Design Sprint Sync",
      "from": "Design Team <design@company.com>",
      "to": "Alex <alex@company.com>",
      "date": "Wed, 3 Apr 2024 09:12:00 -0700",
      "snippet": "Hey Alex, we've updated the roadmap...",
      "body": "<full decoded body>",
      "labels": ["INBOX", "UNREAD"],
      "summary": "This email shares the updated roadmap and asks for a sync."
    }
  ],
  "next_page_token": "opaque-token",
  "sync_status": "idle",
  "last_synced_at": "2024-04-03T16:15:30Z"
}
```

`sync_status` values: `idle`, `syncing`, `error`.

---

**Query Parameters**
- `query`: freeform Gmail search query.
- `filter`: `all | unread | tasks`.
- `label_ids`: repeated query parameter, e.g. `label_ids=INBOX&label_ids=STARRED`.
- `max_results`: 1-100.
- `page_token`: token from previous response.
- `refresh`: `true` to trigger a background sync.
- `summaries`: `true` (default) or `false` (cached summaries only).

**Filter Mapping**
- `all` -> `""`
- `unread` -> `is:unread`
- `tasks` -> `label:tasks`

If `query` is provided, backend appends it to the filter query.

---

**UI Binding Guide (Provided Mock HTML)**

Search + Filter row:
- Search input -> `query` param
- Filter pills (`ALL`, `UNREAD`, `TASKS`) -> `filter` param

Email list (left column):
- Use `items` to render cards (sender, subject, snippet, date)
- Highlight the selected item
- Unread dot -> `labels` contains `UNREAD` (optional)

Email detail (right column):
- Title -> `subject`
- Sender line -> `from`, `date`
- AI Briefing banner -> `summary`
- Body content -> `body` (render as HTML or plain text)

Pagination row:
- Previous/Next buttons -> call the endpoint with `page_token`
- Use `next_page_token` to fetch the next page
- Show a "Syncing..." state if `sync_status` is `syncing`
- Show a stale marker if `last_synced_at` is older than your UI threshold

---

**Enable/Disable**

Use `PATCH /api/v1/integrations/{integration_id}` to toggle status:
```json
{ "status": "active" }
```
```json
{ "status": "disconnected" }
```

---

**Example Requests**

Fetch first page (cached summaries):
```
GET /api/v1/integrations/{id}/emails?filter=all&max_results=20&summaries=true
```

Search + unread:
```
GET /api/v1/integrations/{id}/emails?filter=unread&query=from:design@company.com
```

Next page:
```
GET /api/v1/integrations/{id}/emails?page_token=NEXT_TOKEN
```

Trigger background sync:
```
POST /api/v1/integrations/{id}/emails/sync
```

---

**Error Handling**
- `401/403`: session expired -> redirect to login.
- `404`: integration not found.
- `429`: rate limit -> show retry hint.
- `502`: upstream Gmail error -> show toast/banner.
- If OpenAI is not configured, `summary` will be `null` and the request still succeeds.
- If the integration is expired (no refresh token), prompt the user to reconnect.
