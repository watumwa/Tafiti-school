export function workspaceMediaSrc(value: unknown): string {
  const raw = typeof value === 'string' ? value.trim() : '';
  if (!raw) return '';

  let path = raw;
  try {
    if (/^https?:\/\//i.test(raw)) path = new URL(raw).pathname;
  } catch {
    return '';
  }

  if (!path.startsWith('/media/')) return raw;
  const relative = path.slice('/media/'.length);
  const encoded = relative.split('/').filter(Boolean).map((part) => encodeURIComponent(part)).join('/');
  return encoded ? `/api/media/${encoded}` : '';
}
