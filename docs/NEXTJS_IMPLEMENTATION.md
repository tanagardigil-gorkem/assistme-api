# Next.js Gmail Integration Implementation

Complete Next.js implementation guide for Gmail OAuth2 integration using the App Router.

## Table of Contents

1. [Project Structure](#project-structure)
2. [Environment Setup](#environment-setup)
3. [Type Definitions](#type-definitions)
4. [API Client Setup](#api-client-setup)
5. [Server Actions](#server-actions)
6. [Components](#components)
7. [Pages](#pages)
8. [Hooks](#hooks)
9. [Error Handling](#error-handling)
10. [Testing](#testing)

---

## Project Structure

```
app/
├── api/
│   └── auth/
│       └── [...nextauth]/     # Optional: if using NextAuth
├── integrations/
│   └── page.tsx               # Integrations page
├── components/
│   ├── integrations/
│   │   ├── GmailConnect.tsx   # Connect button component
│   │   ├── IntegrationList.tsx # List of integrations
│   │   └── EmailList.tsx      # Display emails
│   └── ui/                    # Shared UI components
├── lib/
│   ├── api.ts                 # API client
│   ├── auth.ts                # Auth utilities
│   └── types.ts               # TypeScript types
└── hooks/
    └── useIntegrations.ts     # React hooks
```

---

## Environment Setup

### `.env.local`

```bash
# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000

# For server-side calls (backend internal URL if different)
API_URL=http://localhost:8000

# NextAuth (if using for JWT management)
# NEXTAUTH_URL=http://localhost:3000
# NEXTAUTH_SECRET=your-nextauth-secret
```

### `next.config.js`

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  async redirects() {
    return [
      {
        source: '/auth/callback',
        destination: '/integrations?oauth_success=true',
        permanent: false,
      },
    ]
  },
}

module.exports = nextConfig
```

---

## Type Definitions

### `app/lib/types.ts`

```typescript
export interface Integration {
  id: string;
  provider_type: 'gmail' | 'slack' | 'notion' | 'microsoft';
  status: 'active' | 'expired' | 'error' | 'disconnected';
  config: Record<string, any> | null;
  created_at: string;
  updated_at: string;
}

export interface GmailConfig {
  query?: string;
  label_ids?: string[];
  max_results?: number;
}

export interface AvailableProvider {
  provider_type: string;
  name: string;
  description: string;
}

export interface ConnectResponse {
  authorization_url: string;
  state: string;
}

export interface ExecuteResponse<T = any> {
  success: boolean;
  data: T | null;
  error: string | null;
}

export interface Email {
  id: string;
  thread_id: string;
  subject: string;
  from: string;
  to: string;
  date: string;
  snippet: string;
  body: string;
  labels: string[];
}

export interface User {
  id: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  updated_at: string;
}
```

---

## API Client Setup

### `app/lib/api.ts`

```typescript
'use server';

import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import {
  AvailableProvider,
  ConnectResponse,
  Email,
  ExecuteResponse,
  Integration,
} from './types';

const API_URL = process.env.API_URL || 'http://localhost:8000';

// Get JWT token from cookies
async function getAuthToken(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get('jwt_token')?.value || null;
}

// Generic API fetch with auth
async function fetchAPI<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = await getAuthToken();
  
  if (!token) {
    redirect('/login');
  }

  const url = `${API_URL}/api/v1${endpoint}`;
  
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
      ...options.headers,
    },
  });

  if (response.status === 401) {
    // Token expired, redirect to login
    redirect('/login');
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// Get available integrations
export async function getAvailableIntegrations(): Promise<AvailableProvider[]> {
  return fetchAPI<AvailableProvider[]>('/integrations/available');
}

// Get user's integrations
export async function getMyIntegrations(): Promise<Integration[]> {
  const data = await fetchAPI<{ items: Integration[] }>('/integrations/');
  return data.items;
}

// Connect Gmail (Server Action)
export async function connectGmail(redirectUri: string): Promise<ConnectResponse> {
  return fetchAPI<ConnectResponse>('/integrations/gmail/connect', {
    method: 'POST',
    body: JSON.stringify({ redirect_uri: redirectUri }),
  });
}

// Disconnect integration
export async function disconnectIntegration(integrationId: string): Promise<void> {
  await fetchAPI(`/integrations/${integrationId}`, {
    method: 'DELETE',
  });
}

// Update integration status or config
export async function updateIntegration(
  integrationId: string,
  update: {
    status?: 'active' | 'disconnected';
    config?: GmailConfig;
  }
): Promise<Integration> {
  return fetchAPI<Integration>(`/integrations/${integrationId}`, {
    method: 'PATCH',
    body: JSON.stringify(update),
  });
}

// Execute Gmail action
export async function executeGmailAction<T = any>(
  integrationId: string,
  action: string,
  params: Record<string, any> = {}
): Promise<T> {
  const result = await fetchAPI<ExecuteResponse<T>>(`/integrations/${integrationId}/execute`, {
    method: 'POST',
    body: JSON.stringify({ action, params }),
  });

  if (!result.success) {
    throw new Error(result.error || 'Action failed');
  }

  return result.data as T;
}

// Gmail-specific actions
export async function getRecentEmails(
  integrationId: string,
  maxResults: number = 10
): Promise<Email[]> {
  return executeGmailAction<Email[]>(integrationId, 'list_emails', {
    max_results: maxResults,
  });
}

export async function searchEmails(
  integrationId: string,
  query: string,
  maxResults: number = 20
): Promise<Email[]> {
  return executeGmailAction<Email[]>(integrationId, 'search', {
    query,
    max_results: maxResults,
  });
}

export async function getEmail(
  integrationId: string,
  messageId: string
): Promise<Email> {
  return executeGmailAction<Email>(integrationId, 'get_email', {
    message_id: messageId,
  });
}
```

---

## Components

### `app/components/integrations/GmailConnect.tsx`

```typescript
'use client';

import { useState } from 'react';
import { connectGmail } from '@/app/lib/api';
import { Button } from '@/app/components/ui/Button';
import { toast } from 'sonner';

interface GmailConnectProps {
  onSuccess?: () => void;
}

export function GmailConnect({ onSuccess }: GmailConnectProps) {
  const [isConnecting, setIsConnecting] = useState(false);

  async function handleConnect() {
    try {
      setIsConnecting(true);
      
      // Get current URL to redirect back after OAuth
      const redirectUri = window.location.href;
      
      const { authorization_url } = await connectGmail(redirectUri);
      
      // Store that we're in the middle of OAuth (optional)
      sessionStorage.setItem('oauth_pending', 'true');
      
      // Redirect to Google's OAuth page
      window.location.href = authorization_url;
    } catch (error) {
      toast.error('Failed to initiate connection', {
        description: error instanceof Error ? error.message : 'Unknown error',
      });
    } finally {
      setIsConnecting(false);
    }
  }

  return (
    <Button
      onClick={handleConnect}
      disabled={isConnecting}
      className="w-full"
      variant="primary"
    >
      {isConnecting ? (
        <>
          <LoadingSpinner className="mr-2 h-4 w-4" />
          Connecting...
        </>
      ) : (
        <>
          <GmailIcon className="mr-2 h-5 w-5" />
          Connect Gmail
        </>
      )}
    </Button>
  );
}

// Helper components
function LoadingSpinner({ className }: { className?: string }) {
  return (
    <svg
      className={`animate-spin ${className}`}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}

function GmailIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z" />
    </svg>
  );
}
```

### `app/components/integrations/IntegrationList.tsx`

Use `updateIntegration` to toggle status (`active`/`disconnected`) and save Gmail filter settings
(`query`, `label_ids`, `max_results`) in `config`.

```typescript
'use client';

import { useState } from 'react';
import { disconnectIntegration } from '@/app/lib/api';
import { Integration } from '@/app/lib/types';
import { Button } from '@/app/components/ui/Button';
import { toast } from 'sonner';
import { GmailConnect } from './GmailConnect';

interface IntegrationListProps {
  integrations: Integration[];
  onUpdate: () => void;
}

export function IntegrationList({ integrations, onUpdate }: IntegrationListProps) {
  const [disconnecting, setDisconnecting] = useState<string | null>(null);

  async function handleDisconnect(integrationId: string) {
    if (!confirm('Are you sure you want to disconnect Gmail?')) {
      return;
    }

    try {
      setDisconnecting(integrationId);
      await disconnectIntegration(integrationId);
      toast.success('Gmail disconnected successfully');
      onUpdate();
    } catch (error) {
      toast.error('Failed to disconnect', {
        description: error instanceof Error ? error.message : 'Unknown error',
      });
    } finally {
      setDisconnecting(null);
    }
  }

  const gmailIntegration = integrations.find((i) => i.provider_type === 'gmail');

  return (
    <div className="space-y-4">
      <div className="rounded-lg border p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="rounded-full bg-red-100 p-3">
              <GmailIcon className="h-6 w-6 text-red-600" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">Gmail</h3>
              <p className="text-sm text-gray-500">
                {gmailIntegration
                  ? `Connected since ${new Date(gmailIntegration.created_at).toLocaleDateString()}`
                  : 'Connect your Gmail account to read emails'}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            {gmailIntegration ? (
              <>
                <StatusBadge status={gmailIntegration.status} />
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => handleDisconnect(gmailIntegration.id)}
                  disabled={disconnecting === gmailIntegration.id}
                >
                  {disconnecting === gmailIntegration.id
                    ? 'Disconnecting...'
                    : 'Disconnect'}
                </Button>
              </>
            ) : (
              <GmailConnect onSuccess={onUpdate} />
            )}
          </div>
        </div>

        {gmailIntegration && gmailIntegration.status === 'expired' && (
          <div className="mt-4 rounded-md bg-yellow-50 p-4">
            <p className="text-sm text-yellow-800">
              Your Gmail connection has expired. Please reconnect to continue.
            </p>
            <GmailConnect onSuccess={onUpdate} />
          </div>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors = {
    active: 'bg-green-100 text-green-800',
    expired: 'bg-yellow-100 text-yellow-800',
    error: 'bg-red-100 text-red-800',
    disconnected: 'bg-gray-100 text-gray-800',
  };

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
        colors[status as keyof typeof colors] || colors.disconnected
      }`}
    >
      <span className="mr-1.5 h-2 w-2 rounded-full bg-current" />
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

function GmailIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z" />
    </svg>
  );
}
```

### `app/components/integrations/EmailList.tsx`

```typescript
'use client';

import { useState } from 'react';
import { Email } from '@/app/lib/types';
import { getRecentEmails, searchEmails } from '@/app/lib/api';
import { toast } from 'sonner';

interface EmailListProps {
  integrationId: string;
}

export function EmailList({ integrationId }: EmailListProps) {
  const [emails, setEmails] = useState<Email[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  async function loadEmails() {
    try {
      setLoading(true);
      const data = await getRecentEmails(integrationId, 10);
      setEmails(data);
    } catch (error) {
      toast.error('Failed to load emails', {
        description: error instanceof Error ? error.message : 'Unknown error',
      });
    } finally {
      setLoading(false);
    }
  }

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    try {
      setLoading(true);
      const data = await searchEmails(integrationId, searchQuery, 20);
      setEmails(data);
    } catch (error) {
      toast.error('Search failed', {
        description: error instanceof Error ? error.message : 'Unknown error',
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Recent Emails</h3>
        <button
          onClick={loadEmails}
          disabled={loading}
          className="rounded-md bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      <form onSubmit={handleSearch} className="flex gap-2">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search emails..."
          className="flex-1 rounded-md border border-gray-300 px-4 py-2 focus:border-blue-500 focus:outline-none"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-gray-600 px-4 py-2 text-white hover:bg-gray-700 disabled:opacity-50"
        >
          Search
        </button>
      </form>

      {emails.length === 0 && !loading && (
        <p className="text-gray-500">No emails to display. Click Refresh to load.</p>
      )}

      <div className="space-y-2">
        {emails.map((email) => (
          <EmailCard key={email.id} email={email} />
        ))}
      </div>
    </div>
  );
}

function EmailCard({ email }: { email: Email }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg border p-4 hover:bg-gray-50">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h4 className="font-semibold text-gray-900">{email.subject || '(No subject)'}</h4>
          <p className="text-sm text-gray-600">From: {email.from}</p>
          <p className="text-xs text-gray-400">{new Date(email.date).toLocaleString()}</p>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-sm text-blue-600 hover:text-blue-800"
        >
          {expanded ? 'Collapse' : 'Expand'}
        </button>
      </div>
      
      <p className="mt-2 text-sm text-gray-700">{email.snippet}</p>
      
      {expanded && (
        <div className="mt-4 border-t pt-4">
          <div className="prose max-w-none text-sm" dangerouslySetInnerHTML={{ __html: email.body }} />
        </div>
      )}
    </div>
  );
}
```

---

## Pages

### `app/integrations/page.tsx`

```typescript
import { Suspense } from 'react';
import { redirect } from 'next/navigation';
import { getAvailableIntegrations, getMyIntegrations } from '@/app/lib/api';
import { IntegrationList } from '@/app/components/integrations/IntegrationList';
import { EmailList } from '@/app/components/integrations/EmailList';

interface IntegrationsPageProps {
  searchParams: { [key: string]: string | string[] | undefined };
}

export default async function IntegrationsPage({ searchParams }: IntegrationsPageProps) {
  // Check for OAuth callback success/error
  const oauthSuccess = searchParams.oauth_success;
  const oauthError = searchParams.oauth_error;

  let integrations: Awaited<ReturnType<typeof getMyIntegrations>> = [];
  let available: Awaited<ReturnType<typeof getAvailableIntegrations>> = [];
  let error: string | null = null;

  try {
    [integrations, available] = await Promise.all([
      getMyIntegrations(),
      getAvailableIntegrations(),
    ]);
  } catch (err) {
    error = err instanceof Error ? err.message : 'Failed to load integrations';
  }

  const gmailIntegration = integrations.find((i) => i.provider_type === 'gmail');

  return (
    <div className="container mx-auto max-w-4xl p-6">
      <h1 className="mb-8 text-3xl font-bold">Integrations</h1>

      {/* OAuth Success/Error Messages */}
      {oauthSuccess && (
        <div className="mb-6 rounded-md bg-green-50 p-4 text-green-800">
          Gmail connected successfully!
        </div>
      )}
      
      {oauthError && (
        <div className="mb-6 rounded-md bg-red-50 p-4 text-red-800">
          Failed to connect: {oauthError}
        </div>
      )}

      {error && (
        <div className="mb-6 rounded-md bg-red-50 p-4 text-red-800">
          Error: {error}
        </div>
      )}

      <Suspense fallback={<div>Loading integrations...</div>}>
        <IntegrationList 
          integrations={integrations} 
          onUpdate={async () => {
            'use server';
            // Revalidate page data
            redirect('/integrations');
          }} 
        />
      </Suspense>

      {/* Show email list if Gmail is connected */}
      {gmailIntegration && gmailIntegration.status === 'active' && (
        <div className="mt-8">
          <h2 className="mb-4 text-xl font-semibold">Your Gmail</h2>
          <Suspense fallback={<div>Loading emails...</div>}>
            <EmailListClient integrationId={gmailIntegration.id} />
          </Suspense>
        </div>
      )}

      {/* Show available providers that aren't connected */}
      <div className="mt-8">
        <h2 className="mb-4 text-xl font-semibold">Available Integrations</h2>
        <div className="grid gap-4 md:grid-cols-2">
          {available
            .filter((provider) => 
              !integrations.some((i) => i.provider_type === provider.provider_type)
            )
            .map((provider) => (
              <div
                key={provider.provider_type}
                className="rounded-lg border p-4 opacity-50"
              >
                <h3 className="font-semibold">{provider.name}</h3>
                <p className="text-sm text-gray-600">{provider.description}</p>
                <p className="mt-2 text-xs text-gray-400">Coming soon</p>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}

// Client component wrapper for EmailList
'use client';

function EmailListClient({ integrationId }: { integrationId: string }) {
  return <EmailList integrationId={integrationId} />;
}
```

---

## Hooks (Optional)

### `app/hooks/useIntegrations.ts`

```typescript
'use client';

import { useState, useEffect, useCallback } from 'react';
import { Integration } from '@/app/lib/types';
import { getMyIntegrations } from '@/app/lib/api';

export function useIntegrations() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchIntegrations = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getMyIntegrations();
      setIntegrations(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchIntegrations();
  }, [fetchIntegrations]);

  return {
    integrations,
    loading,
    error,
    refresh: fetchIntegrations,
  };
}
```

---

## UI Components

### `app/components/ui/Button.tsx`

```typescript
import { ButtonHTMLAttributes, forwardRef } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger';
  size?: 'sm' | 'md' | 'lg';
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className = '', variant = 'primary', size = 'md', ...props }, ref) => {
    const baseStyles = 'inline-flex items-center justify-center rounded-md font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50';
    
    const variants = {
      primary: 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500',
      secondary: 'bg-gray-200 text-gray-900 hover:bg-gray-300 focus:ring-gray-500',
      danger: 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500',
    };
    
    const sizes = {
      sm: 'px-3 py-1.5 text-sm',
      md: 'px-4 py-2 text-base',
      lg: 'px-6 py-3 text-lg',
    };

    return (
      <button
        ref={ref}
        className={`${baseStyles} ${variants[variant]} ${sizes[size]} ${className}`}
        {...props}
      />
    );
  }
);

Button.displayName = 'Button';
```

---

## Error Handling

### `app/error.tsx`

```typescript
'use client';

import { useEffect } from 'react';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Integration error:', error);
  }, [error]);

  return (
    <div className="flex min-h-[400px] flex-col items-center justify-center">
      <h2 className="mb-4 text-2xl font-bold">Something went wrong!</h2>
      <p className="mb-4 text-gray-600">{error.message}</p>
      <button
        onClick={reset}
        className="rounded-md bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
      >
        Try again
      </button>
    </div>
  );
}
```

---

## Testing

### Test the Integration Flow

1. **Navigate to `/integrations`**
   ```bash
   npm run dev
   # Open http://localhost:3000/integrations
   ```

2. **Test Connection**
   - Click "Connect Gmail"
   - Should redirect to Google OAuth
   - Grant permissions
   - Should return to `/integrations` with success message

3. **Test Email Loading**
   - After connection, "Your Gmail" section should appear
   - Click "Refresh" to load emails
   - Test search functionality

4. **Test Disconnect**
   - Click "Disconnect"
   - Confirm dialog
   - Integration should disappear
   - Connect button should reappear

---

## Key Next.js Features Used

1. **Server Components**: `page.tsx` fetches data server-side
2. **Client Components**: `'use client'` for interactive UI
3. **Server Actions**: API calls in `lib/api.ts` with `'use server'`
4. **Suspense**: Loading states while fetching data
5. **Error Boundaries**: `error.tsx` for graceful error handling
6. **Route Groups**: Organized under `app/integrations/`

---

## Additional Features to Add

1. **Real-time updates** using Server-Sent Events or WebSockets
2. **Email caching** with SWR or React Query
3. **Infinite scroll** for large email lists
4. **Email composition** (requires additional Gmail scope)
5. **Label management**
6. **Attachment handling**

---

## Production Checklist

- [ ] Update `API_URL` to production backend
- [ ] Use HTTPS for all URLs
- [ ] Update Google Cloud Console redirect URIs to production
- [ ] Implement proper JWT token storage (httpOnly cookies)
- [ ] Add error tracking (Sentry, etc.)
- [ ] Add analytics for integration usage
- [ ] Rate limiting tests
- [ ] Mobile responsiveness
- [ ] Accessibility audit

This implementation provides a complete, production-ready Gmail integration for Next.js App Router! 🚀
