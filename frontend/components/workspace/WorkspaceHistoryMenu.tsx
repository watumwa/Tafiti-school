'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Clock3, Pin, PinOff, X } from 'lucide-react';

type HistoryItem = {
  path: string;
  label: string;
  visitedAt: number;
};

type Props = {
  dashboardPath: string;
  currentPath: string;
  currentLabel: string;
};

function readItems(key: string): HistoryItem[] {
  if (typeof window === 'undefined') return [];
  try {
    const value = JSON.parse(window.localStorage.getItem(key) || '[]');
    return Array.isArray(value) ? value.filter((item) => item && typeof item.path === 'string' && typeof item.label === 'string') : [];
  } catch {
    return [];
  }
}

function writeItems(key: string, items: HistoryItem[]) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(key, JSON.stringify(items));
}

export function WorkspaceHistoryMenu({ dashboardPath, currentPath, currentLabel }: Props) {
  const [open, setOpen] = useState(false);
  const [recent, setRecent] = useState<HistoryItem[]>([]);
  const [pinned, setPinned] = useState<HistoryItem[]>([]);

  const storageScope = useMemo(() => dashboardPath.replaceAll('/', '_') || 'default', [dashboardPath]);
  const recentKey = `tafiti:recent:${storageScope}`;
  const pinnedKey = `tafiti:pinned:${storageScope}`;
  const currentPinned = pinned.some((item) => item.path === currentPath);

  useEffect(() => {
    setRecent(readItems(recentKey));
    setPinned(readItems(pinnedKey));
  }, [pinnedKey, recentKey]);

  useEffect(() => {
    if (!currentPath.startsWith(dashboardPath) || !currentLabel.trim()) return;
    const item: HistoryItem = { path: currentPath, label: currentLabel.trim(), visitedAt: Date.now() };
    const next = [item, ...readItems(recentKey).filter((entry) => entry.path !== currentPath)].slice(0, 8);
    writeItems(recentKey, next);
    setRecent(next);
  }, [currentLabel, currentPath, dashboardPath, recentKey]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  function togglePin() {
    const current: HistoryItem = { path: currentPath, label: currentLabel || 'Workspace', visitedAt: Date.now() };
    const next = currentPinned
      ? pinned.filter((item) => item.path !== currentPath)
      : [current, ...pinned.filter((item) => item.path !== currentPath)].slice(0, 6);
    setPinned(next);
    writeItems(pinnedKey, next);
  }

  function clearRecent() {
    setRecent([]);
    writeItems(recentKey, []);
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="grid h-9 w-9 place-items-center rounded-lg border border-slate-200 bg-white text-slate-600 transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
        aria-label="Recent and pinned workspaces"
        title="Recent and pinned workspaces"
      >
        <Clock3 size={16} />
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-2 w-[320px] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-[0_18px_50px_rgba(15,35,70,.18)]">
          <div className="flex items-center justify-between border-b border-slate-100 px-3.5 py-3">
            <div>
              <p className="text-[10px] font-extrabold text-[#10224A]">Continue working</p>
              <p className="mt-0.5 text-[9px] text-slate-400">Return to recent records without searching again.</p>
            </div>
            <button type="button" onClick={() => setOpen(false)} className="grid h-7 w-7 place-items-center rounded-lg text-slate-400 hover:bg-slate-50 hover:text-slate-700" aria-label="Close recent workspaces"><X size={14} /></button>
          </div>

          <div className="border-b border-slate-100 p-3">
            <button type="button" onClick={togglePin} className="flex w-full items-center gap-2 rounded-lg bg-[#F8FAFD] px-3 py-2 text-left text-[9px] font-bold text-slate-600 hover:bg-blue-50 hover:text-blue-700">
              {currentPinned ? <PinOff size={13} /> : <Pin size={13} />}
              {currentPinned ? 'Unpin this workspace' : 'Pin this workspace'}
            </button>
          </div>

          <div className="max-h-[360px] overflow-y-auto p-2.5">
            {pinned.length > 0 && (
              <div className="mb-3">
                <p className="mb-1.5 px-1 text-[8px] font-extrabold uppercase tracking-[.1em] text-slate-400">Pinned</p>
                <div className="space-y-1">
                  {pinned.map((item) => <Link key={item.path} href={item.path} onClick={() => setOpen(false)} className="flex items-center gap-2 rounded-lg px-2.5 py-2 text-[10px] font-bold text-slate-700 hover:bg-blue-50 hover:text-blue-700"><Pin size={12} className="shrink-0 text-blue-500" /><span className="truncate">{item.label}</span></Link>)}
                </div>
              </div>
            )}

            <div>
              <div className="mb-1.5 flex items-center justify-between px-1"><p className="text-[8px] font-extrabold uppercase tracking-[.1em] text-slate-400">Recent</p>{recent.length > 0 && <button type="button" onClick={clearRecent} className="text-[8px] font-bold text-slate-400 hover:text-red-500">Clear</button>}</div>
              <div className="space-y-1">
                {recent.map((item) => <Link key={item.path} href={item.path} onClick={() => setOpen(false)} className="flex items-center gap-2 rounded-lg px-2.5 py-2 text-[10px] font-bold text-slate-700 hover:bg-slate-50 hover:text-blue-700"><Clock3 size={12} className="shrink-0 text-slate-400" /><span className="truncate">{item.label}</span></Link>)}
                {!recent.length && <p className="rounded-lg bg-[#F8FAFD] px-3 py-5 text-center text-[9px] text-slate-400">Your recent workspaces will appear here.</p>}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
