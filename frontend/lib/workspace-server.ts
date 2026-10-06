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

async function authenticatedToken() {
  const cookieStore = await cookies();
  const refresh = cookieStore.get(REFRESH_COOKIE)?.value ?? '';
  let access = cookieStore.get(ACCESS_COOKIE)?.value ?? '';
  if (!access && refresh) {
    access = await refreshAccess(refresh);
    if (access) cookieStore.set(ACCESS_COOKIE, access, authCookieOptions);
  }
  return { cookieStore, refresh, access };
}

export async function proxyWorkspaceRequest(path: string, request?: Request) {
  const { cookieStore, refresh, access: initialAccess } = await authenticatedToken();
  let access = initialAccess;

  try {
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
        access = nextAccess;
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

export async function proxyWorkspaceDownload(path: string, request: Request) {
  const { cookieStore, refresh, access: initialAccess } = await authenticatedToken();
  let access = initialAccess;

  try {
    if (!access) {
      await clearAuthCookies();
      return NextResponse.json({ code: 'session_expired', detail: 'Your session has expired.' }, { status: 401 });
    }

    const query = new URL(request.url).search;
    const sendRequest = (token: string) => fetch(`${backendApiUrl(path)}${query}`, {
      method: 'GET',
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    });

    let response = await sendRequest(access);
    if (response.status === 401 && refresh) {
      const nextAccess = await refreshAccess(refresh);
      if (nextAccess) {
        access = nextAccess;
        cookieStore.set(ACCESS_COOKIE, nextAccess, authCookieOptions);
        response = await sendRequest(nextAccess);
      }
    }

    if (response.status === 401) {
      await clearAuthCookies();
      return NextResponse.json({ code: 'session_expired', detail: 'Your session has expired. Please sign in again.' }, { status: 401 });
    }

    if (!response.ok) {
      const data = await readJsonResponse(response);
      return NextResponse.json(data, { status: response.status });
    }

    const headers = new Headers();
    const contentType = response.headers.get('content-type');
    const disposition = response.headers.get('content-disposition');
    if (contentType) headers.set('content-type', contentType);
    if (disposition) headers.set('content-disposition', disposition);
    headers.set('cache-control', 'no-store');
    return new Response(await response.arrayBuffer(), { status: response.status, headers });
  } catch {
    return NextResponse.json({ code: 'network_error', detail: 'The school server could not be reached.' }, { status: 503 });
  }
}
