import { NextResponse } from 'next/server';

import { backendApiUrl, readJsonResponse } from '@/lib/backend';

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as { email?: string };
    const response = await fetch(backendApiUrl('auth/password/reset/'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: body.email }),
      cache: 'no-store',
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch {
    return NextResponse.json({ code: 'network_error' }, { status: 503 });
  }
}
