import { NextResponse } from 'next/server';

import { authenticatedBackendGet } from '@/lib/serverProxy';

export const dynamic = 'force-dynamic';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ resource: string }> },
) {
  const { resource } = await params;
  const incoming = new URL(request.url);
  const query = incoming.searchParams.toString();
  const result = await authenticatedBackendGet(`workspace/${encodeURIComponent(resource)}/${query ? `?${query}` : ''}`);
  return NextResponse.json(result.body, { status: result.status });
}
