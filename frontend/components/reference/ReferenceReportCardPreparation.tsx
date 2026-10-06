'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  ClipboardCheck,
  FileText,
  LoaderCircle,
  Save,
  Send,
  ShieldCheck,
  Users,
} from 'lucide-react';

import { useToast } from '@/components/ui/ToastProvider';
import { ProfileAvatar } from '@/components/workspace/ProfileAvatar';

type Metric = { label: string; value: string | number; hint: string; tone: string };
type ClassRow = {
  class_id: number;
  class: string;
  year: string;
  term: string;
  students: number;
  assessments: number;
  verified_assessments: number;
  pending_assessments: number;
  submitted_remarks: number;
  approved_remarks: number;
  status: string;
  can_prepare: boolean;
  can_approve: boolean;
};
type ClassListPayload = {
  title: string;
  description: string;
  metrics: Metric[];
  rows: ClassRow[];
};
type StudentRow = {
  student_id: number;
  student_number: string;
  student: string;
  photo: string;
  class_teacher_remark: string;
  submitted: boolean;
  submitted_at: string;
  head_teacher_remark: string;
  approved: boolean;
  approved_at: string;
};
type ClassPayload = {
  title: string;
  description: string;
  class_id: number;
  class: string;
  year: string;
  term: string;
  ready: boolean;
  assessments: number;
  verified_assessments: number;
  pending_assessments: number;
  students: number;
  submitted: number;
  approved: number;
  rows: StudentRow[];
  permissions: { prepare: boolean; approve: boolean };
};

function statusClass(value: string) {
  const text = value.toLowerCase();
  if (text.includes('approved')) return 'border-emerald-100 bg-emerald-50 text-emerald-700';
  if (text.includes('ready')) return 'border-blue-100 bg-blue-50 text-blue-700';
  return 'border-amber-100 bg-amber-50 text-amber-700';
}

export function ReferenceReportCardPreparation() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  const classId = searchParams.get('class');
  const [list, setList] = useState<ClassListPayload | null>(null);
  const [report, setReport] = useState<ClassPayload | null>(null);
  const [remarks, setRemarks] = useState<Record<string, string>>({});
  const [headRemarks, setHeadRemarks] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    const url = classId && /^\d+$/.test(classId)
      ? `/api/workspace/results/operations/report-class/${classId}`
      : '/api/workspace/results/operations/report-cards';
    fetch(url, { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Report-card workflow could not be loaded.');
        return payload as ClassPayload | ClassListPayload;
      })
      .then((payload) => {
        if ('class_id' in payload) {
          setReport(payload);
          setList(null);
          setRemarks(Object.fromEntries(payload.rows.map((row) => [String(row.student_id), row.class_teacher_remark || ''])));
          setHeadRemarks(Object.fromEntries(payload.rows.map((row) => [String(row.student_id), row.head_teacher_remark || ''])));
        } else {
          setList(payload);
          setReport(null);
        }
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Report-card workflow could not be loaded.');
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [classId, reloadKey]);

  const completedRemarks = useMemo(
    () => Object.values(remarks).filter((value) => value.trim()).length,
    [remarks],
  );

  function openClass(id: number) {
    const params = new URLSearchParams(searchParams.toString());
    params.set('view', 'report-cards');
    params.set('class', String(id));
    router.replace(`?${params.toString()}`, { scroll: false });
  }

  function backToClasses() {
    const params = new URLSearchParams(searchParams.toString());
    params.set('view', 'report-cards');
    params.delete('class');
    router.replace(`?${params.toString()}`, { scroll: false });
  }

  async function runAction(action: 'save_remarks' | 'submit_remarks' | 'approve_remarks') {
    if (!report) return;
    setSaving(true);
    try {
      const response = await fetch(`/api/workspace/results/operations/report-class/${report.class_id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, remarks, head_remarks: headRemarks }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'The report-card action could not be completed.');
      toast.success(
        action === 'approve_remarks' ? 'Reports approved' : action === 'submit_remarks' ? 'Remarks submitted' : 'Drafts saved',
        payload.detail || 'Report-card workflow updated.',
      );
      if (payload.report) {
        const refreshed = payload.report as ClassPayload;
        setReport(refreshed);
        setRemarks(Object.fromEntries(refreshed.rows.map((row) => [String(row.student_id), row.class_teacher_remark || ''])));
        setHeadRemarks(Object.fromEntries(refreshed.rows.map((row) => [String(row.student_id), row.head_teacher_remark || ''])));
      } else {
        setReloadKey((value) => value + 1);
      }
    } catch (reason: unknown) {
      toast.error('Report-card action failed', reason instanceof Error ? reason.message : 'Please try again.');
    } finally {
      setSaving(false);
    }
  }

  if (loading && !list && !report) {
    return <div className="tafiti-card grid min-h-[420px] place-items-center"><div className="text-center text-xs font-semibold text-slate-500"><LoaderCircle className="mx-auto mb-3 animate-spin text-blue-600" size={24} />Loading report cards…</div></div>;
  }
  if (error && !list && !report) {
    return <div className="tafiti-card grid min-h-[380px] place-items-center p-6 text-center"><div><AlertCircle className="mx-auto text-red-500" size={24} /><p className="mt-3 text-sm font-bold text-slate-800">Report cards unavailable</p><p className="mt-2 text-xs text-slate-500">{error}</p><button type="button" onClick={() => setReloadKey((value) => value + 1)} className="clay-button-primary mt-4">Try again</button></div></div>;
  }

  if (report) {
    return (
      <section>
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex items-start gap-3">
            <button type="button" onClick={backToClasses} className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"><ArrowLeft size={17} /></button>
            <div><h1 className="text-[1.65rem] font-extrabold tracking-[-0.035em] text-[#10224A]">{report.title}</h1><p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">{report.description}</p><p className="mt-1 text-[10px] font-bold text-blue-700">{report.year} · {report.term}</p></div>
          </div>
          <div className="flex flex-wrap gap-2">
            {report.permissions.prepare && <button type="button" disabled={saving} onClick={() => void runAction('save_remarks')} className="clay-button-secondary"><Save size={14} />Save drafts</button>}
            {report.permissions.prepare && <button type="button" disabled={saving || !report.ready || completedRemarks === 0} onClick={() => void runAction('submit_remarks')} className="clay-button-primary"><Send size={14} />Submit completed</button>}
            {report.permissions.approve && <button type="button" disabled={saving || !report.ready || report.submitted === 0} onClick={() => void runAction('approve_remarks')} className="clay-button-primary"><ShieldCheck size={14} />Approve submitted</button>}
          </div>
        </div>

        {!report.ready && <div className="mb-4 flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4"><AlertCircle className="mt-0.5 shrink-0 text-amber-600" size={17} /><div><p className="text-xs font-bold text-amber-800">Report cards are not ready yet</p><p className="mt-1 text-[10px] leading-4 text-amber-700">{report.verified_assessments}/{report.assessments} assessment batches are verified. Finish mark entry and verification before submitting or approving remarks.</p></div></div>}

        <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <article className="tafiti-kpi"><p className="text-[9px] font-bold text-slate-400">STUDENTS</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{report.students}</p><p className="mt-1 text-[9px] text-slate-400">Current class register</p></article>
          <article className="tafiti-kpi"><p className="text-[9px] font-bold text-slate-400">VERIFIED ASSESSMENTS</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{report.verified_assessments}/{report.assessments}</p><p className="mt-1 text-[9px] text-slate-400">Required before submission</p></article>
          <article className="tafiti-kpi"><p className="text-[9px] font-bold text-slate-400">SUBMITTED REMARKS</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{report.submitted}/{report.students}</p><p className="mt-1 text-[9px] text-slate-400">Class-teacher stage</p></article>
          <article className="tafiti-kpi"><p className="text-[9px] font-bold text-slate-400">APPROVED REPORTS</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{report.approved}/{report.students}</p><p className="mt-1 text-[9px] text-slate-400">Head-teacher stage</p></article>
        </div>

        <section className="tafiti-card overflow-hidden">
          <div className="border-b border-slate-100 px-4 py-3.5 sm:px-5"><h2 className="text-sm font-extrabold text-[#10224A]">Learner report remarks</h2><p className="mt-1 text-[10px] text-slate-500">Work down the class once. Draft, submit and approve without reopening individual students.</p></div>
          <div className="divide-y divide-slate-100">
            {report.rows.map((row) => (
              <div key={row.student_id} className="grid gap-3 px-4 py-4 lg:grid-cols-[220px_minmax(0,1fr)_minmax(0,.75fr)_110px] lg:items-start sm:px-5">
                <div className="flex items-center gap-2.5"><ProfileAvatar src={row.photo} name={row.student} size="sm" /><div className="min-w-0"><p className="truncate text-xs font-bold text-slate-800">{row.student}</p><p className="mt-0.5 text-[9px] text-slate-400">{row.student_number}</p></div></div>
                <div><p className="mb-1 text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">Class teacher remark</p>{report.permissions.prepare ? <textarea rows={3} maxLength={1000} value={remarks[String(row.student_id)] ?? ''} onChange={(event) => setRemarks((current) => ({ ...current, [String(row.student_id)]: event.target.value }))} className="tafiti-input min-h-[76px] w-full resize-y p-2.5 text-xs" placeholder="Enter the learner's class-teacher remark…" /> : <p className="min-h-[76px] rounded-lg border border-slate-100 bg-slate-50 p-2.5 text-xs leading-5 text-slate-600">{row.class_teacher_remark || 'No remark yet.'}</p>}</div>
                <div><p className="mb-1 text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">Head teacher remark</p>{report.permissions.approve ? <textarea rows={3} maxLength={240} value={headRemarks[String(row.student_id)] ?? ''} onChange={(event) => setHeadRemarks((current) => ({ ...current, [String(row.student_id)]: event.target.value }))} className="tafiti-input min-h-[76px] w-full resize-y p-2.5 text-xs" placeholder="Optional approval remark…" /> : <p className="min-h-[76px] rounded-lg border border-slate-100 bg-slate-50 p-2.5 text-xs leading-5 text-slate-600">{row.head_teacher_remark || '—'}</p>}</div>
                <div className="flex flex-row gap-1.5 lg:flex-col"><span className={`rounded-full border px-2 py-1 text-center text-[8px] font-bold ${row.submitted ? 'border-blue-100 bg-blue-50 text-blue-700' : 'border-slate-200 bg-slate-50 text-slate-500'}`}>{row.submitted ? 'Submitted' : 'Draft'}</span><span className={`rounded-full border px-2 py-1 text-center text-[8px] font-bold ${row.approved ? 'border-emerald-100 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-slate-50 text-slate-500'}`}>{row.approved ? 'Approved' : 'Not approved'}</span></div>
              </div>
            ))}
          </div>
          {!report.rows.length && <div className="px-5 py-12 text-center text-xs text-slate-400">No active learners are registered in this class.</div>}
        </section>
      </section>
    );
  }

  if (!list) return null;
  return (
    <section>
      <div className="mb-4 flex items-start gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-600"><FileText size={21} /></span><div><h1 className="text-[1.65rem] font-extrabold tracking-[-0.035em] text-[#10224A]">{list.title}</h1><p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">{list.description}</p></div></div>
      <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{list.metrics.map((metric) => <article key={metric.label} className="tafiti-kpi"><p className="text-[9px] font-bold text-slate-400">{metric.label.toUpperCase()}</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{metric.value}</p><p className="mt-1 text-[9px] text-slate-400">{metric.hint}</p></article>)}</div>
      <section className="tafiti-card overflow-hidden">
        <div className="border-b border-slate-100 px-4 py-3.5 sm:px-5"><h2 className="text-sm font-extrabold text-[#10224A]">Class report workflow</h2><p className="mt-1 text-[10px] text-slate-500">Choose a class once, then prepare every learner's report on one page.</p></div>
        <div className="overflow-x-auto"><table className="w-full min-w-[900px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">CLASS</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STUDENTS</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">ASSESSMENTS</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">REMARKS</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STATUS</th><th className="px-4 py-3 text-right text-[9px] font-extrabold text-slate-400">ACTION</th></tr></thead><tbody className="divide-y divide-slate-100">{list.rows.map((row) => <tr key={row.class_id} className="hover:bg-blue-50/25"><td className="px-4 py-3"><p className="text-xs font-bold text-slate-800">{row.class}</p><p className="mt-0.5 text-[9px] text-slate-400">{row.year} · {row.term}</p></td><td className="px-4 py-3 text-xs font-bold text-slate-700">{row.students}</td><td className="px-4 py-3"><p className="text-xs font-bold text-slate-700">{row.verified_assessments}/{row.assessments} verified</p>{row.pending_assessments > 0 && <p className="mt-0.5 text-[9px] font-semibold text-amber-600">{row.pending_assessments} pending / flagged</p>}</td><td className="px-4 py-3 text-xs text-slate-600">{row.submitted_remarks} submitted · {row.approved_remarks} approved</td><td className="px-4 py-3"><span className={`rounded-full border px-2 py-1 text-[9px] font-bold ${statusClass(row.status)}`}>{row.status}</span></td><td className="px-4 py-3 text-right"><button type="button" onClick={() => openClass(row.class_id)} className="inline-flex items-center gap-1.5 text-[10px] font-bold text-blue-600 hover:underline">{row.can_approve ? <ClipboardCheck size={13} /> : row.can_prepare ? <Users size={13} /> : <CheckCircle2 size={13} />}Open class</button></td></tr>)}</tbody></table></div>
        {!list.rows.length && <div className="px-5 py-12 text-center text-xs text-slate-400">No report-card classes are available for your current role and academic period.</div>}
      </section>
    </section>
  );
}
