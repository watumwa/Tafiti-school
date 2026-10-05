import { cookies } from 'next/headers';

export const ACCESS_COOKIE = 'tafiti_access';
export const REFRESH_COOKIE = 'tafiti_refresh';

export function backendApiUrl(path: string): string {
  const configured =
    process.env.DJANGO_API_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    'http://127.0.0.1:8000/api';
  const base = configured.replace(/\/+$/, '');
  const apiBase = base.endsWith('/api') ? base : `${base}/api`;
  return `${apiBase}/${path.replace(/^\/+/, '')}`;
}

export const authCookieOptions = {
  httpOnly: true,
  sameSite: 'strict' as const,
  secure: process.env.NODE_ENV === 'production',
  path: '/',
};

export async function clearAuthCookies(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.set(ACCESS_COOKIE, '', { ...authCookieOptions, maxAge: 0 });
  cookieStore.set(REFRESH_COOKIE, '', { ...authCookieOptions, maxAge: 0 });
}

export async function readJsonResponse(response: Response): Promise<Record<string, unknown>> {
  try {
    return (await response.json()) as Record<string, unknown>;
  } catch {
    return {};
  }
}
