import { NextResponse } from 'next/server';

import { proxyWorkspaceRequest } from '@/lib/workspace-server';

export const dynamic = 'force-dynamic';

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ userId: string }> },
) {
  const { userId } = await params;
  if (!/^\d+$/.test(userId)) {
    return NextResponse.json({ detail: 'Invalid user account.' }, { status: 400 });
  }
  return proxyWorkspaceRequest(`workspace/users-roles/${userId}/`, request);
}
