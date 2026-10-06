'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  Banknote,
  CheckCircle2,
  FileSpreadsheet,
  Landmark,
  LoaderCircle,
  RefreshCw,
  Search,
  Upload,
} from 'lucide-react';

import { useToast } from '@/components/ui/ToastProvider';

type Metric = { label: string; value: string | number; hint: string; tone: string };
type Account = { id: number; label: string; bank: string; account_number: string };
type Payment = {
  id: number;
  student: string;
  reg_no: string;
  class: string;
  date: string;
  amount: string;
  amount_display: string;
  method: string;
  reference: string;
};
type Suggestion = {
  payment_id: number;
  student: string;
  reg_no: string;
  reference: string;
  payment_date: string;
  amount: string;
  amount_display: string;
  reason: string;
};
type BankTransaction = {
  id: number;
  account: string;
  date: string;
  description: string;
  amount: string;
  amount_display: string;
  type: string;
  reference: string;
  reconciled: boolean;
  payment_id: number | null;
  reconciled_at: string;
  notes: string;
  suggestions: Suggestion[];
};
type Statement = {
  id: number;
  account: string;
  account_id: number;
  date: string;
  opening_balance: string;
  closing_balance: string;
  transactions: number;
  reconciled: number;
  unreconciled: number;
  uploaded: string;
  file: string;
};
type Payload = {
  period: { year: string; term: string; start: string; end: string };
  permissions: { write: boolean };
  metrics: Metric[];
  accounts: Account[];
  statements: Statement[];
  transactions: BankTransaction[];
  payments: Payment[];
  recent_reconciled: BankTransaction[];
};

function dateLabel(value: string) {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, { day: '2-digit', month: 'short', year: 'numeric' }).format(parsed);
}

export function ReferenceFinanceReconciliation() {
  const toast = useToast();
  const [data, setData] = useState<Payload | null>(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [reloadKey, setReloadKey] = useState(0);
  const [showUpload, setShowUpload] = useState(false);
  const [selectedPayments, setSelectedPayments] = useState<Record<number, string>>({});

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetch('/api/workspace/finance-reconciliation', { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Bank reconciliation could not be loaded.');
        return payload as Payload;
      })
      .then((payload) => {
        setData(payload);
        setSelectedPayments(Object.fromEntries(payload.transactions.map((row) => [row.id, row.suggestions[0]?.payment_id ? String(row.suggestions[0].payment_id) : ''])));
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Bank reconciliation could not be loaded.');
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [reloadKey]);

  const transactions = useMemo(() => {
    const text = query.trim().toLowerCase();
    if (!text) return data?.transactions ?? [];
    return (data?.transactions ?? []).filter((row) => [row.account, row.description, row.reference, row.amount_display].some((value) => String(value || '').toLowerCase().includes(text)));
  }, [data, query]);

  async function reconcile(transactionId: number) {
    const paymentId = selectedPayments[transactionId];
    if (!paymentId) {
      toast.warning('Choose a payment', 'Select the recorded school payment that belongs to this bank credit.');
      return;
    }
    setWorking(true);
    try {
      const response = await fetch('/api/workspace/finance-reconciliation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'reconcile', transaction_id: transactionId, payment_id: Number(paymentId) }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'The transaction could not be reconciled.');
      toast.success('Payment reconciled', payload.detail);
      setReloadKey((value) => value + 1);
    } catch (reason: unknown) {
      toast.error('Reconciliation failed', reason instanceof Error ? reason.message : 'Please try again.');
    } finally { setWorking(false); }
  }

  async function uploadStatement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setWorking(true);
    const form = new FormData(event.currentTarget);
    form.set('action', 'upload_statement');
    try {
      const response = await fetch('/api/workspace/finance-reconciliation', { method: 'POST', body: form });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'The statement could not be uploaded.');
      toast.success('Statement imported', payload.detail);
      setShowUpload(false);
      event.currentTarget.reset();
      setReloadKey((value) => value + 1);
    } catch (reason: unknown) {
      toast.error('Statement not imported', reason instanceof Error ? reason.message : 'Please check the CSV and try again.');
    } finally { setWorking(false); }
  }

  if (loading && !data) return <div className="tafiti-card grid min-h-[440px] place-items-center"><LoaderCircle className="animate-spin text-blue-600" size={24} /></div>;
  if (error && !data) return <div className="tafiti-card p-6 text-center"><AlertCircle className="mx-auto text-red-500" size={24} /><p className="mt-3 text-sm font-bold text-slate-800">Bank reconciliation unavailable</p><p className="mt-2 text-xs text-slate-500">{error}</p><button type="button" onClick={() => setReloadKey((value) => value + 1)} className="clay-button-primary mt-4">Try again</button></div>;
  if (!data) return null;

  return (
    <section>
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex items-start gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-600"><Landmark size={21} /></span><div><h1 className="text-[1.65rem] font-extrabold tracking-[-0.035em] text-[#10224A]">Bank Reconciliation</h1><p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">Match bank credits to recorded school payments without leaving Finance. Suggested matches use amount, date and reference evidence.</p><p className="mt-1 text-[10px] font-bold text-blue-700">{data.period.year || 'Academic year'} · {data.period.term || 'Current term'}</p></div></div>
        <div className="flex flex-wrap gap-2"><button type="button" onClick={() => setReloadKey((value) => value + 1)} className="clay-button-secondary"><RefreshCw size={14} />Refresh</button>{data.permissions.write && <button type="button" onClick={() => setShowUpload((value) => !value)} className="clay-button-primary"><Upload size={14} />Upload statement</button>}</div>
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {data.metrics.map((metric) => <article key={metric.label} className="tafiti-kpi"><p className="text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">{metric.label}</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{metric.value}</p><p className="mt-1 text-[9px] text-slate-400">{metric.hint}</p></article>)}
      </div>

      {showUpload && data.permissions.write && (
        <form onSubmit={uploadStatement} className="tafiti-card mb-4 p-4 sm:p-5">
          <div className="mb-4 flex items-center gap-2"><FileSpreadsheet size={17} className="text-blue-600" /><div><h2 className="text-sm font-extrabold text-[#10224A]">Import bank statement</h2><p className="mt-1 text-[10px] text-slate-500">CSV columns: Date, Description, Amount and optional Reference. Positive amounts are treated as credits.</p></div></div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            <label className="text-[10px] font-bold text-slate-600">Bank account<select name="bank_account" required className="tafiti-input mt-1 h-10 w-full px-3 text-xs"><option value="">Choose account</option>{data.accounts.map((account) => <option key={account.id} value={account.id}>{account.label}</option>)}</select></label>
            <label className="text-[10px] font-bold text-slate-600">Statement date<input name="statement_date" type="date" required className="tafiti-input mt-1 h-10 w-full px-3 text-xs" /></label>
            <label className="text-[10px] font-bold text-slate-600">Opening balance<input name="opening_balance" type="number" step="0.01" required className="tafiti-input mt-1 h-10 w-full px-3 text-xs" /></label>
            <label className="text-[10px] font-bold text-slate-600">Closing balance<input name="closing_balance" type="number" step="0.01" required className="tafiti-input mt-1 h-10 w-full px-3 text-xs" /></label>
            <label className="text-[10px] font-bold text-slate-600">CSV file<input name="statement_file" type="file" accept=".csv,text/csv" required className="tafiti-input mt-1 h-10 w-full px-2 py-1.5 text-[10px]" /></label>
          </div>
          <div className="mt-4 flex justify-end"><button type="submit" disabled={working} className="clay-button-primary"><Upload size={14} />{working ? 'Importing…' : 'Import statement'}</button></div>
        </form>
      )}

      <section className="tafiti-card mb-4 overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-slate-100 px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between sm:px-5"><div><h2 className="text-sm font-extrabold text-[#10224A]">Unreconciled bank transactions</h2><p className="mt-1 text-[10px] text-slate-500">Select a payment beside the bank credit and reconcile it directly.</p></div><div className="relative w-full sm:max-w-[330px]"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search bank transaction…" className="tafiti-input h-9 w-full pl-9 pr-3 text-xs" /></div></div>
        <div className="overflow-x-auto"><table className="w-full min-w-[1160px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">BANK TRANSACTION</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">AMOUNT</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">REFERENCE</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">MATCH TO PAYMENT</th><th className="px-4 py-3 text-right text-[9px] font-extrabold text-slate-400">ACTION</th></tr></thead>
          <tbody className="divide-y divide-slate-100">{transactions.map((row) => {
            const amountPayments = data.payments.filter((payment) => Number(payment.amount) === Math.abs(Number(row.amount)));
            const options = amountPayments.length ? amountPayments : data.payments;
            return <tr key={row.id} className="align-top hover:bg-blue-50/20"><td className="px-4 py-3"><p className="text-xs font-bold text-slate-800">{row.description}</p><p className="mt-0.5 text-[9px] text-slate-400">{row.account} · {dateLabel(row.date)} · {row.type}</p>{row.suggestions[0] && <p className="mt-1 text-[9px] font-semibold text-blue-600">Suggested: {row.suggestions[0].student} · {row.suggestions[0].reason}</p>}</td><td className="px-4 py-3 text-xs font-extrabold text-slate-800">UGX {row.amount_display}</td><td className="px-4 py-3 text-xs text-slate-500">{row.reference || '—'}</td><td className="px-4 py-3"><select disabled={!data.permissions.write || row.type !== 'Credit'} value={selectedPayments[row.id] ?? ''} onChange={(event) => setSelectedPayments((current) => ({ ...current, [row.id]: event.target.value }))} className="tafiti-input h-9 min-w-[370px] px-3 text-[10px]"><option value="">Choose recorded payment</option>{options.map((payment) => <option key={payment.id} value={payment.id}>{payment.student} · {payment.reference} · UGX {payment.amount_display} · {dateLabel(payment.date)}</option>)}</select></td><td className="px-4 py-3 text-right">{data.permissions.write && row.type === 'Credit' ? <button type="button" disabled={working || !selectedPayments[row.id]} onClick={() => void reconcile(row.id)} className="clay-button-primary"><CheckCircle2 size={13} />Match</button> : <span className="text-[9px] font-bold text-slate-400">Review only</span>}</td></tr>;
          })}</tbody>
        </table></div>
        {!transactions.length && <div className="px-5 py-12 text-center"><CheckCircle2 className="mx-auto text-emerald-500" size={22} /><p className="mt-2 text-xs font-bold text-slate-700">No unreconciled transactions in this period.</p></div>}
      </section>

      <div className="grid gap-4 xl:grid-cols-2">
        <section className="tafiti-card overflow-hidden"><div className="border-b border-slate-100 px-4 py-3.5"><div className="flex items-center gap-2"><FileSpreadsheet size={16} className="text-blue-600" /><h2 className="text-sm font-extrabold text-[#10224A]">Bank statements</h2></div></div><div className="divide-y divide-slate-100">{data.statements.slice(0, 10).map((row) => <div key={row.id} className="flex items-center gap-3 px-4 py-3"><span className="grid h-9 w-9 place-items-center rounded-xl bg-blue-50 text-blue-600"><Landmark size={15} /></span><div className="min-w-0 flex-1"><p className="truncate text-xs font-bold text-slate-800">{row.account}</p><p className="mt-0.5 text-[9px] text-slate-400">{dateLabel(row.date)} · {row.reconciled}/{row.transactions} reconciled</p></div><span className={`rounded-full border px-2 py-1 text-[9px] font-bold ${row.unreconciled ? 'border-amber-100 bg-amber-50 text-amber-700' : 'border-emerald-100 bg-emerald-50 text-emerald-700'}`}>{row.unreconciled ? `${row.unreconciled} open` : 'Complete'}</span></div>)}{!data.statements.length && <div className="px-5 py-10 text-center text-xs text-slate-400">No bank statements uploaded.</div>}</div></section>
        <section className="tafiti-card overflow-hidden"><div className="border-b border-slate-100 px-4 py-3.5"><div className="flex items-center gap-2"><Banknote size={16} className="text-emerald-600" /><h2 className="text-sm font-extrabold text-[#10224A]">Recently reconciled</h2></div></div><div className="divide-y divide-slate-100">{data.recent_reconciled.slice(0, 10).map((row) => <div key={row.id} className="flex items-center gap-3 px-4 py-3"><span className="grid h-9 w-9 place-items-center rounded-xl bg-emerald-50 text-emerald-600"><CheckCircle2 size={15} /></span><div className="min-w-0 flex-1"><p className="truncate text-xs font-bold text-slate-800">{row.description}</p><p className="mt-0.5 text-[9px] text-slate-400">{dateLabel(row.date)} · {row.reference || 'No reference'}</p></div><p className="text-xs font-extrabold text-slate-800">UGX {row.amount_display}</p></div>)}{!data.recent_reconciled.length && <div className="px-5 py-10 text-center text-xs text-slate-400">No reconciled transactions yet.</div>}</div></section>
      </div>
    </section>
  );
}
