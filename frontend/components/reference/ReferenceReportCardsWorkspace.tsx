'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  FileText,
  LoaderCircle,
  RefreshCw,
  RotateCcw,
  Save,
  Send,
} from 'lucide-react';

import { useToast } from '@/components/ui/ToastProvider';

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
  marks_ready: boolean;
  status: string;
};

type ClassListPayload = {
  title: string;
  description: string;
  metrics: Metric[];
  rows: ClassRow[];
};

type StudentRemarkRow = {
  student_id: number;
  student: string;
  reg_no: string;
  class_teacher_remark: string;
  head_teacher_remark: string;
  submitted: boolean;
  approved: boolean;
  submitted_at: string;
  approved_at: string;
};

type ClassDetailPayload = {
  class_id: number;
  class: string;
  year: string;
  term: string;
  scope_key: string;
  scope_label: string;
  marks_ready: boolean;
  assessment_count: number;
  verified_count: number;
  students: number;
  submitted: number;
  approved: number;
  can_edit_class_remarks: boolean;
  can_approve: boolean;
  rows: StudentRemarkRow[];
};

function statusClass(value: string) {
  const text = value.toLowerCase();
  if (text.includes('approved') || text.includes('ready')) return 'border-emerald-100 bg-emerald-50 text-emerald-700';
  if (text.includes('awaiting')) return 'border-violet-100 bg-violet-50 text-violet-700';
  if (text.includes('remark') || text.includes('progress')) return 'border-amber-100 bg-amber-50 text-amber-700';
  return 'border-slate-200 bg-slate-50 text-slate-600';
}

function ResultsNav({ dashboardPath }: { dashboardPath: string }) {
  const base = `${dashboardPath}/results`;
  const items = [
    ['Overview', base],
    ['Marks Entry', `${base}?view=marks`],
    ['Verification', `${base}?view=verification`],
    ['Report Cards', `${base}?view=report-cards`],
    ['Performance', `${base}?view=performance`],
  ] as const;
  return (
    <div className="mb-4 overflow-x-auto rounded-xl border border-slate-200 bg-white p-1.5 shadow-[0_5px_16px_rgba(28,55,97,.035)]">
      <div className="flex min-w-max gap-1">
        {items.map(([label, href]) => (
          <Link key={label} href={href} className={`rounded-lg px-3.5 py-2 text-[10px] font-extrabold transition ${label === 'Report Cards' ? 'bg-blue-600 text-white shadow-[0_5px_12px_rgba(37,99,235,.18)]' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'}`}>
            {label}
          </Link>
        ))}
      </div>
    </div>
  );
}

export function ReferenceReportCardsWorkspace({ dashboardPath }: { dashboardPath: string }) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const classId = searchParams.get('class');

  return (
    <section>
      <ResultsNav dashboardPath={dashboardPath} />
      {classId ? <ReportClassWorkspace dashboardPath={dashboardPath} classId={classId} onBack={() => router.replace(`${dashboardPath}/results?view=report-cards`)} /> : <ReportClassList dashboardPath={dashboardPath} />}
    </section>
  );
}

function ReportClassList({ dashboardPath }: { dashboardPath: string }) {
  const [data, setData] = useState<ClassListPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetch('/api/workspace/results/operations/report-cards', { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Report cards could not be loaded.');
        return payload as ClassListPayload;
      })
      .then(setData)
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Report cards could not be loaded.');
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [reloadKey]);

  if (loading && !data) return <div className="tafiti-card grid min-h-[420px] place-items-center"><LoaderCircle className="animate-spin text-blue-600" size={24} /></div>;
  if (error && !data) return <div className="tafiti-card p-6 text-center"><AlertCircle className="mx-auto text-red-500" size={22} /><p className="mt-3 text-sm font-bold text-slate-800">Report cards unavailable</p><p className="mt-2 text-xs text-slate-500">{error}</p><button type="button" className="clay-button-primary mt-4" onClick={() => setReloadKey((value) => value + 1)}>Try again</button></div>;
  if (!data) return null;

  return (
    <>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex items-start gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-600"><FileText size={21} /></span><div><h1 className="text-[1.65rem] font-extrabold tracking-[-0.035em] text-[#10224A]">{data.title}</h1><p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">{data.description}</p></div></div>
        <div className="flex flex-wrap gap-2"><button type="button" onClick={() => setReloadKey((value) => value + 1)} className="clay-button-secondary"><RefreshCw size={14} />Refresh</button><Link href={`${dashboardPath}/reports`} className="clay-button-secondary"><FileText size={14} />Report Center</Link></div>
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {data.metrics.map((metric) => <article key={metric.label} className="tafiti-kpi"><p className="text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">{metric.label}</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{metric.value}</p><p className="mt-1 text-[9px] text-slate-400">{metric.hint}</p></article>)}
      </div>

      <section className="tafiti-card overflow-hidden">
        <div className="border-b border-slate-100 px-4 py-3.5 sm:px-5"><h2 className="text-sm font-extrabold text-[#10224A]">Class workflow</h2><p className="mt-1 text-[10px] text-slate-500">Open a class once and finish remarks and approval from the same workspace.</p></div>
        <div className="overflow-x-auto"><table className="w-full min-w-[980px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">CLASS</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STUDENTS</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">ASSESSMENTS</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">REMARKS</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STATUS</th><th className="px-4 py-3 text-right text-[9px] font-extrabold text-slate-400">NEXT ACTION</th></tr></thead>
          <tbody className="divide-y divide-slate-100">{data.rows.map((row) => <tr key={row.class_id} className="hover:bg-blue-50/25"><td className="px-4 py-3"><p className="text-xs font-bold text-slate-800">{row.class}</p><p className="mt-0.5 text-[9px] text-slate-400">{row.year} · {row.term}</p></td><td className="px-4 py-3 text-xs font-bold text-slate-700">{row.students}</td><td className="px-4 py-3"><p className="text-xs font-bold text-slate-700">{row.verified_assessments}/{row.assessments} verified</p>{row.pending_assessments > 0 && <p className="mt-0.5 text-[9px] font-semibold text-amber-600">{row.pending_assessments} pending / flagged</p>}</td><td className="px-4 py-3 text-xs text-slate-600"><span className="font-bold text-slate-800">{row.submitted_remarks}/{row.students}</span> submitted · <span className="font-bold text-slate-800">{row.approved_remarks}/{row.students}</span> approved</td><td className="px-4 py-3"><span className={`rounded-full border px-2 py-1 text-[9px] font-bold ${statusClass(row.status)}`}>{row.status}</span></td><td className="px-4 py-3 text-right"><Link href={`${dashboardPath}/results?view=report-cards&class=${row.class_id}`} className="inline-flex items-center gap-1 text-[10px] font-bold text-blue-600 hover:underline">Open class <ArrowRight size={12} /></Link></td></tr>)}</tbody>
        </table></div>
        {!data.rows.length && <div className="px-5 py-12 text-center text-xs text-slate-400">No report-card classes are available for the current period.</div>}
      </section>
    </>
  );
}

function ReportClassWorkspace({ dashboardPath, classId, onBack }: { dashboardPath: string; classId: string; onBack: () => void }) {
  const toast = useToast();
  const [data, setData] = useState<ClassDetailPayload | null>(null);
  const [remarks, setRemarks] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetch(`/api/workspace/results/operations/report-cards?class_id=${encodeURIComponent(classId)}`, { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'This report-card class could not be loaded.');
        return payload as ClassDetailPayload;
      })
      .then((payload) => {
        setData(payload);
        setRemarks(Object.fromEntries(payload.rows.map((row) => [String(row.student_id), row.class_teacher_remark])));
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'This report-card class could not be loaded.');
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [classId, reloadKey]);

  const completion = useMemo(() => {
    if (!data?.students) return 0;
    return Math.round((data.approved / data.students) * 100);
  }, [data]);

  async function runAction(action: 'save_class' | 'submit_class' | 'approve_class' | 'return_class') {
    if (!data || saving) return;
    setSaving(true);
    try {
      const response = await fetch('/api/workspace/results/operations/report-cards', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, class_id: data.class_id, remarks }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'The report-card action could not be completed.');
      toast.success(action === 'approve_class' ? 'Class approved' : action === 'submit_class' ? 'Remarks submitted' : action === 'return_class' ? 'Returned for revision' : 'Drafts saved', payload.detail);
      setReloadKey((value) => value + 1);
    } catch (reason: unknown) {
      toast.error('Report cards not updated', reason instanceof Error ? reason.message : 'Please try again.');
    } finally { setSaving(false); }
  }

  if (loading && !data) return <div className="tafiti-card grid min-h-[430px] place-items-center"><LoaderCircle className="animate-spin text-blue-600" size={24} /></div>;
  if (error && !data) return <div className="tafiti-card p-6 text-center"><AlertCircle className="mx-auto text-red-500" size={22} /><p className="mt-3 text-sm font-bold text-slate-800">Class report cards unavailable</p><p className="mt-2 text-xs text-slate-500">{error}</p><button type="button" onClick={onBack} className="clay-button-secondary mt-4"><ArrowLeft size={14} />Back to classes</button></div>;
  if (!data) return null;

  const allSubmitted = data.students > 0 && data.submitted === data.students;
  const allApproved = data.students > 0 && data.approved === data.students;

  return (
    <>
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div><button type="button" onClick={onBack} className="mb-2 inline-flex items-center gap-1 text-[10px] font-bold text-slate-500 hover:text-blue-600"><ArrowLeft size={12} />Report-card classes</button><h1 className="text-[1.65rem] font-extrabold tracking-[-0.035em] text-[#10224A]">{data.class} Report Cards</h1><p className="mt-1 text-xs text-slate-500">{data.year} · {data.term} · {data.scope_label}</p></div>
        <div className="flex flex-wrap gap-2">
          {data.can_edit_class_remarks && !allApproved && <button type="button" disabled={saving} onClick={() => void runAction('save_class')} className="clay-button-secondary"><Save size={14} />Save drafts</button>}
          {data.can_edit_class_remarks && data.marks_ready && !allSubmitted && <button type="button" disabled={saving} onClick={() => void runAction('submit_class')} className="clay-button-primary"><Send size={14} />Submit class remarks</button>}
          {data.can_approve && allSubmitted && !allApproved && <button type="button" disabled={saving} onClick={() => void runAction('approve_class')} className="clay-button-primary"><CheckCircle2 size={14} />Approve class</button>}
          {data.can_approve && allSubmitted && <button type="button" disabled={saving} onClick={() => void runAction('return_class')} className="clay-button-secondary"><RotateCcw size={14} />Return for revision</button>}
          {allApproved && <Link href={`${dashboardPath}/reports`} className="clay-button-primary"><FileText size={14} />Generate reports</Link>}
        </div>
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <article className="tafiti-kpi"><p className="text-[9px] font-bold text-slate-400">MARKS VERIFIED</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{data.verified_count}/{data.assessment_count}</p><p className="mt-1 text-[9px] text-slate-400">{data.marks_ready ? 'Ready for remarks' : 'Finish verification first'}</p></article>
        <article className="tafiti-kpi"><p className="text-[9px] font-bold text-slate-400">STUDENTS</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{data.students}</p><p className="mt-1 text-[9px] text-slate-400">Current active class register</p></article>
        <article className="tafiti-kpi"><p className="text-[9px] font-bold text-slate-400">REMARKS SUBMITTED</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{data.submitted}/{data.students}</p><p className="mt-1 text-[9px] text-slate-400">Class Teacher stage</p></article>
        <article className="tafiti-kpi"><p className="text-[9px] font-bold text-slate-400">APPROVED</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{completion}%</p><p className="mt-1 text-[9px] text-slate-400">Head Teacher completion</p></article>
      </div>

      {!data.marks_ready && <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-[11px] font-semibold text-amber-800">All assessment batches must be verified before class remarks can be submitted.</div>}

      <section className="tafiti-card overflow-hidden">
        <div className="border-b border-slate-100 px-4 py-3.5 sm:px-5"><h2 className="text-sm font-extrabold text-[#10224A]">Student remarks</h2><p className="mt-1 text-[10px] text-slate-500">Prepare the whole class here, save drafts once, then submit the class once.</p></div>
        <div className="overflow-x-auto"><table className="w-full min-w-[1050px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STUDENT</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">CLASS TEACHER REMARK</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">HEAD TEACHER</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STATUS</th></tr></thead>
          <tbody className="divide-y divide-slate-100">{data.rows.map((row) => <tr key={row.student_id} className="align-top"><td className="px-4 py-3"><p className="text-xs font-bold text-slate-800">{row.student}</p><p className="mt-0.5 text-[9px] text-slate-400">{row.reg_no}</p></td><td className="px-4 py-3">{data.can_edit_class_remarks && !row.approved ? <textarea value={remarks[String(row.student_id)] ?? ''} onChange={(event) => setRemarks((current) => ({ ...current, [String(row.student_id)]: event.target.value }))} maxLength={1000} rows={3} className="tafiti-input min-h-[76px] w-full min-w-[420px] resize-y px-3 py-2 text-xs" placeholder="Class Teacher remark…" /> : <p className="max-w-xl whitespace-pre-wrap text-xs leading-5 text-slate-600">{row.class_teacher_remark || '—'}</p>}</td><td className="px-4 py-3"><p className="max-w-sm whitespace-pre-wrap text-xs leading-5 text-slate-600">{row.head_teacher_remark || (row.approved ? 'Approved' : '—')}</p></td><td className="px-4 py-3">{row.approved ? <span className="rounded-full border border-emerald-100 bg-emerald-50 px-2 py-1 text-[9px] font-bold text-emerald-700">Approved</span> : row.submitted ? <span className="rounded-full border border-violet-100 bg-violet-50 px-2 py-1 text-[9px] font-bold text-violet-700">Submitted</span> : <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-[9px] font-bold text-slate-500">Draft</span>}</td></tr>)}</tbody>
        </table></div>
      </section>
    </>
  );
}
