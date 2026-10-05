import { NextRequest, NextResponse } from 'next/server';

const ACCESS_COOKIE = 'tafiti_access';
const REFRESH_COOKIE = 'tafiti_refresh';

export function proxy(request: NextRequest) {
  const hasSession =
    Boolean(request.cookies.get(ACCESS_COOKIE)?.value) ||
    Boolean(request.cookies.get(REFRESH_COOKIE)?.value);

  if (!hasSession) {
    const loginUrl = new URL('/login', request.url);
    loginUrl.searchParams.set('notice', 'session-required');
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/dashboard/:path*', '/account/:path*'],
};
