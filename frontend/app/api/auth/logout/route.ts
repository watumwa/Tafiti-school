import { NextResponse } from 'next/server';

import { clearAuthCookies } from '@/lib/backend';

export const dynamic = 'force-dynamic';

export async function POST() {
  await clearAuthCookies();
  return NextResponse.json({ success: true });
}
