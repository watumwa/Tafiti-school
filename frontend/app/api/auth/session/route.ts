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

export const dynamic = 'force-dynamic';

async function fetchProfile(access: string) {
  return fetch(backendApiUrl('auth/me/'), {
    headers: { Authorization: `Bearer ${access}` },
    cache: 'no-store',
  });
}

export async function GET() {
  const cookieStore = await cookies();
  const access = cookieStore.get(ACCESS_COOKIE)?.value;
  const refresh = cookieStore.get(REFRESH_COOKIE)?.value;

  try {
    if (access) {
      const profileResponse = await fetchProfile(access);
      if (profileResponse.ok) {
        return NextResponse.json(await readJsonResponse(profileResponse));
      }
      if (profileResponse.status !== 401) {
        return NextResponse.json(await readJsonResponse(profileResponse), { status: profileResponse.status });
      }
    }

    if (!refresh) {
      await clearAuthCookies();
      return NextResponse.json({ code: 'session_expired' }, { status: 401 });
    }

    const refreshResponse = await fetch(backendApiUrl('auth/refresh/'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh }),
      cache: 'no-store',
    });
    const refreshed = await readJsonResponse(refreshResponse);
    const nextAccess = typeof refreshed.access === 'string' ? refreshed.access : '';
    if (!refreshResponse.ok || !nextAccess) {
      await clearAuthCookies();
      return NextResponse.json({ code: 'session_expired' }, { status: 401 });
    }

    cookieStore.set(ACCESS_COOKIE, nextAccess, authCookieOptions);
    const profileResponse = await fetchProfile(nextAccess);
    const profile = await readJsonResponse(profileResponse);
    if (!profileResponse.ok) {
      await clearAuthCookies();
      return NextResponse.json(profile, { status: profileResponse.status });
    }
    return NextResponse.json(profile);
  } catch {
    return NextResponse.json({ code: 'network_error' }, { status: 503 });
  }
}
