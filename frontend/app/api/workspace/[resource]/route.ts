import { NextResponse } from 'next/server';

import { authenticatedBackendGet } from '@/lib/serverProxy';

export const dynamic = 'force-dynamic';

const FILTER_PREFIX = 'filter_';
const MAX_BACKEND_PAGES = 40;

function text(value: unknown) {
  return value === null || value === undefined ? '' : String(value).trim();
}

function parseDate(value: unknown) {
  const raw = text(value);
  if (!raw || raw === '—') return null;
  const date = new Date(raw.length === 10 ? `${raw}T00:00:00` : raw);
  return Number.isNaN(date.getTime()) ? null : date;
}

function applyFilters(rows: Record<string, unknown>[], params: URLSearchParams) {
  let filtered = rows;

  for (const [key, value] of params.entries()) {
    if (!key.startsWith(FILTER_PREFIX) || !value.trim()) continue;
    const column = key.slice(FILTER_PREFIX.length);
    const target = value.trim().toLocaleLowerCase();
    filtered = filtered.filter((row) => text(row[column]).toLocaleLowerCase().includes(target));
  }

  const dateKey = params.get('date_key')?.trim() ?? '';
  const from = parseDate(params.get('date_from'));
  const to = parseDate(params.get('date_to'));
  if (dateKey && (from || to)) {
    filtered = filtered.filter((row) => {
      const value = parseDate(row[dateKey]);
      if (!value) return false;
      if (from && value < from) return false;
      if (to) {
        const inclusiveTo = new Date(to);
        inclusiveTo.setHours(23, 59, 59, 999);
        if (value > inclusiveTo) return false;
      }
      return true;
    });
  }

  return filtered;
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ resource: string }> },
) {
  const { resource } = await params;
  const incoming = new URL(request.url);
  const original = new URLSearchParams(incoming.searchParams);
  const hasAdvancedFilters = Array.from(original.keys()).some((key) => key.startsWith(FILTER_PREFIX))
    || Boolean(original.get('date_from'))
    || Boolean(original.get('date_to'));

  if (!hasAdvancedFilters) {
    const query = original.toString();
    const result = await authenticatedBackendGet(`workspace/resources/${encodeURIComponent(resource)}/${query ? `?${query}` : ''}`);
    return NextResponse.json(result.body, { status: result.status });
  }

  const requestedPage = Math.max(1, Number(original.get('page') ?? '1') || 1);
  const requestedPageSize = Math.min(100, Math.max(1, Number(original.get('page_size') ?? '25') || 25));

  const backendParams = new URLSearchParams(original);
  for (const key of Array.from(backendParams.keys())) {
    if (key.startsWith(FILTER_PREFIX)) backendParams.delete(key);
  }
  backendParams.delete('date_key');
  backendParams.delete('date_from');
  backendParams.delete('date_to');
  backendParams.set('page', '1');
  backendParams.set('page_size', '100');

  const first = await authenticatedBackendGet(
    `workspace/resources/${encodeURIComponent(resource)}/?${backendParams.toString()}`,
  );
  if (first.status !== 200 || !first.body || typeof first.body !== 'object') {
    return NextResponse.json(first.body, { status: first.status });
  }

  const firstBody = first.body as Record<string, unknown>;
  const firstRows = Array.isArray(firstBody.rows) ? firstBody.rows as Record<string, unknown>[] : [];
  const pagination = (firstBody.pagination ?? {}) as Record<string, unknown>;
  const backendPages = Math.min(MAX_BACKEND_PAGES, Math.max(1, Number(pagination.pages ?? 1) || 1));
  const allRows = [...firstRows];

  for (let page = 2; page <= backendPages; page += 1) {
    backendParams.set('page', String(page));
    const next = await authenticatedBackendGet(
      `workspace/${encodeURIComponent(resource)}/?${backendParams.toString()}`,
    );
    if (next.status !== 200 || !next.body || typeof next.body !== 'object') break;
    const nextRows = Array.isArray((next.body as Record<string, unknown>).rows)
      ? (next.body as Record<string, unknown>).rows as Record<string, unknown>[]
      : [];
    allRows.push(...nextRows);
  }

  const filteredRows = applyFilters(allRows, original);
  const total = filteredRows.length;
  const pages = Math.max(1, Math.ceil(total / requestedPageSize));
  const page = Math.min(requestedPage, pages);
  const start = (page - 1) * requestedPageSize;

  return NextResponse.json({
    ...firstBody,
    rows: filteredRows.slice(start, start + requestedPageSize),
    pagination: {
      page,
      page_size: requestedPageSize,
      total,
      pages,
    },
  });
}
