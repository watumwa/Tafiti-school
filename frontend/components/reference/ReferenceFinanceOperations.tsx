'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, BadgeCheck, Landmark, LoaderCircle, RefreshCw, Search, ShieldCheck } from 'lucide-react';

import { useToast } from '@/components/ui/ToastProvider';

type ReconciliationPayload = {
  title: string;
  description: string;
  period: { year: string; term: string };
  metrics: { bank_accounts: number; statements: number; unreconciled: number; unmatched_payments: number };
  transactions: { id: number; date: string; bank: string; description: string; amount: string; type: string; reference: string; status: string; payment_id: number | null; payment_reference: string }[];
  payments: { id: number; date: string; student: string; student_number: string; amount: string; method: string; reference: string }[];
  can_reconcile: boolean;
};
type ApprovalPayload = {
  title: string;
  description: string;
  metrics: { pending: number; approved: number; total_pending: string };
  rows: { id: number; date: string; description: string; vendor: string; department: string; expense: string; amount: string; payment_status: string; approval: string; approved_by: string }[];
  can_approve: boolean;
};

export function ReferenceFinanceOperations({ screen }: { screen: 'approvals' | 'reconciliation' }) {
  const toast = useToast();
  const [data, setData] = useState<ReconciliationPayload | ApprovalPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [reloadKey, setReloadKey] = useState(0);
  const [saving, setSaving] = useState(false);
  const [selectedPayment, setSelectedPayment] = useState<Record<string, number>>({});

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetch(`/api/workspace/finance-operations/${screen}`, { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Finance operations could not be loaded.');
        return payload as ReconciliationPayload | ApprovalPayload;
      })
      .then(setData)
      .catch((reason: unknown) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Finance operations could not be loaded.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [reloadKey, screen]);

  async function post(body: Record<string, unknown>, successTitle: string) {
    setSaving(true);
    try {
      const response = await fetch(`/api/workspace/finance-operations/${screen}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Finance action could not be completed.');
      toast.success(successTitle, payload.detail || 'Finance workflow updated.');
      setReloadKey((value) => value + 1);
    } catch (reason: unknown) {
      toast.error('Finance action failed', reason instanceof Error ? reason.message : 'Please try again.');
    } finally { setSaving(false); }
  }

  if (loading && !data) return <div className="tafiti-card grid min-h-[400px] place-items-center"><LoaderCircle className="animate-spin text-blue-600" size={24} /></div>;
  if (error && !data) return <div className="tafiti-card p-6 text-center"><AlertCircle className="mx-auto text-red-500" size={24} /><p className="mt-3 text-sm font-bold text-slate-800">Finance operations unavailable</p><p className="mt-2 text-xs text-slate-500">{error}</p></div>;
  if (!data) return null;

  if (screen === 'approvals') {
    const payload = data as ApprovalPayload;
    const rows = payload.rows.filter((row) => !query.trim() || Object.values(row).some((value) => String(value).toLowerCase().includes(query.toLowerCase())));
    return <section>
      <Header title={payload.title} description={payload.description} onRefresh={() => setReloadKey((v) => v + 1)} />
      <div className="mb-4 grid gap-3 sm:grid-cols-3"><Metric label="Pending approvals" value={payload.metrics.pending} /><Metric label="Approved" value={payload.metrics.approved} /><Metric label="Pending value" value={`UGX ${payload.metrics.total_pending}`} /></div>
      <section className="tafiti-card overflow-hidden"><SearchBar value={query} onChange={setQuery} placeholder="Search expenditure, vendor or department…" /><div className="overflow-x-auto"><table className="w-full min-w-[980px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><Th>Date</Th><Th>Expenditure</Th><Th>Vendor</Th><Th>Department</Th><Th>Amount</Th><Th>Status</Th><Th right>Action</Th></tr></thead><tbody className="divide-y divide-slate-100">{rows.map((row) => <tr key={row.id} className="hover:bg-blue-50/25"><Td>{row.date}</Td><td className="px-4 py-3"><p className="text-xs font-bold text-slate-800">{row.description}</p><p className="mt-0.5 text-[9px] text-slate-400">{row.expense}</p></td><Td>{row.vendor}</Td><Td>{row.department}</Td><td className="px-4 py-3 text-xs font-bold text-slate-800">UGX {row.amount}</td><td className="px-4 py-3"><span className={`rounded-full border px-2 py-1 text-[9px] font-bold ${row.approval === 'Approved' ? 'border-emerald-100 bg-emerald-50 text-emerald-700' : 'border-amber-100 bg-amber-50 text-amber-700'}`}>{row.approval}</span></td><td className="px-4 py-3 text-right">{payload.can_approve && <button disabled={saving} type="button" onClick={() => void post({ action: row.approval === 'Approved' ? 'revoke' : 'approve', expenditure_id: row.id }, row.approval === 'Approved' ? 'Approval revoked' : 'Expenditure approved')} className="text-[10px] font-bold text-blue-600 hover:underline">{row.approval === 'Approved' ? 'Revoke' : 'Approve'}</button>}</td></tr>)}</tbody></table></div></section>
    </section>;
  }

  const payload = data as ReconciliationPayload;
  const transactions = payload.transactions.filter((row) => !query.trim() || Object.values(row).some((value) => String(value).toLowerCase().includes(query.toLowerCase())));
  return <section>
    <Header title={payload.title} description={payload.description} onRefresh={() => setReloadKey((v) => v + 1)} />
    <p className="mb-3 text-[10px] font-bold text-blue-700">{payload.period.year || 'Academic year'} · {payload.period.term || 'Term'}</p>
    <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Metric label="Bank accounts" value={payload.metrics.bank_accounts} /><Metric label="Statements" value={payload.metrics.statements} /><Metric label="Unreconciled" value={payload.metrics.unreconciled} /><Metric label="Unmatched receipts" value={payload.metrics.unmatched_payments} /></div>
    <section className="tafiti-card overflow-hidden"><SearchBar value={query} onChange={setQuery} placeholder="Search bank transactions…" /><div className="overflow-x-auto"><table className="w-full min-w-[1120px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><Th>Date</Th><Th>Bank transaction</Th><Th>Amount</Th><Th>Reference</Th><Th>Status</Th><Th>Match receipt</Th><Th right>Action</Th></tr></thead><tbody className="divide-y divide-slate-100">{transactions.map((row) => <tr key={row.id} className="hover:bg-blue-50/25"><Td>{row.date}</Td><td className="px-4 py-3"><p className="text-xs font-bold text-slate-800">{row.description}</p><p className="mt-0.5 text-[9px] text-slate-400">{row.bank} · {row.type}</p></td><td className="px-4 py-3 text-xs font-bold text-slate-800">UGX {row.amount}</td><Td>{row.reference || '—'}</Td><td className="px-4 py-3"><span className={`rounded-full border px-2 py-1 text-[9px] font-bold ${row.status === 'Reconciled' ? 'border-emerald-100 bg-emerald-50 text-emerald-700' : 'border-amber-100 bg-amber-50 text-amber-700'}`}>{row.status}</span></td><td className="px-4 py-3">{row.status === 'Reconciled' ? <span className="text-[10px] font-semibold text-slate-500">{row.payment_reference}</span> : <select value={selectedPayment[String(row.id)] ?? ''} onChange={(event) => setSelectedPayment((current) => ({ ...current, [String(row.id)]: Number(event.target.value) }))} className="tafiti-input h-9 min-w-[280px] text-[10px]"><option value="">Choose matching receipt…</option>{payload.payments.map((payment) => <option key={payment.id} value={payment.id}>{payment.reference} · {payment.student} · UGX {payment.amount}</option>)}</select>}</td><td className="px-4 py-3 text-right">{payload.can_reconcile && row.status !== 'Reconciled' && <button disabled={saving || !selectedPayment[String(row.id)]} type="button" onClick={() => void post({ transaction_id: row.id, payment_id: selectedPayment[String(row.id)] }, 'Transaction reconciled')} className="inline-flex items-center gap-1 text-[10px] font-bold text-blue-600 hover:underline"><BadgeCheck size={12} />Match</button>}</td></tr>)}</tbody></table></div></section>
  </section>;
}

function Header({ title, description, onRefresh }: { title: string; description: string; onRefresh: () => void }) {
  return <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div className="flex items-start gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-600"><Landmark size={21} /></span><div><h1 className="text-[1.65rem] font-extrabold tracking-[-0.035em] text-[#10224A]">{title}</h1><p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">{description}</p></div></div><button type="button" onClick={onRefresh} className="clay-button-secondary"><RefreshCw size={14} />Refresh</button></div>;
}
function Metric({ label, value }: { label: string; value: string | number }) { return <article className="tafiti-kpi"><p className="text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">{label}</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{value}</p></article>; }
function SearchBar({ value, onChange, placeholder }: { value: string; onChange: (value: string) => void; placeholder: string }) { return <div className="border-b border-slate-100 px-4 py-3.5 sm:px-5"><div className="relative max-w-[420px]"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} /><input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} className="tafiti-input h-9 w-full pl-9 pr-3 text-xs" /></div></div>; }
function Th({ children, right = false }: { children: React.ReactNode; right?: boolean }) { return <th className={`px-4 py-3 text-[9px] font-extrabold uppercase tracking-[.05em] text-slate-400 ${right ? 'text-right' : ''}`}>{children}</th>; }
function Td({ children }: { children: React.ReactNode }) { return <td className="px-4 py-3 text-xs text-slate-600">{children}</td>; }
