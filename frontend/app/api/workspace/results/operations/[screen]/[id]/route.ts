import { NextResponse } from 'next/server';

import { proxyWorkspaceRequest } from '@/lib/workspace-server';

export const dynamic = 'force-dynamic';

async function resolvePath(screen: string, id: string) {
  if (!/^\d+$/.test(id)) return null;
  return `workspace/results/operations/${screen}/${id}/`;
}

export async function GET(request: Request, { params }: { params: Promise<{ screen: string; id: string }> }) {
  const { screen, id } = await params;
  const path = await resolvePath(screen, id);
  if (!path) return NextResponse.json({ detail: 'Invalid report-card class.' }, { status: 400 });
  return proxyWorkspaceRequest(path, request);
}

export async function POST(request: Request, { params }: { params: Promise<{ screen: string; id: string }> }) {
  const { screen, id } = await params;
  const path = await resolvePath(screen, id);
  if (!path) return NextResponse.json({ detail: 'Invalid report-card class.' }, { status: 400 });
  return proxyWorkspaceRequest(path, request);
}
