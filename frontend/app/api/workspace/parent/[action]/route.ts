import { NextResponse } from 'next/server';

import { proxyWorkspaceRequest } from '@/lib/workspace-server';

export const dynamic = 'force-dynamic';

const allowedActions = new Set([
  'profile',
  'children',
  'results',
  'attendance',
  'finance',
  'calendar',
  'communication',
  'notifications',
  'reports',
  'message',
  'reply',
  'notifications-read',
  'report',
]);

export async function GET(
  request: Request,
  { params }: { params: Promise<{ action: string }> },
) {
  const { action } = await params;
  if (!allowedActions.has(action)) {
    return NextResponse.json({ detail: 'Unknown parent workspace action.' }, { status: 404 });
  }
  return proxyWorkspaceRequest(`workspace/parent/${action}/`, request);
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ action: string }> },
) {
  const { action } = await params;
  if (!allowedActions.has(action)) {
    return NextResponse.json({ detail: 'Unknown parent workspace action.' }, { status: 404 });
  }
  return proxyWorkspaceRequest(`workspace/parent/${action}/`, request);
}

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ action: string }> },
) {
  const { action } = await params;
  if (!allowedActions.has(action)) {
    return NextResponse.json({ detail: 'Unknown parent workspace action.' }, { status: 404 });
  }
  return proxyWorkspaceRequest(`workspace/parent/${action}/`, request);
}
