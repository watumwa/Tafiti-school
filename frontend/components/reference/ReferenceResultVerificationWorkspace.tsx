'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  FileCheck2,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  UserCheck,
} from 'lucide-react';

import type { ResultVerificationWorkflow, WorkspaceEntity } from '@/lib/workspace';
import { useToast } from '@/components/ui/ToastProvider';

function statusBadge(value: string) {
  const normalized = value.toLowerCase();
  if (normalized.includes('verified')) return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  if (normalized.includes('flagged') || normalized.includes('correction')) return 'border-rose-200 bg-rose-50 text-rose-700';
  if (normalized.includes('pending')) return 'border-amber-200 bg-amber-50 text-amber-700';
  return 'border-slate-200 bg-slate-50 text-slate-600';
}

export function ReferenceResultVerificationWorkspace({
  id,
  dashboardPath,
  onTitleChange,
}: {
  id: number;
  dashboardPath: string;
  onTitleChange?: (title: string) => void;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  const [data, setData] = useState<WorkspaceEntity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);
  const [marks, setMarks] = useState<Record<string, string>>({});
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState<'finalize' | 'reject' | ''>('');

  const returnPath = searchParams.get('return')?.startsWith(`${dashboardPath}/`)
    ? String(searchParams.get('return'))
    : `${dashboardPath}/results?view=verification&status=PENDING`;

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetch(`/api/workspace/resources/results/${id}?view=verification`, { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Verification batch could not be loaded.');
        return payload as WorkspaceEntity;
      })
      .then((payload) => {
        setData(payload);
        onTitleChange?.(payload.title);
        const workflow = payload.workflow?.kind === 'result_verification' ? payload.workflow : null;
        if (workflow) {
          setMarks(Object.fromEntries(workflow.samples.map((sample) => [String(sample.sample_id), sample.value])));
        }
      })
      .catch((reasonValue: unknown) => {
        if (!controller.signal.aborted) setError(reasonValue instanceof Error ? reasonValue.message : 'Verification batch could not be loaded.');
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [id, onTitleChange, reloadKey]);

  const workflow = data?.workflow?.kind === 'result_verification' ? data.workflow as ResultVerificationWorkflow : null;

  const comparisonMap = useMemo(() => {
    const samplesTab = data?.tabs.find((tab) => tab.key === 'samples');
    return new Map((samplesTab?.rows ?? []).map((row) => [String(row.student_id ?? ''), String(row.status ?? 'Pending')]));
  }, [data]);

  const completed = workflow?.samples.filter((sample) => String(marks[String(sample.sample_id)] ?? '').trim() !== '').length ?? 0;
  const total = workflow?.samples.length ?? 0;
  const progress = total ? Math.round((completed / total) * 100) : 0;
  const differenceMetric = data?.metrics.find((metric) => metric.label === 'Differences');
  const differences = Number(differenceMetric?.value ?? 0);

  async function submit(action: 'finalize' | 'reject') {
    if (!workflow) return;
    setSubmitting(action);
    try {
      const response = await fetch(`/api/workspace/resources/results/${id}/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, marks, rejection_reason: reason }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'Verification could not be completed.');
      toast.success(result.status === 'VERIFIED' ? 'Batch verified' : 'Returned for correction', result.detail || 'Decision saved.');
      if (result.next_href) router.push(String(result.next_href));
      else setReloadKey((value) => value + 1);
    } catch (reasonValue: unknown) {
      toast.error('Verification not completed', reasonValue instanceof Error ? reasonValue.message : 'Please try again.');
    } finally {
      setSubmitting('');
    }
  }

  if (loading && !data) {
    return <div className="tafiti-card grid min-h-[460px] place-items-center"><div className="text-center text-xs font-semibold text-slate-500"><LoaderCircle className="mx-auto mb-3 animate-spin text-blue-600" size={24} />Loading verification review…</div></div>;
  }

  if (error && !data) {
    return <div className="tafiti-card grid min-h-[420px] place-items-center p-6 text-center"><div><AlertCircle className="mx-auto text-red-500" size={24} /><h2 className="mt-3 text-sm font-bold text-slate-900">Verification batch unavailable</h2><p className="mt-2 text-xs text-slate-500">{error}</p><button type="button" onClick={() => setReloadKey((value) => value + 1)} className="clay-button-primary mt-4"><RefreshCw size={14} /> Try again</button></div></div>;
  }

  if (!data || !workflow) return null;

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link href={returnPath} className="inline-flex items-center gap-1.5 text-[11px] font-bold text-slate-500 hover:text-blue-600"><ArrowLeft size={13} /> Back to verification queue</Link>
        {workflow.next_href && <Link href={workflow.next_href} className="inline-flex items-center gap-1.5 text-[11px] font-bold text-blue-600 hover:underline">Next pending batch <ArrowRight size={13} /></Link>}
      </div>

      <header className="tafiti-card overflow-hidden">
        <div className="flex flex-col gap-4 p-5 lg:flex-row lg:items-center lg:justify-between sm:p-6">
          <div className="flex items-start gap-3"><span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-violet-50 text-violet-600"><FileCheck2 size={22} /></span><div><p className="text-[9px] font-extrabold uppercase tracking-[.12em] text-violet-600">Result verification</p><div className="mt-1 flex flex-wrap items-center gap-2"><h1 className="text-2xl font-extrabold tracking-[-.035em] text-[#10224A]">{data.title}</h1><span className={`rounded-full border px-2.5 py-1 text-[9px] font-extrabold ${statusBadge(data.status)}`}>{data.status}</span></div><p className="mt-1 text-xs font-semibold text-slate-500">{data.subtitle}</p></div></div>
          <div className="grid gap-2 sm:grid-cols-2 lg:min-w-[430px]">{data.metadata.map((item) => <div key={item.label} className="rounded-xl border border-slate-100 bg-[#F8FAFD] px-3 py-2.5"><p className="text-[8px] font-bold uppercase tracking-[.06em] text-slate-400">{item.label}</p><p className="mt-1 truncate text-[10px] font-bold text-slate-700">{item.value}</p></div>)}</div>
        </div>
      </header>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{data.metrics.map((metric, index) => {
        const iconClasses = ['bg-blue-50 text-blue-600', 'bg-emerald-50 text-emerald-600', 'bg-violet-50 text-violet-600', 'bg-amber-50 text-amber-600'];
        const Icon = index === 0 ? FileCheck2 : index === 1 ? ShieldCheck : index === 2 ? UserCheck : AlertCircle;
        return <article key={metric.label} className="tafiti-kpi"><div className="flex items-center gap-3"><span className={`grid h-10 w-10 place-items-center rounded-xl ${iconClasses[index % iconClasses.length]}`}><Icon size={17} /></span><div><p className="text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">{metric.label}</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{metric.value}</p><p className="mt-0.5 text-[9px] text-slate-400">{metric.hint}</p></div></div></article>;
      })}</div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,.6fr)]">
        <section className="tafiti-card overflow-hidden">
          <div className="border-b border-slate-100 bg-[#FBFCFE] px-4 py-4 sm:px-5"><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><h2 className="text-sm font-extrabold text-[#10224A]">Independent sample review</h2><p className="mt-1 text-[10px] leading-4 text-slate-500">Enter the verifier mark independently. The original teacher mark remains hidden until Django evaluates the sample.</p></div><span className="rounded-full border border-blue-100 bg-blue-50 px-3 py-1.5 text-[10px] font-bold text-blue-700">Out of {workflow.out_of}</span></div></div>

          <div className="border-b border-slate-100 px-4 py-3 sm:px-5"><div className="flex items-center gap-3"><div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-gradient-to-r from-blue-500 to-violet-500 transition-all" style={{ width: `${progress}%` }} /></div><span className="min-w-[98px] text-right text-[10px] font-bold text-slate-500">{completed}/{total} reviewed</span></div></div>

          {!workflow.can_finalize && workflow.blocked_reason && <div className="flex items-start gap-3 border-b border-amber-100 bg-amber-50 px-4 py-3.5 text-xs text-amber-800 sm:px-5"><AlertCircle size={16} className="mt-0.5 shrink-0" /><span>{workflow.blocked_reason}</span></div>}

          <div className="hidden overflow-x-auto md:block"><table className="w-full min-w-[760px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold uppercase tracking-[.06em] text-slate-400">Student</th><th className="px-4 py-3 text-[9px] font-extrabold uppercase tracking-[.06em] text-slate-400">Verifier mark</th><th className="px-4 py-3 text-[9px] font-extrabold uppercase tracking-[.06em] text-slate-400">Review state</th></tr></thead><tbody className="divide-y divide-slate-100">{workflow.samples.map((sample) => {
            const state = comparisonMap.get(sample.student_id) ?? (sample.checked ? 'Reviewed' : 'Pending');
            return <tr key={sample.sample_id} className="hover:bg-blue-50/20"><td className="px-4 py-3"><p className="text-xs font-bold text-slate-800">{sample.student}</p><p className="mt-0.5 text-[9px] text-slate-400">{sample.student_id}</p></td><td className="px-4 py-3"><div className="relative w-[170px]"><input type="number" min={0} max={workflow.out_of} step="0.01" disabled={!workflow.can_finalize || Boolean(submitting)} value={marks[String(sample.sample_id)] ?? ''} onChange={(event) => setMarks((current) => ({ ...current, [String(sample.sample_id)]: event.target.value }))} className="tafiti-input h-9 w-full px-3 pr-14 text-xs font-bold" placeholder="Mark" /><span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[9px] text-slate-400">/ {workflow.out_of}</span></div></td><td className="px-4 py-3"><span className={`rounded-full border px-2 py-1 text-[9px] font-bold ${state.toLowerCase().includes('match') && !state.toLowerCase().includes('mismatch') ? 'border-emerald-100 bg-emerald-50 text-emerald-700' : state.toLowerCase().includes('mismatch') ? 'border-rose-100 bg-rose-50 text-rose-700' : 'border-amber-100 bg-amber-50 text-amber-700'}`}>{state}</span></td></tr>;
          })}</tbody></table></div>

          <div className="space-y-3 p-3 md:hidden">{workflow.samples.map((sample) => {
            const state = comparisonMap.get(sample.student_id) ?? (sample.checked ? 'Reviewed' : 'Pending');
            return <article key={sample.sample_id} className="rounded-2xl border border-slate-100 bg-[#FBFCFE] p-3.5"><div className="flex items-center justify-between gap-3"><div><p className="text-xs font-bold text-slate-800">{sample.student}</p><p className="mt-0.5 text-[9px] text-slate-400">{sample.student_id}</p></div><span className="rounded-full border border-slate-200 bg-white px-2 py-1 text-[9px] font-bold text-slate-500">{state}</span></div><div className="relative mt-3"><input type="number" min={0} max={workflow.out_of} step="0.01" disabled={!workflow.can_finalize || Boolean(submitting)} value={marks[String(sample.sample_id)] ?? ''} onChange={(event) => setMarks((current) => ({ ...current, [String(sample.sample_id)]: event.target.value }))} className="tafiti-input h-10 w-full px-3 pr-14 text-sm font-bold" placeholder="Verifier mark" /><span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[10px] text-slate-400">/ {workflow.out_of}</span></div></article>;
          })}</div>
        </section>

        <aside className="space-y-4 xl:sticky xl:top-[82px] xl:self-start">
          <section className="tafiti-card p-4 sm:p-5"><div className="flex items-center gap-2"><ShieldCheck size={17} className="text-blue-600" /><h2 className="text-sm font-extrabold text-[#10224A]">Decision</h2></div><p className="mt-2 text-[10px] leading-4 text-slate-500">Approve only after every verification sample is independently re-entered. If marks differ, explain the correction before finalising.</p><label className="mt-4 block"><span className="mb-1.5 block text-[10px] font-bold text-slate-600">Correction / review note</span><textarea value={reason} onChange={(event) => setReason(event.target.value)} disabled={!workflow.can_finalize || Boolean(submitting)} rows={5} className="tafiti-input w-full px-3 py-2.5 text-xs" placeholder="Required when returning a batch or when differences are found…" /></label>{differences > 0 && <div className="mt-3 rounded-xl border border-amber-100 bg-amber-50 p-3 text-[10px] leading-4 text-amber-800"><strong>{differences} difference{differences === 1 ? '' : 's'}</strong> currently recorded. Django will require a reason before finalisation.</div>}{workflow.can_finalize ? <div className="mt-4 space-y-2"><button type="button" disabled={Boolean(submitting) || !reason.trim()} onClick={() => void submit('reject')} className="flex h-10 w-full items-center justify-center gap-2 rounded-xl border border-rose-100 bg-rose-50 px-3 text-[10px] font-extrabold text-rose-700 disabled:opacity-50">{submitting === 'reject' ? <LoaderCircle className="animate-spin" size={14} /> : <AlertCircle size={14} />} Return for correction</button><button type="button" disabled={Boolean(submitting) || completed < total} onClick={() => void submit('finalize')} className="clay-button-primary w-full">{submitting === 'finalize' ? <LoaderCircle className="animate-spin" size={14} /> : <CheckCircle2 size={14} />} Approve verification</button></div> : <div className="mt-4 rounded-xl border border-slate-100 bg-[#F8FAFD] p-3 text-[10px] leading-4 text-slate-500">This batch is read-only in your current state.</div>}</section>

          <section className="tafiti-card p-4 sm:p-5"><h3 className="text-xs font-extrabold text-[#10224A]">Verification safeguards</h3><div className="mt-3 space-y-2 text-[10px] leading-4 text-slate-500"><p>• Original teacher marks remain hidden during independent entry.</p><p>• The submitter cannot verify their own pending batch.</p><p>• Final comparison, flagging and audit records stay in Django.</p></div></section>
        </aside>
      </div>
    </section>
  );
}
