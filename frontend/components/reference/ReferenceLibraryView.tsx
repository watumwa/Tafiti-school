'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  Clock3,
  Library,
  LoaderCircle,
  Search,
  UserRound,
  X,
} from 'lucide-react';

import type { WorkspaceResource } from '@/lib/workspace';

function dateLabel(value: unknown) {
  const text = String(value ?? '');
  if (!text || text === '—') return '—';
  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) return text;
  return new Intl.DateTimeFormat(undefined, { day: '2-digit', month: 'short', year: 'numeric' }).format(parsed);
}

function statusClass(value: unknown) {
  const text = String(value ?? '').toLowerCase();
  if (text.includes('overdue')) return 'border-red-100 bg-red-50 text-red-700';
  if (text.includes('returned')) return 'border-emerald-100 bg-emerald-50 text-emerald-700';
  return 'border-blue-100 bg-blue-50 text-blue-700';
}

export function ReferenceLibraryView() {
  const [data, setData] = useState<WorkspaceResource | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState<'all' | 'loan' | 'overdue' | 'returned'>('all');
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetch('/api/workspace/resources/library?page_size=100', { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Library records could not be loaded.');
        return payload as WorkspaceResource;
      })
      .then(setData)
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Library records could not be loaded.');
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [reloadKey]);

  const rows = useMemo(() => {
    const text = query.trim().toLowerCase();
    return (data?.rows ?? []).filter((row) => {
      const rowStatus = String(row.status ?? '').toLowerCase();
      const statusMatch = status === 'all'
        || (status === 'loan' && rowStatus === 'on loan')
        || (status === 'overdue' && rowStatus === 'overdue')
        || (status === 'returned' && rowStatus === 'returned');
      const queryMatch = !text || [row.book, row.accession, row.borrower, row.borrower_type].some((value) => String(value ?? '').toLowerCase().includes(text));
      return statusMatch && queryMatch;
    });
  }, [data, query, status]);

  const counts = useMemo(() => {
    const all = data?.rows ?? [];
    return {
      total: all.length,
      loan: all.filter((row) => String(row.status) === 'On loan').length,
      overdue: all.filter((row) => String(row.status) === 'Overdue').length,
      returned: all.filter((row) => String(row.status) === 'Returned').length,
    };
  }, [data]);

  if (loading && !data) return <div className="tafiti-card grid min-h-[430px] place-items-center"><div className="text-center text-xs font-semibold text-slate-500"><LoaderCircle className="mx-auto mb-3 animate-spin text-blue-600" size={24} />Loading library records…</div></div>;
  if (error && !data) return <div className="tafiti-card grid min-h-[430px] place-items-center p-6 text-center"><div><p className="text-sm font-bold text-slate-800">Library unavailable</p><p className="mt-2 text-xs text-slate-500">{error}</p><button type="button" onClick={() => setReloadKey((value) => value + 1)} className="clay-button-primary mt-4">Try again</button></div></div>;

  return (
    <section>
      <div className="mb-4 flex items-start gap-3">
        <span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-600"><Library size={21} /></span>
        <div><h1 className="text-[1.65rem] font-extrabold tracking-[-0.035em] text-[#10224A]">Library</h1><p className="mt-1 text-xs leading-5 text-slate-500">Current and historical circulation. Open any loan without leaving the workspace.</p></div>
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          ['Loan records', counts.total, 'bg-blue-50 text-blue-600', Library],
          ['On loan', counts.loan, 'bg-violet-50 text-violet-600', BookOpen],
          ['Overdue', counts.overdue, 'bg-red-50 text-red-600', Clock3],
          ['Returned', counts.returned, 'bg-emerald-50 text-emerald-600', CheckCircle2],
        ].map(([label, value, cls, Icon]) => {
          const IconComponent = Icon as typeof Library;
          return <article key={String(label)} className="tafiti-kpi"><div className="flex items-center gap-3"><span className={`grid h-10 w-10 place-items-center rounded-xl ${String(cls)}`}><IconComponent size={18} /></span><div><p className="text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">{String(label)}</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{String(value)}</p></div></div></article>;
        })}
      </div>

      <section className="tafiti-card overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-slate-100 px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between sm:px-5">
          <div className="relative w-full sm:max-w-[360px]"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search book, accession or borrower…" className="tafiti-input h-9 w-full pl-9 pr-3 text-xs" /></div>
          <div className="flex flex-wrap gap-1 rounded-lg bg-[#F5F8FC] p-1">{([['all','All'],['loan','On loan'],['overdue','Overdue'],['returned','Returned']] as const).map(([value,label]) => <button key={value} type="button" onClick={() => setStatus(value)} className={`rounded-md px-2.5 py-1.5 text-[9px] font-bold ${status === value ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-500'}`}>{label}</button>)}</div>
        </div>
        <div className="overflow-x-auto"><table className="w-full min-w-[880px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">BOOK</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">ACCESSION</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">BORROWER</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">ISSUED</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">DUE</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STATUS</th><th className="px-4 py-3 text-right text-[9px] font-extrabold text-slate-400">ACTION</th></tr></thead><tbody className="divide-y divide-slate-100">{rows.map((row, index) => <tr key={String(row.id ?? index)} className="hover:bg-blue-50/25"><td className="px-4 py-3"><div className="flex items-center gap-2.5"><span className="grid h-9 w-9 place-items-center rounded-xl bg-blue-50 text-blue-600"><BookOpen size={16} /></span><div><p className="text-xs font-bold text-slate-800">{String(row.book ?? '—')}</p><p className="mt-0.5 text-[9px] text-slate-400">Physical copy</p></div></div></td><td className="px-4 py-3 text-xs font-semibold text-slate-600">{String(row.accession ?? '—')}</td><td className="px-4 py-3"><p className="text-xs font-bold text-slate-700">{String(row.borrower ?? '—')}</p><p className="mt-0.5 text-[9px] text-slate-400">{String(row.borrower_type ?? '')}</p></td><td className="px-4 py-3 text-xs text-slate-500">{dateLabel(row.issued)}</td><td className="px-4 py-3 text-xs text-slate-500">{dateLabel(row.due)}</td><td className="px-4 py-3"><span className={`rounded-full border px-2 py-1 text-[9px] font-bold ${statusClass(row.status)}`}>{String(row.status ?? '—')}</span></td><td className="px-4 py-3 text-right"><button type="button" onClick={() => setSelected(row)} className="inline-flex items-center gap-1 text-[10px] font-bold text-blue-600 hover:underline">Open <ArrowRight size={12} /></button></td></tr>)}</tbody></table></div>
        {!rows.length && <div className="px-5 py-12 text-center text-xs text-slate-400">No library records match these filters.</div>}
      </section>

      {selected && <><button type="button" onClick={() => setSelected(null)} className="fixed inset-0 z-40 bg-slate-950/30 backdrop-blur-[1px]" aria-label="Close library detail" /><aside className="fixed inset-y-0 right-0 z-50 w-full max-w-[430px] overflow-y-auto border-l border-slate-200 bg-[#F7FAFD] shadow-[-20px_0_50px_rgba(15,39,71,.13)]"><div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white/95 px-5 py-4 backdrop-blur"><div><p className="text-[9px] font-bold uppercase tracking-[.1em] text-blue-600">Library loan</p><h2 className="mt-1 text-lg font-extrabold text-[#10224A]">{String(selected.book ?? 'Book')}</h2></div><button type="button" onClick={() => setSelected(null)} className="grid h-9 w-9 place-items-center rounded-lg border border-slate-200 bg-white text-slate-500"><X size={16} /></button></div><div className="p-5"><div className="grid place-items-center rounded-2xl border border-blue-100 bg-gradient-to-br from-blue-50 to-white py-8"><span className="grid h-20 w-20 place-items-center rounded-2xl bg-white text-blue-600 shadow-sm"><BookOpen size={34} /></span><p className="mt-4 max-w-[300px] text-center text-sm font-extrabold text-[#10224A]">{String(selected.book ?? '—')}</p><p className="mt-1 text-[10px] font-semibold text-slate-400">Accession {String(selected.accession ?? '—')}</p></div><div className="mt-4 grid gap-3 sm:grid-cols-2">{[
        ['Borrower', selected.borrower, UserRound], ['Borrower type', selected.borrower_type, UserRound], ['Issued', dateLabel(selected.issued), CalendarDays], ['Due', dateLabel(selected.due), Clock3], ['Returned', dateLabel(selected.returned), CheckCircle2], ['Status', selected.status, Library],
      ].map(([label,value,Icon]) => { const DetailIcon = Icon as typeof Library; return <div key={String(label)} className="rounded-xl border border-slate-100 bg-white p-3.5"><span className="grid h-8 w-8 place-items-center rounded-lg bg-blue-50 text-blue-600"><DetailIcon size={14} /></span><p className="mt-3 text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">{String(label)}</p><p className="mt-1 text-xs font-bold text-slate-800">{String(value ?? '—')}</p></div>; })}</div></div></aside></>}
    </section>
  );
}
