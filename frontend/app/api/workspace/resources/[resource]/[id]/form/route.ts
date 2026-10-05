import { NextResponse } from 'next/server';

import { proxyWorkspaceRequest } from '@/lib/workspace-server';

export const dynamic = 'force-dynamic';

function validate(resource: string, id: string) {
  return /^[a-z-]+$/.test(resource) && /^\d+$/.test(id);
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ resource: string; id: string }> },
) {
  const { resource, id } = await params;
  if (!validate(resource, id)) return NextResponse.json({ detail: 'Invalid resource request.' }, { status: 400 });
  return proxyWorkspaceRequest(`workspace/resources/${resource}/${id}/form/`, request);
}

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ resource: string; id: string }> },
) {
  const { resource, id } = await params;
  if (!validate(resource, id)) return NextResponse.json({ detail: 'Invalid resource request.' }, { status: 400 });
  return proxyWorkspaceRequest(`workspace/resources/${resource}/${id}/form/`, request);
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ resource: string; id: string }> },
) {
  const { resource, id } = await params;
  if (!validate(resource, id)) return NextResponse.json({ detail: 'Invalid resource request.' }, { status: 400 });
  return proxyWorkspaceRequest(`workspace/resources/${resource}/${id}/form/`, request);
}
