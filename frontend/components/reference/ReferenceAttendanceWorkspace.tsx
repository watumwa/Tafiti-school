'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import {
  AlertCircle,
  ArrowLeft,
  CalendarCheck,
  CheckCircle2,
  Clock3,
  LoaderCircle,
  LockKeyhole,
  RefreshCw,
  RotateCcw,
  Save,
  ShieldCheck,
  Users,
} from 'lucide-react';

import type { AttendanceCaptureWorkflow, WorkspaceEntity } from '@/lib/workspace';
import { useToast } from '@/components/ui/ToastProvider';

const STATUS_META: Record<string, { active: string; dot: string }> = {
  present: { active: 'border-emerald-200 bg-emerald-50 text-emerald-700', dot: 'bg-emerald-500' },
  absent: { active: 'border-rose-200 bg-rose-50 text-rose-700', dot: 'bg-rose-500' },
  late: { active: 'border-amber-200 bg-amber-50 text-amber-700', dot: 'bg-amber-500' },
  excused: { active: 'border-blue-200 bg-blue-50 text-blue-700', dot: 'bg-blue-500' },
};

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase();
}

function metricCard(label: string, value: number, className: string, icon: React.ReactNode) {
  return (
    <article className="tafiti-kpi">
      <div className="flex items-center gap-3">
        <span className={`grid h-10 w-10 place-items-center rounded-xl ${className}`}>{icon}</span>
        <div><p className="text-xl font-extrabold text-[#10224A]">{value}</p><p className="text-[9px] font-semibold text-slate-500">{label}</p></div>
      </div>
    </article>
  );
}

export function ReferenceAttendanceWorkspace({ id, dashboardPath, onTitleChange }: { id: number; dashboardPath: string; onTitleChange?: (title: string) => void }) {
  const toast = useToast();
  const searchParams = useSearchParams();
  const [data, setData] = useState<WorkspaceEntity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);
  const [marks, setMarks] = useState<Record<string, { status: string; remarks: string }>>({});
  const [reopenReason, setReopenReason] = useState('');
  const [submitting, setSubmitting] = useState<'save' | 'submit' | 'unlock' | ''>('');

  const returnPath = searchParams.get('return')?.startsWith(`${dashboardPath}/`) ? String(searchParams.get('return')) : `${dashboardPath}/attendance`;

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    fetch(`/api/workspace/resources/attendance/${id}`, { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Attendance session could not be loaded.');
        return payload as WorkspaceEntity;
      })
      .then((payload) => {
        setData(payload); onTitleChange?.(payload.title);
        if (payload.workflow?.kind === 'attendance_capture') {
          setMarks(Object.fromEntries(payload.workflow.students.map((student) => [String(student.student_id), { status: student.status, remarks: student.remarks }])));
        }
      })
      .catch((reason: unknown) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Attendance session could not be loaded.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [id, onTitleChange, reloadKey]);

  const workflow = data?.workflow?.kind === 'attendance_capture' ? data.workflow as AttendanceCaptureWorkflow : null;
  const summary = useMemo(() => {
    const values = Object.values(marks);
    return {
      total: values.length,
      present: values.filter((item) => item.status === 'present').length,
      absent: values.filter((item) => item.status === 'absent').length,
      late: values.filter((item) => item.status === 'late').length,
      excused: values.filter((item) => item.status === 'excused').length,
      unmarked: values.filter((item) => item.status === 'unmarked' || !item.status).length,
    };
  }, [marks]);
  const completion = summary.total ? Math.round(((summary.total - summary.unmarked) / summary.total) * 100) : 0;

  function markAll(status: string) {
    if (!workflow?.can_edit) return;
    setMarks((current) => Object.fromEntries(Object.entries(current).map(([key, value]) => [key, { ...value, status }])));
  }

  async function perform(action: 'save' | 'submit' | 'unlock') {
    setSubmitting(action);
    try {
      const response = await fetch(`/api/workspace/resources/attendance/${id}/action`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action, marks, reason: reopenReason }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'Attendance could not be updated.');
      toast.success(action === 'submit' ? 'Attendance submitted' : action === 'unlock' ? 'Attendance reopened' : 'Attendance saved', result.detail || 'Attendance updated successfully.');
      setReopenReason(''); setReloadKey((value) => value + 1);
    } catch (reason: unknown) {
      toast.error('Attendance not updated', reason instanceof Error ? reason.message : 'Please try again.');
    } finally { setSubmitting(''); }
  }

  if (loading && !data) return <div className="tafiti-card grid min-h-[460px] place-items-center"><div className="text-center text-xs font-semibold text-slate-500"><LoaderCircle className="mx-auto mb-3 animate-spin text-blue-600" size={24} />Loading attendance register…</div></div>;
  if (error && !data) return <div className="tafiti-card grid min-h-[420px] place-items-center p-6 text-center"><div><AlertCircle className="mx-auto text-red-500" size={24} /><h2 className="mt-3 text-sm font-bold text-slate-900">Attendance session unavailable</h2><p className="mt-2 text-xs text-slate-500">{error}</p><button type="button" onClick={() => setReloadKey((value) => value + 1)} className="clay-button-primary mt-4"><RefreshCw size={14} /> Try again</button></div></div>;
  if (!data || !workflow) return null;

  const options = workflow.statuses.filter((option) => ['present', 'absent', 'late', 'excused'].includes(option.value));

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <Link href={returnPath} className="inline-flex items-center gap-1.5 text-[11px] font-bold text-slate-500 hover:text-blue-600"><ArrowLeft size={13} /> Back to attendance</Link>
        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[9px] font-extrabold ${workflow.locked ? 'border-amber-200 bg-amber-50 text-amber-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'}`}>{workflow.locked ? <LockKeyhole size={11} /> : <CalendarCheck size={11} />}{data.status}</span>
      </div>

      <header className="tafiti-card p-5 sm:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-3"><span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-blue-50 text-blue-600"><CalendarCheck size={22} /></span><div><p className="text-[9px] font-extrabold uppercase tracking-[.12em] text-blue-600">Attendance capture</p><h1 className="mt-1 text-2xl font-extrabold tracking-[-.035em] text-[#10224A]">{data.title}</h1><p className="mt-1 text-xs font-semibold text-slate-500">{data.subtitle}</p></div></div>
          <div className="grid gap-2 sm:grid-cols-2 lg:min-w-[430px]">{data.metadata.map((item) => <div key={item.label} className="rounded-xl border border-slate-100 bg-[#F8FAFD] px-3 py-2.5"><p className="text-[8px] font-bold uppercase text-slate-400">{item.label}</p><p className="mt-1 truncate text-[10px] font-bold text-slate-700">{item.value}</p></div>)}</div>
        </div>
      </header>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {metricCard('Students', summary.total, 'bg-blue-50 text-blue-600', <Users size={17} />)}
        {metricCard('Present', summary.present, 'bg-emerald-50 text-emerald-600', <CheckCircle2 size={17} />)}
        {metricCard('Absent', summary.absent, 'bg-rose-50 text-rose-600', <AlertCircle size={17} />)}
        {metricCard('Late', summary.late, 'bg-amber-50 text-amber-600', <Clock3 size={17} />)}
        {metricCard('Excused', summary.excused, 'bg-violet-50 text-violet-600', <ShieldCheck size={17} />)}
      </div>

      <section className="tafiti-card overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-slate-100 bg-[#FBFCFE] px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5"><div><h2 className="text-sm font-extrabold text-[#10224A]">Student register</h2><p className="mt-1 text-[10px] text-slate-500">Mark every learner, add remarks where needed, then submit to lock the session.</p></div>{workflow.can_edit && <div className="flex gap-2"><button type="button" onClick={() => markAll('present')} className="clay-button-secondary">Mark all present</button><button type="button" onClick={() => markAll('unmarked')} className="clay-button-secondary"><RotateCcw size={13} /> Reset</button></div>}</div>
        <div className="border-b border-slate-100 px-4 py-3 sm:px-5"><div className="flex items-center gap-3"><div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-gradient-to-r from-blue-500 to-emerald-500" style={{ width: `${completion}%` }} /></div><span className="min-w-[86px] text-right text-[10px] font-bold text-slate-500">{completion}% complete</span></div></div>
        {workflow.blocked_reason && !workflow.can_edit && !workflow.can_unlock && <div className="flex items-start gap-3 border-b border-amber-100 bg-amber-50 px-4 py-3.5 text-xs text-amber-800 sm:px-5"><AlertCircle size={16} className="mt-0.5 shrink-0" />{workflow.blocked_reason}</div>}

        <div className="hidden overflow-x-auto md:block"><table className="w-full min-w-[1020px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STUDENT</th>{options.map((option) => <th key={option.value} className="px-2 py-3 text-center text-[9px] font-extrabold text-slate-400">{option.label.toUpperCase()}</th>)}<th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">REMARKS</th></tr></thead><tbody className="divide-y divide-slate-100">{workflow.students.map((student) => {
          const key = String(student.student_id); const mark = marks[key] ?? { status: student.status, remarks: student.remarks };
          return <tr key={key} className="hover:bg-blue-50/20"><td className="px-4 py-3"><div className="flex items-center gap-2.5"><span className="grid h-9 w-9 place-items-center rounded-full bg-blue-50 text-[9px] font-extrabold text-blue-700">{initials(student.student_name)}</span><div><p className="text-xs font-bold text-slate-800">{student.student_name}</p><p className="text-[9px] text-slate-400">{student.display_id}</p></div></div></td>{options.map((option) => { const selected = mark.status === option.value; const meta = STATUS_META[option.value]; return <td key={option.value} className="px-2 py-3 text-center"><button type="button" disabled={!workflow.can_edit || Boolean(submitting)} onClick={() => setMarks((current) => ({ ...current, [key]: { ...mark, status: option.value } }))} className={`inline-flex min-w-[72px] items-center justify-center gap-1.5 rounded-full border px-2.5 py-1.5 text-[9px] font-bold ${selected ? meta.active : 'border-slate-200 bg-white text-slate-400'}`}><span className={`h-1.5 w-1.5 rounded-full ${selected ? meta.dot : 'bg-slate-300'}`} />{option.label}</button></td>; })}<td className="px-4 py-3"><input value={mark.remarks} disabled={!workflow.can_edit || Boolean(submitting)} onChange={(event) => setMarks((current) => ({ ...current, [key]: { ...mark, remarks: event.target.value } }))} placeholder="Optional note" className="tafiti-input h-9 min-w-[180px] w-full px-3 text-xs" /></td></tr>;
        })}</tbody></table></div>

        <div className="space-y-3 p-3 md:hidden">{workflow.students.map((student) => {
          const key = String(student.student_id); const mark = marks[key] ?? { status: student.status, remarks: student.remarks };
          return <article key={key} className="rounded-2xl border border-slate-100 bg-[#FBFCFE] p-3.5"><div className="flex items-center gap-2.5"><span className="grid h-9 w-9 place-items-center rounded-full bg-blue-50 text-[9px] font-extrabold text-blue-700">{initials(student.student_name)}</span><div><p className="text-xs font-bold text-slate-800">{student.student_name}</p><p className="text-[9px] text-slate-400">{student.display_id}</p></div></div><div className="mt-3 grid grid-cols-2 gap-2">{options.map((option) => { const selected = mark.status === option.value; const meta = STATUS_META[option.value]; return <button key={option.value} type="button" disabled={!workflow.can_edit || Boolean(submitting)} onClick={() => setMarks((current) => ({ ...current, [key]: { ...mark, status: option.value } }))} className={`rounded-xl border px-3 py-2 text-[10px] font-bold ${selected ? meta.active : 'border-slate-200 bg-white text-slate-500'}`}>{option.label}</button>; })}</div><input value={mark.remarks} disabled={!workflow.can_edit || Boolean(submitting)} onChange={(event) => setMarks((current) => ({ ...current, [key]: { ...mark, remarks: event.target.value } }))} placeholder="Optional remark" className="tafiti-input mt-3 h-9 w-full px-3 text-xs" /></article>;
        })}</div>
      </section>

      <div className="sticky bottom-3 z-20 rounded-2xl border border-slate-200 bg-white/95 p-3.5 shadow-[0_18px_45px_rgba(17,38,73,.14)] backdrop-blur-xl sm:p-4"><div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between"><div><div className="flex flex-wrap gap-3 text-[10px] font-bold"><span className="text-emerald-600">{summary.present} present</span><span className="text-rose-600">{summary.absent} absent</span><span className="text-amber-600">{summary.late} late</span><span className="text-blue-600">{summary.excused} excused</span>{summary.unmarked > 0 && <span className="text-slate-500">{summary.unmarked} unmarked</span>}</div><p className="mt-1 text-[9px] text-slate-400">Submitting locks attendance and includes it in official reports.</p></div><div className="flex flex-col gap-2 sm:flex-row sm:items-center">{workflow.can_unlock && <><input value={reopenReason} onChange={(event) => setReopenReason(event.target.value)} placeholder="Reason for reopening" className="tafiti-input h-9 min-w-[210px] px-3 text-xs" /><button type="button" disabled={!reopenReason.trim() || Boolean(submitting)} onClick={() => void perform('unlock')} className="clay-button-secondary">{submitting === 'unlock' ? <LoaderCircle className="animate-spin" size={14} /> : <RefreshCw size={14} />} Reopen session</button></>}{workflow.can_edit && <><button type="button" disabled={Boolean(submitting)} onClick={() => void perform('save')} className="clay-button-secondary">{submitting === 'save' ? <LoaderCircle className="animate-spin" size={14} /> : <Save size={14} />} Save draft</button><button type="button" disabled={Boolean(submitting) || !workflow.students.length || summary.unmarked > 0} onClick={() => void perform('submit')} className="clay-button-primary">{submitting === 'submit' ? <LoaderCircle className="animate-spin" size={14} /> : <CheckCircle2 size={14} />} Submit attendance</button></>}</div></div></div>
    </section>
  );
}
