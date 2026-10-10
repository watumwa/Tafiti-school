import { NextResponse } from 'next/server';

import { proxyWorkspaceRequest } from '@/lib/workspace-server';

export const dynamic = 'force-dynamic';

async function validRoleId(params: Promise<{ roleId: string }>) {
  const { roleId } = await params;
  return /^\d+$/.test(roleId) ? roleId : '';
}

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ roleId: string }> },
) {
  const roleId = await validRoleId(params);
  if (!roleId) return NextResponse.json({ detail: 'Invalid role.' }, { status: 400 });
  return proxyWorkspaceRequest(`workspace/users-roles/roles/${roleId}/`, request);
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ roleId: string }> },
) {
  const roleId = await validRoleId(params);
  if (!roleId) return NextResponse.json({ detail: 'Invalid role.' }, { status: 400 });
  return proxyWorkspaceRequest(`workspace/users-roles/roles/${roleId}/`, request);
}
