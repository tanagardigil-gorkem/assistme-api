# assist me api

FastAPI backend for the Assist Me personal assistant app.

## Quick Start

### 1. Setup Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings (especially security keys and OAuth credentials)
```

### 2. Start PostgreSQL with pgvector

```bash
docker-compose up -d
```

PostgreSQL will be available on port **5433** (to avoid conflicts with local PostgreSQL).

### 3. Create virtual environment and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
```

### 4. Run database migrations

```bash
alembic upgrade head
```

Or let the app auto-create tables (for development):

```bash
uvicorn app.main:app --reload
```

## API Endpoints

### Public Endpoints
- `GET /api/v1/health` - Health check

### Authentication (fastapi-users)
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/jwt/login` - Login (returns JWT)
- `POST /api/v1/auth/jwt/logout` - Logout
- `GET /api/v1/auth/me` - Get current user

### Integrations (OAuth2)
- `GET /api/v1/integrations/available` - List available providers
- `GET /api/v1/integrations/` - List my integrations
- `POST /api/v1/integrations/{provider}/connect` - Start OAuth flow
  - Body: `{"redirect_uri": "http://localhost:3000/integrations"}`
- `GET /api/v1/integrations/callback` - OAuth callback (redirects back to frontend)
- `DELETE /api/v1/integrations/{id}` - Disconnect integration
- `POST /api/v1/integrations/{id}/execute` - Execute provider action
  - Body: `{"action": "list_emails", "params": {"max_results": 10}}`

### Existing Endpoints
- `GET /api/v1/weather/current?lat=..&lon=..&timezone=..`
- `GET /api/v1/news/top?limit=10&q=..&sources=a,b`
- `GET /api/v1/dashboard/morning?lat=..&lon=..&timezone=..&limit=10&q=..`

## Integration System

### Supported Providers
- **Gmail** - Read emails, search, get threads (OAuth2 with `gmail.readonly` scope)
- More coming soon (Slack, Notion, Microsoft, etc.)

### OAuth2 Flow
1. Frontend calls `POST /integrations/{provider}/connect` with `redirect_uri`
2. Backend returns authorization URL
3. Frontend redirects user to authorization URL
4. User consents on provider's site
5. Provider redirects to `/integrations/callback`
6. Backend exchanges code for tokens, encrypts and stores them
7. Backend redirects back to original `redirect_uri`
8. User is back on integrations page, now connected!

### Adding New Integrations

1. Create service class in `app/services/integrations/{provider}.py`:
```python
from app.services.integrations.base import BaseIntegrationService
from app.services.integrations.registry import register_provider

@register_provider("provider_name")
class MyProviderService(BaseIntegrationService):
    provider_type = "provider_name"
    
    async def execute(self, session, integration_id, action, params):
        # Implement actions
        pass
    
    async def refresh_token(self, session, integration_id):
        # Handle token refresh
        pass
```

2. That's it! The provider will automatically appear in `/integrations/available`

## Security

- **JWT Authentication**: All endpoints (except public) require valid JWT token
- **Token Encryption**: All OAuth tokens encrypted with Fernet (AES-128) before storage
- **Rate Limiting**: 
  - Connect endpoint: 5/minute
  - Execute endpoint: 30/minute per user
  - Global: 100/minute per IP
- **Data Isolation**: Users can only access their own integrations

## Configuration

### Required Environment Variables
```bash
# Database
ASSISTME_DATABASE_URL=postgresql+asyncpg://assistme:devpassword@localhost:5433/assistme

# Security (generate strong keys for production!)
ASSISTME_SECRET_KEY=your-jwt-secret-key-min-32-characters-long
ASSISTME_ENCRYPTION_KEY=your-32-byte-base64-fernet-key-here-

# Google OAuth (for Gmail integration)
ASSISTME_GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
ASSISTME_GOOGLE_CLIENT_SECRET=your-google-client-secret
ASSISTME_OAUTH_CALLBACK_URL=http://localhost:8000/api/v1/integrations/callback
```

### Optional Environment Variables
- `ASSISTME_CORS_ORIGINS` - JSON array or comma-separated string
- `ASSISTME_RSS_FEEDS` - JSON array or comma-separated string
- `ASSISTME_RSS_TTL_SECONDS` (default 1200)
- `ASSISTME_WEATHER_TTL_SECONDS` (default 600)

## Database

- **PostgreSQL** with **pgvector** extension
- Port: **5433** (to avoid local PostgreSQL conflicts)
- Auto-creates tables on startup (for development)
- Alembic migrations available for production

## Architecture

### Project Structure
```
app/
├── db/                      # Database layer
│   ├── models/              # SQLAlchemy models
│   │   ├── user.py          # fastapi-users User model
│   │   ├── integration.py   # Integration & ProviderType
│   │   ├── integration_token.py  # Encrypted OAuth tokens
│   │   └── oauth_state.py   # OAuth flow state
│   ├── base.py              # SQLAlchemy base with pgvector
│   └── session.py           # Async session management
├── services/
│   ├── auth/                # fastapi-users setup
│   └── integrations/        # Integration services
│       ├── base.py          # Abstract base class
│       ├── registry.py      # Provider registration
│       ├── oauth.py         # Generic OAuth2 handler
│       └── gmail.py         # Gmail implementation
├── api/v1/endpoints/
│   ├── auth.py              # Auth endpoints
│   └── integrations.py      # Integration endpoints
├── core/
│   ├── security.py          # Fernet encryption
│   └── config.py            # Settings
└── main.py                  # App factory with lifespan
```

### Design Principles
- **Generic Integration Model**: One `Integration` table covers all providers via JSONB config
- **Provider Registration**: Decorator-based registration makes adding providers trivial
- **OAuth State Management**: Secure state parameter storage with 15-minute TTL
- **Auto Token Refresh**: Access tokens automatically refreshed when near expiry
- **Multi-tenant**: All queries filtered by `user_id` - complete data isolation
