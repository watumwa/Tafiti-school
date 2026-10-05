'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CalendarCheck,
  ChartNoAxesColumn,
  CheckCircle2,
  ChevronRight,
  CircleDollarSign,
  Clock3,
  FileText,
  LoaderCircle,
  MessageSquare,
  Pencil,
  RefreshCw,
  School,
  ShieldCheck,
  UserRound,
  Users,
  WalletCards,
} from 'lucide-react';

import type {
  AttendanceCaptureWorkflow,
  ResultVerificationWorkflow,
  WorkspaceEntity,
  WorkspaceEntityAction,
  WorkspaceEntityMetric,
  WorkspaceFormSchema,
} from '@/lib/workspace';
import { useToast } from '@/components/ui/ToastProvider';
import { ProfileAvatar } from './ProfileAvatar';
import { ResourceFormDialog } from './ResourceFormDialog';

const metricTone: Record<WorkspaceEntityMetric['tone'], string> = {
  green: 'border-emerald-200/80 bg-emerald-50/65 text-emerald-950',
  blue: 'border-blue-200/80 bg-blue-50/65 text-blue-950',
  gold: 'border-amber-200/80 bg-amber-50/70 text-amber-950',
  violet: 'border-violet-200/80 bg-violet-50/65 text-violet-950',
};

const actionIcons = {
  edit: Pencil,
  chart: ChartNoAxesColumn,
  result: ChartNoAxesColumn,
  wallet: WalletCards,
  attendance: CalendarCheck,
  message: MessageSquare,
  subject: BookOpen,
  class: School,
  student: Users,
  user: UserRound,
  history: Clock3,
  report: FileText,
  queue: ShieldCheck,
  next: ArrowRight,
} as const;

function display(value: unknown) {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return String(value);
}

function statusClass(status: string) {
  const normalized = status.toLowerCase();
  if (['active', 'verified', 'settled', 'accepted', 'enrolled', 'current', 'completed'].some((item) => normalized.includes(item))) {
    return 'border-emerald-300/30 bg-emerald-400/15 text-emerald-100';
  }
  if (['pending', 'outstanding', 'draft', 'review'].some((item) => normalized.includes(item))) {
    return 'border-amber-300/30 bg-amber-400/15 text-amber-100';
  }
  if (['inactive', 'retired', 'flagged', 'rejected'].some((item) => normalized.includes(item))) {
    return 'border-red-300/30 bg-red-400/15 text-red-100';
  }
  return 'border-slate-300/25 bg-white/10 text-slate-200';
}

function cellStatusClass(value: string) {
  const normalized = value.toLowerCase();
  if (['active', 'verified', 'settled', 'matched', 'recorded', 'allowed', 'completed'].some((item) => normalized.includes(item))) {
    return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  }
  if (['pending', 'open', 'draft', 'outstanding', 'progress'].some((item) => normalized.includes(item))) {
    return 'border-amber-200 bg-amber-50 text-amber-800';
  }
  if (['inactive', 'retired', 'flagged', 'mismatch', 'rejected', 'blocked'].some((item) => normalized.includes(item))) {
    return 'border-red-200 bg-red-50 text-red-700';
  }
  return 'border-slate-200 bg-slate-50 text-slate-600';
}

function actionIcon(action: WorkspaceEntityAction) {
  const Icon = actionIcons[action.icon as keyof typeof actionIcons] ?? ChevronRight;
  return <Icon size={15} aria-hidden="true" />;
}

function ContextTable({ entity }: { entity: WorkspaceEntity }) {
  const searchParams = useSearchParams();
  const activeKey = searchParams.get('tab') || entity.tabs[0]?.key || '';
  const activeTab = entity.tabs.find((tab) => tab.key === activeKey) ?? entity.tabs[0];
  if (!activeTab) return null;

  if (!activeTab.rows.length) {
    return (
      <div className="grid min-h-[280px] place-items-center px-5 py-10 text-center">
        <div className="max-w-sm">
          <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-[#E9EEF7] text-[#3157D5]"><FileText size={21} /></span>
          <h3 className="mt-4 text-base font-semibold text-slate-900">{activeTab.empty_title}</h3>
          <p className="mt-2 text-sm leading-6 text-slate-500">{activeTab.description}</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="border-b border-slate-100 px-5 py-4 sm:px-6">
        <h2 className="text-base font-semibold text-slate-950">{activeTab.label}</h2>
        <p className="mt-1 text-xs leading-5 text-slate-500">{activeTab.description}</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] border-collapse text-left">
          <thead>
            <tr className="border-b border-slate-200 bg-[#F5F7FB]">
              {activeTab.columns.map((column) => (
                <th key={column.key} className="whitespace-nowrap px-5 py-3 text-[10px] font-bold uppercase tracking-[0.09em] text-slate-500">{column.label}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {activeTab.rows.map((row, index) => {
              const links = (row._links ?? {}) as Record<string, string>;
              return (
                <tr key={String(row.id ?? row.student_id ?? row.reference ?? index)} className="transition hover:bg-slate-50/75">
                  {activeTab.columns.map((column) => {
                    const text = display(row[column.key]);
                    const isStatus = ['status', 'comparison'].includes(column.key);
                    const cell = isStatus ? (
                      <span className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold ${cellStatusClass(text)}`}>{text}</span>
                    ) : (
                      <span className={['student', 'teacher', 'subject', 'class', 'bill', 'batch', 'field'].includes(column.key) ? 'font-semibold text-slate-900' : ''}>{text}</span>
                    );
                    return (
                      <td key={column.key} className="max-w-[360px] px-5 py-3.5 text-sm text-slate-650">
                        {links[column.key] ? <Link href={links[column.key]} className="inline-flex items-center gap-1.5 text-[#244BB9] hover:text-[#173A99] hover:underline">{cell}<ChevronRight size={13} /></Link> : cell}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function VerificationPanel({
  resource,
  entityId,
  workflow,
  onComplete,
}: {
  resource: string;
  entityId: number;
  workflow: ResultVerificationWorkflow;
  onComplete: () => void;
}) {
  const router = useRouter();
  const toast = useToast();
  const [marks, setMarks] = useState<Record<string, string>>(() => Object.fromEntries(workflow.samples.map((sample) => [String(sample.sample_id), sample.value])));
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState<'finalize' | 'reject' | ''>('');

  useEffect(() => {
    setMarks(Object.fromEntries(workflow.samples.map((sample) => [String(sample.sample_id), sample.value])));
    setReason('');
  }, [workflow]);

  async function submit(action: 'finalize' | 'reject') {
    setSubmitting(action);
    try {
      const response = await fetch(`/api/workspace/resources/${resource}/${entityId}/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, marks, rejection_reason: reason }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'The verification decision could not be saved.');
      toast.success(result.status === 'VERIFIED' ? 'Batch verified' : 'Batch sent for correction', result.detail);
      if (result.next_href) router.push(result.next_href);
      else onComplete();
    } catch (reasonValue: unknown) {
      toast.error('Verification not completed', reasonValue instanceof Error ? reasonValue.message : 'The verification decision could not be saved.');
    } finally {
      setSubmitting('');
    }
  }

  return (
    <section className="mb-5 overflow-hidden rounded-[22px] border border-blue-200/70 bg-white shadow-[0_10px_32px_rgba(49,87,213,.08)]">
      <div className="flex flex-col gap-3 border-b border-blue-100 bg-blue-50/65 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#3157D5]">Independent verification</p>
          <h2 className="mt-1 text-base font-semibold text-slate-950">Re-enter the sampled marks</h2>
          <p className="mt-1 text-xs leading-5 text-slate-500">Teacher marks remain hidden here to protect the independence of the check.</p>
        </div>
        <span className="inline-flex self-start rounded-full border border-blue-200 bg-white px-3 py-1.5 text-xs font-semibold text-blue-700">Out of {workflow.out_of}</span>
      </div>

      {!workflow.can_finalize ? (
        <div className="flex gap-3 px-5 py-5 text-sm text-amber-800 sm:px-6">
          <AlertCircle className="mt-0.5 shrink-0" size={18} />
          <p>{workflow.blocked_reason || 'This batch cannot be changed.'}</p>
        </div>
      ) : (
        <div className="p-5 sm:p-6">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {workflow.samples.map((sample) => (
              <label key={sample.sample_id} className="rounded-2xl border border-slate-200 bg-slate-50/60 p-3.5">
                <span className="block truncate text-sm font-semibold text-slate-900">{sample.student}</span>
                <span className="mt-0.5 block text-[11px] text-slate-500">{sample.student_id}</span>
                <span className="relative mt-3 block">
                  <input
                    type="number"
                    min={0}
                    max={workflow.out_of}
                    step="0.01"
                    value={marks[String(sample.sample_id)] ?? ''}
                    onChange={(event) => setMarks((current) => ({ ...current, [String(sample.sample_id)]: event.target.value }))}
                    className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 pr-16 text-sm font-semibold text-slate-900 outline-none transition focus:border-[#3157D5] focus:ring-4 focus:ring-[#3157D5]/10"
                    placeholder="Mark"
                  />
                  <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs font-medium text-slate-400">/ {workflow.out_of}</span>
                </span>
              </label>
            ))}
          </div>
          <label className="mt-4 block">
            <span className="mb-1.5 block text-xs font-semibold text-slate-700">Correction reason <span className="font-normal text-slate-400">(required when marks differ or you flag the batch)</span></span>
            <textarea value={reason} onChange={(event) => setReason(event.target.value)} rows={3} placeholder="Explain what needs correction…" className="w-full rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm outline-none transition focus:border-[#3157D5] focus:ring-4 focus:ring-[#3157D5]/10" />
          </label>
          <div className="mt-4 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button type="button" disabled={Boolean(submitting)} onClick={() => void submit('reject')} className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-red-200 bg-red-50 px-4 text-xs font-bold text-red-700 transition hover:bg-red-100 disabled:opacity-50">
              {submitting === 'reject' ? <LoaderCircle size={15} className="animate-spin" /> : <AlertCircle size={15} />} Flag for correction
            </button>
            <button type="button" disabled={Boolean(submitting)} onClick={() => void submit('finalize')} className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#3157D5] px-4 text-xs font-bold text-white shadow-[0_8px_18px_rgba(49,87,213,.2)] transition hover:bg-[#294CC0] disabled:opacity-50">
              {submitting === 'finalize' ? <LoaderCircle size={15} className="animate-spin" /> : <CheckCircle2 size={15} />} Complete verification
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

function AttendanceCapturePanel({
  resource,
  entityId,
  workflow,
  onComplete,
}: {
  resource: string;
  entityId: number;
  workflow: AttendanceCaptureWorkflow;
  onComplete: () => void;
}) {
  const toast = useToast();
  const [marks, setMarks] = useState<Record<string, { status: string; remarks: string }>>({});
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState<'save' | 'submit' | 'unlock' | ''>('');

  useEffect(() => {
    setMarks(Object.fromEntries(workflow.students.map((student) => [
      String(student.student_id),
      { status: student.status, remarks: student.remarks },
    ])));
  }, [workflow]);

  async function perform(action: 'save' | 'submit' | 'unlock') {
    setSubmitting(action);
    try {
      const response = await fetch(`/api/workspace/resources/${resource}/${entityId}/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action,
          marks,
          reason,
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'The attendance action could not be completed.');
      toast.success(action === 'submit' ? 'Attendance submitted' : action === 'unlock' ? 'Session reopened' : 'Attendance saved', result.detail);
      setReason('');
      onComplete();
    } catch (reasonValue: unknown) {
      toast.error('Attendance not updated', reasonValue instanceof Error ? reasonValue.message : 'The attendance action could not be completed.');
    } finally {
      setSubmitting('');
    }
  }

  const editable = workflow.can_edit;
  const busy = submitting !== '';

  return (
    <section className="mt-5 overflow-hidden rounded-[22px] border border-blue-200/70 bg-white shadow-[0_10px_32px_rgba(49,87,213,.08)]">
      <div className="flex flex-col gap-3 border-b border-blue-100 bg-blue-50/65 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#3157D5]">Roll call</p>
          <h2 className="mt-1 text-base font-semibold text-slate-950">Mark student attendance</h2>
          <p className="mt-1 text-xs leading-5 text-slate-500">Choose a status for every student. Submitting locks the session and records the action.</p>
        </div>
        <span className={`inline-flex self-start rounded-full border px-3 py-1.5 text-xs font-semibold ${workflow.locked ? 'border-amber-200 bg-amber-50 text-amber-800' : 'border-emerald-200 bg-emerald-50 text-emerald-700'}`}>
          {workflow.locked ? 'Locked' : 'Open'}
        </span>
      </div>

      {workflow.blocked_reason && !editable && !workflow.can_unlock ? (
        <div className="flex gap-3 px-5 py-5 text-sm text-amber-800 sm:px-6">
          <AlertCircle className="mt-0.5 shrink-0" size={18} />
          <p>{workflow.blocked_reason}</p>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] border-collapse text-left">
              <thead>
                <tr className="border-b border-slate-200 bg-[#F5F7FB]">
                  <th className="px-5 py-3 text-[10px] font-bold uppercase tracking-[0.09em] text-slate-500">Student</th>
                  <th className="px-5 py-3 text-[10px] font-bold uppercase tracking-[0.09em] text-slate-500">Attendance</th>
                  <th className="px-5 py-3 text-[10px] font-bold uppercase tracking-[0.09em] text-slate-500">Remarks</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {workflow.students.map((student) => {
                  const key = String(student.student_id);
                  const mark = marks[key] ?? { status: student.status, remarks: student.remarks };
                  return (
                    <tr key={key} className="hover:bg-slate-50/75">
                      <td className="px-5 py-3">
                        <span className="block text-sm font-semibold text-slate-900">{student.student_name}</span>
                        <span className="mt-0.5 block text-[11px] text-slate-500">{student.display_id}</span>
                      </td>
                      <td className="px-5 py-3">
                        <select
                          aria-label={`Attendance for ${student.student_name}`}
                          value={mark.status}
                          disabled={!editable || busy}
                          onChange={(event) => setMarks((current) => ({ ...current, [key]: { ...mark, status: event.target.value } }))}
                          className="h-10 min-w-36 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-[#3157D5] focus:ring-4 focus:ring-[#3157D5]/10 disabled:bg-slate-100"
                        >
                          {workflow.statuses.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                        </select>
                      </td>
                      <td className="px-5 py-3">
                        <input
                          aria-label={`Remarks for ${student.student_name}`}
                          value={mark.remarks}
                          maxLength={255}
                          disabled={!editable || busy}
                          onChange={(event) => setMarks((current) => ({ ...current, [key]: { ...mark, remarks: event.target.value } }))}
                          placeholder="Optional"
                          className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-[#3157D5] focus:ring-4 focus:ring-[#3157D5]/10 disabled:bg-slate-100"
                        />
                      </td>
                    </tr>
                  );
                })}
                {!workflow.students.length && (
                  <tr><td colSpan={3} className="px-5 py-10 text-center text-sm text-slate-500">No students are registered in this class stream.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="flex flex-col gap-3 border-t border-slate-100 px-5 py-4 sm:flex-row sm:items-end sm:justify-between sm:px-6">
            <p className="text-xs text-slate-500">{workflow.students.length} student{workflow.students.length === 1 ? '' : 's'} · Changes are recorded in the attendance audit log.</p>
            <div className="flex flex-col gap-2 sm:flex-row">
              {workflow.can_unlock && (
                <>
                  <input
                    value={reason}
                    maxLength={255}
                    onChange={(event) => setReason(event.target.value)}
                    placeholder="Reason for reopening"
                    aria-label="Reason for reopening attendance session"
                    className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:border-[#3157D5] focus:ring-4 focus:ring-[#3157D5]/10"
                  />
                  <button type="button" disabled={busy || !reason.trim()} onClick={() => void perform('unlock')} className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 text-xs font-bold text-amber-800 hover:bg-amber-100 disabled:opacity-50">
                    {submitting === 'unlock' ? <LoaderCircle size={15} className="animate-spin" /> : <RefreshCw size={15} />} Reopen session
                  </button>
                </>
              )}
              {editable && (
                <>
                  <button type="button" disabled={busy} onClick={() => void perform('save')} className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-50">
                    {submitting === 'save' ? <LoaderCircle size={15} className="animate-spin" /> : <RefreshCw size={15} />} Save draft
                  </button>
                  <button type="button" disabled={busy || workflow.students.length === 0} onClick={() => void perform('submit')} className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#3157D5] px-4 text-xs font-bold text-white shadow-[0_8px_18px_rgba(49,87,213,.2)] hover:bg-[#294CC0] disabled:opacity-50">
                    {submitting === 'submit' ? <LoaderCircle size={15} className="animate-spin" /> : <CheckCircle2 size={15} />} Submit attendance
                  </button>
                </>
              )}
            </div>
          </div>
        </>
      )}
    </section>
  );
}

export function EntityWorkspace({
  resource,
  id,
  dashboardPath,
  onTitleChange,
}: {
  resource: string;
  id: number;
  dashboardPath: string;
  onTitleChange?: (title: string) => void;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  const [data, setData] = useState<WorkspaceEntity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);
  const [formOpen, setFormOpen] = useState(false);
  const [formSchema, setFormSchema] = useState<WorkspaceFormSchema | null>(null);
  const [formLoading, setFormLoading] = useState(false);
  const [formErrors, setFormErrors] = useState<Record<string, string[]>>({});

  const requestQuery = searchParams.toString();
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetch(`/api/workspace/resources/${resource}/${id}${requestQuery ? `?${requestQuery}` : ''}`, { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || 'This contextual workspace could not be opened.');
        return result as WorkspaceEntity;
      })
      .then((result) => {
        setData(result);
        onTitleChange?.(result.title);
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setError(reason instanceof Error ? reason.message : 'This contextual workspace could not be opened.');
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [id, onTitleChange, reloadKey, requestQuery, resource]);

  const activeTab = searchParams.get('tab') || data?.tabs[0]?.key || '';
  const returnPath = useMemo(() => {
    const value = searchParams.get('return');
    return value?.startsWith(`${dashboardPath}/`) ? value : `${dashboardPath}/${resource}`;
  }, [dashboardPath, resource, searchParams]);

  function selectTab(tab: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set('tab', tab);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }

  async function openEditForm() {
    setFormOpen(true);
    setFormSchema(null);
    setFormErrors({});
    setFormLoading(true);
    try {
      const response = await fetch(`/api/workspace/resources/${resource}/${id}/form`, { cache: 'no-store' });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'The edit form could not be opened.');
      setFormSchema(result as WorkspaceFormSchema);
    } catch (reason: unknown) {
      toast.error('Could not open form', reason instanceof Error ? reason.message : 'The edit form could not be opened.');
      setFormOpen(false);
    } finally {
      setFormLoading(false);
    }
  }

  async function submitForm(values: Record<string, unknown>) {
    if (!formSchema) return;
    setFormLoading(true);
    setFormErrors({});
    try {
      const hasFile = Object.values(values).some((value) => value instanceof File);
      let body: BodyInit;
      let headers: HeadersInit | undefined;
      if (hasFile) {
        const formData = new FormData();
        for (const [key, value] of Object.entries(values)) {
          if (value instanceof File) formData.append(key, value);
          else if (Array.isArray(value)) value.forEach((item) => formData.append(key, String(item)));
          else if (typeof value === 'boolean') formData.append(key, value ? 'true' : 'false');
          else if (value !== null && value !== undefined) formData.append(key, String(value));
        }
        body = formData;
      } else {
        headers = { 'Content-Type': 'application/json' };
        body = JSON.stringify(values);
      }
      const response = await fetch(`/api/workspace/resources/${resource}/${id}/form`, { method: 'PATCH', headers, body });
      const result = await response.json();
      if (!response.ok) {
        setFormErrors((result.errors as Record<string, string[]>) ?? {});
        throw new Error(result.detail || 'The record could not be saved.');
      }
      toast.success('Changes saved', result.detail);
      setFormOpen(false);
      setReloadKey((value) => value + 1);
    } catch (reason: unknown) {
      toast.error('Could not save changes', reason instanceof Error ? reason.message : 'The record could not be saved.');
    } finally {
      setFormLoading(false);
    }
  }

  if (loading && !data) {
    return <div className="clay-panel grid min-h-[440px] place-items-center"><div className="text-center text-sm font-medium text-slate-500"><LoaderCircle className="mx-auto mb-3 animate-spin text-[#3157D5]" size={25} />Opening contextual workspace…</div></div>;
  }

  if (error && !data) {
    return (
      <div className="clay-panel grid min-h-[440px] place-items-center px-5 text-center">
        <div className="max-w-sm"><AlertCircle className="mx-auto text-red-600" size={28} /><h2 className="mt-4 text-base font-semibold text-slate-900">We couldn’t open this workspace</h2><p className="mt-2 text-sm leading-6 text-slate-500">{error}</p><button type="button" onClick={() => setReloadKey((value) => value + 1)} className="clay-button-primary mt-5"><RefreshCw size={15} /> Try again</button></div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <section>
      <Link href={returnPath} className="mb-4 inline-flex items-center gap-2 text-xs font-semibold text-slate-500 transition hover:text-[#3157D5]"><ArrowLeft size={15} /> Back to {resource === 'fees' ? 'fee accounts' : resource}</Link>

      <div className="relative overflow-hidden rounded-[26px] bg-[#0B1739] px-5 py-6 text-white shadow-[0_18px_55px_rgba(11,23,57,.18)] sm:px-7 lg:px-8">
        <div className="absolute -right-12 -top-20 h-64 w-64 rounded-full border border-white/10" aria-hidden="true" />
        <div className="absolute -bottom-24 right-28 h-48 w-48 rounded-full bg-[#3157D5]/20 blur-3xl" aria-hidden="true" />
        <div className="relative flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
          <div className="flex min-w-0 flex-col gap-4 sm:flex-row sm:items-center">
            <ProfileAvatar src={data.photo} name={data.title} size="xl" className="border-white/20 bg-white/10 text-white" />
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-blue-200">{data.eyebrow}</p>
                <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-bold ${statusClass(data.status)}`}>{data.status}</span>
              </div>
              <h1 className="mt-2 truncate text-2xl font-semibold tracking-[-0.025em] sm:text-[2rem]">{data.title}</h1>
              <p className="mt-1 text-sm font-medium text-slate-300">{data.subtitle}</p>
              <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2">
                {data.metadata.map((item) => (
                  <span key={item.label} className="text-xs text-slate-300"><span className="text-slate-500">{item.label}</span> · {item.href ? <Link href={item.href} className="font-semibold text-white hover:underline">{item.value}</Link> : <span className="font-semibold text-white">{item.value}</span>}</span>
                ))}
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {data.actions.map((action) => action.action === 'edit' ? (
              <button key={action.label} type="button" onClick={() => void openEditForm()} className={action.primary ? 'inline-flex h-10 items-center gap-2 rounded-xl bg-[#3157D5] px-4 text-xs font-bold text-white shadow-lg hover:bg-[#294CC0]' : 'inline-flex h-10 items-center gap-2 rounded-xl border border-white/15 bg-white/[0.07] px-4 text-xs font-bold text-white hover:bg-white/[0.12]'}>{actionIcon(action)} {action.label}</button>
            ) : action.href ? (
              <Link key={action.label} href={action.href} className={action.primary ? 'inline-flex h-10 items-center gap-2 rounded-xl bg-[#3157D5] px-4 text-xs font-bold text-white shadow-lg hover:bg-[#294CC0]' : 'inline-flex h-10 items-center gap-2 rounded-xl border border-white/15 bg-white/[0.07] px-4 text-xs font-bold text-white hover:bg-white/[0.12]'}>{actionIcon(action)} {action.label}</Link>
            ) : null)}
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {data.metrics.map((metric) => (
          <article key={metric.label} className={`rounded-2xl border p-4 ${metricTone[metric.tone]}`}>
            <p className="text-[11px] font-semibold text-slate-500">{metric.label}</p>
            <p className="mt-2 text-xl font-semibold tracking-[-0.02em]">{metric.value}</p>
            <p className="mt-1.5 text-[11px] text-slate-500">{metric.hint}</p>
          </article>
        ))}
      </div>

      {data.workflow?.kind === 'result_verification' && (
        <div className="mt-5">
          <VerificationPanel resource={resource} entityId={id} workflow={data.workflow} onComplete={() => setReloadKey((value) => value + 1)} />
        </div>
      )}

      {data.workflow?.kind === 'attendance_capture' && (
        <AttendanceCapturePanel resource={resource} entityId={id} workflow={data.workflow} onComplete={() => setReloadKey((value) => value + 1)} />
      )}

      <div className="mt-5 overflow-hidden rounded-[22px] border border-slate-200 bg-white shadow-[0_10px_30px_rgba(15,23,42,.045)]">
        <div className="overflow-x-auto border-b border-slate-200 bg-[#F8FAFD] px-3 pt-3">
          <div className="flex min-w-max gap-1">
            {data.tabs.map((tab) => (
              <button key={tab.key} type="button" onClick={() => selectTab(tab.key)} className={`relative inline-flex h-11 items-center gap-2 rounded-t-xl px-3.5 text-xs font-semibold transition ${activeTab === tab.key ? 'bg-white text-[#3157D5] shadow-[0_-3px_12px_rgba(15,23,42,.035)]' : 'text-slate-500 hover:bg-white/60 hover:text-slate-800'}`}>
                {tab.label}
                <span className={`rounded-full px-1.5 py-0.5 text-[9px] ${activeTab === tab.key ? 'bg-blue-50 text-blue-700' : 'bg-slate-200/70 text-slate-500'}`}>{tab.count}</span>
                {activeTab === tab.key && <span className="absolute inset-x-3 bottom-0 h-0.5 rounded-full bg-[#3157D5]" />}
              </button>
            ))}
          </div>
        </div>
        <ContextTable entity={data} />
      </div>

      <ResourceFormDialog open={formOpen} schema={formSchema} loading={formLoading} errors={formErrors} onClose={() => { setFormOpen(false); setFormErrors({}); }} onSubmit={submitForm} />
    </section>
  );
}
