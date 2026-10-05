import { NextResponse } from 'next/server';

import { proxyWorkspaceRequest } from '@/lib/workspace-server';

export const dynamic = 'force-dynamic';

function validResource(resource: string) {
  return /^[a-z-]+$/.test(resource);
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ resource: string }> },
) {
  const { resource } = await params;
  if (!validResource(resource)) return NextResponse.json({ detail: 'Invalid resource.' }, { status: 400 });
  return proxyWorkspaceRequest(`workspace/resources/${resource}/form/`, request);
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ resource: string }> },
) {
  const { resource } = await params;
  if (!validResource(resource)) return NextResponse.json({ detail: 'Invalid resource.' }, { status: 400 });
  return proxyWorkspaceRequest(`workspace/resources/${resource}/form/`, request);
}
