import { NextResponse } from 'next/server';

import { backendApiUrl, readJsonResponse } from '@/lib/backend';

export async function GET(request: Request) {
  try {
    const authorization = request.headers.get('authorization') || '';
    const response = await fetch(backendApiUrl('maintenance/library-daily/'), {
      method: 'GET',
      headers: { Authorization: authorization },
      cache: 'no-store',
    });
    return NextResponse.json(await readJsonResponse(response), { status: response.status });
  } catch {
    return NextResponse.json({ detail: 'Maintenance service is unavailable.' }, { status: 503 });
  }
}
