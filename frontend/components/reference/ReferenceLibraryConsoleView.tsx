'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  CircleDollarSign,
  Clock3,
  Library,
  LoaderCircle,
  Pencil,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  UserRound,
  Users,
  X,
} from 'lucide-react';

import type { WorkspaceFormSchema } from '@/lib/workspace';
import { useToast } from '@/components/ui/ToastProvider';
import { ResourceFormDialog } from '@/components/workspace/ResourceFormDialog';

type Overview = {
  books: number;
  copies: number;
  available: number;
  on_loan: number;
  overdue: number;
  outstanding_fines: number;
  student_members: number;
  staff_members: number;
};

type ConsoleRows = {
  rows: Record<string, unknown>[];
  can_write: boolean;
  form?: WorkspaceFormSchema;
};

function statusClass(value: unknown) {
  const text = String(value ?? '').toLowerCase();
  if (text.includes('overdue') || text.includes('outstanding') || text.includes('lost')) return 'border-red-100 bg-red-50 text-red-700';
  if (text.includes('returned') || text.includes('paid') || text.includes('available')) return 'border-emerald-100 bg-emerald-50 text-emerald-700';
  if (text.includes('waived')) return 'border-violet-100 bg-violet-50 text-violet-700';
  return 'border-blue-100 bg-blue-50 text-blue-700';
}

function dateLabel(value: unknown) {
  const text = String(value ?? '');
  if (!text) return '—';
  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) return text;
  return new Intl.DateTimeFormat(undefined, { day: '2-digit', month: 'short', year: 'numeric' }).format(parsed);
}

export function ReferenceLibraryConsoleView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  const requestedTab = searchParams.get('tab') || 'loans';
  const tab = ['books', 'loans', 'fines', 'members'].includes(requestedTab) ? requestedTab : 'loans';
  const [overview, setOverview] = useState<Overview | null>(null);
  const [data, setData] = useState<ConsoleRows | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [reloadKey, setReloadKey] = useState(0);
  const [selectedLoan, setSelectedLoan] = useState<Record<string, unknown> | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogSchema, setDialogSchema] = useState<WorkspaceFormSchema | null>(null);
  const [dialogLoading, setDialogLoading] = useState(false);
  const [dialogErrors, setDialogErrors] = useState<Record<string, string[]>>({});
  const [dialogAction, setDialogAction] = useState<{ screen: string; id?: number } | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    const dataScreen = tab === 'members' ? 'overview' : tab;
    Promise.all([
      fetch('/api/workspace/library-console/overview', { cache: 'no-store', signal: controller.signal }).then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Library summary could not be loaded.');
        return payload as Overview;
      }),
      dataScreen === 'overview'
        ? Promise.resolve(null)
        : fetch(`/api/workspace/library-console/${dataScreen}`, { cache: 'no-store', signal: controller.signal }).then(async (response) => {
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.detail || 'Library records could not be loaded.');
            return payload as ConsoleRows;
          }),
    ]).then(([summary, records]) => {
      setOverview(summary);
      setData(records);
      setQuery('');
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Library could not be loaded.');
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [reloadKey, tab]);

  const rows = useMemo(() => {
    const text = query.trim().toLowerCase();
    if (!text) return data?.rows ?? [];
    return (data?.rows ?? []).filter((row) => Object.values(row).some((value) => String(value ?? '').toLowerCase().includes(text)));
  }, [data, query]);

  function selectTab(next: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set('tab', next);
    router.replace(`?${params.toString()}`, { scroll: false });
  }

  async function openForm(screen: string, id?: number, fallbackSchema?: WorkspaceFormSchema) {
    setDialogAction({ screen, id });
    setDialogOpen(true);
    setDialogErrors({});
    if (fallbackSchema && !id) {
      setDialogSchema(fallbackSchema);
      return;
    }
    setDialogSchema(null);
    setDialogLoading(true);
    try {
      const path = id ? `/api/workspace/library-console/${screen}/${id}` : `/api/workspace/library-console/${screen}`;
      const response = await fetch(path, { cache: 'no-store' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'The library form could not be opened.');
      setDialogSchema(payload as WorkspaceFormSchema);
    } catch (reason: unknown) {
      toast.error('Could not open library form', reason instanceof Error ? reason.message : 'Please try again.');
      setDialogOpen(false);
    } finally { setDialogLoading(false); }
  }

  async function submitForm(values: Record<string, unknown>) {
    if (!dialogAction) return;
    setDialogLoading(true);
    setDialogErrors({});
    try {
      const path = dialogAction.id
        ? `/api/workspace/library-console/${dialogAction.screen}/${dialogAction.id}`
        : `/api/workspace/library-console/${dialogAction.screen}`;
      const response = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values) });
      const payload = await response.json();
      if (!response.ok) {
        setDialogErrors((payload.errors as Record<string, string[]>) ?? {});
        throw new Error(payload.detail || 'The library action could not be completed.');
      }
      toast.success('Library updated', payload.detail || 'The action completed successfully.');
      setDialogOpen(false);
      setSelectedLoan(null);
      setReloadKey((value) => value + 1);
    } catch (reason: unknown) {
      toast.error('Library action failed', reason instanceof Error ? reason.message : 'Please try again.');
    } finally { setDialogLoading(false); }
  }

  async function simpleAction(screen: string, id: number, body: Record<string, unknown> = {}) {
    setDialogLoading(true);
    try {
      const response = await fetch(`/api/workspace/library-console/${screen}/${id}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'The library action could not be completed.');
      toast.success('Library updated', payload.detail || 'Action completed.');
      setSelectedLoan(null);
      setReloadKey((value) => value + 1);
    } catch (reason: unknown) {
      toast.error('Library action failed', reason instanceof Error ? reason.message : 'Please try again.');
    } finally { setDialogLoading(false); }
  }

  const canWrite = Boolean(data?.can_write);

  return (
    <section>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex items-start gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-600"><Library size={21} /></span><div><h1 className="text-[1.65rem] font-extrabold tracking-[-0.035em] text-[#10224A]">Library</h1><p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">Catalogue, circulation, overdue books and fines in one workspace using the existing Django library rules.</p></div></div>
        <div className="flex flex-wrap gap-2"><button type="button" onClick={() => setReloadKey((value) => value + 1)} className="clay-button-secondary"><RefreshCw size={14} />Refresh</button>{canWrite && <button type="button" onClick={() => void openForm('issue')} className="clay-button-primary"><Plus size={14} />Issue book</button>}</div>
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          ['Books', overview?.books ?? 0, BookOpen, 'bg-blue-50 text-blue-600'],
          ['Available copies', overview?.available ?? 0, CheckCircle2, 'bg-emerald-50 text-emerald-600'],
          ['On loan', overview?.on_loan ?? 0, RotateCcw, 'bg-violet-50 text-violet-600'],
          ['Overdue', overview?.overdue ?? 0, Clock3, 'bg-red-50 text-red-600'],
        ].map(([label, value, Icon, cls]) => { const CardIcon = Icon as typeof Library; return <article key={String(label)} className="tafiti-kpi"><div className="flex items-center gap-3"><span className={`grid h-10 w-10 place-items-center rounded-xl ${String(cls)}`}><CardIcon size={18} /></span><div><p className="text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">{String(label)}</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{String(value)}</p></div></div></article>; })}
      </div>

      <div className="mb-4 overflow-x-auto rounded-xl border border-slate-200 bg-white p-1.5 shadow-[0_5px_16px_rgba(28,55,97,.035)]">
        <div className="flex min-w-max gap-1">{[
          ['books', 'Books', BookOpen], ['loans', 'Loans & Returns', RotateCcw], ['fines', 'Fines', CircleDollarSign], ['members', 'Members', Users],
        ].map(([key, label, Icon]) => { const TabIcon = Icon as typeof Library; const active = tab === key; return <button key={String(key)} type="button" onClick={() => selectTab(String(key))} className={`inline-flex h-9 items-center gap-1.5 rounded-lg px-3 text-[10px] font-extrabold transition ${active ? 'bg-blue-600 text-white shadow-[0_5px_12px_rgba(37,99,235,.18)]' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'}`}><TabIcon size={13} />{String(label)}</button>; })}</div>
      </div>

      {loading && !overview ? <div className="tafiti-card grid min-h-[380px] place-items-center"><LoaderCircle className="animate-spin text-blue-600" size={24} /></div>
        : error ? <div className="tafiti-card p-6 text-center"><AlertCircle className="mx-auto text-red-500" /><p className="mt-3 text-sm font-bold text-slate-800">Library unavailable</p><p className="mt-2 text-xs text-slate-500">{error}</p></div>
        : tab === 'members' ? <section className="grid gap-4 md:grid-cols-2"><article className="tafiti-card p-5"><span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-600"><Users size={19} /></span><p className="mt-4 text-3xl font-extrabold tracking-[-.04em] text-[#10224A]">{overview?.student_members ?? 0}</p><p className="mt-1 text-xs font-bold text-slate-600">Active student members</p><p className="mt-2 text-[10px] text-slate-400">Students become eligible borrowers through their existing active student profile.</p></article><article className="tafiti-card p-5"><span className="grid h-11 w-11 place-items-center rounded-xl bg-violet-50 text-violet-600"><UserRound size={19} /></span><p className="mt-4 text-3xl font-extrabold tracking-[-.04em] text-[#10224A]">{overview?.staff_members ?? 0}</p><p className="mt-1 text-xs font-bold text-slate-600">Active staff members</p><p className="mt-2 text-[10px] text-slate-400">Staff borrowing eligibility follows the existing staff status and library policy.</p></article></section>
        : <section className="tafiti-card overflow-hidden">
            <div className="flex flex-col gap-3 border-b border-slate-100 px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between sm:px-5"><div className="relative w-full sm:max-w-[360px]"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={`Search ${tab}…`} className="tafiti-input h-9 w-full pl-9 pr-3 text-xs" /></div>{tab === 'books' && data?.can_write && <button type="button" onClick={() => void openForm('books', undefined, data.form)} className="clay-button-primary"><Plus size={14} />Add book</button>}</div>
            {tab === 'books' && <div className="overflow-x-auto"><table className="w-full min-w-[880px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">BOOK</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">CATEGORY</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">ISBN</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">SHELF</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">COPIES</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">AVAILABLE</th>{data?.can_write && <th className="px-4 py-3 text-right text-[9px] font-extrabold text-slate-400">ACTION</th>}</tr></thead><tbody className="divide-y divide-slate-100">{rows.map((row, index) => <tr key={String(row.id ?? index)} className="hover:bg-blue-50/25"><td className="px-4 py-3"><div className="flex items-center gap-2.5"><span className="grid h-9 w-9 place-items-center rounded-xl bg-blue-50 text-blue-600"><BookOpen size={16} /></span><div><p className="text-xs font-bold text-slate-800">{String(row.title ?? '—')}</p><p className="mt-0.5 text-[9px] text-slate-400">{String(row.author ?? '—')}</p></div></div></td><td className="px-4 py-3 text-xs text-slate-600">{String(row.category ?? '—')}</td><td className="px-4 py-3 text-xs text-slate-500">{String(row.isbn ?? '—')}</td><td className="px-4 py-3 text-xs text-slate-500">{String(row.shelf ?? '—')}</td><td className="px-4 py-3 text-xs font-bold text-slate-700">{String(row.copies ?? 0)}</td><td className="px-4 py-3 text-xs font-bold text-emerald-600">{String(row.available ?? 0)}</td>{data?.can_write && <td className="px-4 py-3 text-right"><button type="button" onClick={() => typeof row.id === 'number' && void openForm('books', row.id)} className="inline-flex items-center gap-1 text-[10px] font-bold text-blue-600 hover:underline"><Pencil size={12} />Edit</button></td>}</tr>)}</tbody></table></div>}
            {tab === 'loans' && <div className="overflow-x-auto"><table className="w-full min-w-[980px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">BOOK</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">BORROWER</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">ISSUED</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">DUE</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STATUS</th><th className="px-4 py-3 text-right text-[9px] font-extrabold text-slate-400">ACTION</th></tr></thead><tbody className="divide-y divide-slate-100">{rows.map((row, index) => <tr key={String(row.id ?? index)} className="hover:bg-blue-50/25"><td className="px-4 py-3"><p className="text-xs font-bold text-slate-800">{String(row.book ?? '—')}</p><p className="mt-0.5 text-[9px] text-slate-400">{String(row.accession ?? '—')}</p></td><td className="px-4 py-3"><p className="text-xs font-bold text-slate-700">{String(row.borrower ?? '—')}</p><p className="mt-0.5 text-[9px] text-slate-400">{String(row.borrower_type ?? '')}</p></td><td className="px-4 py-3 text-xs text-slate-500">{dateLabel(row.issued)}</td><td className="px-4 py-3 text-xs text-slate-500">{dateLabel(row.due)}</td><td className="px-4 py-3"><span className={`rounded-full border px-2 py-1 text-[9px] font-bold ${statusClass(row.status)}`}>{String(row.status ?? '—')}</span></td><td className="px-4 py-3 text-right"><button type="button" onClick={() => setSelectedLoan(row)} className="text-[10px] font-bold text-blue-600 hover:underline">Open loan</button></td></tr>)}</tbody></table></div>}
            {tab === 'fines' && <div className="overflow-x-auto"><table className="w-full min-w-[900px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">BOOK / BORROWER</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">REASON</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">AMOUNT</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STATUS</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">ASSESSED</th>{data?.can_write && <th className="px-4 py-3 text-right text-[9px] font-extrabold text-slate-400">ACTION</th>}</tr></thead><tbody className="divide-y divide-slate-100">{rows.map((row, index) => <tr key={String(row.id ?? index)} className="hover:bg-blue-50/25"><td className="px-4 py-3"><p className="text-xs font-bold text-slate-800">{String(row.book ?? '—')}</p><p className="mt-0.5 text-[9px] text-slate-400">{String(row.borrower ?? '—')}</p></td><td className="px-4 py-3 text-xs text-slate-600">{String(row.reason ?? '—')}</td><td className="px-4 py-3 text-xs font-extrabold text-slate-800">UGX {String(row.amount ?? '0')}</td><td className="px-4 py-3"><span className={`rounded-full border px-2 py-1 text-[9px] font-bold ${statusClass(row.status)}`}>{String(row.status ?? '—')}</span></td><td className="px-4 py-3 text-xs text-slate-500">{dateLabel(row.assessed)}</td>{data?.can_write && <td className="px-4 py-3 text-right">{String(row.status).toLowerCase() === 'outstanding' && typeof row.id === 'number' ? <span className="inline-flex gap-2"><button type="button" onClick={() => void simpleAction('fine', row.id as number, { resolution: 'paid' })} className="text-[10px] font-bold text-emerald-600 hover:underline">Mark paid</button><button type="button" onClick={() => void simpleAction('fine', row.id as number, { resolution: 'waived' })} className="text-[10px] font-bold text-violet-600 hover:underline">Waive</button></span> : <span className="text-[10px] text-slate-400">Resolved</span>}</td>}</tr>)}</tbody></table></div>}
            {!loading && !rows.length && <div className="px-5 py-12 text-center text-xs text-slate-400">No {tab} match this view.</div>}
          </section>}

      {selectedLoan && <><button type="button" onClick={() => setSelectedLoan(null)} className="fixed inset-0 z-40 bg-slate-950/30 backdrop-blur-[1px]" aria-label="Close loan detail" /><aside className="fixed inset-y-0 right-0 z-50 w-full max-w-[430px] overflow-y-auto border-l border-slate-200 bg-[#F7FAFD] shadow-[-20px_0_50px_rgba(15,39,71,.13)]"><div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white/95 px-5 py-4 backdrop-blur"><div><p className="text-[9px] font-bold uppercase tracking-[.1em] text-blue-600">Library loan</p><h2 className="mt-1 text-lg font-extrabold text-[#10224A]">{String(selectedLoan.book ?? 'Book')}</h2></div><button type="button" onClick={() => setSelectedLoan(null)} className="grid h-9 w-9 place-items-center rounded-lg border border-slate-200 bg-white text-slate-500"><X size={16} /></button></div><div className="p-5"><div className="grid place-items-center rounded-2xl border border-blue-100 bg-gradient-to-br from-blue-50 to-white py-8"><span className="grid h-20 w-20 place-items-center rounded-2xl bg-white text-blue-600 shadow-sm"><BookOpen size={34} /></span><p className="mt-4 max-w-[300px] text-center text-sm font-extrabold text-[#10224A]">{String(selectedLoan.book ?? '—')}</p><p className="mt-1 text-[10px] font-semibold text-slate-400">Accession {String(selectedLoan.accession ?? '—')}</p></div><div className="mt-4 grid gap-3 sm:grid-cols-2">{[['Borrower', selectedLoan.borrower], ['Type', selectedLoan.borrower_type], ['Issued', dateLabel(selectedLoan.issued)], ['Due', dateLabel(selectedLoan.due)], ['Renewals', selectedLoan.renewals], ['Status', selectedLoan.status]].map(([label,value]) => <div key={String(label)} className="rounded-xl border border-slate-100 bg-white p-3.5"><p className="text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">{String(label)}</p><p className="mt-1.5 text-xs font-bold text-slate-800">{String(value ?? '—')}</p></div>)}</div>{canWrite && String(selectedLoan.status) !== 'Returned' && typeof selectedLoan.id === 'number' && <div className="mt-5 grid gap-2"><button type="button" disabled={dialogLoading} onClick={() => void simpleAction('renew', selectedLoan.id as number)} className="clay-button-secondary w-full"><RotateCcw size={14} />Renew loan</button><button type="button" onClick={() => void openForm('return', selectedLoan.id as number)} className="clay-button-primary w-full"><CheckCircle2 size={14} />Return book</button><button type="button" onClick={() => void openForm('lost', selectedLoan.id as number)} className="inline-flex h-9 items-center justify-center rounded-lg border border-red-100 bg-red-50 text-[10px] font-bold text-red-600 hover:bg-red-100">Mark item lost</button></div>}</div></aside></>}

      <ResourceFormDialog open={dialogOpen} schema={dialogSchema} loading={dialogLoading} errors={dialogErrors} onClose={() => { setDialogOpen(false); setDialogAction(null); setDialogErrors({}); }} onSubmit={submitForm} />
    </section>
  );
}
