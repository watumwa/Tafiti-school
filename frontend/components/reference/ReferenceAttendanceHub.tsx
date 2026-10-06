'use client';

import { FormEvent, useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import {
  AlertTriangle,
  CalendarCheck,
  CheckCircle2,
  ChevronRight,
  Clock3,
  History,
  LoaderCircle,
  Search,
  ShieldCheck,
  TrendingUp,
  UserCheck,
  Users,
} from 'lucide-react';

import { useToast } from '@/components/ui/ToastProvider';

type Metric = { label: string; value: number; hint: string; tone: string };
type Option = { id: number; label: string };
type ScheduledRow = {
  lesson_id: number;
  session_id: number | null;
  date: string;
  time: string;
  class_stream_id: number;
  class: string;
  stream: string;
  subject: string;
  teacher: string;
  room: string;
  students: number;
  present: number;
  late: number;
  absent: number;
  excused: number;
  completion: number;
  status: string;
  locked: boolean;
  can_take: boolean;
};
type HistoryRow = {
  id: number;
  date: string;
  time: string;
  class: string;
  stream: string;
  subject: string;
  teacher: string;
  present: number;
  late: number;
  absent: number;
  excused: number;
  attendance_rate: number;
  status: string;
  submitted_at: string;
};
type ReportRow = {
  student_id: string;
  student: string;
  class: string;
  stream: string;
  present: number;
  late: number;
  absent: number;
  excused: number;
  marked: number;
  attendance_rate: number;
  status: string;
};
type AttendanceHubPayload = {
  title: string;
  description: string;
  view: 'today' | 'take' | 'history' | 'reports';
  selected_date: string;
  academic_context: { year: string; term: string };
  metrics: Metric[];
  scheduled: ScheduledRow[];
  history: HistoryRow[];
  reports: ReportRow[];
  report_minimum: number;
  class_streams: Option[];
  filters: {
    date: string;
    date_from: string;
    date_to: string;
    class_stream: number | null;
    state: string;
    q: string;
  };
  actions: { can_take: boolean; is_manager: boolean; role: string };
};

const TABS = [
  { value: 'today', label: 'Today', icon: CalendarCheck },
  { value: 'take', label: 'Take Attendance', icon: UserCheck },
  { value: 'history', label: 'History', icon: History },
  { value: 'reports', label: 'Reports', icon: TrendingUp },
] as const;

function readableDate(value: string) {
  if (!value) return '—';
  const [year, month, day] = value.slice(0, 10).split('-').map(Number);
  const parsed = new Date(year, month - 1, day);
  return new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }).format(parsed);
}

function sessionStatusClass(value: string) {
  const status = value.toLowerCase();
  if (status.includes('submitted')) return 'border-emerald-100 bg-emerald-50 text-emerald-700';
  if (status.includes('progress') || status.includes('open')) return 'border-amber-100 bg-amber-50 text-amber-700';
  return 'border-slate-200 bg-slate-50 text-slate-600';
}

function metricIcon(label: string) {
  const value = label.toLowerCase();
  if (value.includes('submitted')) return CheckCircle2;
  if (value.includes('pending')) return Clock3;
  if (value.includes('absent')) return AlertTriangle;
  return CalendarCheck;
}

export function ReferenceAttendanceHub({ dashboardPath }: { dashboardPath: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  const [data, setData] = useState<AttendanceHubPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState(searchParams.get('q') ?? '');
  const [startingLesson, setStartingLesson] = useState<number | null>(null);
  const queryString = searchParams.toString();

  useEffect(() => setQuery(searchParams.get('q') ?? ''), [searchParams]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetch(`/api/workspace/attendance-console/hub${queryString ? `?${queryString}` : ''}`, {
      cache: 'no-store',
      signal: controller.signal,
    })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Attendance could not be loaded.');
        return payload as AttendanceHubPayload;
      })
      .then((payload) => setData(payload))
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Attendance could not be loaded.');
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [queryString]);

  function updateFilter(key: string, value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value) params.set(key, value); else params.delete(key);
    router.replace(`${pathname}${params.toString() ? `?${params.toString()}` : ''}`, { scroll: false });
  }

  function changeView(view: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (view === 'today') params.delete('view'); else params.set('view', view);
    router.replace(`${pathname}${params.toString() ? `?${params.toString()}` : ''}`, { scroll: false });
  }

  function submitSearch(event: FormEvent) {
    event.preventDefault();
    updateFilter('q', query.trim());
  }

  async function openRegister(row: ScheduledRow) {
    if (row.session_id) {
      const returnValue = `${pathname}${queryString ? `?${queryString}` : ''}`;
      router.push(`${dashboardPath}/attendance/${row.session_id}?return=${encodeURIComponent(returnValue)}`);
      return;
    }
    setStartingLesson(row.lesson_id);
    try {
      const response = await fetch('/api/workspace/attendance-console/hub', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'start', lesson_id: row.lesson_id, date: data?.selected_date }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Attendance register could not be opened.');
      const returnValue = `${pathname}${queryString ? `?${queryString}` : ''}`;
      router.push(`${dashboardPath}/attendance/${payload.session_id}?return=${encodeURIComponent(returnValue)}`);
    } catch (reason: unknown) {
      toast.error('Could not open register', reason instanceof Error ? reason.message : 'Please try again.');
    } finally {
      setStartingLesson(null);
    }
  }

  if (loading && !data) return <div className="tafiti-card grid min-h-[460px] place-items-center"><div className="text-center text-xs font-semibold text-slate-500"><LoaderCircle className="mx-auto mb-3 animate-spin text-blue-600" size={24} />Opening attendance workspace…</div></div>;
  if (error && !data) return <div className="tafiti-card grid min-h-[420px] place-items-center p-6 text-center"><div><AlertTriangle className="mx-auto text-red-500" size={24} /><h2 className="mt-3 text-sm font-extrabold text-slate-900">Attendance unavailable</h2><p className="mt-2 text-xs text-slate-500">{error}</p></div></div>;
  if (!data) return null;

  return (
    <section className="space-y-4">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-[9px] font-extrabold uppercase tracking-[.14em] text-blue-600">Academics · Attendance</p>
          <h1 className="mt-1 text-2xl font-extrabold tracking-[-.035em] text-[#10224A]">{data.title}</h1>
          <p className="mt-1 max-w-3xl text-[11px] leading-5 text-slate-500">{data.description}</p>
        </div>
        <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-[9px] font-bold text-slate-500"><ShieldCheck size={14} className="text-blue-600" />{data.academic_context.year || 'Academic year'} · {data.academic_context.term || 'Term'}</div>
      </header>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {data.metrics.map((metric) => {
          const Icon = metricIcon(metric.label);
          return <article key={metric.label} className="tafiti-kpi"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-blue-50 text-blue-600"><Icon size={17} /></span><div><p className="text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">{metric.label}</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{metric.value}</p><p className="mt-0.5 text-[9px] text-slate-400">{metric.hint}</p></div></div></article>;
        })}
      </div>

      <section className="tafiti-card overflow-hidden">
        <div className="overflow-x-auto border-b border-slate-100 px-3 py-2">
          <div className="flex min-w-max gap-1">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              const active = data.view === tab.value;
              return <button key={tab.value} type="button" onClick={() => changeView(tab.value)} className={`inline-flex h-9 items-center gap-1.5 rounded-lg px-3 text-[10px] font-extrabold transition ${active ? 'bg-blue-600 text-white shadow-[0_5px_12px_rgba(37,99,235,.18)]' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'}`}><Icon size={13} />{tab.label}</button>;
            })}
          </div>
        </div>

        {(data.view === 'today' || data.view === 'take') && <>
          <div className="flex flex-col gap-3 border-b border-slate-100 bg-[#FBFCFE] p-3 sm:flex-row sm:items-center sm:justify-between">
            <div><p className="text-[9px] font-extrabold uppercase tracking-[.08em] text-slate-400">Lesson date</p><p className="mt-1 text-xs font-extrabold text-[#10224A]">{readableDate(data.selected_date)}</p></div>
            <input type="date" value={data.selected_date} onChange={(event) => updateFilter('date', event.target.value)} className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-[10px] font-bold text-slate-600 outline-none focus:border-blue-400" />
          </div>
          {data.scheduled.length ? <div className="divide-y divide-slate-100">{data.scheduled.map((row) => <article key={row.lesson_id} className="grid gap-3 px-4 py-4 transition hover:bg-blue-50/20 sm:px-5 lg:grid-cols-[115px_minmax(0,1.2fr)_minmax(0,.9fr)_180px_130px] lg:items-center"><div><p className="text-xs font-extrabold text-[#10224A]">{row.time}</p><p className="mt-1 text-[9px] text-slate-400">{row.room}</p></div><div><p className="text-xs font-extrabold text-slate-800">{row.class} · {row.stream}</p><p className="mt-1 text-[10px] font-semibold text-blue-700">{row.subject}</p><p className="mt-1 text-[9px] text-slate-400">{row.teacher} · {row.students} students</p></div><div><div className="flex flex-wrap gap-1.5"><span className="rounded-full bg-emerald-50 px-2 py-1 text-[8px] font-extrabold text-emerald-700">P {row.present}</span><span className="rounded-full bg-amber-50 px-2 py-1 text-[8px] font-extrabold text-amber-700">L {row.late}</span><span className="rounded-full bg-rose-50 px-2 py-1 text-[8px] font-extrabold text-rose-700">A {row.absent}</span><span className="rounded-full bg-blue-50 px-2 py-1 text-[8px] font-extrabold text-blue-700">E {row.excused}</span></div>{row.session_id && <div className="mt-2 flex items-center gap-2"><div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-blue-600" style={{ width: `${row.completion}%` }} /></div><span className="text-[8px] font-bold text-slate-400">{row.completion}%</span></div>}</div><div><span className={`inline-flex rounded-full border px-2.5 py-1 text-[8px] font-extrabold ${sessionStatusClass(row.status)}`}>{row.status}</span></div><div className="lg:text-right"><button type="button" disabled={startingLesson === row.lesson_id || !row.can_take} onClick={() => void openRegister(row)} className={row.locked ? 'clay-button-secondary' : 'clay-button-primary'}>{startingLesson === row.lesson_id ? <LoaderCircle size={13} className="animate-spin" /> : row.locked ? <History size={13} /> : <UserCheck size={13} />}{row.locked ? 'View' : row.session_id ? 'Continue' : 'Take attendance'}</button>{!row.can_take && <p className="mt-1 text-[8px] text-amber-600">Teacher assignment required</p>}</div></article>)}</div> : <div className="grid min-h-[260px] place-items-center p-6 text-center"><div><CalendarCheck className="mx-auto text-blue-300" size={30} /><h3 className="mt-3 text-sm font-extrabold text-slate-800">No scheduled lessons</h3><p className="mt-1 text-[10px] text-slate-400">There are no timetable lessons available to your role on this date.</p></div></div>}
        </>}

        {data.view === 'history' && <>
          <div className="grid gap-2 border-b border-slate-100 bg-[#FBFCFE] p-3 md:grid-cols-2 xl:grid-cols-[1.4fr_1fr_1fr_.85fr_.85fr]">
            <form onSubmit={submitSearch} className="relative"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search class, subject or teacher…" className="h-10 w-full rounded-xl border border-slate-200 bg-white pl-9 pr-3 text-[10px] font-semibold text-slate-700 outline-none focus:border-blue-400" /></form>
            <select value={data.filters.class_stream ?? ''} onChange={(event) => updateFilter('class_stream', event.target.value)} className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-[10px] font-bold text-slate-600 outline-none"><option value="">All classes</option>{data.class_streams.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select>
            <select value={data.filters.state} onChange={(event) => updateFilter('state', event.target.value)} className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-[10px] font-bold text-slate-600 outline-none"><option value="all">All session states</option><option value="submitted">Submitted</option><option value="open">Open</option></select>
            <input type="date" value={data.filters.date_from} onChange={(event) => updateFilter('date_from', event.target.value)} className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-[10px] font-bold text-slate-600 outline-none" />
            <input type="date" value={data.filters.date_to} onChange={(event) => updateFilter('date_to', event.target.value)} className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-[10px] font-bold text-slate-600 outline-none" />
          </div>
          {data.history.length ? <div className="overflow-x-auto"><table className="w-full min-w-[1050px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">DATE / TIME</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">CLASS</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">SUBJECT</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">TEACHER</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">P / L / A / E</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">RATE</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STATUS</th><th className="w-10" /></tr></thead><tbody className="divide-y divide-slate-100">{data.history.map((row) => <tr key={row.id} className="group hover:bg-blue-50/20"><td className="px-4 py-3"><p className="text-[10px] font-extrabold text-slate-700">{readableDate(row.date)}</p><p className="mt-0.5 text-[9px] text-slate-400">{row.time}</p></td><td className="px-4 py-3"><p className="text-[10px] font-bold text-slate-700">{row.class}</p><p className="text-[9px] text-slate-400">{row.stream}</p></td><td className="px-4 py-3 text-[10px] font-bold text-blue-700">{row.subject}</td><td className="px-4 py-3 text-[10px] text-slate-500">{row.teacher}</td><td className="px-4 py-3 text-[10px] font-bold text-slate-600">{row.present} / {row.late} / {row.absent} / {row.excused}</td><td className="px-4 py-3 text-[10px] font-extrabold text-slate-700">{row.attendance_rate}%</td><td className="px-4 py-3"><span className={`rounded-full border px-2 py-1 text-[8px] font-extrabold ${sessionStatusClass(row.status)}`}>{row.status}</span></td><td className="px-3"><Link href={`${dashboardPath}/attendance/${row.id}?return=${encodeURIComponent(`${pathname}?${queryString}`)}`} className="grid h-8 w-8 place-items-center rounded-lg text-slate-300 group-hover:bg-white group-hover:text-blue-600"><ChevronRight size={15} /></Link></td></tr>)}</tbody></table></div> : <div className="grid min-h-[250px] place-items-center p-6 text-center text-xs text-slate-400">No attendance sessions match these filters.</div>}
        </>}

        {data.view === 'reports' && <>
          <div className="grid gap-2 border-b border-slate-100 bg-[#FBFCFE] p-3 sm:grid-cols-3"><select value={data.filters.class_stream ?? ''} onChange={(event) => updateFilter('class_stream', event.target.value)} className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-[10px] font-bold text-slate-600 outline-none"><option value="">All classes</option>{data.class_streams.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select><input type="date" value={data.filters.date_from} onChange={(event) => updateFilter('date_from', event.target.value)} className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-[10px] font-bold text-slate-600 outline-none" /><input type="date" value={data.filters.date_to} onChange={(event) => updateFilter('date_to', event.target.value)} className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-[10px] font-bold text-slate-600 outline-none" /></div>
          <div className="flex items-center gap-2 border-b border-blue-100 bg-blue-50 px-4 py-3 text-[10px] text-blue-800 sm:px-5"><TrendingUp size={14} /><span>Attendance alert threshold: <b>{data.report_minimum}%</b>. Present, late and excused sessions count as attended.</span></div>
          {data.reports.length ? <div className="overflow-x-auto"><table className="w-full min-w-[980px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STUDENT</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">CLASS</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">MARKED</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">PRESENT</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">LATE</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">ABSENT</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">EXCUSED</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">RATE</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STATUS</th></tr></thead><tbody className="divide-y divide-slate-100">{data.reports.map((row) => <tr key={`${row.student_id}-${row.class}-${row.stream}`} className="hover:bg-blue-50/20"><td className="px-4 py-3"><p className="text-[10px] font-extrabold text-slate-800">{row.student}</p><p className="mt-0.5 text-[9px] text-slate-400">{row.student_id}</p></td><td className="px-4 py-3"><p className="text-[10px] font-bold text-slate-700">{row.class}</p><p className="text-[9px] text-slate-400">{row.stream}</p></td><td className="px-4 py-3 text-[10px] font-bold text-slate-600">{row.marked}</td><td className="px-4 py-3 text-[10px] font-bold text-emerald-700">{row.present}</td><td className="px-4 py-3 text-[10px] font-bold text-amber-700">{row.late}</td><td className="px-4 py-3 text-[10px] font-bold text-rose-700">{row.absent}</td><td className="px-4 py-3 text-[10px] font-bold text-blue-700">{row.excused}</td><td className="px-4 py-3 text-xs font-extrabold text-[#10224A]">{row.attendance_rate}%</td><td className="px-4 py-3"><span className={`rounded-full border px-2 py-1 text-[8px] font-extrabold ${row.status === 'On track' ? 'border-emerald-100 bg-emerald-50 text-emerald-700' : 'border-rose-100 bg-rose-50 text-rose-700'}`}>{row.status}</span></td></tr>)}</tbody></table></div> : <div className="grid min-h-[250px] place-items-center p-6 text-center text-xs text-slate-400">No marked attendance is available in this reporting range.</div>}
        </>}
      </section>
    </section>
  );
}
