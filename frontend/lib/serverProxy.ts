import { cookies } from 'next/headers';

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

export async function authenticatedBackendGet(path: string) {
  const cookieStore = await cookies();
  let access = cookieStore.get(ACCESS_COOKIE)?.value ?? '';
  const refresh = cookieStore.get(REFRESH_COOKIE)?.value ?? '';

  if (!access && refresh) {
    access = await refreshAccess(refresh);
    if (access) cookieStore.set(ACCESS_COOKIE, access, authCookieOptions);
  }

  if (!access) {
    await clearAuthCookies();
    return { status: 401, body: { code: 'session_expired', detail: 'Your session has expired.' } };
  }

  let response: Response;
  try {
    response = await fetch(backendApiUrl(path), {
      headers: { Authorization: `Bearer ${access}` },
      cache: 'no-store',
    });
  } catch {
    return { status: 503, body: { code: 'network_error', detail: 'The school server could not be reached.' } };
  }

  if (response.status === 401 && refresh) {
    const nextAccess = await refreshAccess(refresh);
    if (nextAccess) {
      cookieStore.set(ACCESS_COOKIE, nextAccess, authCookieOptions);
      response = await fetch(backendApiUrl(path), {
        headers: { Authorization: `Bearer ${nextAccess}` },
        cache: 'no-store',
      });
    }
  }

  const body = await readJsonResponse(response);
  if (response.status === 401) await clearAuthCookies();
  return { status: response.status, body };
}
