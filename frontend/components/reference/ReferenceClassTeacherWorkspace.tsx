'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  AlertCircle,
  ArrowRight,
  BookOpenCheck,
  CalendarCheck,
  CalendarDays,
  ClipboardPenLine,
  FileText,
  LoaderCircle,
  RefreshCw,
  Users,
} from 'lucide-react';

import type { WorkspaceStat } from '@/lib/workspace';

type ClassStream = { id: number; label: string; students: number };
type ClassStudent = {
  id: number;
  name: string;
  admission_no: string;
  photo: string;
  class_stream_id: number;
  class: string;
  stream: string;
  attendance_status: string;
  attendance_percent: number | null;
  average: string;
  missing_marks: number;
  remark_status: string;
};
type TimetableRow = { id: number; time: string; subject: string; class: string; stream: string; teacher: string; room: string };
type AssessmentRow = { id: number; date: string; class: string; subject: string; assessment: string; out_of: number };

export type ClassTeacherWorkspaceData = {
  title: string;
  description: string;
  date: string;
  assigned_classes: ClassStream[];
  metrics: WorkspaceStat[];
  students: ClassStudent[];
  timetable: TimetableRow[];
  upcoming_assessments: AssessmentRow[];
};

const tone: Record<WorkspaceStat['tone'], string> = {
  green: 'border-emerald-100 bg-emerald-50 text-emerald-700',
  blue: 'border-blue-100 bg-blue-50 text-blue-700',
  gold: 'border-amber-100 bg-amber-50 text-amber-700',
  violet: 'border-violet-100 bg-violet-50 text-violet-700',
};

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase() || 'S';
}

function readableDate(value: string) {
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short' }).format(date);
}

function statusClass(value: string) {
  const normalized = value.toLowerCase();
  if (normalized === 'present' || normalized === 'submitted') return 'border-emerald-100 bg-emerald-50 text-emerald-700';
  if (normalized === 'late' || normalized === 'draft') return 'border-amber-100 bg-amber-50 text-amber-700';
  if (normalized === 'absent' || normalized === 'needed') return 'border-red-100 bg-red-50 text-red-700';
  if (normalized === 'excused') return 'border-violet-100 bg-violet-50 text-violet-700';
  return 'border-slate-200 bg-slate-50 text-slate-500';
}

function useClassTeacherWorkspace() {
  const [data, setData] = useState<ClassTeacherWorkspaceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetch('/api/workspace/my-class', { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'The class workspace could not be loaded.');
        return payload as ClassTeacherWorkspaceData;
      })
      .then(setData)
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'The class workspace could not be loaded.');
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [reloadKey]);

  return { data, loading, error, refresh: () => setReloadKey((value) => value + 1) };
}

function ClassMetrics({ metrics }: { metrics: WorkspaceStat[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric) => (
        <article key={metric.label} className="tafiti-kpi min-w-0">
          <span className={`inline-flex rounded-lg border px-2 py-1 text-[8px] font-extrabold uppercase tracking-[.08em] ${tone[metric.tone]}`}>{metric.label}</span>
          <p className="mt-3 truncate text-2xl font-extrabold tracking-[-0.035em] text-[#10224A]">{metric.value}</p>
          <p className="mt-1 truncate text-[10px] font-semibold text-slate-500">{metric.hint}</p>
        </article>
      ))}
    </div>
  );
}

export function ClassTeacherDashboardPanel({ dashboardPath }: { dashboardPath: string }) {
  const { data, loading, error, refresh } = useClassTeacherWorkspace();

  if (loading && !data) return <section className="grid min-h-[190px] place-items-center rounded-2xl border border-slate-100 bg-white"><LoaderCircle className="animate-spin text-blue-600" size={22} /></section>;
  if (error && !data) return <section className="rounded-2xl border border-red-100 bg-red-50 p-4"><div className="flex items-start gap-3"><AlertCircle className="mt-0.5 shrink-0 text-red-500" size={18} /><div><p className="text-xs font-bold text-red-900">My Class could not be loaded</p><p className="mt-1 text-[11px] text-red-700">{error}</p><button type="button" onClick={refresh} className="mt-3 text-[11px] font-bold text-red-700 underline">Try again</button></div></div></section>;
  if (!data) return null;

  const upcoming = data.upcoming_assessments[0];
  return (
    <section className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(310px,.8fr)]">
      <article className="tafiti-card overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-slate-100 px-4 py-4 sm:flex-row sm:items-start sm:justify-between sm:px-5">
          <div><div className="flex items-center gap-2"><span className="grid h-8 w-8 place-items-center rounded-lg bg-blue-50 text-blue-600"><Users size={16} /></span><h2 className="text-sm font-extrabold text-[#10224A]">My Class pulse</h2></div><p className="mt-2 text-[11px] text-slate-500">Your learner register, follow-up work and today&apos;s class activity.</p></div>
          <Link href={`${dashboardPath}/my-class`} className="inline-flex items-center gap-1 text-[11px] font-bold text-blue-600 hover:underline">Open My Class <ArrowRight size={13} /></Link>
        </div>
        <div className="grid gap-2.5 p-4 sm:grid-cols-3 sm:p-5">
          <Link href={`${dashboardPath}/attendance`} className="rounded-xl border border-slate-100 bg-[#F8FAFD] p-3 transition hover:border-blue-200"><CalendarCheck size={16} className="text-blue-600" /><p className="mt-2 text-xs font-bold text-slate-800">Attendance</p><p className="mt-1 text-[10px] leading-4 text-slate-500">{data.metrics.find((metric) => metric.label === 'Attendance today')?.hint || 'Review today’s register'}</p></Link>
          <Link href={`${dashboardPath}/results?view=marks`} className="rounded-xl border border-slate-100 bg-[#F8FAFD] p-3 transition hover:border-blue-200"><ClipboardPenLine size={16} className="text-amber-600" /><p className="mt-2 text-xs font-bold text-slate-800">Marks follow-up</p><p className="mt-1 text-[10px] leading-4 text-slate-500">{data.metrics.find((metric) => metric.label === 'Marks to follow up')?.value || 0} expected mark{data.metrics.find((metric) => metric.label === 'Marks to follow up')?.value === 1 ? '' : 's'} not entered.</p></Link>
          <Link href={`${dashboardPath}/results?view=report-cards`} className="rounded-xl border border-slate-100 bg-[#F8FAFD] p-3 transition hover:border-blue-200"><FileText size={16} className="text-violet-600" /><p className="mt-2 text-xs font-bold text-slate-800">Report cards</p><p className="mt-1 text-[10px] leading-4 text-slate-500">{data.metrics.find((metric) => metric.label === 'Remarks needed')?.value || 0} class remark{data.metrics.find((metric) => metric.label === 'Remarks needed')?.value === 1 ? '' : 's'} still needed.</p></Link>
        </div>
      </article>
      <article className="tafiti-card p-4 sm:p-5">
        <div className="flex items-center gap-2"><CalendarDays size={17} className="text-blue-600" /><h2 className="text-sm font-extrabold text-[#10224A]">Next assessment</h2></div>
        {upcoming ? <div className="mt-4 rounded-xl border border-blue-100 bg-blue-50/60 p-3.5"><p className="text-xs font-extrabold text-slate-800">{upcoming.subject}</p><p className="mt-1 text-[10px] text-slate-500">{upcoming.assessment} · {upcoming.class} · out of {upcoming.out_of}</p><p className="mt-3 text-[11px] font-bold text-blue-700">{readableDate(upcoming.date)}</p></div> : <div className="mt-4 rounded-xl border border-slate-100 bg-[#F8FAFD] p-4 text-center text-[11px] text-slate-500">No upcoming assessment is scheduled for your assigned class.</div>}
        <Link href={`${dashboardPath}/timetable`} className="mt-3 inline-flex items-center gap-1 text-[10px] font-bold text-blue-600 hover:underline">View timetable <ArrowRight size={12} /></Link>
      </article>
    </section>
  );
}

export function ReferenceClassTeacherWorkspace({ dashboardPath }: { dashboardPath: string }) {
  const { data, loading, error, refresh } = useClassTeacherWorkspace();
  const [selectedStream, setSelectedStream] = useState('all');
  const students = useMemo(() => (
    data?.students.filter((student) => selectedStream === 'all' || String(student.class_stream_id) === selectedStream) ?? []
  ), [data, selectedStream]);

  if (loading && !data) return <div className="tafiti-card grid min-h-[460px] place-items-center"><div className="text-center text-xs font-semibold text-slate-500"><LoaderCircle className="mx-auto mb-3 animate-spin text-blue-600" size={24} />Opening your class workspace…</div></div>;
  if (error && !data) return <div className="tafiti-card p-7 text-center"><AlertCircle className="mx-auto text-red-500" size={24} /><p className="mt-3 text-sm font-bold text-slate-800">My Class is unavailable</p><p className="mx-auto mt-2 max-w-md text-xs leading-5 text-slate-500">{error}</p><button type="button" className="clay-button-primary mt-4" onClick={refresh}>Try again</button></div>;
  if (!data) return null;

  return (
    <section>
      <header className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex items-start gap-3"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-blue-50 text-blue-600"><Users size={21} /></span><div><p className="text-[9px] font-extrabold uppercase tracking-[.14em] text-blue-600">Class teacher workspace</p><h1 className="mt-0.5 text-[1.65rem] font-extrabold tracking-[-0.035em] text-[#10224A]">{data.title}</h1><p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">{data.description}</p></div></div>
        <div className="flex flex-wrap gap-2"><button type="button" onClick={refresh} className="clay-button-secondary"><RefreshCw size={14} />Refresh</button><Link href={`${dashboardPath}/attendance`} className="clay-button-secondary"><CalendarCheck size={14} />Take attendance</Link><Link href={`${dashboardPath}/results?view=marks`} className="clay-button-primary"><ClipboardPenLine size={14} />Enter marks</Link></div>
      </header>

      <ClassMetrics metrics={data.metrics} />

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(300px,.7fr)]">
        <section className="tafiti-card overflow-hidden">
          <div className="flex flex-col gap-3 border-b border-slate-100 px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between sm:px-5"><div><h2 className="text-sm font-extrabold text-[#10224A]">Class register</h2><p className="mt-1 text-[10px] text-slate-500">Learners assigned to you in the current academic period.</p></div>{data.assigned_classes.length > 1 && <select value={selectedStream} onChange={(event) => setSelectedStream(event.target.value)} className="tafiti-input h-9 min-w-[180px] px-3 text-xs"><option value="all">All assigned streams</option>{data.assigned_classes.map((stream) => <option key={stream.id} value={stream.id}>{stream.label} · {stream.students}</option>)}</select>}</div>
          <div className="overflow-x-auto"><table className="w-full min-w-[900px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]">{['Learner','Class','Today','Attendance','Average','Follow-up','Profile'].map((label) => <th key={label} className="px-4 py-3 text-[9px] font-extrabold uppercase tracking-[.05em] text-slate-400">{label}</th>)}</tr></thead><tbody className="divide-y divide-slate-100">{students.map((student) => <tr key={student.id} className="hover:bg-blue-50/25"><td className="px-4 py-3"><div className="flex items-center gap-2.5"><span className="grid h-9 w-9 shrink-0 place-items-center overflow-hidden rounded-full bg-blue-50 text-[10px] font-extrabold text-blue-700">{student.photo ? <img src={student.photo} alt="" className="h-full w-full object-cover" /> : initials(student.name)}</span><div className="min-w-0"><p className="truncate text-xs font-bold text-slate-800">{student.name}</p><p className="mt-0.5 text-[9px] text-slate-400">{student.admission_no}</p></div></div></td><td className="px-4 py-3 text-xs font-semibold text-slate-600">{student.class} · {student.stream}</td><td className="px-4 py-3"><span className={`rounded-full border px-2 py-1 text-[9px] font-bold ${statusClass(student.attendance_status)}`}>{student.attendance_status}</span></td><td className="px-4 py-3 text-xs font-bold text-slate-700">{student.attendance_percent === null ? '—' : `${student.attendance_percent}%`}</td><td className="px-4 py-3 text-xs font-bold text-slate-700">{student.average}</td><td className="px-4 py-3"><p className={`text-[10px] font-bold ${student.missing_marks ? 'text-amber-700' : 'text-emerald-700'}`}>{student.missing_marks ? `${student.missing_marks} mark${student.missing_marks === 1 ? '' : 's'} missing` : 'Marks complete'}</p><p className={`mt-1 text-[9px] font-semibold ${student.remark_status === 'Needed' ? 'text-violet-700' : 'text-slate-400'}`}>Remark: {student.remark_status}</p></td><td className="px-4 py-3 text-right"><Link href={`${dashboardPath}/students/${student.id}`} className="inline-flex items-center gap-1 text-[10px] font-bold text-blue-600 hover:underline">Open <ArrowRight size={12} /></Link></td></tr>)}</tbody></table></div>
          {!students.length && <div className="px-5 py-12 text-center text-xs text-slate-400">No active learners are registered in your assigned class yet.</div>}
        </section>

        <aside className="space-y-4">
          <section className="tafiti-card overflow-hidden"><div className="border-b border-slate-100 px-4 py-3.5"><div className="flex items-center gap-2"><BookOpenCheck size={16} className="text-blue-600" /><h2 className="text-sm font-extrabold text-[#10224A]">Today&apos;s timetable</h2></div></div><div className="divide-y divide-slate-100">{data.timetable.map((lesson) => <div key={lesson.id} className="px-4 py-3"><div className="flex items-center justify-between gap-3"><p className="text-xs font-bold text-slate-800">{lesson.subject}</p><span className="text-[9px] font-bold text-blue-700">{lesson.time}</span></div><p className="mt-1 text-[10px] text-slate-500">{lesson.class} · {lesson.stream} · {lesson.room}</p></div>)}{!data.timetable.length && <div className="px-4 py-9 text-center text-[11px] text-slate-400">No lessons are scheduled for this class today.</div>}</div></section>
          <section className="tafiti-card overflow-hidden"><div className="border-b border-slate-100 px-4 py-3.5"><div className="flex items-center gap-2"><CalendarDays size={16} className="text-violet-600" /><h2 className="text-sm font-extrabold text-[#10224A]">Upcoming assessments</h2></div></div><div className="divide-y divide-slate-100">{data.upcoming_assessments.map((assessment) => <div key={assessment.id} className="px-4 py-3"><p className="text-xs font-bold text-slate-800">{assessment.subject}</p><p className="mt-1 text-[10px] text-slate-500">{assessment.assessment} · {assessment.class} · out of {assessment.out_of}</p><p className="mt-1.5 text-[10px] font-bold text-violet-700">{readableDate(assessment.date)}</p></div>)}{!data.upcoming_assessments.length && <div className="px-4 py-9 text-center text-[11px] text-slate-400">No upcoming assessments are scheduled.</div>}</div><Link href={`${dashboardPath}/results?view=report-cards`} className="flex items-center justify-center gap-1 border-t border-slate-100 px-4 py-3 text-[10px] font-bold text-blue-600 hover:bg-blue-50">Open report-card workflow <ArrowRight size={12} /></Link></section>
        </aside>
      </div>
    </section>
  );
}
