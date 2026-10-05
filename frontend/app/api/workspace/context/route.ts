import { NextResponse } from 'next/server';

import { authenticatedBackendGet } from '@/lib/serverProxy';

export const dynamic = 'force-dynamic';

export async function GET() {
  const result = await authenticatedBackendGet('workspace/context/');
  return NextResponse.json(result.body, { status: result.status });
}
