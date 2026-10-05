import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';

import { ACCESS_COOKIE, backendApiUrl, readJsonResponse } from '@/lib/backend';

const endpoints: Record<string, string> = {
  students: 'students/',
  academics: 'grades/',
  finance: 'fees/',
};

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ resource: string }> },
) {
  const { resource } = await params;
  const endpoint = endpoints[resource];
  if (!endpoint) {
    return NextResponse.json({ detail: 'Unknown school data resource.' }, { status: 404 });
  }

  const access = (await cookies()).get(ACCESS_COOKIE)?.value;
  if (!access) {
    return NextResponse.json({ detail: 'Your session has expired.' }, { status: 401 });
  }

  let response: Response;
  try {
    response = await fetch(backendApiUrl(endpoint), {
      headers: { Authorization: `Bearer ${access}` },
      cache: 'no-store',
    });
  } catch {
    return NextResponse.json({ detail: 'The school server could not be reached.' }, { status: 503 });
  }

  const result = await readJsonResponse(response);
  if (!response.ok && !result.detail) {
    result.detail = `The school server returned an error (${response.status}).`;
  }
  return NextResponse.json(result, { status: response.status });
}