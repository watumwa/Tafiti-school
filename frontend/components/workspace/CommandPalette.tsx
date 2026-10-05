'use client';

import { useEffect, useMemo, useState } from 'react';
import { Search, X } from 'lucide-react';
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

  useEffect(() => {
    if (!open) setQuery('');
  }, [open]);

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
            placeholder="Search students, finance, attendance, settings…"
            className="h-14 min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-slate-400"
          />
          <button type="button" onClick={onClose} className="grid h-8 w-8 place-items-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="Close search"><X size={16} /></button>
        </div>
        <div className="max-h-[55vh] overflow-y-auto p-2">
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
            <div className="px-5 py-12 text-center">
              <p className="text-sm font-semibold text-slate-800">No module found</p>
              <p className="mt-1 text-xs text-slate-500">Try another name or keyword.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
