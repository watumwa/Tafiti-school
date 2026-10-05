import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';

import { ACCESS_COOKIE } from '@/lib/backend';

function djangoOrigin() {
  const configured = process.env.DJANGO_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000/api';
  const base = configured.replace(/\/+$/, '');
  return base.endsWith('/api') ? base.slice(0, -4) : base;
}

export async function GET(_request: Request, context: { params: Promise<{ path: string[] }> }) {
  const access = (await cookies()).get(ACCESS_COOKIE)?.value;
  if (!access) return new NextResponse(null, { status: 401 });

  const { path } = await context.params;
  if (!path?.length || path.some((part) => part === '..' || part.includes('\0'))) {
    return NextResponse.json({ detail: 'Invalid media path.' }, { status: 400 });
  }

  const relative = path.map((part) => encodeURIComponent(part)).join('/');
  const target = `${djangoOrigin()}/media/${relative}`;
  try {
    const response = await fetch(target, { cache: 'no-store' });
    if (!response.ok || !response.body) return new NextResponse(null, { status: response.status || 404 });
    const headers = new Headers();
    headers.set('Content-Type', response.headers.get('content-type') ?? 'application/octet-stream');
    headers.set('Cache-Control', 'private, max-age=300');
    const length = response.headers.get('content-length');
    if (length) headers.set('Content-Length', length);
    return new NextResponse(response.body, { status: 200, headers });
  } catch {
    return new NextResponse(null, { status: 502 });
  }
}
