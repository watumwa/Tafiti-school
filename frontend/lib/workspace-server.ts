import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';

import {
  ACCESS_COOKIE,
  REFRESH_COOKIE,
  authCookieOptions,
  backendApiUrl,
  clearAuthCookies,
  readJsonResponse,
} from '@/lib/backend';

async function refreshAccess(refresh: string): Promise<string> {
  const response = await fetch(backendApiUrl('auth/refresh/'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh }),
    cache: 'no-store',
  });
  const result = await readJsonResponse(response);
  return response.ok && typeof result.access === 'string' ? result.access : '';
}

export async function proxyWorkspaceRequest(path: string, request?: Request) {
  const cookieStore = await cookies();
  const refresh = cookieStore.get(REFRESH_COOKIE)?.value ?? '';
  let access = cookieStore.get(ACCESS_COOKIE)?.value ?? '';

  try {
    if (!access && refresh) {
      access = await refreshAccess(refresh);
      if (access) cookieStore.set(ACCESS_COOKIE, access, authCookieOptions);
    }

    if (!access) {
      await clearAuthCookies();
      return NextResponse.json(
        { code: 'session_expired', detail: 'Your session has expired.' },
        { status: 401 },
      );
    }

    const incoming = request ? new URL(request.url) : null;
    const query = incoming?.search ?? '';
    const method = request?.method ?? 'GET';
    let body: BodyInit | undefined;
    let isJsonBody = false;

    if (request && !['GET', 'HEAD'].includes(method)) {
      const contentType = request.headers.get('content-type') ?? '';
      if (contentType.includes('application/json')) {
        body = await request.text();
        isJsonBody = true;
      } else if (contentType.includes('multipart/form-data')) {
        const incomingForm = await request.formData();
        const outgoingForm = new FormData();
        for (const [key, value] of incomingForm.entries()) outgoingForm.append(key, value);
        body = outgoingForm;
      }
    }

    const sendRequest = (token: string) => {
      const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
      if (isJsonBody) headers['Content-Type'] = 'application/json';
      return fetch(`${backendApiUrl(path)}${query}`, {
        method,
        headers,
        body,
        cache: 'no-store',
      });
    };

    let response = await sendRequest(access);
    if (response.status === 401 && refresh) {
      const nextAccess = await refreshAccess(refresh);
      if (nextAccess) {
        cookieStore.set(ACCESS_COOKIE, nextAccess, authCookieOptions);
        response = await sendRequest(nextAccess);
      }
    }

    const data = await readJsonResponse(response);
    if (!response.ok && !data.detail) data.detail = `The school server returned an error (${response.status}).`;
    if (response.status === 401) {
      await clearAuthCookies();
      return NextResponse.json(
        { code: 'session_expired', detail: 'Your session has expired. Please sign in again.' },
        { status: 401 },
      );
    }
    return NextResponse.json(data, { status: response.status });
  } catch {
    return NextResponse.json(
      { code: 'network_error', detail: 'The school server could not be reached.' },
      { status: 503 },
    );
  }
}
