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

type LoginBody = {
  identifier?: string;
  password?: string;
  remember_me?: boolean;
};

export async function POST(request: Request) {
  let body: LoginBody;
  try {
    body = (await request.json()) as LoginBody;
  } catch {
    return NextResponse.json({ code: 'invalid_request', detail: 'Enter your sign-in details.' }, { status: 400 });
  }

  try {
    const response = await fetch(backendApiUrl('auth/login/'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        identifier: body.identifier,
        password: body.password,
      }),
      cache: 'no-store',
    });
    const data = await readJsonResponse(response);

    if (!response.ok) {
      return NextResponse.json(data, { status: response.status });
    }

    const access = typeof data.access === 'string' ? data.access : '';
    const refresh = typeof data.refresh === 'string' ? data.refresh : '';
    if (!access || !refresh || !data.user) {
      return NextResponse.json(
        { code: 'invalid_response', detail: 'The sign-in service returned an invalid response.' },
        { status: 502 },
      );
    }

    const persistent = body.remember_me === true;
    const cookieStore = await cookies();
    cookieStore.set(ACCESS_COOKIE, access, {
      ...authCookieOptions,
      ...(persistent ? { maxAge: 15 * 60 } : {}),
    });
    cookieStore.set(REFRESH_COOKIE, refresh, {
      ...authCookieOptions,
      ...(persistent ? { maxAge: 7 * 24 * 60 * 60 } : {}),
    });
    cookieStore.set(REMEMBER_COOKIE, persistent ? '1' : '0', {
      ...authCookieOptions,
      ...(persistent ? { maxAge: 7 * 24 * 60 * 60 } : {}),
    });

    return NextResponse.json({ user: data.user }, { status: 200 });
  } catch {
    return NextResponse.json(
      { code: 'network_error', detail: "We couldn't connect to Tafiti." },
      { status: 503 },
    );
  }
}
