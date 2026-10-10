import { NextResponse } from 'next/server';

import { proxyWorkspaceRequest } from '@/lib/workspace-server';

export const dynamic = 'force-dynamic';

export async function POST(request: Request) {
  return proxyWorkspaceRequest('workspace/users-roles/roles/', request);
}

export async function GET() {
  return NextResponse.json({ detail: 'Use the Users & Roles workspace to list roles.' }, { status: 405 });
}
