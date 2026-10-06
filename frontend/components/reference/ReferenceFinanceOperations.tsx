'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { ArrowRightLeft, Banknote, CheckCircle2, LoaderCircle, RefreshCw, Search, XCircle } from 'lucide-react';

import { useToast } from '@/components/ui/ToastProvider';

type ReconciliationPayload = {
  title: string;
  description: string;
  can_write: boolean;
  metrics: { bank_accounts: number; statements: number; unmatched_bank: number; unmatched_payments: number; matched: number };
  unmatched_transactions: Array<{ id: number; date: string; account: string; description: string; reference: string; amount: string }>;
  unmatched_payments: Array<{ id: number; date: string; student: string; student_number: string; reference: string; method: string; amount: string }>;
  matched: Array<{ transaction_id: number; payment_id: number; date: string; student: string; bank_reference: string; payment_reference: string; amount: string }>;
};

type BillingPayload = {
  title: string;
  description: string;
  can_write: boolean;
  classes: Array<{ id: number; label: string; class: string; year: string; term: string; templates: number; registered: number; billed: number }>;
};

export function ReferenceFinanceOperations() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  const requested = searchParams.get('view') || 'reconciliation';
  const view = requested === 'billing' ? 'billing' : 'reconciliation';
  const [reconciliation, setReconciliation] = useState<ReconciliationPayload | null>(null);
  const [billing, setBilling] = useState<BillingPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [transactionId, setTransactionId] = useState<number | null>(null);
  const [paymentId, setPaymentId] = useState<number | null>(null);
  const [query, setQuery] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetch(`/api/workspace/finance-console/${view}`, { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Finance operations could not be loaded.');
        if (view === 'billing') setBilling(payload as BillingPayload);
        else setReconciliation(payload as ReconciliationPayload);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) toast.error('Finance operations unavailable', reason instanceof Error ? reason.message : 'Please try again.');
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [reloadKey, toast, view]);

  function switchView(next: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set('view', next);
    router.replace(`?${params.toString()}`, { scroll: false });
  }

  async function post(screen: string, body: Record<string, unknown>, successTitle: string) {
    setSaving(true);
    try {
      const response = await fetch(`/api/workspace/finance-console/${screen}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Finance action failed.');
      toast.success(successTitle, payload.detail || 'Finance updated.');
      setTransactionId(null);
      setPaymentId(null);
      setReloadKey((value) => value + 1);
    } catch (reason: unknown) {
      toast.error('Finance action failed', reason instanceof Error ? reason.message : 'Please try again.');
    } finally { setSaving(false); }
  }

  const filteredClasses = useMemo(() => {
    const text = query.trim().toLowerCase();
    if (!text) return billing?.classes ?? [];
    return (billing?.classes ?? []).filter((row) => [row.label, row.class, row.year, row.term].some((value) => value.toLowerCase().includes(text)));
  }, [billing, query]);

  return (
    <section>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div><h1 className="text-[1.65rem] font-extrabold tracking-[-0.035em] text-[#10224A]">Finance Operations</h1><p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">Reconcile collections and keep student billing aligned with class fee templates without leaving this workspace.</p></div>
        <button type="button" onClick={() => setReloadKey((value) => value + 1)} className="clay-button-secondary"><RefreshCw size={14} />Refresh</button>
      </div>

      <div className="mb-4 flex w-fit gap-1 rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
        <button type="button" onClick={() => switchView('reconciliation')} className={`rounded-lg px-4 py-2 text-[10px] font-extrabold ${view === 'reconciliation' ? 'bg-blue-600 text-white' : 'text-slate-500 hover:bg-slate-50'}`}><span className="inline-flex items-center gap-1.5"><ArrowRightLeft size={13} />Reconciliation</span></button>
        <button type="button" onClick={() => switchView('billing')} className={`rounded-lg px-4 py-2 text-[10px] font-extrabold ${view === 'billing' ? 'bg-blue-600 text-white' : 'text-slate-500 hover:bg-slate-50'}`}><span className="inline-flex items-center gap-1.5"><RefreshCw size={13} />Billing Sync</span></button>
      </div>

      {loading ? <div className="tafiti-card grid min-h-[360px] place-items-center"><LoaderCircle className="animate-spin text-blue-600" size={24} /></div>
        : view === 'reconciliation' && reconciliation ? (
          <>
            <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              {[
                ['Bank accounts', reconciliation.metrics.bank_accounts], ['Statements', reconciliation.metrics.statements], ['Unmatched bank', reconciliation.metrics.unmatched_bank], ['Unmatched payments', reconciliation.metrics.unmatched_payments], ['Matched', reconciliation.metrics.matched],
              ].map(([label, value]) => <article key={String(label)} className="tafiti-kpi"><p className="text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">{String(label)}</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{String(value)}</p></article>)}
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
              <section className="tafiti-card overflow-hidden"><div className="border-b border-slate-100 px-4 py-3.5"><h2 className="text-sm font-extrabold text-[#10224A]">Unmatched bank credits</h2></div><div className="max-h-[420px] overflow-auto divide-y divide-slate-100">{reconciliation.unmatched_transactions.map((row) => <button key={row.id} type="button" onClick={() => setTransactionId(row.id)} className={`flex w-full items-center gap-3 px-4 py-3 text-left ${transactionId === row.id ? 'bg-blue-50' : 'hover:bg-slate-50'}`}><Banknote size={16} className="text-blue-600" /><div className="min-w-0 flex-1"><p className="truncate text-xs font-bold text-slate-800">{row.description}</p><p className="mt-0.5 text-[9px] text-slate-400">{row.date} · {row.reference || 'No reference'}</p></div><p className="text-xs font-extrabold text-slate-800">UGX {row.amount}</p></button>)}</div></section>
              <section className="tafiti-card overflow-hidden"><div className="border-b border-slate-100 px-4 py-3.5"><h2 className="text-sm font-extrabold text-[#10224A]">Unmatched payments</h2></div><div className="max-h-[420px] overflow-auto divide-y divide-slate-100">{reconciliation.unmatched_payments.map((row) => <button key={row.id} type="button" onClick={() => setPaymentId(row.id)} className={`flex w-full items-center gap-3 px-4 py-3 text-left ${paymentId === row.id ? 'bg-blue-50' : 'hover:bg-slate-50'}`}><CheckCircle2 size={16} className="text-emerald-600" /><div className="min-w-0 flex-1"><p className="truncate text-xs font-bold text-slate-800">{row.student}</p><p className="mt-0.5 text-[9px] text-slate-400">{row.reference} · {row.date}</p></div><p className="text-xs font-extrabold text-slate-800">UGX {row.amount}</p></button>)}</div></section>
            </div>

            {reconciliation.can_write && <div className="my-4 flex justify-end"><button disabled={!transactionId || !paymentId || saving} type="button" onClick={() => void post('reconciliation', { action: 'match', transaction_id: transactionId, payment_id: paymentId }, 'Payment reconciled')} className="clay-button-primary disabled:cursor-not-allowed disabled:opacity-50"><ArrowRightLeft size={14} />Match selected</button></div>}

            <section className="tafiti-card overflow-hidden"><div className="border-b border-slate-100 px-4 py-3.5"><h2 className="text-sm font-extrabold text-[#10224A]">Recent matches</h2></div><div className="overflow-x-auto"><table className="w-full min-w-[780px] text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] text-slate-400">STUDENT</th><th className="px-4 py-3 text-[9px] text-slate-400">BANK REF</th><th className="px-4 py-3 text-[9px] text-slate-400">PAYMENT REF</th><th className="px-4 py-3 text-[9px] text-slate-400">AMOUNT</th><th className="px-4 py-3 text-right text-[9px] text-slate-400">ACTION</th></tr></thead><tbody className="divide-y divide-slate-100">{reconciliation.matched.map((row) => <tr key={row.transaction_id}><td className="px-4 py-3 text-xs font-bold text-slate-800">{row.student}</td><td className="px-4 py-3 text-xs text-slate-500">{row.bank_reference || '—'}</td><td className="px-4 py-3 text-xs text-slate-500">{row.payment_reference}</td><td className="px-4 py-3 text-xs font-bold">UGX {row.amount}</td><td className="px-4 py-3 text-right">{reconciliation.can_write && <button type="button" disabled={saving} onClick={() => void post('reconciliation', { action: 'unmatch', transaction_id: row.transaction_id }, 'Match removed')} className="inline-flex items-center gap-1 text-[10px] font-bold text-red-600"><XCircle size={12} />Unmatch</button>}</td></tr>)}</tbody></table></div></section>
          </>
        ) : billing ? (
          <section className="tafiti-card overflow-hidden"><div className="flex flex-col gap-3 border-b border-slate-100 px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between"><div><h2 className="text-sm font-extrabold text-[#10224A]">Class billing status</h2><p className="mt-1 text-[10px] text-slate-500">Synchronise only when a class register or fee template has changed.</p></div><div className="relative w-full sm:max-w-[320px]"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} /><input value={query} onChange={(event) => setQuery(event.target.value)} className="tafiti-input h-9 w-full pl-9 pr-3 text-xs" placeholder="Search classes…" /></div></div><div className="overflow-x-auto"><table className="w-full min-w-[820px] text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] text-slate-400">CLASS</th><th className="px-4 py-3 text-[9px] text-slate-400">PERIOD</th><th className="px-4 py-3 text-[9px] text-slate-400">TEMPLATES</th><th className="px-4 py-3 text-[9px] text-slate-400">REGISTERED</th><th className="px-4 py-3 text-[9px] text-slate-400">BILLED</th><th className="px-4 py-3 text-right text-[9px] text-slate-400">ACTION</th></tr></thead><tbody className="divide-y divide-slate-100">{filteredClasses.map((row) => <tr key={row.id}><td className="px-4 py-3 text-xs font-bold text-slate-800">{row.class}</td><td className="px-4 py-3 text-xs text-slate-500">{row.year} · {row.term}</td><td className="px-4 py-3 text-xs">{row.templates}</td><td className="px-4 py-3 text-xs">{row.registered}</td><td className="px-4 py-3 text-xs">{row.billed}</td><td className="px-4 py-3 text-right">{billing.can_write && <button type="button" disabled={saving} onClick={() => void post('billing', { academic_class_id: row.id }, 'Billing synchronised')} className="inline-flex items-center gap-1 text-[10px] font-bold text-blue-600"><RefreshCw size={12} />Sync</button>}</td></tr>)}</tbody></table></div></section>
        ) : null}
    </section>
  );
}
