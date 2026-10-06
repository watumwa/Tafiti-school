'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import {
  ArrowLeft,
  CircleDollarSign,
  FileText,
  LoaderCircle,
  MessageCircle,
  Printer,
  ReceiptText,
  UserRound,
  WalletCards,
} from 'lucide-react';

import type { WorkspaceEntity, WorkspaceFormSchema } from '@/lib/workspace';
import { useToast } from '@/components/ui/ToastProvider';
import { ProfileAvatar } from '@/components/workspace/ProfileAvatar';
import { ResourceFormDialog } from '@/components/workspace/ResourceFormDialog';

function statusClass(value: string) {
  return value.toLowerCase().includes('settled')
    ? 'border-emerald-100 bg-emerald-50 text-emerald-700'
    : 'border-amber-100 bg-amber-50 text-amber-700';
}

function metricIcon(label: string) {
  const value = label.toLowerCase();
  if (value.includes('paid')) return ReceiptText;
  if (value.includes('credit')) return WalletCards;
  return CircleDollarSign;
}

export function ReferenceFeeAccountWorkspace({ id, dashboardPath, onTitleChange }: { id: number; dashboardPath: string; onTitleChange?: (title: string) => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  const [data, setData] = useState<WorkspaceEntity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);
  const [paymentOpen, setPaymentOpen] = useState(false);
  const [paymentSchema, setPaymentSchema] = useState<WorkspaceFormSchema | null>(null);
  const [paymentLoading, setPaymentLoading] = useState(false);
  const [paymentErrors, setPaymentErrors] = useState<Record<string, string[]>>({});

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    fetch(`/api/workspace/resources/fees/${id}`, { cache: 'no-store', signal: controller.signal })
      .then(async (response) => { const payload = await response.json(); if (!response.ok) throw new Error(payload.detail || 'Fee account could not be opened.'); return payload as WorkspaceEntity; })
      .then((payload) => { setData(payload); onTitleChange?.(payload.title); })
      .catch((reason: unknown) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Fee account could not be opened.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [id, onTitleChange, reloadKey]);

  const activeTab = searchParams.get('tab') || data?.tabs[0]?.key || 'statement';
  const active = data?.tabs.find((tab) => tab.key === activeTab) ?? data?.tabs[0];
  const studentAction = data?.actions.find((action) => action.label.toLowerCase().includes('student profile'));
  const guardianAction = data?.actions.find((action) => action.label.toLowerCase().includes('guardian'));

  function selectTab(tab: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set('tab', tab);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }

  async function openPayment() {
    setPaymentOpen(true); setPaymentSchema(null); setPaymentErrors({}); setPaymentLoading(true);
    try {
      const response = await fetch('/api/workspace/resources/fees-payments/form', { cache: 'no-store' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Payment form could not be opened.');
      const schema = payload as WorkspaceFormSchema;
      setPaymentSchema({
        ...schema,
        fields: schema.fields.map((field) => field.name === 'bill' ? { ...field, initial: String(id) } : field),
      });
    } catch (reason: unknown) {
      toast.error('Could not open payment form', reason instanceof Error ? reason.message : 'Please try again.');
      setPaymentOpen(false);
    } finally { setPaymentLoading(false); }
  }

  async function submitPayment(values: Record<string, unknown>) {
    setPaymentLoading(true); setPaymentErrors({});
    try {
      const response = await fetch('/api/workspace/resources/fees-payments/form', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values) });
      const payload = await response.json();
      if (!response.ok) {
        setPaymentErrors((payload.errors as Record<string, string[]>) ?? {});
        throw new Error(payload.detail || 'Payment could not be recorded.');
      }
      toast.success('Payment recorded', payload.detail || 'The student fee account has been updated.');
      setPaymentOpen(false); setReloadKey((value) => value + 1);
      const params = new URLSearchParams(searchParams.toString()); params.set('tab', 'payments'); router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    } catch (reason: unknown) { toast.error('Payment not recorded', reason instanceof Error ? reason.message : 'Please try again.'); }
    finally { setPaymentLoading(false); }
  }

  if (loading && !data) return <div className="tafiti-card grid min-h-[440px] place-items-center"><div className="text-center text-xs font-semibold text-slate-500"><LoaderCircle className="mx-auto mb-3 animate-spin text-blue-600" size={24} />Opening fee account…</div></div>;
  if (error && !data) return <div className="tafiti-card p-6 text-center"><p className="text-sm font-bold text-slate-800">Fee account unavailable</p><p className="mt-2 text-xs text-slate-500">{error}</p></div>;
  if (!data) return null;

  return (
    <section>
      <Link href={`${dashboardPath}/fees`} className="mb-3 inline-flex items-center gap-1.5 text-[10px] font-bold text-slate-500 hover:text-blue-600"><ArrowLeft size={13} />Back to student accounts</Link>

      <section className="tafiti-card overflow-hidden">
        <div className="flex flex-col gap-5 px-5 py-5 lg:flex-row lg:items-center lg:justify-between sm:px-6">
          <div className="flex min-w-0 flex-col gap-4 sm:flex-row sm:items-center"><ProfileAvatar src={data.photo} name={data.title} size="xl" className="border-4 border-white shadow-[0_5px_16px_rgba(28,55,97,.12)]" /><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h1 className="truncate text-2xl font-extrabold tracking-[-0.035em] text-[#10224A]">{data.title}</h1><span className={`rounded-full border px-2.5 py-1 text-[9px] font-extrabold ${statusClass(data.status)}`}>{data.status}</span></div><p className="mt-1 text-xs font-bold text-blue-700">{data.subtitle}</p><div className="mt-3 flex flex-wrap gap-x-4 gap-y-2">{data.metadata.map((item) => <span key={item.label} className="text-[10px] text-slate-500"><span className="font-bold text-slate-400">{item.label}</span> · <span className="font-bold text-slate-700">{item.value}</span></span>)}</div></div></div>
          <div className="flex flex-wrap gap-2"><button type="button" onClick={() => void openPayment()} className="clay-button-primary"><CircleDollarSign size={14} />Record payment</button><button type="button" onClick={() => window.print()} className="clay-button-secondary"><Printer size={14} />Print statement</button>{studentAction?.href && <Link href={studentAction.href} className="clay-button-secondary"><UserRound size={14} />Student profile</Link>}{guardianAction?.href && <Link href={guardianAction.href} className="clay-button-secondary"><MessageCircle size={14} />Contact guardian</Link>}</div>
        </div>

        <div className="border-t border-slate-100 bg-[#FBFCFE] px-3 pt-2"><div className="flex min-w-max gap-1 overflow-x-auto">{data.tabs.map((tab) => <button key={tab.key} type="button" onClick={() => selectTab(tab.key)} className={`relative h-10 px-3.5 text-[10px] font-extrabold ${activeTab === tab.key ? 'text-blue-700' : 'text-slate-500 hover:text-slate-800'}`}>{tab.label}{tab.count > 0 && <span className={`ml-1.5 rounded-full px-1.5 py-0.5 text-[8px] ${activeTab === tab.key ? 'bg-blue-50 text-blue-700' : 'bg-slate-100 text-slate-500'}`}>{tab.count}</span>}{activeTab === tab.key && <span className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-blue-600" />}</button>)}</div></div>
      </section>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{data.metrics.map((metric) => { const Icon = metricIcon(metric.label); return <article key={metric.label} className="tafiti-kpi"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-blue-50 text-blue-600"><Icon size={17} /></span><div className="min-w-0"><p className="text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">{metric.label}</p><p className="mt-1 truncate text-lg font-extrabold text-[#10224A]">{metric.value}</p><p className="mt-0.5 truncate text-[9px] text-slate-400">{metric.hint}</p></div></div></article>; })}</div>

      <section className="tafiti-card mt-4 overflow-hidden">
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3.5 sm:px-5"><div><h2 className="text-sm font-extrabold text-[#10224A]">{active?.label ?? 'Statement'}</h2><p className="mt-1 text-[10px] text-slate-500">{active?.description}</p></div><FileText size={17} className="text-blue-600" /></div>
        {active?.rows.length ? <div className="overflow-x-auto"><table className="w-full min-w-[760px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]">{active.columns.map((column) => <th key={column.key} className="px-4 py-3 text-[9px] font-extrabold uppercase tracking-[.05em] text-slate-400">{column.label}</th>)}</tr></thead><tbody className="divide-y divide-slate-100">{active.rows.map((row, index) => <tr key={String(row.id ?? row.reference ?? index)} className="hover:bg-blue-50/25">{active.columns.map((column) => <td key={column.key} className={`px-4 py-3 text-xs ${['balance','amount','billed','paid','debit','credit'].includes(column.key) ? 'font-bold text-slate-800' : 'text-slate-600'}`}>{String(row[column.key] ?? '—')}</td>)}</tr>)}</tbody></table></div> : <div className="px-5 py-12 text-center text-xs text-slate-400">{active?.empty_title ?? 'No account entries.'}</div>}
      </section>

      <ResourceFormDialog open={paymentOpen} schema={paymentSchema} loading={paymentLoading} errors={paymentErrors} onClose={() => { setPaymentOpen(false); setPaymentErrors({}); }} onSubmit={submitPayment} />
    </section>
  );
}
