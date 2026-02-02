# No Auth Mode - Development Setup

## Changes Made

Authentication has been **disabled for all endpoints** during development. Here's what was changed:

### 1. New Dev Mode Setting (`app/core/config.py`)

Added `dev_mode: bool = Field(default=True)` - when `True`, all auth checks are bypassed.

### 2. Mock User Helper (`app/api/v1/deps.py`)

Created a dev user that is automatically used when `dev_mode=True`:
- ID: `00000000-0000-0000-0000-000000000001`
- Email: `dev@example.com`
- Superuser: Yes

### 3. Updated Integration Endpoints

All endpoints now use `get_current_user` instead of `current_active_user`:
- `GET /integrations/` - List integrations
- `POST /integrations/{provider}/connect` - Connect provider
- `DELETE /integrations/{id}` - Disconnect
- `POST /integrations/{id}/execute` - Execute actions

## How to Enable Auth Later

Simply set `dev_mode=false` in your `.env` file:

```bash
ASSISTME_DEV_MODE=false
```

When disabled, all endpoints will require valid JWT tokens again.

## Testing Without Auth

You can now test all integration endpoints without sending any Authorization header:

```bash
# 1. List integrations (no auth needed)
curl http://localhost:8000/api/v1/integrations/

# 2. Connect Gmail (no auth needed)
curl -X POST http://localhost:8000/api/v1/integrations/gmail/connect \
  -H "Content-Type: application/json" \
  -d '{"redirect_uri": "http://localhost:3000/integrations"}'

# 3. List available providers
curl http://localhost:8000/api/v1/integrations/available
```

## Next Steps

1. Restart your backend to pick up the changes
2. Test the integration menu from your frontend
3. All requests will succeed without 401 errors
4. When ready for production, set `ASSISTME_DEV_MODE=false`

## Note

- The auth endpoints (`/auth/*`) are still available if you want to test JWT flows
- Database still requires the user to exist - integrations are tied to the dev user ID
- Rate limiting is still active (5/min for connect, 30/min for execute)
