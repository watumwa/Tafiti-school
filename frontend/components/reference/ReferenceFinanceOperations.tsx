'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { ArrowRightLeft, Landmark, LoaderCircle, ReceiptText, RefreshCw, Search, WalletCards } from 'lucide-react';

import { useToast } from '@/components/ui/ToastProvider';
import { ReferenceResourceView } from './ReferenceResourceView';

type BillingPayload = {
  can_write: boolean;
  period: { year: string; term: string };
  classes: { id: number; class: string; year: string; term: string; students: number; bills: number; templates: number }[];
  bill_items: { id: number; label: string; category: string; description: string }[];
};
type CarryPayload = {
  can_write: boolean;
  terms: { id: number; label: string }[];
  source_term_id: number | null;
  target_term_id: number | null;
  total: string;
  rows: { student_id: number; student: string; student_number: string; source_bill_id: number; source_class: string; target_class: string; outstanding: string; can_post: boolean }[];
};
type ReconciliationPayload = {
  can_write: boolean;
  statements: { id: number; account: string; date: string; opening: string; closing: string; transactions: number }[];
  transactions: { id: number; date: string; account: string; description: string; amount: string; type: string; reference: string }[];
  payments: { id: number; date: string; student: string; student_number: string; amount: string; method: string; reference: string }[];
};

type View = 'overview' | 'billing' | 'carry-forward' | 'reconciliation';

const tabs: { key: View; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'billing', label: 'Bulk Billing' },
  { key: 'carry-forward', label: 'Carry Forward' },
  { key: 'reconciliation', label: 'Reconciliation' },
];

export function ReferenceFinanceOperations() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requested = searchParams.get('view') as View | null;
  const view: View = tabs.some((item) => item.key === requested) ? requested! : 'overview';

  function switchView(next: View) {
    const params = new URLSearchParams(searchParams.toString());
    if (next === 'overview') params.delete('view');
    else params.set('view', next);
    router.replace(`?${params.toString()}`, { scroll: false });
  }

  return (
    <section>
      <div className="mb-4 overflow-x-auto rounded-xl border border-slate-200 bg-white p-1.5 shadow-[0_5px_16px_rgba(28,55,97,.035)]">
        <div className="flex min-w-max gap-1">{tabs.map((item) => <button key={item.key} type="button" onClick={() => switchView(item.key)} className={`rounded-lg px-3.5 py-2 text-[10px] font-extrabold transition ${view === item.key ? 'bg-blue-600 text-white shadow-[0_5px_12px_rgba(37,99,235,.18)]' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'}`}>{item.label}</button>)}</div>
      </div>
      {view === 'overview' && <ReferenceResourceView resource="finance" />}
      {view === 'billing' && <BillingView />}
      {view === 'carry-forward' && <CarryForwardView />}
      {view === 'reconciliation' && <ReconciliationView />}
    </section>
  );
}

function Loading() {
  return <div className="tafiti-card grid min-h-[360px] place-items-center"><LoaderCircle className="animate-spin text-blue-600" size={24} /></div>;
}

function BillingView() {
  const toast = useToast();
  const [data, setData] = useState<BillingPayload | null>(null);
  const [selected, setSelected] = useState<number[]>([]);
  const [billItem, setBillItem] = useState('');
  const [amount, setAmount] = useState('');
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    fetch('/api/workspace/finance/operations/billing', { cache: 'no-store' })
      .then(async (response) => { const payload = await response.json(); if (!response.ok) throw new Error(payload.detail); return payload as BillingPayload; })
      .then(setData).catch((reason) => toast.error('Billing unavailable', reason instanceof Error ? reason.message : 'Please try again.'));
  }, [reload, toast]);

  async function generate() {
    if (!selected.length || !billItem || !amount) return toast.warning('Complete billing details', 'Choose class(es), a fee category and amount.');
    setBusy(true);
    try {
      const response = await fetch('/api/workspace/finance/operations/billing', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ class_ids: selected, bill_item_id: Number(billItem), amount }) });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Bulk billing failed.');
      toast.success('Bills generated', payload.detail);
      setReload((value) => value + 1);
    } catch (reason) { toast.error('Billing failed', reason instanceof Error ? reason.message : 'Please try again.'); }
    finally { setBusy(false); }
  }

  if (!data) return <Loading />;
  return <section>
    <div className="mb-4 flex items-start gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-600"><ReceiptText size={21} /></span><div><h1 className="text-[1.65rem] font-extrabold tracking-[-.035em] text-[#10224A]">Bulk Billing</h1><p className="mt-1 text-xs text-slate-500">Create or update a class fee once and sync it to every active registered student account.</p><p className="mt-1 text-[10px] font-bold text-blue-700">{data.period.year} · {data.period.term}</p></div></div>
    {data.can_write && <div className="tafiti-card mb-4 grid gap-3 p-4 md:grid-cols-[1fr_180px_auto] md:items-end"><label><span className="mb-1 block text-[9px] font-bold text-slate-400">FEE CATEGORY</span><select value={billItem} onChange={(e) => setBillItem(e.target.value)} className="tafiti-input h-10 w-full px-3 text-xs"><option value="">Choose category</option>{data.bill_items.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label><label><span className="mb-1 block text-[9px] font-bold text-slate-400">AMOUNT (UGX)</span><input value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" className="tafiti-input h-10 w-full px-3 text-xs" placeholder="0" /></label><button disabled={busy} onClick={() => void generate()} className="clay-button-primary h-10">{busy ? <LoaderCircle className="animate-spin" size={14} /> : <ReceiptText size={14} />}Generate</button></div>}
    <section className="tafiti-card overflow-hidden"><div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left"><thead><tr className="border-b bg-[#F8FAFD]"><th className="px-4 py-3"></th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">CLASS</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STUDENTS</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">ACCOUNTS</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">FEE TEMPLATES</th></tr></thead><tbody className="divide-y divide-slate-100">{data.classes.map((row) => <tr key={row.id}><td className="px-4 py-3"><input type="checkbox" checked={selected.includes(row.id)} onChange={(e) => setSelected((current) => e.target.checked ? [...current, row.id] : current.filter((id) => id !== row.id))} /></td><td className="px-4 py-3"><p className="text-xs font-bold text-slate-800">{row.class}</p><p className="text-[9px] text-slate-400">{row.year} · {row.term}</p></td><td className="px-4 py-3 text-xs font-bold text-slate-700">{row.students}</td><td className="px-4 py-3 text-xs text-slate-600">{row.bills}</td><td className="px-4 py-3 text-xs text-slate-600">{row.templates}</td></tr>)}</tbody></table></div></section>
  </section>;
}

function CarryForwardView() {
  const toast = useToast();
  const [data, setData] = useState<CarryPayload | null>(null);
  const [source, setSource] = useState('');
  const [target, setTarget] = useState('');
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const query = new URLSearchParams(); if (source) query.set('source_term', source); if (target) query.set('target_term', target);
    fetch(`/api/workspace/finance/operations/carry-forward?${query.toString()}`, { cache: 'no-store' })
      .then(async (response) => { const payload = await response.json(); if (!response.ok) throw new Error(payload.detail); return payload as CarryPayload; })
      .then((payload) => { setData(payload); if (!source && payload.source_term_id) setSource(String(payload.source_term_id)); if (!target && payload.target_term_id) setTarget(String(payload.target_term_id)); })
      .catch((reason) => toast.error('Carry-forward unavailable', reason instanceof Error ? reason.message : 'Please try again.'));
  }, [reload, source, target, toast]);

  async function post() {
    if (!source || !target) return;
    setBusy(true);
    try {
      const response = await fetch('/api/workspace/finance/operations/carry-forward', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ source_term_id: Number(source), target_term_id: Number(target), active_students_only: true }) });
      const payload = await response.json(); if (!response.ok) throw new Error(payload.detail || 'Carry-forward failed.');
      toast.success('Balances carried forward', payload.detail); setReload((value) => value + 1);
    } catch (reason) { toast.error('Carry-forward failed', reason instanceof Error ? reason.message : 'Please try again.'); } finally { setBusy(false); }
  }

  if (!data) return <Loading />;
  return <section><div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div className="flex items-start gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl bg-violet-50 text-violet-600"><ArrowRightLeft size={21} /></span><div><h1 className="text-[1.65rem] font-extrabold text-[#10224A]">Carry Forward</h1><p className="mt-1 text-xs text-slate-500">Preview outstanding balances before moving them into the next configured term.</p></div></div>{data.can_write && <button disabled={busy || !data.rows.some((row) => row.can_post)} onClick={() => void post()} className="clay-button-primary">{busy ? <LoaderCircle className="animate-spin" size={14} /> : <ArrowRightLeft size={14} />}Post UGX {data.total}</button>}</div>
    <div className="tafiti-card mb-4 grid gap-3 p-4 sm:grid-cols-2"><label><span className="mb-1 block text-[9px] font-bold text-slate-400">SOURCE TERM</span><select value={source} onChange={(e) => setSource(e.target.value)} className="tafiti-input h-10 w-full px-3 text-xs"><option value="">Choose term</option>{data.terms.map((term) => <option key={term.id} value={term.id}>{term.label}</option>)}</select></label><label><span className="mb-1 block text-[9px] font-bold text-slate-400">TARGET TERM</span><select value={target} onChange={(e) => setTarget(e.target.value)} className="tafiti-input h-10 w-full px-3 text-xs"><option value="">Choose term</option>{data.terms.map((term) => <option key={term.id} value={term.id}>{term.label}</option>)}</select></label></div>
    <section className="tafiti-card overflow-hidden"><div className="overflow-x-auto"><table className="w-full min-w-[850px] text-left"><thead><tr className="border-b bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STUDENT</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">FROM</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">TO</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">OUTSTANDING</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STATUS</th></tr></thead><tbody className="divide-y divide-slate-100">{data.rows.map((row) => <tr key={row.source_bill_id}><td className="px-4 py-3"><p className="text-xs font-bold text-slate-800">{row.student}</p><p className="text-[9px] text-slate-400">{row.student_number}</p></td><td className="px-4 py-3 text-xs text-slate-600">{row.source_class}</td><td className="px-4 py-3 text-xs text-slate-600">{row.target_class}</td><td className="px-4 py-3 text-xs font-bold text-slate-800">UGX {row.outstanding}</td><td className="px-4 py-3 text-[10px] font-bold">{row.can_post ? <span className="text-emerald-600">Ready</span> : <span className="text-amber-600">Target class missing</span>}</td></tr>)}</tbody></table></div>{!data.rows.length && <div className="px-5 py-12 text-center text-xs text-slate-400">No outstanding balances in this scope.</div>}</section>
  </section>;
}

function ReconciliationView() {
  const toast = useToast();
  const [data, setData] = useState<ReconciliationPayload | null>(null);
  const [transactionId, setTransactionId] = useState('');
  const [paymentId, setPaymentId] = useState('');
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);

  useEffect(() => { fetch('/api/workspace/finance/operations/reconciliation', { cache: 'no-store' }).then(async (response) => { const payload = await response.json(); if (!response.ok) throw new Error(payload.detail); return payload as ReconciliationPayload; }).then(setData).catch((reason) => toast.error('Reconciliation unavailable', reason instanceof Error ? reason.message : 'Please try again.')); }, [reload, toast]);
  const payments = useMemo(() => { const text = query.trim().toLowerCase(); return !text ? data?.payments ?? [] : (data?.payments ?? []).filter((row) => [row.student, row.student_number, row.reference, row.amount].some((value) => String(value).toLowerCase().includes(text))); }, [data, query]);

  async function match() {
    if (!transactionId || !paymentId) return toast.warning('Choose both records', 'Select the bank transaction and its matching student payment.');
    setBusy(true); try { const response = await fetch('/api/workspace/finance/operations/reconciliation', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ transaction_id: Number(transactionId), payment_id: Number(paymentId) }) }); const payload = await response.json(); if (!response.ok) throw new Error(payload.detail || 'Reconciliation failed.'); toast.success('Payment reconciled', payload.detail); setTransactionId(''); setPaymentId(''); setReload((value) => value + 1); } catch (reason) { toast.error('Reconciliation failed', reason instanceof Error ? reason.message : 'Please try again.'); } finally { setBusy(false); }
  }
  if (!data) return <Loading />;
  return <section><div className="mb-4 flex items-start gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl bg-emerald-50 text-emerald-600"><Landmark size={21} /></span><div><h1 className="text-[1.65rem] font-extrabold text-[#10224A]">Bank Reconciliation</h1><p className="mt-1 text-xs text-slate-500">Match an unreconciled bank credit to the exact recorded student payment without changing either original record.</p></div></div>
    <div className="grid gap-4 xl:grid-cols-2"><section className="tafiti-card overflow-hidden"><div className="border-b px-4 py-3.5"><h2 className="text-sm font-extrabold text-[#10224A]">Bank credits</h2></div><div className="max-h-[520px] divide-y overflow-y-auto">{data.transactions.map((row) => <label key={row.id} className={`flex cursor-pointer gap-3 p-4 ${String(row.id) === transactionId ? 'bg-blue-50' : ''}`}><input type="radio" name="bank-transaction" value={row.id} checked={String(row.id) === transactionId} onChange={() => setTransactionId(String(row.id))} /><div className="min-w-0 flex-1"><p className="text-xs font-bold text-slate-800">UGX {row.amount} · {row.reference || 'No reference'}</p><p className="mt-1 truncate text-[10px] text-slate-500">{row.date} · {row.account} · {row.description}</p></div></label>)}{!data.transactions.length && <div className="p-10 text-center text-xs text-slate-400">No unreconciled bank credits.</div>}</div></section>
      <section className="tafiti-card overflow-hidden"><div className="border-b p-4"><div className="relative"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search student, reference or amount…" className="tafiti-input h-9 w-full pl-9 pr-3 text-xs" /></div></div><div className="max-h-[460px] divide-y overflow-y-auto">{payments.map((row) => <label key={row.id} className={`flex cursor-pointer gap-3 p-4 ${String(row.id) === paymentId ? 'bg-emerald-50' : ''}`}><input type="radio" name="payment" value={row.id} checked={String(row.id) === paymentId} onChange={() => setPaymentId(String(row.id))} /><div className="min-w-0 flex-1"><p className="text-xs font-bold text-slate-800">{row.student} · UGX {row.amount}</p><p className="mt-1 text-[10px] text-slate-500">{row.student_number} · {row.reference} · {row.date}</p></div></label>)}</div><div className="border-t p-4"><button disabled={busy || !data.can_write} onClick={() => void match()} className="clay-button-primary w-full justify-center">{busy ? <LoaderCircle className="animate-spin" size={14} /> : <Landmark size={14} />}Match selected records</button></div></section></div>
  </section>;
}
