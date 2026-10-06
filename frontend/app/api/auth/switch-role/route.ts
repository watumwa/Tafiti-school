import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';

import {
  ACCESS_COOKIE,
  REFRESH_COOKIE,
  REMEMBER_COOKIE,
  authCookieOptions,
  backendApiUrl,
  readJsonResponse,
} from '@/lib/backend';

export const dynamic = 'force-dynamic';

type SwitchRoleBody = {
  role?: string;
};

export async function POST(request: Request) {
  let body: SwitchRoleBody;
  try {
    body = (await request.json()) as SwitchRoleBody;
  } catch {
    return NextResponse.json({ code: 'invalid_request', detail: 'Choose a workspace to continue.' }, { status: 400 });
  }

  const cookieStore = await cookies();
  const access = cookieStore.get(ACCESS_COOKIE)?.value;
  if (!access) {
    return NextResponse.json({ code: 'session_expired', detail: 'Sign in again to continue.' }, { status: 401 });
  }

  try {
    const response = await fetch(backendApiUrl('auth/switch-role/'), {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${access}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ role: body.role }),
      cache: 'no-store',
    });
    const data = await readJsonResponse(response);

    if (!response.ok) {
      return NextResponse.json(data, { status: response.status });
    }

    const nextAccess = typeof data.access === 'string' ? data.access : '';
    const nextRefresh = typeof data.refresh === 'string' ? data.refresh : '';
    if (!nextAccess || !nextRefresh || !data.user) {
      return NextResponse.json(
        { code: 'invalid_response', detail: 'The workspace service returned an invalid response.' },
        { status: 502 },
      );
    }

    const persistent = cookieStore.get(REMEMBER_COOKIE)?.value === '1';
    cookieStore.set(ACCESS_COOKIE, nextAccess, {
      ...authCookieOptions,
      ...(persistent ? { maxAge: 15 * 60 } : {}),
    });
    cookieStore.set(REFRESH_COOKIE, nextRefresh, {
      ...authCookieOptions,
      ...(persistent ? { maxAge: 7 * 24 * 60 * 60 } : {}),
    });

    return NextResponse.json({ user: data.user }, { status: 200 });
  } catch {
    return NextResponse.json(
      { code: 'network_error', detail: "We couldn't switch workspaces right now." },
      { status: 503 },
    );
  }
}
