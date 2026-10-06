'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  AlertCircle,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  FileText,
  GraduationCap,
  LoaderCircle,
  MessageSquareText,
  RotateCcw,
  Save,
  Send,
  ShieldCheck,
} from 'lucide-react';

import { useToast } from '@/components/ui/ToastProvider';
import { ReferenceResultsWorkspace } from './ReferenceResultsWorkspace';

type Metric = { label: string; value: string | number; hint: string; tone: string };
type OverviewRow = {
  assessment_id: number;
  class: string;
  subject: string;
  assessment: string;
  date: string;
  out_of: number;
  entered: number;
  expected: number;
  verified: number;
  missing: number;
  status: string;
  status_code: string;
};
type ReportCardRow = {
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
  scope_key?: string;
  scope_label?: string;
  status: string;
};
type PerformanceRow = { subject_id?: number; class_id?: number; subject?: string; class?: string; average: string; results: number };
type ReportRemarkRow = {
  student_id: number;
  student: string;
  reg_no: string;
  class_teacher_remark: string;
  head_teacher_remark: string;
  submitted_at: string;
  approved_at: string;
  status: string;
};
type ReportWorkflowPayload = {
  title: string;
  description: string;
  classes: { id: number; label: string }[];
  selected_class_id: number | null;
  selected_class?: string;
  scope_label?: string;
  rows: ReportRemarkRow[];
  permissions: { edit: boolean; approve: boolean };
  metrics: Metric[];
};
type Payload = {
  title: string;
  description: string;
  metrics: Metric[];
  rows?: OverviewRow[] | ReportCardRow[];
  subjects?: PerformanceRow[];
  classes?: PerformanceRow[];
  period?: { academic_year: string; term: string };
};

function statusClass(value: string) {
  const text = value.toLowerCase();
  if (text.includes('verified') || text === 'ready' || text === 'approved') return 'border-emerald-100 bg-emerald-50 text-emerald-700';
  if (text.includes('flagged')) return 'border-red-100 bg-red-50 text-red-700';
  if (text.includes('pending') || text.includes('progress') || text === 'submitted') return 'border-amber-100 bg-amber-50 text-amber-700';
  if (text === 'draft') return 'border-blue-100 bg-blue-50 text-blue-700';
  return 'border-slate-200 bg-slate-50 text-slate-600';
}

function ResultsNav({ dashboardPath, view }: { dashboardPath: string; view: string }) {
  const base = `${dashboardPath}/results`;
  const items = [
    ['overview', 'Overview', base],
    ['marks', 'Marks Entry', `${base}?view=marks`],
    ['verification', 'Verification', `${base}?view=verification`],
    ['report-cards', 'Report Cards', `${base}?view=report-cards`],
    ['report-workflow', 'Remarks & Approval', `${base}?view=report-workflow`],
    ['performance', 'Performance', `${base}?view=performance`],
  ] as const;
  return (
    <div className="mb-4 overflow-x-auto rounded-xl border border-slate-200 bg-white p-1.5 shadow-[0_5px_16px_rgba(28,55,97,.035)]">
      <div className="flex min-w-max gap-1">
        {items.map(([key, label, href]) => (
          <Link key={key} href={href} className={`rounded-lg px-3.5 py-2 text-[10px] font-extrabold transition ${view === key ? 'bg-blue-600 text-white shadow-[0_5px_12px_rgba(37,99,235,.18)]' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'}`}>
            {label}
          </Link>
        ))}
      </div>
    </div>
  );
}

export function ReferenceResultsOperations({ dashboardPath }: { dashboardPath: string }) {
  const searchParams = useSearchParams();
  const view = searchParams.get('view') || 'overview';

  if (view === 'marks' || view === 'verification') {
    return <ReferenceResultsWorkspace dashboardPath={dashboardPath} />;
  }
  if (view === 'report-workflow') {
    return <ReportWorkflowScreen dashboardPath={dashboardPath} />;
  }

  const screen = view === 'report-cards' ? 'report-cards' : view === 'performance' ? 'performance' : 'overview';
  return <OperationsScreen screen={screen} dashboardPath={dashboardPath} />;
}

function OperationsScreen({ screen, dashboardPath }: { screen: 'overview' | 'report-cards' | 'performance'; dashboardPath: string }) {
  const [data, setData] = useState<Payload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetch(`/api/workspace/results/operations/${screen}`, { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Results workspace could not be loaded.');
        return payload as Payload;
      })
      .then(setData)
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Results workspace could not be loaded.');
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [screen]);

  const view = screen === 'report-cards' ? 'report-cards' : screen === 'performance' ? 'performance' : 'overview';

  if (loading && !data) {
    return <div className="tafiti-card grid min-h-[430px] place-items-center"><div className="text-center text-xs font-semibold text-slate-500"><LoaderCircle className="mx-auto mb-3 animate-spin text-blue-600" size={24} />Loading results operations…</div></div>;
  }
  if (error && !data) {
    return <div className="tafiti-card p-6 text-center"><AlertCircle className="mx-auto text-red-500" size={22} /><p className="mt-3 text-sm font-bold text-slate-800">Results workspace unavailable</p><p className="mt-2 text-xs text-slate-500">{error}</p></div>;
  }
  if (!data) return null;

  return (
    <section>
      <ResultsNav dashboardPath={dashboardPath} view={view} />
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex items-start gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-600">{screen === 'performance' ? <BarChart3 size={21} /> : screen === 'report-cards' ? <FileText size={21} /> : <GraduationCap size={21} />}</span>
          <div><h1 className="text-[1.65rem] font-extrabold tracking-[-0.035em] text-[#10224A]">{data.title}</h1><p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">{data.description}</p>{data.period && <p className="mt-1 text-[10px] font-bold text-blue-700">{data.period.academic_year} · {data.period.term}</p>}</div>
        </div>
        {screen === 'report-cards' && <Link href={`${dashboardPath}/reports`} className="clay-button-secondary"><FileText size={14} />Report Center</Link>}
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {data.metrics.map((metric) => <article key={metric.label} className="tafiti-kpi"><p className="text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">{metric.label}</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{metric.value}</p><p className="mt-1 text-[9px] text-slate-400">{metric.hint}</p></article>)}
      </div>

      {screen === 'overview' && <OverviewTable rows={(data.rows ?? []) as OverviewRow[]} dashboardPath={dashboardPath} />}
      {screen === 'report-cards' && <ReportCardsTable rows={(data.rows ?? []) as ReportCardRow[]} dashboardPath={dashboardPath} />}
      {screen === 'performance' && <PerformanceTables subjects={data.subjects ?? []} classes={data.classes ?? []} />}
    </section>
  );
}

function ReportWorkflowScreen({ dashboardPath }: { dashboardPath: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  const classId = searchParams.get('class_id') || '';
  const [data, setData] = useState<ReportWorkflowPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busyKey, setBusyKey] = useState('');
  const [drafts, setDrafts] = useState<Record<number, { classRemark: string; headRemark: string }>>({});
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    const query = classId ? `?class_id=${encodeURIComponent(classId)}` : '';
    fetch(`/api/workspace/results/operations/report-workflow${query}`, { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Report preparation could not be loaded.');
        return payload as ReportWorkflowPayload;
      })
      .then((payload) => {
        setData(payload);
        setDrafts(Object.fromEntries(payload.rows.map((row) => [row.student_id, {
          classRemark: row.class_teacher_remark,
          headRemark: row.head_teacher_remark,
        }])));
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Report preparation could not be loaded.');
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [classId, reloadKey]);

  function chooseClass(nextId: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set('view', 'report-workflow');
    if (nextId) params.set('class_id', nextId);
    else params.delete('class_id');
    router.replace(`?${params.toString()}`, { scroll: false });
  }

  async function runAction(row: ReportRemarkRow, action: 'save' | 'submit' | 'approve' | 'reopen') {
    if (!data?.selected_class_id) return;
    const key = `${row.student_id}:${action}`;
    setBusyKey(key);
    try {
      const values = drafts[row.student_id] ?? { classRemark: row.class_teacher_remark, headRemark: row.head_teacher_remark };
      const response = await fetch('/api/workspace/results/operations/report-workflow', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action,
          class_id: data.selected_class_id,
          student_id: row.student_id,
          class_teacher_remark: values.classRemark,
          head_teacher_remark: values.headRemark,
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'The report action could not be completed.');
      toast.success('Report workflow updated', payload.detail || 'Changes saved.');
      setReloadKey((value) => value + 1);
    } catch (reason: unknown) {
      toast.error('Report action failed', reason instanceof Error ? reason.message : 'Please try again.');
    } finally {
      setBusyKey('');
    }
  }

  if (loading && !data) {
    return <div className="tafiti-card grid min-h-[430px] place-items-center"><LoaderCircle className="animate-spin text-blue-600" size={24} /></div>;
  }
  if (error && !data) {
    return <div className="tafiti-card p-6 text-center"><AlertCircle className="mx-auto text-red-500" size={22} /><p className="mt-3 text-sm font-bold text-slate-800">Report workflow unavailable</p><p className="mt-2 text-xs text-slate-500">{error}</p></div>;
  }
  if (!data) return null;

  return (
    <section>
      <ResultsNav dashboardPath={dashboardPath} view="report-workflow" />
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex items-start gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-600"><MessageSquareText size={21} /></span>
          <div><h1 className="text-[1.65rem] font-extrabold tracking-[-0.035em] text-[#10224A]">{data.title}</h1><p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">{data.description}</p>{data.scope_label && <p className="mt-1 text-[10px] font-bold text-blue-700">{data.scope_label}</p>}</div>
        </div>
        <select value={String(data.selected_class_id ?? '')} onChange={(event) => chooseClass(event.target.value)} className="tafiti-input h-10 min-w-[230px] px-3 text-xs font-bold">
          {data.classes.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
        </select>
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {data.metrics.map((metric) => <article key={metric.label} className="tafiti-kpi"><p className="text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">{metric.label}</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{metric.value}</p><p className="mt-1 text-[9px] text-slate-400">{metric.hint}</p></article>)}
      </div>

      <section className="tafiti-card overflow-hidden">
        <div className="border-b border-slate-100 px-4 py-3.5 sm:px-5"><h2 className="text-sm font-extrabold text-[#10224A]">{data.selected_class || 'Class'} remarks</h2><p className="mt-1 text-[10px] text-slate-500">Save drafts as you work. Submission hands the remark to the Head Teacher; approval completes the report-card remark stage.</p></div>
        <div className="divide-y divide-slate-100">
          {data.rows.map((row) => {
            const draft = drafts[row.student_id] ?? { classRemark: row.class_teacher_remark, headRemark: row.head_teacher_remark };
            const approved = row.status === 'Approved';
            const submitted = row.status === 'Submitted';
            return (
              <div key={row.student_id} className="p-4 sm:p-5">
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <div className="min-w-0 flex-1"><p className="text-xs font-extrabold text-slate-800">{row.student}</p><p className="mt-0.5 text-[9px] text-slate-400">{row.reg_no}</p></div>
                  <span className={`rounded-full border px-2.5 py-1 text-[9px] font-bold ${statusClass(row.status)}`}>{row.status}</span>
                </div>
                <div className="grid gap-3 xl:grid-cols-2">
                  <label className="block"><span className="mb-1.5 block text-[9px] font-extrabold uppercase tracking-[.06em] text-slate-400">Class-teacher remark</span><textarea value={draft.classRemark} disabled={!data.permissions.edit || approved || submitted} onChange={(event) => setDrafts((current) => ({ ...current, [row.student_id]: { ...draft, classRemark: event.target.value } }))} rows={3} maxLength={1000} className="tafiti-input min-h-[86px] w-full resize-y px-3 py-2 text-xs" /></label>
                  <label className="block"><span className="mb-1.5 block text-[9px] font-extrabold uppercase tracking-[.06em] text-slate-400">Head-teacher remark</span><textarea value={draft.headRemark} disabled={!data.permissions.approve || approved} onChange={(event) => setDrafts((current) => ({ ...current, [row.student_id]: { ...draft, headRemark: event.target.value } }))} rows={3} maxLength={240} className="tafiti-input min-h-[86px] w-full resize-y px-3 py-2 text-xs" /></label>
                </div>
                <div className="mt-3 flex flex-wrap justify-end gap-2">
                  {data.permissions.edit && !submitted && !approved && <button type="button" disabled={Boolean(busyKey)} onClick={() => void runAction(row, 'save')} className="clay-button-secondary"><Save size={13} />Save draft</button>}
                  {data.permissions.edit && !submitted && !approved && <button type="button" disabled={Boolean(busyKey)} onClick={() => void runAction(row, 'submit')} className="clay-button-primary"><Send size={13} />Submit remark</button>}
                  {data.permissions.approve && submitted && !approved && <button type="button" disabled={Boolean(busyKey)} onClick={() => void runAction(row, 'approve')} className="clay-button-primary"><ShieldCheck size={13} />Approve</button>}
                  {data.permissions.approve && approved && <button type="button" disabled={Boolean(busyKey)} onClick={() => void runAction(row, 'reopen')} className="clay-button-secondary"><RotateCcw size={13} />Reopen</button>}
                </div>
              </div>
            );
          })}
          {!data.rows.length && <div className="px-5 py-12 text-center text-xs text-slate-400">No students are registered in the selected class.</div>}
        </div>
      </section>
    </section>
  );
}

function OverviewTable({ rows, dashboardPath }: { rows: OverviewRow[]; dashboardPath: string }) {
  return (
    <section className="tafiti-card overflow-hidden">
      <div className="border-b border-slate-100 px-4 py-3.5 sm:px-5"><h2 className="text-sm font-extrabold text-[#10224A]">Assessment workflow</h2><p className="mt-1 text-[10px] text-slate-500">Start with marks entry, submit complete batches, then verify before reporting.</p></div>
      <div className="overflow-x-auto"><table className="w-full min-w-[900px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">CLASS / SUBJECT</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">ASSESSMENT</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">MARKS</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">VERIFIED</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STATUS</th><th className="px-4 py-3 text-right text-[9px] font-extrabold text-slate-400">ACTION</th></tr></thead>
        <tbody className="divide-y divide-slate-100">{rows.map((row) => <tr key={row.assessment_id} className="hover:bg-blue-50/25"><td className="px-4 py-3"><p className="text-xs font-bold text-slate-800">{row.class}</p><p className="mt-0.5 text-[10px] text-slate-500">{row.subject}</p></td><td className="px-4 py-3"><p className="text-xs font-semibold text-slate-700">{row.assessment}</p><p className="mt-0.5 text-[9px] text-slate-400">Out of {row.out_of} · {row.date}</p></td><td className="px-4 py-3 text-xs font-bold text-slate-700">{row.entered}/{row.expected}{row.missing > 0 && <span className="ml-1 text-[9px] font-semibold text-amber-600">({row.missing} missing)</span>}</td><td className="px-4 py-3 text-xs font-bold text-slate-700">{row.verified}/{row.expected}</td><td className="px-4 py-3"><span className={`rounded-full border px-2 py-1 text-[9px] font-bold ${statusClass(row.status)}`}>{row.status}</span></td><td className="px-4 py-3 text-right"><Link href={`${dashboardPath}/results?view=marks&assessment=${row.assessment_id}`} className="inline-flex items-center gap-1 text-[10px] font-bold text-blue-600 hover:underline">Open <ArrowRight size={12} /></Link></td></tr>)}</tbody>
      </table></div>
      {!rows.length && <div className="px-5 py-12 text-center text-xs text-slate-400">No assessments are configured for the current academic period.</div>}
    </section>
  );
}

function ReportCardsTable({ rows, dashboardPath }: { rows: ReportCardRow[]; dashboardPath: string }) {
  return (
    <section className="tafiti-card overflow-hidden">
      <div className="border-b border-slate-100 px-4 py-3.5 sm:px-5"><h2 className="text-sm font-extrabold text-[#10224A]">Class readiness</h2><p className="mt-1 text-[10px] text-slate-500">A class is ready only when marks are verified, class-teacher remarks are submitted and head-teacher approval is complete.</p></div>
      <div className="overflow-x-auto"><table className="w-full min-w-[960px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">CLASS</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STUDENTS</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">ASSESSMENTS</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">REMARKS</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STATUS</th><th className="px-4 py-3 text-right text-[9px] font-extrabold text-slate-400">NEXT ACTION</th></tr></thead>
        <tbody className="divide-y divide-slate-100">{rows.map((row) => <tr key={row.class_id} className="hover:bg-blue-50/25"><td className="px-4 py-3"><p className="text-xs font-bold text-slate-800">{row.class}</p><p className="mt-0.5 text-[9px] text-slate-400">{row.year} · {row.term}</p></td><td className="px-4 py-3 text-xs font-bold text-slate-700">{row.students}</td><td className="px-4 py-3"><p className="text-xs font-bold text-slate-700">{row.verified_assessments}/{row.assessments} verified</p>{row.pending_assessments > 0 && <p className="mt-0.5 text-[9px] font-semibold text-amber-600">{row.pending_assessments} need attention</p>}</td><td className="px-4 py-3 text-xs text-slate-600"><span className="font-bold text-slate-800">{row.submitted_remarks}/{row.students}</span> submitted · <span className="font-bold text-slate-800">{row.approved_remarks}/{row.students}</span> approved</td><td className="px-4 py-3"><span className={`rounded-full border px-2 py-1 text-[9px] font-bold ${statusClass(row.status)}`}>{row.status}</span></td><td className="px-4 py-3 text-right"><div className="flex justify-end gap-3"><Link href={`${dashboardPath}/results?view=report-workflow&class_id=${row.class_id}`} className="inline-flex items-center gap-1 text-[10px] font-bold text-blue-600 hover:underline">Prepare / approve <ArrowRight size={12} /></Link>{row.status === 'Ready' && <Link href={`${dashboardPath}/reports`} className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-600 hover:underline">Reports <FileText size={12} /></Link>}</div></td></tr>)}</tbody>
      </table></div>
      {!rows.length && <div className="px-5 py-12 text-center text-xs text-slate-400">No class report-card work is available for this period.</div>}
    </section>
  );
}

function PerformanceTables({ subjects, classes }: { subjects: PerformanceRow[]; classes: PerformanceRow[] }) {
  const sortedSubjects = useMemo(() => subjects.slice().sort((a, b) => Number(b.average) - Number(a.average)), [subjects]);
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <section className="tafiti-card overflow-hidden"><div className="border-b border-slate-100 px-4 py-3.5"><div className="flex items-center gap-2"><BarChart3 size={16} className="text-blue-600" /><h2 className="text-sm font-extrabold text-[#10224A]">Subject performance</h2></div></div><div className="divide-y divide-slate-100">{sortedSubjects.map((row, index) => <div key={row.subject_id ?? row.subject} className="flex items-center gap-3 px-4 py-3"><span className="grid h-7 w-7 place-items-center rounded-lg bg-blue-50 text-[9px] font-extrabold text-blue-700">{index + 1}</span><div className="min-w-0 flex-1"><p className="truncate text-xs font-bold text-slate-800">{row.subject}</p><p className="mt-0.5 text-[9px] text-slate-400">{row.results} verified results</p></div><p className="text-sm font-extrabold text-[#10224A]">{row.average}%</p></div>)}{!sortedSubjects.length && <div className="px-5 py-12 text-center text-xs text-slate-400">No verified results yet.</div>}</div></section>
      <section className="tafiti-card overflow-hidden"><div className="border-b border-slate-100 px-4 py-3.5"><div className="flex items-center gap-2"><ShieldCheck size={16} className="text-emerald-600" /><h2 className="text-sm font-extrabold text-[#10224A]">Class performance</h2></div></div><div className="divide-y divide-slate-100">{classes.map((row) => <div key={row.class_id ?? row.class} className="flex items-center gap-3 px-4 py-3"><span className="grid h-8 w-8 place-items-center rounded-lg bg-emerald-50 text-emerald-600"><CheckCircle2 size={15} /></span><div className="min-w-0 flex-1"><p className="truncate text-xs font-bold text-slate-800">{row.class}</p><p className="mt-0.5 text-[9px] text-slate-400">{row.results} verified results</p></div><p className="text-sm font-extrabold text-[#10224A]">{row.average}%</p></div>)}{!classes.length && <div className="px-5 py-12 text-center text-xs text-slate-400">No verified class results yet.</div>}</div></section>
    </div>
  );
}
