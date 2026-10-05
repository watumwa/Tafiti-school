import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';

import { ACCESS_COOKIE, backendApiUrl, readJsonResponse } from '@/lib/backend';

export const dynamic = 'force-dynamic';

export async function POST(request: Request) {
  const access = (await cookies()).get(ACCESS_COOKIE)?.value;
  if (!access) return NextResponse.json({ code: 'session_expired' }, { status: 401 });

  try {
    const body = (await request.json()) as Record<string, unknown>;
    const response = await fetch(backendApiUrl('auth/password/change/'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${access}`,
      },
      body: JSON.stringify(body),
      cache: 'no-store',
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch {
    return NextResponse.json({ code: 'network_error' }, { status: 503 });
  }
}
