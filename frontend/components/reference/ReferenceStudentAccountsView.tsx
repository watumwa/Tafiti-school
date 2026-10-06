'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import {
  BadgeDollarSign,
  CircleDollarSign,
  CreditCard,
  HandCoins,
  LoaderCircle,
  Search,
  ShieldCheck,
  WalletCards,
} from 'lucide-react';

import { ProfileAvatar } from '@/components/workspace/ProfileAvatar';

interface AccountRow {
  bill_id: number;
  student_id: number;
  student_number: string;
  student: string;
  photo: string;
  class: string;
  stream: string;
  year: string;
  term: string;
  gross_billed: string;
  adjustments: string;
  net_due: string;
  paid: string;
  balance: string;
  credit: string;
  status: string;
  due_date: string;
}

interface AccountsPayload {
  title: string;
  description: string;
  metrics: {
    gross_billed: string;
    adjustments: string;
    paid: string;
    outstanding: string;
    credit: string;
  };
  rows: AccountRow[];
  filters: { year: number | null; term: number | null; status: string; q: string };
  years: { id: number; label: string }[];
  terms: { id: number; label: string }[];
  actions: { can_write: boolean };
}

function money(value: string) {
  const numeric = Number(value || 0);
  return new Intl.NumberFormat('en-UG', { style: 'currency', currency: 'UGX', maximumFractionDigits: 0 }).format(Number.isFinite(numeric) ? numeric : 0);
}

function statusClass(status: string) {
  if (status === 'Paid') return 'border-emerald-100 bg-emerald-50 text-emerald-700';
  if (status === 'Partial') return 'border-amber-100 bg-amber-50 text-amber-700';
  if (status === 'Credit') return 'border-violet-100 bg-violet-50 text-violet-700';
  return 'border-rose-100 bg-rose-50 text-rose-700';
}

function Metric({ label, value, icon, tone }: { label: string; value: string; icon: React.ReactNode; tone: string }) {
  return (
    <article className="tafiti-kpi">
      <div className="flex items-start gap-3">
        <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${tone}`}>{icon}</span>
        <div className="min-w-0"><p className="text-[9px] font-extrabold uppercase tracking-[.07em] text-slate-400">{label}</p><p className="mt-1 truncate text-lg font-extrabold tracking-[-.03em] text-[#10224A]">{money(value)}</p></div>
      </div>
    </article>
  );
}

export function ReferenceStudentAccountsView({ dashboardPath }: { dashboardPath: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [data, setData] = useState<AccountsPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState(searchParams.get('q') ?? '');

  const paramsString = searchParams.toString();
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    fetch(`/api/workspace/student-finance/accounts${paramsString ? `?${paramsString}` : ''}`, { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Student accounts could not be loaded.');
        return payload as AccountsPayload;
      })
      .then(setData)
      .catch((reason: unknown) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Student accounts could not be loaded.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [paramsString]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const current = searchParams.get('q') ?? '';
      if (query.trim() === current) return;
      const next = new URLSearchParams(searchParams.toString());
      if (query.trim()) next.set('q', query.trim()); else next.delete('q');
      router.replace(`${pathname}${next.toString() ? `?${next}` : ''}`, { scroll: false });
    }, 280);
    return () => window.clearTimeout(timer);
  }, [pathname, query, router, searchParams]);

  const counts = useMemo(() => {
    const rows = data?.rows ?? [];
    return {
      all: rows.length,
      outstanding: rows.filter((row) => row.status === 'Outstanding').length,
      partial: rows.filter((row) => row.status === 'Partial').length,
      paid: rows.filter((row) => row.status === 'Paid').length,
      credit: rows.filter((row) => row.status === 'Credit' || Number(row.credit) > 0).length,
    };
  }, [data]);

  function setFilter(name: string, value: string) {
    const next = new URLSearchParams(searchParams.toString());
    if (value && value !== 'all') next.set(name, value); else next.delete(name);
    if (name === 'year') next.delete('term');
    router.replace(`${pathname}${next.toString() ? `?${next}` : ''}`, { scroll: false });
  }

  if (loading && !data) return <div className="tafiti-card grid min-h-[420px] place-items-center"><div className="text-center text-xs font-bold text-slate-500"><LoaderCircle className="mx-auto mb-3 animate-spin text-blue-600" size={24} />Loading student accounts…</div></div>;
  if (error && !data) return <div className="tafiti-card p-8 text-center"><p className="text-sm font-extrabold text-slate-800">Student accounts unavailable</p><p className="mt-2 text-xs text-slate-500">{error}</p></div>;
  if (!data) return null;

  const activeStatus = searchParams.get('status') ?? 'all';

  return (
    <section className="space-y-4">
      <header className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div><p className="text-[9px] font-extrabold uppercase tracking-[.13em] text-blue-600">Student finance</p><h1 className="mt-1 text-[1.7rem] font-extrabold tracking-[-.04em] text-[#10224A]">Student Accounts</h1><p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">Payments are posted to the selected student's bill. Part-payments, bursaries, overpayments and carry-forward credit remain visible on one account.</p></div>
        <Link href={`${dashboardPath}/fees-payments`} className="clay-button-secondary"><CreditCard size={14} /> Payment ledger</Link>
      </header>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Metric label="Gross billed" value={data.metrics.gross_billed} icon={<WalletCards size={17} />} tone="bg-blue-50 text-blue-600" />
        <Metric label="Bursaries / adjustments" value={data.metrics.adjustments} icon={<HandCoins size={17} />} tone="bg-violet-50 text-violet-600" />
        <Metric label="Cash received" value={data.metrics.paid} icon={<BadgeDollarSign size={17} />} tone="bg-emerald-50 text-emerald-600" />
        <Metric label="Outstanding" value={data.metrics.outstanding} icon={<CircleDollarSign size={17} />} tone="bg-amber-50 text-amber-600" />
        <Metric label="Student credit" value={data.metrics.credit} icon={<ShieldCheck size={17} />} tone="bg-cyan-50 text-cyan-700" />
      </div>

      <section className="tafiti-card overflow-hidden">
        <div className="grid gap-3 border-b border-slate-100 bg-[#FBFCFE] p-4 lg:grid-cols-[minmax(240px,1fr)_150px_170px]">
          <label className="relative"><Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search student, ID, SchoolPay code or contact…" className="tafiti-input h-10 w-full pl-9 pr-3 text-xs" /></label>
          <select value={searchParams.get('year') ?? data.filters.year ?? ''} onChange={(event) => setFilter('year', event.target.value)} className="tafiti-input h-10 px-3 text-xs font-bold"><option value="">Current year</option>{data.years.map((year) => <option key={year.id} value={year.id}>{year.label}</option>)}</select>
          <select value={searchParams.get('term') ?? data.filters.term ?? ''} onChange={(event) => setFilter('term', event.target.value)} className="tafiti-input h-10 px-3 text-xs font-bold"><option value="">Current term</option>{data.terms.map((term) => <option key={term.id} value={term.id}>{term.label}</option>)}</select>
        </div>

        <div className="flex gap-1 overflow-x-auto border-b border-slate-100 px-3 py-2">
          {[
            ['all', 'All accounts', counts.all], ['outstanding', 'Outstanding', counts.outstanding], ['partial', 'Partially paid', counts.partial], ['paid', 'Paid', counts.paid], ['credit', 'Credit', counts.credit],
          ].map(([value, label, count]) => <button key={String(value)} type="button" onClick={() => setFilter('status', String(value))} className={`min-w-max rounded-lg px-3 py-2 text-[10px] font-extrabold ${activeStatus === value ? 'bg-blue-600 text-white' : 'text-slate-500 hover:bg-slate-50'}`}>{label} <span className="ml-1 opacity-70">{count}</span></button>)}
        </div>

        <div className="hidden overflow-x-auto md:block">
          <table className="w-full min-w-[1080px] border-collapse text-left">
            <thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STUDENT</th><th className="px-3 py-3 text-[9px] font-extrabold text-slate-400">CLASS</th><th className="px-3 py-3 text-right text-[9px] font-extrabold text-slate-400">GROSS BILL</th><th className="px-3 py-3 text-right text-[9px] font-extrabold text-slate-400">ADJUSTMENTS</th><th className="px-3 py-3 text-right text-[9px] font-extrabold text-slate-400">PAID</th><th className="px-3 py-3 text-right text-[9px] font-extrabold text-slate-400">BALANCE</th><th className="px-3 py-3 text-[9px] font-extrabold text-slate-400">STATUS</th><th className="px-4 py-3 text-right text-[9px] font-extrabold text-slate-400">ACTION</th></tr></thead>
            <tbody className="divide-y divide-slate-100">{data.rows.map((row) => <tr key={row.bill_id} className="hover:bg-blue-50/20"><td className="px-4 py-3"><div className="flex items-center gap-2.5"><ProfileAvatar src={row.photo} name={row.student} size="sm" /><div><p className="text-xs font-extrabold text-slate-800">{row.student}</p><p className="mt-0.5 text-[9px] text-slate-400">{row.student_number}</p></div></div></td><td className="px-3 py-3"><p className="text-xs font-bold text-slate-700">{row.class}{row.stream ? ` · ${row.stream}` : ''}</p><p className="mt-0.5 text-[9px] text-slate-400">{row.year} · {row.term}</p></td><td className="px-3 py-3 text-right text-xs font-bold text-slate-700">{money(row.gross_billed)}</td><td className="px-3 py-3 text-right text-xs font-bold text-violet-700">{Number(row.adjustments) ? `− ${money(row.adjustments)}` : '—'}</td><td className="px-3 py-3 text-right text-xs font-bold text-emerald-700">{money(row.paid)}</td><td className="px-3 py-3 text-right text-xs font-extrabold text-[#10224A]">{money(row.balance)}</td><td className="px-3 py-3"><span className={`rounded-full border px-2 py-1 text-[9px] font-extrabold ${statusClass(row.status)}`}>{row.status}</span>{Number(row.credit) > 0 && <p className="mt-1 text-[9px] font-bold text-violet-600">{money(row.credit)} credit</p>}</td><td className="px-4 py-3 text-right"><div className="inline-flex gap-1.5"><Link href={`${dashboardPath}/fees/${row.bill_id}`} className="clay-row-action px-2.5 !w-auto text-[9px] font-bold">Open</Link>{data.actions.can_write && <Link href={`${dashboardPath}/fees/${row.bill_id}?action=record-payment`} className="clay-button-primary !h-8 px-2.5 text-[9px]">Record payment</Link>}</div></td></tr>)}</tbody>
          </table>
        </div>

        <div className="space-y-3 p-3 md:hidden">{data.rows.map((row) => <article key={row.bill_id} className="rounded-2xl border border-slate-100 bg-[#FBFCFE] p-3.5"><div className="flex items-center gap-2.5"><ProfileAvatar src={row.photo} name={row.student} size="sm" /><div className="min-w-0 flex-1"><p className="truncate text-xs font-extrabold text-slate-800">{row.student}</p><p className="text-[9px] text-slate-400">{row.student_number} · {row.class}</p></div><span className={`rounded-full border px-2 py-1 text-[8px] font-extrabold ${statusClass(row.status)}`}>{row.status}</span></div><div className="mt-3 grid grid-cols-2 gap-2"><div className="rounded-xl bg-white p-2.5"><p className="text-[8px] font-bold text-slate-400">NET DUE</p><p className="mt-1 text-xs font-extrabold text-slate-800">{money(row.net_due)}</p></div><div className="rounded-xl bg-white p-2.5"><p className="text-[8px] font-bold text-slate-400">BALANCE</p><p className="mt-1 text-xs font-extrabold text-amber-700">{money(row.balance)}</p></div><div className="rounded-xl bg-white p-2.5"><p className="text-[8px] font-bold text-slate-400">PAID</p><p className="mt-1 text-xs font-extrabold text-emerald-700">{money(row.paid)}</p></div><div className="rounded-xl bg-white p-2.5"><p className="text-[8px] font-bold text-slate-400">CREDIT</p><p className="mt-1 text-xs font-extrabold text-violet-700">{money(row.credit)}</p></div></div><div className="mt-3 flex gap-2"><Link href={`${dashboardPath}/fees/${row.bill_id}`} className="clay-button-secondary flex-1">Open account</Link>{data.actions.can_write && <Link href={`${dashboardPath}/fees/${row.bill_id}?action=record-payment`} className="clay-button-primary flex-1">Pay</Link>}</div></article>)}</div>

        {!data.rows.length && <div className="px-5 py-14 text-center"><WalletCards size={28} className="mx-auto text-blue-300" /><p className="mt-3 text-sm font-extrabold text-slate-800">No student accounts found</p><p className="mt-1 text-xs text-slate-400">Change the filters or create the class/student bill for this academic period.</p></div>}
      </section>
    </section>
  );
}
