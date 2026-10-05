'use client';

import { useEffect, useMemo, useState } from 'react';
import { LoaderCircle, Search, X } from 'lucide-react';
import { useRouter } from 'next/navigation';

import type { WorkspaceNavGroup } from '@/lib/workspace';
import { WorkspaceIcon } from './WorkspaceIcon';

export function CommandPalette({
  open,
  onClose,
  groups,
  dashboardPath,
}: {
  open: boolean;
  onClose: () => void;
  groups: WorkspaceNavGroup[];
  dashboardPath: string;
}) {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState<{ kind: string; label: string; description: string; href: string; icon: string }[]>([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    if (!open) {
      setQuery('');
      setSearchResults([]);
    }
  }, [open]);

  useEffect(() => {
    const normalized = query.trim();
    if (!open || normalized.length < 2) {
      setSearchResults([]);
      setSearching(false);
      return;
    }
    const controller = new AbortController();
    const handle = window.setTimeout(() => {
      setSearching(true);
      fetch(`/api/workspace/search?q=${encodeURIComponent(normalized)}`, { cache: 'no-store', signal: controller.signal })
        .then((response) => response.json())
        .then((result) => setSearchResults(Array.isArray(result.results) ? result.results : []))
        .catch(() => {
          if (!controller.signal.aborted) setSearchResults([]);
        })
        .finally(() => {
          if (!controller.signal.aborted) setSearching(false);
        });
    }, 220);
    return () => {
      window.clearTimeout(handle);
      controller.abort();
    };
  }, [open, query]);

  const items = useMemo(() => {
    const all = groups.flatMap((group) => group.items.map((item) => ({ ...item, group: group.label })));
    const q = query.trim().toLowerCase();
    if (!q) return all;
    return all.filter((item) => `${item.label} ${item.group}`.toLowerCase().includes(q));
  }, [groups, query]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[80] flex items-start justify-center bg-slate-950/35 px-4 pt-[10vh] backdrop-blur-[2px]" role="dialog" aria-modal="true" aria-label="Go to module">
      <button type="button" className="absolute inset-0" onClick={onClose} aria-label="Close module search" />
      <div className="relative z-10 w-full max-w-2xl overflow-hidden rounded-[22px] border border-white/30 bg-white shadow-[0_24px_90px_rgba(15,23,42,0.22)]">
        <div className="flex items-center gap-3 border-b border-slate-100 px-4">
          <Search size={19} className="text-slate-400" aria-hidden="true" />
          <input
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Find a student, staff member, class, payment, book, or module…"
            className="h-14 min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-slate-400"
          />
          <button type="button" onClick={onClose} className="grid h-8 w-8 place-items-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="Close search"><X size={16} /></button>
        </div>
        <div className="max-h-[60vh] overflow-y-auto p-2">
          {query.trim().length >= 2 && (
            <div className="mb-2">
              <div className="flex items-center justify-between px-3 py-2 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-400">
                <span>School records</span>
                {searching && <LoaderCircle size={13} className="animate-spin" />}
              </div>
              {searchResults.map((result) => (
                <button
                  key={`${result.kind}-${result.href}`}
                  type="button"
                  onClick={() => {
                    onClose();
                    router.push(result.href);
                  }}
                  className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left transition hover:bg-blue-50/60"
                >
                  <span className="grid h-9 w-9 place-items-center rounded-xl bg-blue-50 text-[#3157D5]"><WorkspaceIcon name={result.icon} size={17} /></span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold text-slate-900">{result.label}</span>
                    <span className="mt-0.5 block truncate text-[11px] text-slate-500">{result.kind} · {result.description}</span>
                  </span>
                  <span className="text-xs font-semibold text-[#3157D5]">Open</span>
                </button>
              ))}
              {!searching && !searchResults.length && <p className="px-4 py-4 text-xs text-slate-500">No school record matches “{query.trim()}”.</p>}
            </div>
          )}

          <div className="border-t border-slate-100 pt-2 first:border-0">
            <p className="px-3 py-2 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-400">Modules</p>
          {items.length ? items.map((item) => (
            <button
              key={`${item.group}-${item.slug}`}
              type="button"
              onClick={() => {
                onClose();
                router.push(item.slug === 'overview' ? dashboardPath : `${dashboardPath}/${item.slug}`);
              }}
              className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left hover:bg-slate-50"
            >
              <span className="grid h-9 w-9 place-items-center rounded-xl bg-slate-100 text-slate-700"><WorkspaceIcon name={item.icon} size={17} /></span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-semibold text-slate-900">{item.label}</span>
                <span className="mt-0.5 block text-[11px] font-medium uppercase tracking-[0.08em] text-slate-400">{item.group}</span>
              </span>
              <span className="text-xs text-slate-400">Open</span>
            </button>
          )) : (
            <div className="px-5 py-8 text-center">
              <p className="text-sm font-semibold text-slate-800">No module found</p>
              <p className="mt-1 text-xs text-slate-500">Try another name or keyword.</p>
            </div>
          )}
          </div>
        </div>
      </div>
    </div>
  );
}
