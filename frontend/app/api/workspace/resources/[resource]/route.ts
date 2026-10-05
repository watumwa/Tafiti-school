import { NextResponse } from 'next/server';

import { proxyWorkspaceRequest } from '@/lib/workspace-server';

export const dynamic = 'force-dynamic';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ resource: string }> },
) {
  const { resource } = await params;
  if (!/^[a-z-]+$/.test(resource)) {
    return NextResponse.json({ detail: 'Invalid workspace resource.' }, { status: 400 });
  }
  return proxyWorkspaceRequest(`workspace/resources/${resource}/`, request);
}
