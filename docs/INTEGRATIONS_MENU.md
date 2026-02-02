# Integrations Menu (Next.js App Router)

This guide explains how to build the Connections/Integrations menu UI (matching the provided screenshot) and wire Gmail OAuth using the existing backend endpoints. Gmail is the only live integration; all others are shown as Coming Soon.

**Purpose & Scope**
- Provide a single “Connections” page to manage integrations.
- Gmail is live and actionable.
- Other integrations appear in the UI but are disabled.

---

**Backend Endpoints Used**
- `GET /api/v1/integrations/available`
- `GET /api/v1/integrations/`
- `POST /api/v1/integrations/gmail/connect`
- `DELETE /api/v1/integrations/{integration_id}`

---

**Data Model**

Create or reuse these types in your Next.js app. These match the backend responses.

```ts
// app/lib/types.ts
export type IntegrationStatus = 'active' | 'expired' | 'error' | 'disconnected';

export interface Integration {
  id: string;
  provider_type: 'gmail' | 'slack' | 'notion' | 'microsoft';
  status: IntegrationStatus;
  config: Record<string, any> | null;
  created_at: string;
  updated_at: string;
}

export interface AvailableProvider {
  provider_type: string;
  name: string;
  description: string;
}

export type IntegrationCategory = 'all' | 'mail' | 'productivity' | 'family' | 'calendar';

export interface IntegrationCatalogItem {
  provider_type: string;
  name: string;
  description: string;
  category: IntegrationCategory;
  icon: React.ReactNode;
  comingSoon: boolean;
}

export interface IntegrationCardState {
  provider_type: string;
  name: string;
  description: string;
  category: IntegrationCategory;
  icon: React.ReactNode;
  comingSoon: boolean;
  integrationId: string | null;
  status: IntegrationStatus | 'disconnected';
  enabled: boolean;
}
```

---

**Catalog + API Merge Strategy**

1. Define a static catalog that contains Gmail plus future providers.
2. Fetch `available` and `my integrations` from the backend.
3. Merge by `provider_type`.
4. Only allow actions for providers in `/available`.
5. Mark non-Gmail as `comingSoon` and disabled.

```ts
// app/lib/integrations/catalog.tsx
import { Mail, Calendar, FileText, MessageSquare } from 'lucide-react';
import { IntegrationCatalogItem } from '../types';

export const INTEGRATION_CATALOG: IntegrationCatalogItem[] = [
  {
    provider_type: 'gmail',
    name: 'Gmail',
    description: 'Read, draft, and manage emails.',
    category: 'mail',
    icon: <Mail className="h-5 w-5" />,
    comingSoon: false,
  },
  {
    provider_type: 'microsoft',
    name: 'Microsoft Outlook',
    description: 'Sync work emails and calendar.',
    category: 'mail',
    icon: <Mail className="h-5 w-5" />,
    comingSoon: true,
  },
  {
    provider_type: 'notion',
    name: 'Notion',
    description: 'Connect your workspace and notes.',
    category: 'productivity',
    icon: <FileText className="h-5 w-5" />,
    comingSoon: true,
  },
  {
    provider_type: 'slack',
    name: 'Slack',
    description: 'Get alerts and send messages.',
    category: 'productivity',
    icon: <MessageSquare className="h-5 w-5" />,
    comingSoon: true,
  },
  {
    provider_type: 'google_calendar',
    name: 'Google Calendar',
    description: 'Sync events and reminders.',
    category: 'calendar',
    icon: <Calendar className="h-5 w-5" />,
    comingSoon: true,
  },
];
```

```ts
// app/lib/integrations/merge.ts
import {
  AvailableProvider,
  Integration,
  IntegrationCardState,
  IntegrationStatus,
} from '../types';
import { INTEGRATION_CATALOG } from './catalog';

const AVAILABLE_SET = (available: AvailableProvider[]) =>
  new Set(available.map((p) => p.provider_type));

export function buildIntegrationCards(
  available: AvailableProvider[],
  mine: Integration[],
): IntegrationCardState[] {
  const availableSet = AVAILABLE_SET(available);
  const byProvider = new Map(mine.map((i) => [i.provider_type, i]));

  return INTEGRATION_CATALOG.map((item) => {
    const integration = byProvider.get(item.provider_type) || null;
    const status: IntegrationStatus | 'disconnected' = integration
      ? integration.status
      : 'disconnected';

    const enabled = availableSet.has(item.provider_type) && !item.comingSoon;

    return {
      provider_type: item.provider_type,
      name: item.name,
      description: item.description,
      category: item.category,
      icon: item.icon,
      comingSoon: item.comingSoon,
      integrationId: integration ? integration.id : null,
      status,
      enabled,
    };
  });
}
```

---

**Status → UI Mapping**

Use a small helper for status labels and actions.

```ts
// app/lib/integrations/status.ts
export function statusLabel(status: string): string {
  if (status === 'active') return 'In Sync';
  if (status === 'expired') return 'Action Required';
  if (status === 'error') return 'Error';
  if (status === 'disconnected') return 'Disconnected';
  return 'Unknown';
}

export function primaryActionLabel(status: string): 'Connect' | 'Reconnect' | 'Configure' {
  if (status === 'active') return 'Configure';
  if (status === 'expired' || status === 'error') return 'Reconnect';
  return 'Connect';
}
```

Mapping logic:
- `active` → “In Sync”, toggle on, “Configure” optional
- `expired` → “Action Required”, toggle on, “Reconnect”
- `error` → “Error”, toggle on, “Reconnect”
- missing → “Disconnected”, toggle off, “Connect”
- comingSoon → disabled, “Coming Soon”

---

**Connection Flow**

```ts
// app/lib/integrations/api.ts
'use server';

import { redirect } from 'next/navigation';
import { cookies } from 'next/headers';
import { AvailableProvider, Integration } from '../types';

const API_URL = process.env.API_URL || 'http://localhost:8000';

async function authHeader() {
  const token = (await cookies()).get('jwt_token')?.value;
  if (!token) redirect('/login');
  return { Authorization: `Bearer ${token}` };
}

export async function getAvailableIntegrations(): Promise<AvailableProvider[]> {
  const res = await fetch(`${API_URL}/api/v1/integrations/available`, {
    headers: {
      ...(await authHeader()),
    },
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to load available integrations');
  return res.json();
}

export async function getMyIntegrations(): Promise<Integration[]> {
  const res = await fetch(`${API_URL}/api/v1/integrations/`, {
    headers: {
      ...(await authHeader()),
    },
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to load integrations');
  const data = await res.json();
  return data.items || [];
}

export async function connectGmail(redirectUri: string): Promise<{ authorization_url: string }> {
  const res = await fetch(`${API_URL}/api/v1/integrations/gmail/connect`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(await authHeader()),
    },
    body: JSON.stringify({ redirect_uri: redirectUri }),
  });
  if (!res.ok) throw new Error('Failed to start Gmail OAuth');
  return res.json();
}

export async function disconnectIntegration(integrationId: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/integrations/${integrationId}`, {
    method: 'DELETE',
    headers: {
      ...(await authHeader()),
    },
  });
  if (!res.ok) throw new Error('Failed to disconnect integration');
}
```

Client-side connect action:

```ts
// app/components/integrations/ConnectButton.tsx
'use client';

import { connectGmail } from '@/app/lib/integrations/api';

export async function startGmailOAuth() {
  const redirectUri = window.location.href;
  const { authorization_url } = await connectGmail(redirectUri);
  window.location.href = authorization_url;
}
```

After OAuth returns to your page, refresh the integrations list from `/integrations/`.

---

**Disconnect Flow**

```ts
// app/components/integrations/DisconnectButton.tsx
'use client';

import { disconnectIntegration } from '@/app/lib/integrations/api';

export async function disconnect(integrationId: string) {
  const ok = window.confirm('Disconnect this integration?');
  if (!ok) return;
  await disconnectIntegration(integrationId);
}
```

---

**Search + Filters**

Required filters:
- `All Apps`
- `Mail`
- `Productivity`
- `Family`
- `Calendar`

Filtering should match name or description. Empty state should show “No integrations found” and a short message.

---

**“Request New Integration” Action**

Provide a placeholder for your product’s request flow (modal, form, or mailto).

```ts
// app/components/integrations/RequestIntegration.tsx
'use client';

export function requestNewIntegration() {
  // TODO: replace with your request flow
  window.open('https://your-form-url.example.com', '_blank');
}
```

---

**UI Implementation Notes**

Use the provided screenshot as the style target.

Layout:
- Header with title + subtext
- Search input
- Category tabs
- Card grid
- Footer CTA

Card structure:
- Icon
- Name
- Description
- Status badge
- Toggle (on for active/expired/error)
- Primary action button (`Connect` / `Reconnect` / `Configure`)

Coming Soon:
- Disabled buttons
- Secondary label “Coming Soon”

---

**Error Handling**

Handle these cases in the UI:
- `401/403` → redirect to login or show session expired
- `429` → show rate-limit message
- network errors → show a toast or banner

---

**Manual Test Scenarios**

1. Connect Gmail success flow.
2. Disconnect Gmail.
3. Manually set status to `expired` in DB and confirm UI shows “Action Required”.
4. Coming Soon cards do not call API.
5. Filters and search work together and show empty state when no match.

---

**Notes**
- Gmail is the only live provider. Others are intentionally disabled until backend support is ready.
- When additional providers go live, remove `comingSoon` and ensure they appear in `/integrations/available`.
