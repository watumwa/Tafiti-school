'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  ChevronRight,
  FileText,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  UserRound,
} from 'lucide-react';

import type { AttendanceCaptureWorkflow, ResultVerificationWorkflow, WorkspaceEntity } from '@/lib/workspace';
import { useToast } from '@/components/ui/ToastProvider';
import { ProfileAvatar } from './ProfileAvatar';

function statusBadge(value: string) {
  const normalized = value.toLowerCase();
  if (['active', 'verified', 'completed', 'open'].some((item) => normalized.includes(item))) return 'border-emerald-100 bg-emerald-50 text-emerald-700';
  if (['pending', 'draft', 'locked'].some((item) => normalized.includes(item))) return 'border-amber-100 bg-amber-50 text-amber-700';
  if (['flagged', 'rejected', 'inactive'].some((item) => normalized.includes(item))) return 'border-red-100 bg-red-50 text-red-700';
  return 'border-slate-200 bg-slate-50 text-slate-600';
}

function AttendancePanel({ resource, entityId, workflow, onComplete }: { resource: string; entityId: number; workflow: AttendanceCaptureWorkflow; onComplete: () => void }) {
  const toast = useToast();
  const [marks, setMarks] = useState<Record<string, { status: string; remarks: string }>>({});
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState<'save' | 'submit' | 'unlock' | ''>('');

  useEffect(() => {
    setMarks(Object.fromEntries(workflow.students.map((student) => [String(student.student_id), { status: student.status, remarks: student.remarks }])));
  }, [workflow]);

  const summary = useMemo(() => {
    const values = Object.values(marks);
    return {
      present: values.filter((item) => item.status === 'present').length,
      absent: values.filter((item) => item.status === 'absent').length,
      late: values.filter((item) => item.status === 'late').length,
      excused: values.filter((item) => item.status === 'excused').length,
    };
  }, [marks]);

  async function perform(action: 'save' | 'submit' | 'unlock') {
    setSubmitting(action);
    try {
      const response = await fetch(`/api/workspace/resources/${resource}/${entityId}/action`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action, marks, reason }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'Attendance could not be updated.');
      toast.success(action === 'submit' ? 'Attendance submitted' : action === 'unlock' ? 'Attendance reopened' : 'Attendance saved', result.detail || 'Attendance updated successfully.');
      setReason(''); onComplete();
    } catch (error: unknown) {
      toast.error('Attendance not updated', error instanceof Error ? error.message : 'Please try again.');
    } finally { setSubmitting(''); }
  }

  const options = workflow.statuses.filter((option) => ['present', 'absent', 'late', 'excused'].includes(option.value));
  return (
    <section className="tafiti-card overflow-hidden">
      <div className="grid gap-3 border-b border-slate-100 bg-[#FBFCFE] p-4 sm:grid-cols-2 xl:grid-cols-4 sm:p-5">
        {[
          ['Total students', workflow.students.length, 'bg-violet-50 text-violet-600'],
          ['Present', summary.present, 'bg-emerald-50 text-emerald-600'],
          ['Absent', summary.absent, 'bg-red-50 text-red-600'],
          ['Late / excused', summary.late + summary.excused, 'bg-amber-50 text-amber-600'],
        ].map(([label, value, cls]) => <div key={String(label)} className="rounded-xl border border-slate-100 bg-white p-3.5"><div className="flex items-center gap-3"><span className={`grid h-9 w-9 place-items-center rounded-xl ${String(cls)}`}><ShieldCheck size={16} /></span><div><p className="text-lg font-extrabold text-[#10224A]">{String(value)}</p><p className="text-[9px] font-semibold text-slate-500">{String(label)}</p></div></div></div>)}
      </div>

      {workflow.blocked_reason && !workflow.can_edit && !workflow.can_unlock ? <div className="flex gap-3 p-5 text-xs text-amber-700"><AlertCircle size={17} className="shrink-0" /><p>{workflow.blocked_reason}</p></div> : <>
        <div className="overflow-x-auto"><table className="w-full min-w-[980px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STUDENT</th>{options.map((option) => <th key={option.value} className="px-3 py-3 text-center text-[9px] font-extrabold uppercase text-slate-400">{option.label}</th>)}<th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">REMARKS</th></tr></thead><tbody className="divide-y divide-slate-100">{workflow.students.map((student) => { const key = String(student.student_id); const mark = marks[key] ?? { status: student.status, remarks: student.remarks }; return <tr key={key} className="hover:bg-blue-50/25"><td className="px-4 py-3"><div className="flex items-center gap-2.5"><span className="grid h-8 w-8 place-items-center rounded-full bg-blue-50 text-[9px] font-extrabold text-blue-700">{student.student_name.split(/\s+/).slice(0,2).map((part) => part[0]).join('').toUpperCase()}</span><div><p className="text-xs font-bold text-slate-800">{student.student_name}</p><p className="mt-0.5 text-[9px] text-slate-400">{student.display_id}</p></div></div></td>{options.map((option) => <td key={option.value} className="px-3 py-3 text-center"><input type="radio" name={`attendance-${key}`} checked={mark.status === option.value} disabled={!workflow.can_edit || Boolean(submitting)} onChange={() => setMarks((current) => ({ ...current, [key]: { ...mark, status: option.value } }))} className="h-4 w-4 accent-blue-600" aria-label={`${option.label} ${student.student_name}`} /></td>)}<td className="px-4 py-3"><input value={mark.remarks} disabled={!workflow.can_edit || Boolean(submitting)} onChange={(event) => setMarks((current) => ({ ...current, [key]: { ...mark, remarks: event.target.value } }))} placeholder="Optional" className="tafiti-input h-9 w-full px-3 text-xs" /></td></tr>; })}</tbody></table></div>
        <div className="flex flex-col gap-3 border-t border-slate-100 bg-white px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5"><div className="flex flex-wrap gap-3 text-[10px] font-bold"><span className="text-emerald-600">{summary.present} present</span><span className="text-red-600">{summary.absent} absent</span><span className="text-amber-600">{summary.late} late</span><span className="text-blue-600">{summary.excused} excused</span></div><div className="flex flex-wrap gap-2">{workflow.can_unlock && <><input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Reason for reopening" className="tafiti-input h-9 min-w-[190px] px-3 text-xs" /><button type="button" disabled={!reason.trim() || Boolean(submitting)} onClick={() => void perform('unlock')} className="clay-button-secondary">{submitting === 'unlock' ? <LoaderCircle className="animate-spin" size={14} /> : <RefreshCw size={14} />} Reopen</button></>}{workflow.can_edit && <><button type="button" disabled={Boolean(submitting)} onClick={() => void perform('save')} className="clay-button-secondary">Save draft</button><button type="button" disabled={Boolean(submitting) || !workflow.students.length} onClick={() => void perform('submit')} className="clay-button-primary">{submitting === 'submit' ? <LoaderCircle className="animate-spin" size={14} /> : <CheckCircle2 size={14} />} Submit attendance</button></>}</div></div>
      </>}
    </section>
  );
}

function VerificationPanel({ resource, entityId, workflow, onComplete }: { resource: string; entityId: number; workflow: ResultVerificationWorkflow; onComplete: () => void }) {
  const router = useRouter();
  const toast = useToast();
  const [marks, setMarks] = useState<Record<string, string>>(() => Object.fromEntries(workflow.samples.map((sample) => [String(sample.sample_id), sample.value])));
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState<'finalize' | 'reject' | ''>('');

  useEffect(() => { setMarks(Object.fromEntries(workflow.samples.map((sample) => [String(sample.sample_id), sample.value]))); setReason(''); }, [workflow]);
  async function submit(action: 'finalize' | 'reject') {
    setSubmitting(action);
    try {
      const response = await fetch(`/api/workspace/resources/${resource}/${entityId}/action`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action, marks, rejection_reason: reason }) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'Verification could not be completed.');
      toast.success(result.status === 'VERIFIED' ? 'Batch verified' : 'Returned for correction', result.detail || 'Decision saved.');
      if (result.next_href) router.push(result.next_href); else onComplete();
    } catch (error: unknown) { toast.error('Verification not completed', error instanceof Error ? error.message : 'Please try again.'); }
    finally { setSubmitting(''); }
  }

  return <section className="tafiti-card overflow-hidden"><div className="flex flex-col gap-3 border-b border-slate-100 bg-[#FBFCFE] px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5"><div><h2 className="text-sm font-extrabold text-[#10224A]">Independent mark verification</h2><p className="mt-1 text-[10px] text-slate-500">Re-enter sampled marks. Original teacher marks remain hidden during the check.</p></div><span className="rounded-full border border-blue-100 bg-blue-50 px-3 py-1.5 text-[10px] font-bold text-blue-700">Out of {workflow.out_of}</span></div>{!workflow.can_finalize ? <div className="flex gap-3 p-5 text-xs text-amber-700"><AlertCircle size={17} />{workflow.blocked_reason || 'This batch cannot be changed.'}</div> : <div className="p-4 sm:p-5"><div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{workflow.samples.map((sample) => <label key={sample.sample_id} className="rounded-xl border border-slate-100 bg-[#F8FAFD] p-3.5"><span className="block text-xs font-bold text-slate-800">{sample.student}</span><span className="mt-0.5 block text-[9px] text-slate-400">{sample.student_id}</span><span className="relative mt-3 block"><input type="number" min={0} max={workflow.out_of} step="0.01" value={marks[String(sample.sample_id)] ?? ''} onChange={(event) => setMarks((current) => ({ ...current, [String(sample.sample_id)]: event.target.value }))} className="tafiti-input h-10 w-full px-3 pr-14 text-sm font-bold" placeholder="Mark" /><span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[10px] text-slate-400">/ {workflow.out_of}</span></span></label>)}</div><label className="mt-4 block"><span className="mb-1.5 block text-[10px] font-bold text-slate-600">Correction reason</span><textarea value={reason} onChange={(event) => setReason(event.target.value)} rows={3} className="tafiti-input w-full px-3 py-2.5 text-xs" placeholder="Explain discrepancies or corrections…" /></label><div className="mt-4 flex flex-wrap justify-end gap-2"><button type="button" disabled={Boolean(submitting)} onClick={() => void submit('reject')} className="inline-flex h-9 items-center gap-2 rounded-lg border border-red-100 bg-red-50 px-3 text-[10px] font-bold text-red-700">{submitting === 'reject' ? <LoaderCircle className="animate-spin" size={14} /> : <AlertCircle size={14} />} Return for correction</button><button type="button" disabled={Boolean(submitting)} onClick={() => void submit('finalize')} className="clay-button-primary">{submitting === 'finalize' ? <LoaderCircle className="animate-spin" size={14} /> : <CheckCircle2 size={14} />} Approve verification</button></div></div>}</section>;
}

function GenericTab({ entity, activeKey }: { entity: WorkspaceEntity; activeKey: string }) {
  const tab = entity.tabs.find((item) => item.key === activeKey) ?? entity.tabs[0];
  if (!tab) return null;
  return <section className="tafiti-card mt-4 overflow-hidden"><div className="border-b border-slate-100 px-4 py-3.5"><h2 className="text-sm font-extrabold text-[#10224A]">{tab.label}</h2><p className="mt-1 text-[10px] text-slate-500">{tab.description}</p></div>{tab.rows.length ? <div className="overflow-x-auto"><table className="w-full min-w-[680px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]">{tab.columns.map((column) => <th key={column.key} className="px-4 py-3 text-[9px] font-extrabold text-slate-400">{column.label}</th>)}</tr></thead><tbody className="divide-y divide-slate-100">{tab.rows.map((row, index) => <tr key={String(row.id ?? index)}>{tab.columns.map((column) => <td key={column.key} className="px-4 py-3 text-xs text-slate-600">{String(row[column.key] ?? '—')}</td>)}</tr>)}</tbody></table></div> : <div className="px-5 py-10 text-center text-xs text-slate-400">{tab.empty_title}</div>}</section>;
}

export function EntityWorkspace({ resource, id, dashboardPath, onTitleChange }: { resource: string; id: number; dashboardPath: string; onTitleChange?: (title: string) => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [data, setData] = useState<WorkspaceEntity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  const requestQuery = searchParams.toString();
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    fetch(`/api/workspace/resources/${resource}/${id}${requestQuery ? `?${requestQuery}` : ''}`, { cache: 'no-store', signal: controller.signal })
      .then(async (response) => { const result = await response.json(); if (!response.ok) throw new Error(result.detail || 'This workspace could not be opened.'); return result as WorkspaceEntity; })
      .then((result) => { setData(result); onTitleChange?.(result.title); })
      .catch((reason: unknown) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'This workspace could not be opened.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [id, onTitleChange, reloadKey, requestQuery, resource]);

  const returnPath = useMemo(() => { const value = searchParams.get('return'); return value?.startsWith(`${dashboardPath}/`) ? value : `${dashboardPath}/${resource}`; }, [dashboardPath, resource, searchParams]);
  const activeTab = searchParams.get('tab') || data?.tabs[0]?.key || '';
  function selectTab(tab: string) { const params = new URLSearchParams(searchParams.toString()); params.set('tab', tab); router.replace(`${pathname}?${params.toString()}`, { scroll: false }); }

  if (loading && !data) return <div className="tafiti-card grid min-h-[430px] place-items-center"><LoaderCircle className="animate-spin text-blue-600" /></div>;
  if (error && !data) return <div className="tafiti-card grid min-h-[430px] place-items-center p-6 text-center"><div><AlertCircle className="mx-auto text-red-500" /><p className="mt-3 text-sm font-bold text-slate-800">Unable to open workflow</p><p className="mt-1 text-xs text-slate-400">{error}</p></div></div>;
  if (!data) return null;

  return <section><Link href={returnPath} className="mb-3 inline-flex items-center gap-1.5 text-[10px] font-bold text-slate-500 hover:text-blue-600"><ArrowLeft size={13} /> Back</Link><section className="tafiti-card mb-4 overflow-hidden"><div className="flex flex-col gap-4 px-5 py-5 sm:flex-row sm:items-center sm:justify-between"><div className="flex items-center gap-3"><ProfileAvatar src={data.photo} name={data.title} size="lg" /><div><div className="flex flex-wrap items-center gap-2"><h1 className="text-xl font-extrabold tracking-[-.03em] text-[#10224A]">{data.title}</h1><span className={`rounded-full border px-2 py-1 text-[9px] font-bold ${statusBadge(data.status)}`}>{data.status}</span></div><p className="mt-1 text-xs font-bold text-blue-700">{data.subtitle}</p><div className="mt-2 flex flex-wrap gap-3">{data.metadata.map((item) => <span key={item.label} className="text-[9px] text-slate-400"><b className="text-slate-500">{item.label}</b> · {item.value}</span>)}</div></div></div><span className="grid h-10 w-10 place-items-center rounded-xl bg-blue-50 text-blue-600">{data.workflow?.kind === 'attendance_capture' ? <ShieldCheck size={18} /> : <FileText size={18} />}</span></div>{data.tabs.length > 0 && <div className="border-t border-slate-100 bg-[#FBFCFE] px-3"><div className="flex min-w-max gap-1 overflow-x-auto">{data.tabs.map((tab) => <button key={tab.key} onClick={() => selectTab(tab.key)} className={`relative h-10 px-3 text-[10px] font-bold ${activeTab === tab.key ? 'text-blue-700' : 'text-slate-500'}`}>{tab.label}{activeTab === tab.key && <span className="absolute inset-x-2 bottom-0 h-0.5 bg-blue-600" />}</button>)}</div></div>}</section>{data.workflow?.kind === 'attendance_capture' ? <AttendancePanel resource={resource} entityId={id} workflow={data.workflow} onComplete={() => setReloadKey((value) => value + 1)} /> : data.workflow?.kind === 'result_verification' ? <VerificationPanel resource={resource} entityId={id} workflow={data.workflow} onComplete={() => setReloadKey((value) => value + 1)} /> : <GenericTab entity={data} activeKey={activeTab} />}</section>;
}
