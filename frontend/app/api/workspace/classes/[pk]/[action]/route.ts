import { NextResponse } from 'next/server';

import { proxyWorkspaceRequest } from '@/lib/workspace-server';

export const dynamic = 'force-dynamic';

const actions = new Set(['register-form', 'promotion-form', 'register', 'promote']);

export async function GET(
  request: Request,
  { params }: { params: Promise<{ pk: string; action: string }> },
) {
  const { pk, action } = await params;
  if (!/^\d+$/.test(pk) || !actions.has(action) || !action.endsWith('-form')) {
    return NextResponse.json({ detail: 'Invalid class workflow request.' }, { status: 400 });
  }
  return proxyWorkspaceRequest(`workspace/classes/${pk}/${action}/`, request);
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ pk: string; action: string }> },
) {
  const { pk, action } = await params;
  if (!/^\d+$/.test(pk) || !actions.has(action) || action.endsWith('-form')) {
    return NextResponse.json({ detail: 'Invalid class workflow request.' }, { status: 400 });
  }
  return proxyWorkspaceRequest(`workspace/classes/${pk}/${action}/`, request);
}
