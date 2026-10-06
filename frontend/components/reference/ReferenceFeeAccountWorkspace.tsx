'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  ArrowLeft,
  BadgeDollarSign,
  CircleDollarSign,
  CreditCard,
  FileText,
  HandCoins,
  LoaderCircle,
  MessageCircle,
  Plus,
  Printer,
  ReceiptText,
  ShieldCheck,
  UserRound,
  WalletCards,
  X,
} from 'lucide-react';

import { useToast } from '@/components/ui/ToastProvider';
import { ProfileAvatar } from '@/components/workspace/ProfileAvatar';

interface BillSummary {
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

interface AccountPayload {
  bill: BillSummary;
  student: { id: number; student_number: string; name: string; photo: string; guardian: string; contact: string; class: string; stream: string };
  items: { id: number; description: string; category: string; amount: string; date: string; notes: string }[];
  payments: { id: number; date: string; amount: string; method: string; category: string; reference: string; recorded_by: string; notes: string }[];
  adjustments: { id: number; type: string; calculation_type: string; value: string; amount: string; reason: string; status: string; created_by: string; approved_by: string; created_at: string }[];
  credits: { id: number; date: string; amount: string; description: string; status: string; applied_date: string; original_bill_id: number; applied_to_bill_id: number | null }[];
  available_credit: string;
  actions: { can_record_payment: boolean; can_add_adjustment: boolean; can_apply_credit: boolean; can_cancel_adjustment: boolean };
  payment_methods: string[];
  fee_categories: string[];
  adjustment_types: string[];
}

interface ReceiptData {
  id: number;
  reference: string;
  date: string;
  amount: string;
  method: string;
  student: string;
  student_number: string;
  bill_id: number;
  class: string;
  term: string;
  balance_after: string;
  credit_after: string;
  recorded_by: string;
  school: { name: string; motto: string; address: string; phone: string; email: string };
}

type Tab = 'statement' | 'payments' | 'adjustments' | 'credits' | 'bill-items';

function money(value: string | number) {
  const numeric = Number(value || 0);
  return new Intl.NumberFormat('en-UG', { style: 'currency', currency: 'UGX', maximumFractionDigits: 0 }).format(Number.isFinite(numeric) ? numeric : 0);
}

function statusClass(status: string) {
  if (status === 'Paid') return 'border-emerald-100 bg-emerald-50 text-emerald-700';
  if (status === 'Partial') return 'border-amber-100 bg-amber-50 text-amber-700';
  if (status === 'Credit') return 'border-violet-100 bg-violet-50 text-violet-700';
  return 'border-rose-100 bg-rose-50 text-rose-700';
}

function escapeHtml(value: string | number) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function printPaymentReceipt(receipt: ReceiptData) {
  const popup = window.open('', '_blank', 'width=760,height=920');
  if (!popup) return false;
  const contact = [receipt.school.address, receipt.school.phone, receipt.school.email].filter(Boolean).map(escapeHtml).join(' · ');
  popup.document.write(`<!doctype html>
<html><head><meta charset="utf-8"><title>Receipt ${escapeHtml(receipt.reference)}</title>
<style>
@page{size:A5 portrait;margin:10mm}*{box-sizing:border-box}body{font-family:Arial,sans-serif;color:#0f172a;margin:0;background:#fff}.receipt{border:1px solid #cbd5e1;padding:22px}.head{text-align:center;border-bottom:2px solid #0f3b82;padding-bottom:14px}.school{font-size:20px;font-weight:800;color:#0f3b82}.motto{font-size:10px;font-style:italic;margin-top:4px}.contact{font-size:9px;color:#64748b;margin-top:5px}.title{font-size:14px;font-weight:800;letter-spacing:.12em;margin-top:14px}.ref{font-size:10px;color:#475569;margin-top:4px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:18px}.field{border-bottom:1px solid #e2e8f0;padding:7px 0}.label{font-size:8px;font-weight:700;color:#64748b;text-transform:uppercase}.value{font-size:11px;font-weight:700;margin-top:3px}.amount{margin-top:18px;border:2px solid #0f3b82;padding:14px;text-align:center}.amount .value{font-size:24px;color:#0f3b82}.summary{margin-top:15px;font-size:10px;display:flex;justify-content:space-between;gap:12px}.signatures{display:grid;grid-template-columns:1fr 1fr;gap:28px;margin-top:38px;font-size:9px}.line{border-top:1px solid #64748b;padding-top:5px;text-align:center}.footer{text-align:center;font-size:8px;color:#64748b;margin-top:24px}
</style></head><body><div class="receipt"><div class="head"><div class="school">${escapeHtml(receipt.school.name)}</div>${receipt.school.motto ? `<div class="motto">${escapeHtml(receipt.school.motto)}</div>` : ''}${contact ? `<div class="contact">${contact}</div>` : ''}<div class="title">OFFICIAL PAYMENT RECEIPT</div><div class="ref">Receipt / Reference: ${escapeHtml(receipt.reference)}</div></div><div class="grid"><div class="field"><div class="label">Student</div><div class="value">${escapeHtml(receipt.student)}</div></div><div class="field"><div class="label">Student No.</div><div class="value">${escapeHtml(receipt.student_number)}</div></div><div class="field"><div class="label">Class</div><div class="value">${escapeHtml(receipt.class)}</div></div><div class="field"><div class="label">Term</div><div class="value">${escapeHtml(receipt.term)}</div></div><div class="field"><div class="label">Payment date</div><div class="value">${escapeHtml(receipt.date)}</div></div><div class="field"><div class="label">Payment method</div><div class="value">${escapeHtml(receipt.method)}</div></div><div class="field"><div class="label">Bill</div><div class="value">#${escapeHtml(receipt.bill_id)}</div></div><div class="field"><div class="label">Received by</div><div class="value">${escapeHtml(receipt.recorded_by)}</div></div></div><div class="amount"><div class="label">Amount received</div><div class="value">${escapeHtml(money(receipt.amount))}</div></div><div class="summary"><span>Balance after payment: <strong>${escapeHtml(money(receipt.balance_after))}</strong></span><span>Available credit: <strong>${escapeHtml(money(receipt.credit_after))}</strong></span></div><div class="signatures"><div class="line">Cashier / Bursar signature</div><div class="line">Parent / Payer signature</div></div><div class="footer">Computer-generated receipt · Keep this receipt for your records.</div></div></body></html>`);
  popup.document.close();
  popup.focus();
  window.setTimeout(() => { popup.print(); popup.close(); }, 250);
  return true;
}

function Modal({ open, title, children, onClose }: { open: boolean; title: string; children: React.ReactNode; onClose: () => void }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[90] grid place-items-center bg-slate-950/35 p-4 backdrop-blur-[2px]" onMouseDown={(event) => { if (event.currentTarget === event.target) onClose(); }}>
      <div className="clay-dialog max-h-[92vh] w-full max-w-xl overflow-y-auto">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-100 bg-white px-5 py-4"><h2 className="text-sm font-extrabold text-[#10224A]">{title}</h2><button type="button" onClick={onClose} className="clay-icon-button"><X size={15} /></button></div>
        {children}
      </div>
    </div>
  );
}

function Metric({ label, value, icon, tone, hint }: { label: string; value: string; icon: React.ReactNode; tone: string; hint?: string }) {
  return <article className="tafiti-kpi"><div className="flex items-start gap-3"><span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${tone}`}>{icon}</span><div className="min-w-0"><p className="text-[9px] font-extrabold uppercase tracking-[.06em] text-slate-400">{label}</p><p className="mt-1 truncate text-lg font-extrabold text-[#10224A]">{money(value)}</p>{hint && <p className="mt-0.5 truncate text-[9px] text-slate-400">{hint}</p>}</div></div></article>;
}

export function ReferenceFeeAccountWorkspace({ id, dashboardPath, onTitleChange }: { id: number; dashboardPath: string; onTitleChange?: (title: string) => void }) {
  const toast = useToast();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [data, setData] = useState<AccountPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);
  const [tab, setTab] = useState<Tab>('statement');
  const [paymentOpen, setPaymentOpen] = useState(searchParams.get('action') === 'record-payment');
  const [adjustmentOpen, setAdjustmentOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [receipt, setReceipt] = useState<ReceiptData | null>(null);
  const [payment, setPayment] = useState({ amount: '', payment_date: new Date().toISOString().slice(0, 10), payment_method: 'Cash', reference_no: '', fee_category: '', notes: '' });
  const [adjustment, setAdjustment] = useState({ adjustment_type: 'Bursary', calculation_type: 'Fixed', value: '', reason: '' });

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    fetch(`/api/workspace/student-finance/account/${id}`, { cache: 'no-store', signal: controller.signal })
      .then(async (response) => { const payload = await response.json(); if (!response.ok) throw new Error(payload.detail || 'Fee account could not be opened.'); return payload as AccountPayload; })
      .then((payload) => {
        setData(payload);
        onTitleChange?.(payload.student.name);
        setPayment((current) => ({ ...current, amount: current.amount || payload.bill.balance, payment_method: payload.payment_methods[0] || 'Cash' }));
        setAdjustment((current) => ({ ...current, adjustment_type: payload.adjustment_types[0] || 'Bursary' }));
      })
      .catch((reason: unknown) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Fee account could not be opened.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [id, onTitleChange, reloadKey]);

  const availableCredit = Number(data?.available_credit ?? 0);
  const balance = Number(data?.bill.balance ?? 0);
  const netDue = Number(data?.bill.net_due ?? 0);

  const ledger = useMemo(() => {
    if (!data) return [];
    const rows = [
      ...data.items.map((item) => ({ date: item.date, type: 'Charge', description: item.description, debit: Number(item.amount), credit: 0 })),
      ...data.adjustments.filter((item) => item.status === 'Approved').map((item) => ({ date: item.created_at.slice(0, 10), type: item.type, description: item.reason || item.type, debit: 0, credit: Number(item.amount) })),
      ...data.payments.map((item) => ({ date: item.date, type: 'Payment', description: `${item.method} · ${item.reference}`, debit: 0, credit: Number(item.amount) })),
      ...data.credits.filter((item) => item.amount.startsWith('-')).map((item) => ({ date: item.applied_date || item.date, type: 'Credit applied', description: item.description, debit: 0, credit: Math.abs(Number(item.amount)) })),
    ];
    return rows.sort((a, b) => a.date.localeCompare(b.date));
  }, [data]);

  async function postAction(body: Record<string, unknown>) {
    const response = await fetch(`/api/workspace/student-finance/account/${id}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || 'The finance action could not be completed.');
    return payload;
  }

  async function submitPayment(event: FormEvent) {
    event.preventDefault(); setSubmitting(true);
    try {
      const payload = await postAction({ action: 'record_payment', ...payment });
      setData(payload.account as AccountPayload); setReceipt(payload.payment as ReceiptData); setPaymentOpen(false); setTab('payments');
      setPayment((current) => ({ ...current, amount: '', reference_no: '', notes: '' }));
      toast.success('Payment recorded', 'The payment is now attached to this student bill.');
      router.replace(`${dashboardPath}/fees/${id}?tab=payments`, { scroll: false });
    } catch (reason: unknown) { toast.error('Payment not recorded', reason instanceof Error ? reason.message : 'Please try again.'); }
    finally { setSubmitting(false); }
  }

  async function submitAdjustment(event: FormEvent) {
    event.preventDefault(); setSubmitting(true);
    try {
      const payload = await postAction({ action: 'add_adjustment', ...adjustment });
      setData(payload.account as AccountPayload); setAdjustmentOpen(false); setTab('adjustments');
      setAdjustment((current) => ({ ...current, value: '', reason: '' }));
      toast.success('Adjustment applied', payload.detail || 'The student account has been updated.');
    } catch (reason: unknown) { toast.error('Adjustment not applied', reason instanceof Error ? reason.message : 'Please try again.'); }
    finally { setSubmitting(false); }
  }

  async function applyCredit() {
    setSubmitting(true);
    try {
      const payload = await postAction({ action: 'apply_credit' });
      setData(payload.account as AccountPayload); toast.success('Credit applied', payload.detail || 'Student credit reduced this bill.');
    } catch (reason: unknown) { toast.error('Credit not applied', reason instanceof Error ? reason.message : 'Please try again.'); }
    finally { setSubmitting(false); }
  }

  async function cancelAdjustment(adjustmentId: number) {
    if (!window.confirm('Cancel this bursary/fee adjustment?')) return;
    setSubmitting(true);
    try {
      const payload = await postAction({ action: 'cancel_adjustment', adjustment_id: adjustmentId });
      setData(payload.account as AccountPayload); toast.success('Adjustment cancelled', payload.detail || 'Student account updated.');
    } catch (reason: unknown) { toast.error('Could not cancel adjustment', reason instanceof Error ? reason.message : 'Please try again.'); }
    finally { setSubmitting(false); }
  }

  if (loading && !data) return <div className="tafiti-card grid min-h-[440px] place-items-center"><div className="text-center text-xs font-semibold text-slate-500"><LoaderCircle className="mx-auto mb-3 animate-spin text-blue-600" size={24} />Opening student account…</div></div>;
  if (error && !data) return <div className="tafiti-card p-6 text-center"><p className="text-sm font-bold text-slate-800">Fee account unavailable</p><p className="mt-2 text-xs text-slate-500">{error}</p></div>;
  if (!data) return null;

  const tabs: { key: Tab; label: string; count?: number }[] = [
    { key: 'statement', label: 'Statement', count: ledger.length },
    { key: 'payments', label: 'Payments', count: data.payments.length },
    { key: 'adjustments', label: 'Bursaries & Adjustments', count: data.adjustments.length },
    { key: 'credits', label: 'Credits', count: data.credits.length },
    { key: 'bill-items', label: 'Bill Items', count: data.items.length },
  ];

  return (
    <section className="space-y-4">
      <Link href={`${dashboardPath}/fees`} className="inline-flex items-center gap-1.5 text-[10px] font-bold text-slate-500 hover:text-blue-600"><ArrowLeft size={13} />Back to student accounts</Link>

      <section className="tafiti-card overflow-hidden print:shadow-none">
        <div className="flex flex-col gap-5 px-5 py-5 lg:flex-row lg:items-center lg:justify-between sm:px-6">
          <div className="flex min-w-0 flex-col gap-4 sm:flex-row sm:items-center"><ProfileAvatar src={data.student.photo} name={data.student.name} size="xl" className="border-4 border-white shadow-[0_5px_16px_rgba(28,55,97,.12)]" /><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h1 className="truncate text-2xl font-extrabold tracking-[-0.035em] text-[#10224A]">{data.student.name}</h1><span className={`rounded-full border px-2.5 py-1 text-[9px] font-extrabold ${statusClass(data.bill.status)}`}>{data.bill.status === 'Partial' ? 'Partially Paid' : data.bill.status}</span></div><p className="mt-1 text-xs font-bold text-blue-700">{data.student.student_number} · Bill #{data.bill.bill_id}</p><div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-[10px] text-slate-500"><span><b className="text-slate-400">Class</b> · <b className="text-slate-700">{data.bill.class}{data.bill.stream ? ` · ${data.bill.stream}` : ''}</b></span><span><b className="text-slate-400">Period</b> · <b className="text-slate-700">{data.bill.year} · {data.bill.term}</b></span><span><b className="text-slate-400">Guardian</b> · <b className="text-slate-700">{data.student.guardian}</b></span></div></div></div>
          <div className="flex flex-wrap gap-2 print:hidden">{data.actions.can_record_payment && <button type="button" onClick={() => setPaymentOpen(true)} className="clay-button-primary"><CircleDollarSign size={14} />Record payment</button>}{data.actions.can_add_adjustment && <button type="button" onClick={() => setAdjustmentOpen(true)} className="clay-button-secondary"><HandCoins size={14} />Add bursary</button>}{data.actions.can_apply_credit && availableCredit > 0 && balance > 0 && <button type="button" disabled={submitting} onClick={() => void applyCredit()} className="clay-button-secondary"><ShieldCheck size={14} />Apply {money(Math.min(availableCredit, balance))} credit</button>}<button type="button" onClick={() => window.print()} className="clay-button-secondary"><Printer size={14} />Print statement</button><Link href={`${dashboardPath}/students/${data.student.id}?tab=fees`} className="clay-button-secondary"><UserRound size={14} />Student profile</Link><Link href={`${dashboardPath}/communication?recipient=${encodeURIComponent(data.student.guardian)}&student=${data.student.id}`} className="clay-button-secondary"><MessageCircle size={14} />Guardian</Link></div>
        </div>
        <div className="border-t border-slate-100 bg-[#FBFCFE] px-3 pt-2 print:hidden"><div className="flex min-w-max gap-1 overflow-x-auto">{tabs.map((item) => <button key={item.key} type="button" onClick={() => setTab(item.key)} className={`relative h-10 px-3.5 text-[10px] font-extrabold ${tab === item.key ? 'text-blue-700' : 'text-slate-500 hover:text-slate-800'}`}>{item.label}{item.count ? <span className={`ml-1.5 rounded-full px-1.5 py-0.5 text-[8px] ${tab === item.key ? 'bg-blue-50 text-blue-700' : 'bg-slate-100 text-slate-500'}`}>{item.count}</span> : null}{tab === item.key && <span className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-blue-600" />}</button>)}</div></div>
      </section>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Metric label="Gross bill" value={data.bill.gross_billed} icon={<WalletCards size={17} />} tone="bg-blue-50 text-blue-600" />
        <Metric label="Bursary / adjustments" value={data.bill.adjustments} icon={<HandCoins size={17} />} tone="bg-violet-50 text-violet-600" hint={Number(data.bill.adjustments) ? 'Reduces amount due; not cash received' : 'No concessions applied'} />
        <Metric label="Net amount due" value={data.bill.net_due} icon={<FileText size={17} />} tone="bg-cyan-50 text-cyan-700" />
        <Metric label="Cash paid" value={data.bill.paid} icon={<BadgeDollarSign size={17} />} tone="bg-emerald-50 text-emerald-600" />
        <Metric label="Outstanding" value={data.bill.balance} icon={<CircleDollarSign size={17} />} tone="bg-amber-50 text-amber-600" hint={Number(data.bill.credit) > 0 ? `${money(data.bill.credit)} student credit available` : undefined} />
      </div>

      {Number(data.bill.credit) > 0 && <div className="flex items-start gap-3 rounded-2xl border border-violet-100 bg-violet-50 px-4 py-3 text-xs text-violet-800"><ShieldCheck size={17} className="mt-0.5 shrink-0" /><div><p className="font-extrabold">This student has {money(data.bill.credit)} credit.</p><p className="mt-0.5 text-[10px] leading-4 text-violet-600">Overpayments are held on the student's account and can reduce a later bill; they are not lost or treated as extra income.</p></div></div>}

      <section className="tafiti-card overflow-hidden">
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3.5 sm:px-5"><div><h2 className="text-sm font-extrabold text-[#10224A]">{tabs.find((item) => item.key === tab)?.label}</h2><p className="mt-1 text-[10px] text-slate-500">{tab === 'statement' ? 'Charges, bursaries, payments and applied credits in chronological order.' : tab === 'payments' ? 'Every cash payment recorded against this student bill.' : tab === 'adjustments' ? 'Bursaries, scholarships, waivers and other approved reductions.' : tab === 'credits' ? 'Overpayments and carry-forward credits on the student account.' : 'The charges that make up this bill.'}</p></div><ReceiptText size={17} className="text-blue-600" /></div>

        {tab === 'statement' && <div className="overflow-x-auto"><table className="w-full min-w-[760px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">DATE</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">TYPE</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">DESCRIPTION</th><th className="px-4 py-3 text-right text-[9px] font-extrabold text-slate-400">CHARGE</th><th className="px-4 py-3 text-right text-[9px] font-extrabold text-slate-400">CREDIT / PAYMENT</th></tr></thead><tbody className="divide-y divide-slate-100">{ledger.map((row, index) => <tr key={`${row.date}-${row.type}-${index}`}><td className="px-4 py-3 text-xs text-slate-500">{row.date}</td><td className="px-4 py-3 text-xs font-bold text-slate-700">{row.type}</td><td className="px-4 py-3 text-xs text-slate-600">{row.description}</td><td className="px-4 py-3 text-right text-xs font-bold text-slate-800">{row.debit ? money(row.debit) : '—'}</td><td className="px-4 py-3 text-right text-xs font-bold text-emerald-700">{row.credit ? money(row.credit) : '—'}</td></tr>)}</tbody><tfoot><tr className="border-t border-slate-200 bg-[#F8FAFD]"><td colSpan={3} className="px-4 py-3 text-right text-[10px] font-extrabold text-slate-500">CURRENT OUTSTANDING</td><td colSpan={2} className="px-4 py-3 text-right text-sm font-extrabold text-[#10224A]">{money(data.bill.balance)}</td></tr></tfoot></table></div>}

        {tab === 'payments' && <div>{data.payments.length ? <div className="overflow-x-auto"><table className="w-full min-w-[820px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">DATE</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">REFERENCE</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">METHOD</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">RECORDED BY</th><th className="px-4 py-3 text-right text-[9px] font-extrabold text-slate-400">AMOUNT</th></tr></thead><tbody className="divide-y divide-slate-100">{data.payments.map((row) => <tr key={row.id}><td className="px-4 py-3 text-xs text-slate-500">{row.date}</td><td className="px-4 py-3 text-xs font-bold text-blue-700">{row.reference}</td><td className="px-4 py-3 text-xs text-slate-600">{row.method}</td><td className="px-4 py-3 text-xs text-slate-600">{row.recorded_by}</td><td className="px-4 py-3 text-right text-xs font-extrabold text-emerald-700">{money(row.amount)}</td></tr>)}</tbody></table></div> : <div className="px-5 py-12 text-center text-xs text-slate-400">No payments have been recorded for this bill.</div>}</div>}

        {tab === 'adjustments' && <div>{data.adjustments.length ? <div className="overflow-x-auto"><table className="w-full min-w-[900px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">TYPE</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">BASIS</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">REASON</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">APPROVED BY</th><th className="px-4 py-3 text-right text-[9px] font-extrabold text-slate-400">AMOUNT</th><th className="px-4 py-3 text-right text-[9px] font-extrabold text-slate-400">STATUS</th></tr></thead><tbody className="divide-y divide-slate-100">{data.adjustments.map((row) => <tr key={row.id}><td className="px-4 py-3 text-xs font-bold text-slate-800">{row.type}</td><td className="px-4 py-3 text-xs text-slate-600">{row.calculation_type === 'Percentage' ? `${row.value}%` : money(row.value)}</td><td className="max-w-[300px] px-4 py-3 text-xs text-slate-600">{row.reason || '—'}</td><td className="px-4 py-3 text-xs text-slate-600">{row.approved_by || row.created_by || '—'}</td><td className="px-4 py-3 text-right text-xs font-extrabold text-violet-700">− {money(row.amount)}</td><td className="px-4 py-3 text-right"><span className={`rounded-full border px-2 py-1 text-[9px] font-bold ${row.status === 'Approved' ? 'border-emerald-100 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-slate-50 text-slate-500'}`}>{row.status}</span>{row.status === 'Approved' && data.actions.can_cancel_adjustment && <button type="button" disabled={submitting} onClick={() => void cancelAdjustment(row.id)} className="ml-2 text-[9px] font-bold text-rose-600 hover:underline">Cancel</button>}</td></tr>)}</tbody></table></div> : <div className="px-5 py-12 text-center text-xs text-slate-400">No bursary or fee adjustment has been applied.</div>}</div>}

        {tab === 'credits' && <div>{data.credits.length ? <div className="overflow-x-auto"><table className="w-full min-w-[800px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">DATE</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">DESCRIPTION</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STATUS</th><th className="px-4 py-3 text-right text-[9px] font-extrabold text-slate-400">AMOUNT</th></tr></thead><tbody className="divide-y divide-slate-100">{data.credits.map((row) => <tr key={row.id}><td className="px-4 py-3 text-xs text-slate-500">{row.date}</td><td className="px-4 py-3 text-xs text-slate-600">{row.description}</td><td className="px-4 py-3"><span className={`rounded-full border px-2 py-1 text-[9px] font-bold ${row.status === 'Available' ? 'border-violet-100 bg-violet-50 text-violet-700' : 'border-slate-200 bg-slate-50 text-slate-500'}`}>{row.status}</span></td><td className="px-4 py-3 text-right text-xs font-extrabold text-violet-700">{money(Math.abs(Number(row.amount)))}</td></tr>)}</tbody></table></div> : <div className="px-5 py-12 text-center text-xs text-slate-400">No student credit entries.</div>}</div>}

        {tab === 'bill-items' && <div>{data.items.length ? <div className="overflow-x-auto"><table className="w-full min-w-[760px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">DATE</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">DESCRIPTION</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">CATEGORY</th><th className="px-4 py-3 text-right text-[9px] font-extrabold text-slate-400">AMOUNT</th></tr></thead><tbody className="divide-y divide-slate-100">{data.items.map((row) => <tr key={row.id}><td className="px-4 py-3 text-xs text-slate-500">{row.date}</td><td className="px-4 py-3 text-xs font-bold text-slate-800">{row.description}</td><td className="px-4 py-3 text-xs text-slate-600">{row.category}</td><td className="px-4 py-3 text-right text-xs font-extrabold text-slate-800">{money(row.amount)}</td></tr>)}</tbody></table></div> : <div className="px-5 py-12 text-center text-xs text-slate-400">No bill items.</div>}</div>}
      </section>

      <Modal open={paymentOpen} title={`Record payment · ${data.student.name}`} onClose={() => setPaymentOpen(false)}>
        <form onSubmit={submitPayment} className="space-y-4 p-5">
          <div className="grid grid-cols-2 gap-3 rounded-2xl bg-[#F8FAFD] p-3"><div><p className="text-[8px] font-bold text-slate-400">CURRENT BALANCE</p><p className="mt-1 text-sm font-extrabold text-amber-700">{money(data.bill.balance)}</p></div><div><p className="text-[8px] font-bold text-slate-400">NET AMOUNT DUE</p><p className="mt-1 text-sm font-extrabold text-slate-800">{money(data.bill.net_due)}</p></div></div>
          <div className="grid gap-3 sm:grid-cols-2"><label className="block"><span className="mb-1.5 block text-[10px] font-bold text-slate-600">Amount (UGX)</span><input required type="number" min="1" step="0.01" value={payment.amount} onChange={(event) => setPayment({ ...payment, amount: event.target.value })} className="tafiti-input h-10 w-full px-3 text-xs" /></label><label className="block"><span className="mb-1.5 block text-[10px] font-bold text-slate-600">Payment date</span><input required type="date" value={payment.payment_date} onChange={(event) => setPayment({ ...payment, payment_date: event.target.value })} className="tafiti-input h-10 w-full px-3 text-xs" /></label></div>
          <div className="grid gap-3 sm:grid-cols-2"><label className="block"><span className="mb-1.5 block text-[10px] font-bold text-slate-600">Payment method</span><select value={payment.payment_method} onChange={(event) => setPayment({ ...payment, payment_method: event.target.value })} className="tafiti-input h-10 w-full px-3 text-xs">{data.payment_methods.map((method) => <option key={method}>{method}</option>)}</select></label><label className="block"><span className="mb-1.5 block text-[10px] font-bold text-slate-600">Fee category</span><select value={payment.fee_category} onChange={(event) => setPayment({ ...payment, fee_category: event.target.value })} className="tafiti-input h-10 w-full px-3 text-xs"><option value="">Auto-detect</option>{data.fee_categories.map((category) => <option key={category}>{category}</option>)}</select></label></div>
          <label className="block"><span className="mb-1.5 block text-[10px] font-bold text-slate-600">Reference number <span className="font-normal text-slate-400">(optional)</span></span><input value={payment.reference_no} onChange={(event) => setPayment({ ...payment, reference_no: event.target.value })} placeholder="Auto-generated when blank" className="tafiti-input h-10 w-full px-3 text-xs" /></label>
          <label className="block"><span className="mb-1.5 block text-[10px] font-bold text-slate-600">Notes</span><textarea value={payment.notes} onChange={(event) => setPayment({ ...payment, notes: event.target.value })} rows={3} className="tafiti-input w-full px-3 py-2 text-xs" /></label>
          {Number(payment.amount) > netDue && <div className="rounded-xl border border-violet-100 bg-violet-50 p-3 text-[10px] leading-4 text-violet-700"><b>Overpayment:</b> any amount above the student's net bill will be kept as student credit and can reduce a later bill.</div>}
          <div className="flex justify-end gap-2 border-t border-slate-100 pt-4"><button type="button" onClick={() => setPaymentOpen(false)} className="clay-button-secondary">Cancel</button><button type="submit" disabled={submitting} className="clay-button-primary"><CreditCard size={14} />{submitting ? 'Recording…' : 'Record payment'}</button></div>
        </form>
      </Modal>

      <Modal open={adjustmentOpen} title={`Add bursary / adjustment · ${data.student.name}`} onClose={() => setAdjustmentOpen(false)}>
        <form onSubmit={submitAdjustment} className="space-y-4 p-5">
          <div className="rounded-2xl border border-blue-100 bg-blue-50 p-3 text-[10px] leading-4 text-blue-700"><b>This is not a payment.</b> A bursary, scholarship or waiver reduces the amount the student owes without increasing cash received.</div>
          <div className="grid gap-3 sm:grid-cols-2"><label className="block"><span className="mb-1.5 block text-[10px] font-bold text-slate-600">Adjustment type</span><select value={adjustment.adjustment_type} onChange={(event) => setAdjustment({ ...adjustment, adjustment_type: event.target.value })} className="tafiti-input h-10 w-full px-3 text-xs">{data.adjustment_types.map((type) => <option key={type}>{type}</option>)}</select></label><label className="block"><span className="mb-1.5 block text-[10px] font-bold text-slate-600">Calculation</span><select value={adjustment.calculation_type} onChange={(event) => setAdjustment({ ...adjustment, calculation_type: event.target.value })} className="tafiti-input h-10 w-full px-3 text-xs"><option value="Fixed">Fixed amount</option><option value="Percentage">Percentage</option></select></label></div>
          <label className="block"><span className="mb-1.5 block text-[10px] font-bold text-slate-600">{adjustment.calculation_type === 'Percentage' ? 'Percentage (%)' : 'Amount (UGX)'}</span><input required type="number" min="0.01" max={adjustment.calculation_type === 'Percentage' ? 100 : undefined} step="0.01" value={adjustment.value} onChange={(event) => setAdjustment({ ...adjustment, value: event.target.value })} className="tafiti-input h-10 w-full px-3 text-xs" /></label>
          <label className="block"><span className="mb-1.5 block text-[10px] font-bold text-slate-600">Reason / approval note</span><textarea required value={adjustment.reason} onChange={(event) => setAdjustment({ ...adjustment, reason: event.target.value })} rows={3} placeholder="e.g. 50% bursary approved by school management" className="tafiti-input w-full px-3 py-2 text-xs" /></label>
          <div className="flex justify-end gap-2 border-t border-slate-100 pt-4"><button type="button" onClick={() => setAdjustmentOpen(false)} className="clay-button-secondary">Cancel</button><button type="submit" disabled={submitting} className="clay-button-primary"><Plus size={14} />{submitting ? 'Applying…' : 'Apply adjustment'}</button></div>
        </form>
      </Modal>

      <Modal open={Boolean(receipt)} title="Payment receipt" onClose={() => setReceipt(null)}>
        {receipt && <div className="p-6" id="payment-receipt"><div className="text-center"><p className="text-[9px] font-extrabold uppercase tracking-[.16em] text-blue-600">{receipt.school.name}</p><h2 className="mt-2 text-xl font-extrabold text-[#10224A]">Payment Receipt</h2><p className="mt-1 text-xs text-slate-400">Reference {receipt.reference}</p></div><div className="mt-6 grid gap-3 rounded-2xl border border-slate-100 bg-[#F8FAFD] p-4 sm:grid-cols-2"><div><p className="text-[8px] font-bold text-slate-400">STUDENT</p><p className="mt-1 text-xs font-extrabold text-slate-800">{receipt.student}</p><p className="text-[9px] text-slate-400">{receipt.student_number}</p></div><div><p className="text-[8px] font-bold text-slate-400">BILL</p><p className="mt-1 text-xs font-extrabold text-slate-800">Bill #{receipt.bill_id}</p></div><div><p className="text-[8px] font-bold text-slate-400">DATE</p><p className="mt-1 text-xs font-bold text-slate-700">{receipt.date}</p></div><div><p className="text-[8px] font-bold text-slate-400">METHOD</p><p className="mt-1 text-xs font-bold text-slate-700">{receipt.method}</p></div></div><div className="mt-5 rounded-2xl bg-blue-600 px-5 py-5 text-center text-white"><p className="text-[9px] font-bold uppercase tracking-[.12em] text-blue-100">Amount received</p><p className="mt-1 text-3xl font-extrabold">{money(receipt.amount)}</p></div><div className="mt-5 flex justify-end gap-2 print:hidden"><button type="button" onClick={() => setReceipt(null)} className="clay-button-secondary">Close</button><button type="button" onClick={() => { if (!printPaymentReceipt(receipt)) toast.error('Printing blocked', 'Allow pop-ups for this site, then try again.'); }} className="clay-button-primary"><Printer size={14} />Print receipt</button></div></div>}
      </Modal>
    </section>
  );
}
