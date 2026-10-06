'use client';

import { FormEvent, ReactNode, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  AlertCircle,
  ArrowRight,
  BookOpenCheck,
  CalendarCheck,
  CalendarDays,
  CheckCircle2,
  Clock3,
  Download,
  FileText,
  GraduationCap,
  LoaderCircle,
  Mail,
  MapPin,
  MessageCircle,
  ReceiptText,
  RefreshCw,
  Send,
  TrendingUp,
  UserRound,
  UsersRound,
  WalletCards,
} from 'lucide-react';

import { useToast } from '@/components/ui/ToastProvider';
import { ParentPortalView } from '@/components/workspace/ParentPortalView';

type ParentChild = {
  id: number;
  name: string;
  student_id: string;
  class: string;
  stream: string;
  photo: string;
  attendance_percent: number | null;
  academic_average: number | null;
  outstanding_balance: string | null;
  total_billed: string | null;
  total_paid: string | null;
  active_loans: number;
  overdue_loans: number;
  permissions: { academics: boolean; finance: boolean; attendance: boolean };
};

type ChildrenPayload = { term: string; children: ParentChild[] };
type ResultsPayload = {
  term: { id: number; label: string } | null;
  terms: { id: number; label: string }[];
  students: { id: number; name: string }[];
  results: { id: number; student_id: number; student: string; subject: string; assessment: string; date: string; score: string; out_of: number; percentage: number; grade: string }[];
  performance: { student_id: number; student: string; subject: string; average: number | null; class_average: number | null; rank: number | null; class_size: number; grade: string; assessment_count: number }[];
};
type AttendancePayload = {
  students: { id: number; name: string }[];
  totals: { present: number; absent: number; late: number; excused: number };
  records: { id: number; student_id: number; student: string; date: string; class: string; subject: string; status: string; remarks: string }[];
};
type FinancePayload = {
  students: { id: number; name: string }[];
  summary: { billed: string; paid: string; balance: string };
  bills: { id: number; student_id: number; student: string; term: string; date: string; due_date: string; billed: string; paid: string; balance: string; status: string; items: { description: string; amount: string }[] }[];
  payments: { id: number; student_id: number; student: string; date: string; amount: string; method: string; reference: string }[];
};
type CalendarPayload = { events: { id: number; title: string; description: string; location: string; start: string; end: string }[] };
type MessagePayload = {
  children: { id: number; name: string }[];
  teachers: Record<string, { id: number; name: string }[]>;
  conversations: { id: number; student_id: number; student: string; teacher: string; subject: string; updated_at: string; active: boolean; messages: { id: number; sender: string; from_parent: boolean; body: string; created_at: string }[] }[];
};
type ReportsPayload = { students: { id: number; name: string }[]; terms: { id: number; label: string }[]; current_term_id: number | null };
type ApiError = { detail?: string; errors?: Record<string, string[]> };

const REFERENCE_SCREENS = new Set([
  'parent-children',
  'parent-results',
  'parent-attendance',
  'parent-finance',
  'parent-communication',
  'parent-calendar',
  'parent-reports',
]);

function readableDate(value: string, withTime = false) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, withTime
    ? { dateStyle: 'medium', timeStyle: 'short' }
    : { day: 'numeric', month: 'short', year: 'numeric' }).format(parsed);
}

function money(value: number | string | null) {
  if (value === null || value === '') return '—';
  return `UGX ${Number(value).toLocaleString('en-UG', { maximumFractionDigits: 0 })}`;
}

function childPhoto(photo: string) {
  return photo.startsWith('/') ? `/api/media${photo}` : photo;
}

async function parseResponse<T>(response: Response): Promise<T> {
  const payload = await response.json() as T & ApiError;
  if (!response.ok) throw new Error(payload.detail || Object.values(payload.errors ?? {}).flat()[0] || 'The request could not be completed.');
  return payload;
}

function SectionHeading({ icon, eyebrow, title, description, action }: { icon: ReactNode; eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="flex items-start gap-3">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-blue-50 text-blue-600">{icon}</span>
        <div><p className="text-[9px] font-extrabold uppercase tracking-[.12em] text-blue-600">{eyebrow}</p><h2 className="mt-1 text-xl font-extrabold tracking-[-.03em] text-[#10224A]">{title}</h2><p className="mt-1 max-w-2xl text-[11px] leading-5 text-slate-500">{description}</p></div>
      </div>
      {action}
    </div>
  );
}

function Metric({ label, value, hint, icon, tone = 'blue' }: { label: string; value: string | number; hint: string; icon: ReactNode; tone?: 'blue' | 'green' | 'amber' | 'violet' | 'rose' }) {
  const tones = {
    blue: 'bg-blue-50 text-blue-600', green: 'bg-emerald-50 text-emerald-600', amber: 'bg-amber-50 text-amber-600', violet: 'bg-violet-50 text-violet-600', rose: 'bg-rose-50 text-rose-600',
  };
  return <article className="tafiti-kpi"><div className="flex items-center gap-3"><span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${tones[tone]}`}>{icon}</span><div className="min-w-0"><p className="truncate text-lg font-extrabold text-[#10224A]">{value}</p><p className="text-[9px] font-bold text-slate-500">{label}</p><p className="mt-0.5 truncate text-[8px] text-slate-400">{hint}</p></div></div></article>;
}

function EmptyState({ icon, title, text }: { icon: ReactNode; title: string; text: string }) {
  return <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-5 py-10 text-center"><span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-slate-50 text-slate-300">{icon}</span><p className="mt-3 text-sm font-extrabold text-slate-700">{title}</p><p className="mt-1 text-[10px] leading-5 text-slate-400">{text}</p></div>;
}

function Selector({ label, value, onChange, children }: { label: string; value: string; onChange: (value: string) => void; children: ReactNode }) {
  return <label className="block min-w-[180px] flex-1 text-[9px] font-extrabold uppercase tracking-[.06em] text-slate-400">{label}<select value={value} onChange={(event) => onChange(event.target.value)} className="tafiti-input mt-1.5 h-10 w-full bg-white px-3 text-xs font-bold normal-case tracking-normal text-slate-700">{children}</select></label>;
}

export function ReferenceParentPortalContent({ screen, dashboardPath }: { screen: string; dashboardPath: string }) {
  const toast = useToast();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [data, setData] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  const action = screen.replace(/^parent-/, '');
  const query = useMemo(() => {
    if (!['results', 'attendance', 'finance'].includes(action)) return '';
    const params = new URLSearchParams();
    const student = searchParams.get('student');
    const term = searchParams.get('term');
    if (student) params.set('student', student);
    if (action === 'results' && term) params.set('term', term);
    return params.toString();
  }, [action, searchParams]);

  useEffect(() => {
    if (!REFERENCE_SCREENS.has(screen)) return;
    const controller = new AbortController();
    setLoading(true); setError('');
    fetch(`/api/workspace/parent/${action}${query ? `?${query}` : ''}`, { cache: 'no-store', signal: controller.signal })
      .then((response) => parseResponse<unknown>(response))
      .then(setData)
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        const message = reason instanceof Error ? reason.message : 'This parent page could not be loaded.';
        setError(message); toast.error('Parent portal unavailable', message);
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [action, query, reloadKey, screen, toast]);

  function setFilters(values: Record<string, string>) {
    const params = new URLSearchParams(searchParams.toString());
    Object.entries(values).forEach(([key, value]) => value ? params.set(key, value) : params.delete(key));
    router.replace(`${window.location.pathname}${params.size ? `?${params.toString()}` : ''}`, { scroll: false });
  }

  if (!REFERENCE_SCREENS.has(screen)) return <ParentPortalView screen={screen} dashboardPath={dashboardPath} />;
  if (loading && !data) return <div className="space-y-4"><div className="h-20 animate-pulse rounded-2xl bg-white" /><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{Array.from({ length: 4 }, (_, index) => <div key={index} className="h-24 animate-pulse rounded-2xl bg-white" />)}</div><div className="h-72 animate-pulse rounded-2xl bg-white" /></div>;
  if (error && !data) return <div className="tafiti-card grid min-h-[340px] place-items-center p-6 text-center"><div><AlertCircle className="mx-auto text-rose-500" size={26} /><p className="mt-3 text-sm font-extrabold text-slate-800">This parent page is unavailable</p><p className="mt-2 max-w-md text-xs leading-5 text-slate-500">{error}</p><button type="button" onClick={() => setReloadKey((value) => value + 1)} className="clay-button-primary mt-4"><RefreshCw size={14} /> Try again</button></div></div>;

  if (action === 'children') return <ChildrenScreen data={data as ChildrenPayload} dashboardPath={dashboardPath} />;
  if (action === 'results') return <ResultsScreen data={data as ResultsPayload} student={searchParams.get('student') ?? ''} term={searchParams.get('term') ?? ''} setFilters={setFilters} />;
  if (action === 'attendance') return <AttendanceScreen data={data as AttendancePayload} student={searchParams.get('student') ?? ''} setFilters={setFilters} />;
  if (action === 'finance') return <FinanceScreen data={data as FinancePayload} student={searchParams.get('student') ?? ''} setFilters={setFilters} />;
  if (action === 'calendar') return <CalendarScreen data={data as CalendarPayload} />;
  if (action === 'communication') return <CommunicationScreen data={data as MessagePayload} reload={() => setReloadKey((value) => value + 1)} />;
  if (action === 'reports') return <ReportsScreen data={data as ReportsPayload} />;
  return null;
}

function ChildrenScreen({ data, dashboardPath }: { data: ChildrenPayload; dashboardPath: string }) {
  return <section>
    <SectionHeading icon={<UsersRound size={20} />} eyebrow="Family overview" title="My children" description={`A quick view of the school records available to your account${data.term ? ` for ${data.term}` : ''}.`} />
    {data.children.length ? <div className="grid gap-4 xl:grid-cols-2">{data.children.map((child) => <article key={child.id} className="tafiti-card overflow-hidden"><div className="flex items-center gap-4 border-b border-blue-100 bg-gradient-to-r from-[#EAF3FF] to-white p-5">{child.photo ? <img src={childPhoto(child.photo)} alt="" className="h-14 w-14 rounded-2xl object-cover ring-4 ring-white" /> : <span className="grid h-14 w-14 place-items-center rounded-2xl bg-blue-100 text-blue-700"><UserRound size={23} /></span>}<div className="min-w-0 flex-1"><p className="truncate text-base font-extrabold text-[#10224A]">{child.name}</p><p className="mt-1 text-[10px] font-semibold text-slate-500">{child.student_id} · {child.class}{child.stream ? ` · ${child.stream}` : ''}</p></div><span className="rounded-full border border-emerald-100 bg-emerald-50 px-2.5 py-1 text-[9px] font-bold text-emerald-700">Active</span></div><div className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-4"><MiniStat label="Attendance" value={child.attendance_percent === null ? '—' : `${child.attendance_percent}%`} /><MiniStat label="Average" value={child.academic_average === null ? '—' : `${child.academic_average}%`} /><MiniStat label="Outstanding" value={child.outstanding_balance === null ? '—' : money(child.outstanding_balance)} /><MiniStat label="Library" value={`${child.active_loans} loan${child.active_loans === 1 ? '' : 's'}`} /></div><div className="flex flex-wrap gap-2 border-t border-slate-100 px-4 py-3.5">{child.permissions.academics && <Link href={`${dashboardPath}/parent-results?student=${child.id}`} className="clay-button-secondary"><GraduationCap size={13} /> Results</Link>}{child.permissions.attendance && <Link href={`${dashboardPath}/parent-attendance?student=${child.id}`} className="clay-button-secondary"><CalendarCheck size={13} /> Attendance</Link>}{child.permissions.finance && <Link href={`${dashboardPath}/parent-finance?student=${child.id}`} className="clay-button-secondary"><WalletCards size={13} /> Fees</Link>}<Link href={`${dashboardPath}/parent-communication`} className="ml-auto inline-flex items-center gap-1 text-[10px] font-bold text-blue-600 hover:text-blue-800">Contact school <ArrowRight size={12} /></Link></div></article>)}</div> : <EmptyState icon={<UsersRound size={22} />} title="No linked children" text="The school has not linked an active student record to this parent account." />}
  </section>;
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl border border-slate-100 bg-[#F8FAFD] p-3"><p className="text-[8px] font-bold uppercase tracking-[.05em] text-slate-400">{label}</p><p className="mt-1.5 truncate text-[11px] font-extrabold text-slate-700">{value}</p></div>;
}

function ResultsScreen({ data, student, term, setFilters }: { data: ResultsPayload; student: string; term: string; setFilters: (values: Record<string, string>) => void }) {
  const average = data.results.length ? data.results.reduce((sum, row) => sum + row.percentage, 0) / data.results.length : null;
  const best = data.performance.filter((row) => row.average !== null).sort((a, b) => Number(b.average) - Number(a.average))[0];
  return <section>
    <SectionHeading icon={<GraduationCap size={20} />} eyebrow="Academics" title="Academic progress" description="Verified marks, subject averages and class comparison in one parent-friendly view." action={<span className="rounded-full border border-blue-100 bg-blue-50 px-3 py-1.5 text-[9px] font-bold text-blue-700">Verified results only</span>} />
    <div className="mb-4 flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-3.5 shadow-sm sm:flex-row"><Selector label="Child" value={student} onChange={(value) => setFilters({ student: value, term })}><option value="">All children</option>{data.students.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</Selector><Selector label="Academic term" value={term || (data.term ? String(data.term.id) : '')} onChange={(value) => setFilters({ student, term: value })}><option value="">Current term</option>{data.terms.map((row) => <option key={row.id} value={row.id}>{row.label}</option>)}</Selector></div>
    <div className="mb-4 grid gap-3 sm:grid-cols-3"><Metric label="Verified assessments" value={data.results.length} hint="Visible to this parent account" icon={<CheckCircle2 size={17} />} tone="green" /><Metric label="Average score" value={average === null ? '—' : `${average.toFixed(1)}%`} hint="Across displayed assessments" icon={<TrendingUp size={17} />} /><Metric label="Strongest subject" value={best?.subject ?? '—'} hint={best?.average === null || !best ? 'No analysis yet' : `${best.average}% average`} icon={<BookOpenCheck size={17} />} tone="violet" /></div>
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(290px,.65fr)]"><div className="tafiti-card overflow-hidden"><div className="border-b border-slate-100 px-4 py-3.5"><p className="text-sm font-extrabold text-[#10224A]">Assessment results</p><p className="mt-1 text-[10px] text-slate-500">Scores shown here have already passed the school&apos;s verification workflow.</p></div>{data.results.length ? <><div className="hidden overflow-x-auto md:block"><table className="w-full min-w-[720px] text-left"><thead className="bg-[#F8FAFD]"><tr>{['Student','Subject','Assessment','Score','Percent','Grade'].map((label) => <th key={label} className="px-4 py-3 text-[9px] font-extrabold uppercase text-slate-400">{label}</th>)}</tr></thead><tbody className="divide-y divide-slate-100">{data.results.map((row) => <tr key={row.id} className="hover:bg-blue-50/20"><td className="px-4 py-3 text-xs font-bold text-slate-800">{row.student}</td><td className="px-4 py-3 text-xs text-slate-600">{row.subject}</td><td className="px-4 py-3 text-xs text-slate-600">{row.assessment}<span className="mt-0.5 block text-[9px] text-slate-400">{readableDate(row.date)}</span></td><td className="px-4 py-3 text-xs text-slate-600">{row.score} / {row.out_of}</td><td className="px-4 py-3 text-xs font-extrabold text-[#10224A]">{row.percentage}%</td><td className="px-4 py-3"><span className="rounded-lg bg-emerald-50 px-2 py-1 text-[10px] font-bold text-emerald-700">{row.grade || '—'}</span></td></tr>)}</tbody></table></div><div className="space-y-2 p-3 md:hidden">{data.results.map((row) => <article key={row.id} className="rounded-xl border border-slate-100 bg-[#FBFCFE] p-3.5"><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-extrabold text-slate-800">{row.subject}</p><p className="mt-1 text-[9px] text-slate-400">{row.student} · {row.assessment}</p></div><span className="rounded-lg bg-emerald-50 px-2 py-1 text-[10px] font-bold text-emerald-700">{row.grade || '—'}</span></div><div className="mt-3 flex items-end justify-between"><p className="text-[10px] text-slate-500">{readableDate(row.date)}</p><p className="text-lg font-extrabold text-[#10224A]">{row.percentage}%</p></div></article>)}</div></> : <EmptyState icon={<BookOpenCheck size={22} />} title="No verified results" text="Verified results will appear here when the school publishes them." />}</div><aside className="tafiti-card p-4"><p className="text-sm font-extrabold text-[#10224A]">Subject performance</p><p className="mt-1 text-[10px] text-slate-500">Student average compared with the class average.</p><div className="mt-4 space-y-4">{data.performance.map((row) => <div key={`${row.student_id}-${row.subject}`}><div className="flex items-center justify-between gap-3"><span className="truncate text-[11px] font-bold text-slate-700">{row.subject}</span><span className="text-[11px] font-extrabold text-[#10224A]">{row.average === null ? '—' : `${row.average}%`}</span></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-gradient-to-r from-blue-500 to-blue-600" style={{ width: `${Math.min(100, Math.max(0, row.average ?? 0))}%` }} /></div><p className="mt-1 text-[9px] text-slate-400">{row.rank ? `Rank ${row.rank} of ${row.class_size}` : 'Rank unavailable'}{row.class_average !== null ? ` · Class ${row.class_average}%` : ''}</p></div>)}{!data.performance.length && <p className="py-8 text-center text-[10px] text-slate-400">Performance analysis appears when verified results are available.</p>}</div></aside></div>
  </section>;
}

function AttendanceScreen({ data, student, setFilters }: { data: AttendancePayload; student: string; setFilters: (values: Record<string, string>) => void }) {
  const total = data.totals.present + data.totals.absent + data.totals.late + data.totals.excused;
  const attended = data.totals.present + data.totals.late;
  const rate = total ? Math.round((attended / total) * 100) : 0;
  return <section>
    <SectionHeading icon={<CalendarCheck size={20} />} eyebrow="Attendance" title="Attendance history" description="Only submitted and locked attendance sessions are visible to parents." />
    <div className="mb-4 rounded-2xl border border-slate-200 bg-white p-3.5 shadow-sm"><Selector label="Child" value={student} onChange={(value) => setFilters({ student: value })}><option value="">All children</option>{data.students.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</Selector></div>
    <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5"><Metric label="Attendance rate" value={`${rate}%`} hint={`${attended} attended sessions`} icon={<TrendingUp size={17} />} /><Metric label="Present" value={data.totals.present} hint="Marked present" icon={<CheckCircle2 size={17} />} tone="green" /><Metric label="Absent" value={data.totals.absent} hint="Marked absent" icon={<AlertCircle size={17} />} tone="rose" /><Metric label="Late" value={data.totals.late} hint="Arrived late" icon={<Clock3 size={17} />} tone="amber" /><Metric label="Excused" value={data.totals.excused} hint="Approved absence" icon={<CalendarCheck size={17} />} tone="violet" /></div>
    <div className="tafiti-card overflow-hidden"><div className="border-b border-slate-100 px-4 py-3.5"><p className="text-sm font-extrabold text-[#10224A]">Submitted sessions</p><p className="mt-1 text-[10px] text-slate-500">Attendance remains read-only in the parent portal.</p></div>{data.records.length ? <><div className="hidden overflow-x-auto md:block"><table className="w-full min-w-[760px] text-left"><thead className="bg-[#F8FAFD]"><tr>{['Date','Student','Class','Subject','Status','Remarks'].map((label) => <th key={label} className="px-4 py-3 text-[9px] font-extrabold uppercase text-slate-400">{label}</th>)}</tr></thead><tbody className="divide-y divide-slate-100">{data.records.map((row) => <tr key={row.id}><td className="px-4 py-3 text-xs text-slate-600">{readableDate(row.date)}</td><td className="px-4 py-3 text-xs font-bold text-slate-800">{row.student}</td><td className="px-4 py-3 text-xs text-slate-600">{row.class}</td><td className="px-4 py-3 text-xs text-slate-600">{row.subject}</td><td className="px-4 py-3"><AttendanceBadge status={row.status} /></td><td className="px-4 py-3 text-xs text-slate-500">{row.remarks || '—'}</td></tr>)}</tbody></table></div><div className="space-y-2 p-3 md:hidden">{data.records.map((row) => <article key={row.id} className="rounded-xl border border-slate-100 bg-[#FBFCFE] p-3.5"><div className="flex items-center justify-between gap-3"><div><p className="text-xs font-extrabold text-slate-800">{row.subject}</p><p className="mt-1 text-[9px] text-slate-400">{row.student} · {row.class}</p></div><AttendanceBadge status={row.status} /></div><div className="mt-3 flex items-center justify-between text-[10px] text-slate-500"><span>{readableDate(row.date)}</span><span>{row.remarks || 'No remarks'}</span></div></article>)}</div></> : <EmptyState icon={<CalendarCheck size={22} />} title="No attendance records" text="Submitted attendance records will appear here." />}</div>
  </section>;
}

function AttendanceBadge({ status }: { status: string }) {
  const key = status.toLowerCase();
  const cls = key.includes('present') ? 'bg-emerald-50 text-emerald-700' : key.includes('absent') ? 'bg-rose-50 text-rose-700' : key.includes('late') ? 'bg-amber-50 text-amber-700' : 'bg-blue-50 text-blue-700';
  return <span className={`rounded-full px-2.5 py-1 text-[9px] font-extrabold ${cls}`}>{status}</span>;
}

function FinanceScreen({ data, student, setFilters }: { data: FinancePayload; student: string; setFilters: (values: Record<string, string>) => void }) {
  const [tab, setTab] = useState<'statement' | 'payments'>('statement');
  const billed = data.bills.reduce((sum, row) => sum + Number(row.billed), 0);
  const paid = data.bills.reduce((sum, row) => sum + Number(row.paid), 0);
  const balance = data.bills.reduce((sum, row) => sum + Math.max(0, Number(row.balance)), 0);
  return <section>
    <SectionHeading icon={<WalletCards size={20} />} eyebrow="Finance" title="Fee account" description="A clear read-only view of bills, balances and payment receipts for your linked children." />
    <div className="mb-4 rounded-2xl border border-slate-200 bg-white p-3.5 shadow-sm"><Selector label="Child" value={student} onChange={(value) => setFilters({ student: value })}><option value="">All children</option>{data.students.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</Selector></div>
    <div className="mb-4 grid gap-3 sm:grid-cols-3"><Metric label="Total billed" value={money(billed)} hint={`${data.bills.length} bill${data.bills.length === 1 ? '' : 's'}`} icon={<ReceiptText size={17} />} /><Metric label="Total paid" value={money(paid)} hint={`${data.payments.length} payment receipt${data.payments.length === 1 ? '' : 's'}`} icon={<CheckCircle2 size={17} />} tone="green" /><Metric label="Outstanding" value={money(balance)} hint="Current unpaid balance" icon={<WalletCards size={17} />} tone="amber" /></div>
    <div className="tafiti-card overflow-hidden"><div className="flex flex-col gap-3 border-b border-slate-100 px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-sm font-extrabold text-[#10224A]">Student fee statement</p><p className="mt-1 text-[10px] text-slate-500">Financial records cannot be edited from the parent portal.</p></div><div className="flex rounded-xl bg-slate-100 p-1"><button type="button" onClick={() => setTab('statement')} className={`rounded-lg px-3 py-2 text-[10px] font-bold ${tab === 'statement' ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-500'}`}>Bills & balances</button><button type="button" onClick={() => setTab('payments')} className={`rounded-lg px-3 py-2 text-[10px] font-bold ${tab === 'payments' ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-500'}`}>Payments</button></div></div>{tab === 'statement' ? (data.bills.length ? <div className="divide-y divide-slate-100">{data.bills.map((bill) => <details key={bill.id} className="group"><summary className="grid cursor-pointer list-none gap-3 px-4 py-4 hover:bg-blue-50/20 sm:grid-cols-[1.15fr_.8fr_.8fr_.8fr_.7fr] sm:items-center"><div><p className="text-xs font-extrabold text-slate-800">{bill.student}</p><p className="mt-1 text-[9px] text-slate-400">{bill.term} · {readableDate(bill.date)}</p></div><div><p className="text-[8px] font-bold uppercase text-slate-400">Billed</p><p className="mt-1 text-xs font-bold text-slate-700">{money(bill.billed)}</p></div><div><p className="text-[8px] font-bold uppercase text-slate-400">Paid</p><p className="mt-1 text-xs font-bold text-emerald-700">{money(bill.paid)}</p></div><div><p className="text-[8px] font-bold uppercase text-slate-400">Balance</p><p className="mt-1 text-xs font-extrabold text-[#10224A]">{money(bill.balance)}</p></div><div className="sm:text-right"><span className={`rounded-full px-2 py-1 text-[9px] font-bold ${bill.status === 'Paid' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>{bill.status}</span></div></summary><div className="border-t border-slate-100 bg-[#FBFCFE] px-4 py-3"><p className="text-[9px] font-extrabold uppercase tracking-[.06em] text-slate-400">Bill items</p><div className="mt-2 grid gap-2 sm:grid-cols-2">{bill.items.map((item, index) => <div key={`${bill.id}-${index}`} className="flex items-center justify-between rounded-lg border border-slate-100 bg-white px-3 py-2 text-[10px]"><span className="text-slate-600">{item.description}</span><span className="font-bold text-slate-800">{money(item.amount)}</span></div>)}</div>{bill.due_date && <p className="mt-2 text-[9px] text-slate-400">Due {readableDate(bill.due_date)}</p>}</div></details>)}</div> : <EmptyState icon={<ReceiptText size={22} />} title="No fee bills" text="No bills are available for the selected child." />) : (data.payments.length ? <div className="overflow-x-auto"><table className="w-full min-w-[650px] text-left"><thead className="bg-[#F8FAFD]"><tr>{['Date','Student','Receipt / reference','Method','Amount'].map((label) => <th key={label} className="px-4 py-3 text-[9px] font-extrabold uppercase text-slate-400">{label}</th>)}</tr></thead><tbody className="divide-y divide-slate-100">{data.payments.map((row) => <tr key={row.id}><td className="px-4 py-3 text-xs text-slate-600">{readableDate(row.date)}</td><td className="px-4 py-3 text-xs font-bold text-slate-800">{row.student}</td><td className="px-4 py-3 text-xs text-slate-600">{row.reference}</td><td className="px-4 py-3 text-xs text-slate-600">{row.method}</td><td className="px-4 py-3 text-xs font-extrabold text-emerald-700">{money(row.amount)}</td></tr>)}</tbody></table></div> : <EmptyState icon={<WalletCards size={22} />} title="No payments" text="Recorded payments will appear here." />)}</div>
  </section>;
}

function CalendarScreen({ data }: { data: CalendarPayload }) {
  const upcoming = data.events.filter((event) => new Date(event.start).getTime() >= Date.now()).length;
  const grouped = data.events.reduce<Record<string, CalendarPayload['events']>>((groups, event) => { const key = new Date(event.start).toLocaleDateString(undefined, { month: 'long', year: 'numeric' }); groups[key] = [...(groups[key] ?? []), event]; return groups; }, {});
  return <section>
    <SectionHeading icon={<CalendarDays size={20} />} eyebrow="School calendar" title="Upcoming school activities" description="Parent-facing events and important dates published by the school." />
    <div className="mb-4 grid gap-3 sm:grid-cols-2"><Metric label="Upcoming events" value={upcoming} hint="Within the published calendar window" icon={<CalendarDays size={17} />} /><Metric label="Published events" value={data.events.length} hint="Visible to parent accounts" icon={<CalendarCheck size={17} />} tone="violet" /></div>
    {data.events.length ? <div className="space-y-4">{Object.entries(grouped).map(([month, events]) => <section key={month} className="tafiti-card overflow-hidden"><header className="border-b border-slate-100 bg-[#F8FAFD] px-4 py-3"><p className="text-xs font-extrabold text-slate-700">{month}</p></header><div className="divide-y divide-slate-100">{events.map((event) => <article key={event.id} className="flex gap-4 p-4 sm:p-5"><time className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-blue-50 text-center text-blue-700"><span><span className="block text-[8px] font-extrabold uppercase">{new Date(event.start).toLocaleDateString(undefined, { month: 'short' })}</span><span className="block text-lg font-extrabold leading-5">{new Date(event.start).getDate()}</span></span></time><div className="min-w-0 flex-1"><p className="text-sm font-extrabold text-[#10224A]">{event.title}</p><div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[9px] font-semibold text-slate-400"><span className="inline-flex items-center gap-1"><Clock3 size={11} />{readableDate(event.start, true)}</span>{event.location && <span className="inline-flex items-center gap-1"><MapPin size={11} />{event.location}</span>}</div>{event.description && <p className="mt-2 max-w-3xl text-[10px] leading-5 text-slate-500">{event.description}</p>}</div></article>)}</div></section>)}</div> : <EmptyState icon={<CalendarDays size={22} />} title="No upcoming events" text="School activities published for parents will appear here." />}
  </section>;
}

function CommunicationScreen({ data, reload }: { data: MessagePayload; reload: () => void }) {
  const toast = useToast();
  const [activeId, setActiveId] = useState<number | null>(data.conversations[0]?.id ?? null);
  const [compose, setCompose] = useState(false);
  const [studentId, setStudentId] = useState(data.children[0] ? String(data.children[0].id) : '');
  const [teacherId, setTeacherId] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);
  const active = data.conversations.find((row) => row.id === activeId) ?? null;
  const teachers = data.teachers[studentId] ?? [];

  useEffect(() => { if (!data.conversations.some((row) => row.id === activeId)) setActiveId(data.conversations[0]?.id ?? null); }, [activeId, data.conversations]);
  useEffect(() => { setTeacherId(teachers[0] ? String(teachers[0].id) : ''); }, [studentId, teachers]);

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSending(true);
    try {
      const response = await fetch(`/api/workspace/parent/${compose ? 'message' : 'reply'}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(compose ? { student_id: studentId, teacher_id: teacherId, subject, message: body } : { conversation_id: activeId, message: body }) });
      const result = await parseResponse<{ detail: string; conversation_id?: number }>(response);
      toast.success('Message sent', result.detail); setBody(''); setSubject(''); setCompose(false); if (result.conversation_id) setActiveId(result.conversation_id); reload();
    } catch (reason) { toast.error('Message not sent', reason instanceof Error ? reason.message : 'Please try again.'); }
    finally { setSending(false); }
  }

  return <section>
    <SectionHeading icon={<MessageCircle size={20} />} eyebrow="Communication" title="Messages with the school" description="Contact teachers assigned to your linked children and keep each conversation in one thread." action={<button type="button" onClick={() => setCompose(true)} className="clay-button-primary"><Mail size={14} /> New message</button>} />
    <div className="tafiti-card grid min-h-[560px] overflow-hidden lg:grid-cols-[310px_minmax(0,1fr)]"><aside className="border-b border-slate-100 bg-[#FBFCFE] lg:border-b-0 lg:border-r"><div className="border-b border-slate-100 p-4"><p className="text-xs font-extrabold text-[#10224A]">Conversations</p><p className="mt-1 text-[9px] text-slate-400">{data.conversations.length} thread{data.conversations.length === 1 ? '' : 's'}</p></div><div className="max-h-[240px] overflow-y-auto p-2 lg:max-h-[500px]">{data.conversations.map((conversation) => <button key={conversation.id} type="button" onClick={() => { setCompose(false); setActiveId(conversation.id); }} className={`mb-1 w-full rounded-xl p-3 text-left transition ${activeId === conversation.id && !compose ? 'border border-blue-100 bg-blue-50' : 'border border-transparent hover:bg-white'}`}><div className="flex items-center justify-between gap-2"><p className="truncate text-[11px] font-extrabold text-slate-800">{conversation.subject}</p><span className={`h-2 w-2 shrink-0 rounded-full ${conversation.active ? 'bg-emerald-400' : 'bg-slate-300'}`} /></div><p className="mt-1 truncate text-[9px] text-slate-500">{conversation.student} · {conversation.teacher}</p><p className="mt-1.5 line-clamp-1 text-[9px] text-slate-400">{conversation.messages.at(-1)?.body ?? 'No messages yet'}</p></button>)}{!data.conversations.length && <p className="p-4 text-[10px] leading-5 text-slate-400">No conversations yet. Start a message with an assigned teacher.</p>}</div></aside><div className="flex min-h-[460px] flex-col">{compose ? <form onSubmit={send} className="flex flex-1 flex-col p-4 sm:p-6"><div><p className="text-sm font-extrabold text-[#10224A]">New message</p><p className="mt-1 text-[10px] text-slate-500">Choose a child and one of their assigned teachers.</p></div><div className="mt-5 grid gap-3 sm:grid-cols-2"><Selector label="Child" value={studentId} onChange={setStudentId}><option value="">Select child</option>{data.children.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</Selector><Selector label="Assigned teacher" value={teacherId} onChange={setTeacherId}><option value="">Select teacher</option>{teachers.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</Selector></div>{studentId && !teachers.length && <p className="mt-3 rounded-xl bg-amber-50 p-3 text-[10px] text-amber-700">No active teacher messaging account is assigned to this child.</p>}<label className="mt-4 block text-[9px] font-extrabold uppercase tracking-[.06em] text-slate-400">Subject<input value={subject} onChange={(event) => setSubject(event.target.value)} maxLength={200} className="tafiti-input mt-1.5 h-10 w-full px-3 text-xs font-semibold normal-case tracking-normal text-slate-700" placeholder="What would you like to discuss?" /></label><label className="mt-4 flex-1 text-[9px] font-extrabold uppercase tracking-[.06em] text-slate-400">Message<textarea required maxLength={2000} value={body} onChange={(event) => setBody(event.target.value)} className="tafiti-input mt-1.5 min-h-40 w-full resize-y p-3 text-xs font-normal normal-case leading-5 tracking-normal" placeholder="Write your message…" /></label><div className="mt-4 flex justify-end gap-2"><button type="button" onClick={() => setCompose(false)} className="clay-button-secondary">Cancel</button><button type="submit" disabled={sending || !teacherId || !body.trim()} className="clay-button-primary">{sending ? <LoaderCircle size={14} className="animate-spin" /> : <Send size={14} />} Send message</button></div></form> : active ? <><header className="border-b border-slate-100 px-4 py-4 sm:px-6"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-full bg-blue-50 text-blue-600"><UserRound size={17} /></span><div><p className="text-sm font-extrabold text-[#10224A]">{active.subject}</p><p className="mt-1 text-[9px] text-slate-400">{active.student} · {active.teacher}</p></div></div></header><div className="flex-1 space-y-3 overflow-y-auto bg-[#F8FAFD] p-4 sm:p-6">{active.messages.map((message) => <div key={message.id} className={`flex ${message.from_parent ? 'justify-end' : 'justify-start'}`}><article className={`max-w-[86%] rounded-2xl px-4 py-3 shadow-sm ${message.from_parent ? 'bg-blue-600 text-white' : 'border border-slate-100 bg-white text-slate-700'}`}><p className={`text-[9px] font-bold ${message.from_parent ? 'text-blue-100' : 'text-slate-400'}`}>{message.sender}</p><p className="mt-1 whitespace-pre-wrap text-[11px] leading-5">{message.body}</p><p className={`mt-2 text-right text-[8px] ${message.from_parent ? 'text-blue-100' : 'text-slate-400'}`}>{readableDate(message.created_at, true)}</p></article></div>)}</div><form onSubmit={send} className="flex items-end gap-2 border-t border-slate-100 bg-white p-3 sm:p-4"><textarea required maxLength={2000} rows={2} value={body} onChange={(event) => setBody(event.target.value)} disabled={!active.active} placeholder={active.active ? 'Write a reply…' : 'This conversation is closed'} className="tafiti-input min-h-11 flex-1 resize-y p-3 text-xs" /><button type="submit" disabled={sending || !active.active || !body.trim()} className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-blue-600 text-white disabled:opacity-50">{sending ? <LoaderCircle size={14} className="animate-spin" /> : <Send size={15} />}</button></form></> : <div className="grid flex-1 place-items-center p-8 text-center"><div><MessageCircle className="mx-auto text-blue-200" size={34} /><p className="mt-3 text-sm font-extrabold text-slate-700">Choose a conversation</p><p className="mt-1 text-[10px] text-slate-400">Or start a new message with an assigned teacher.</p></div></div>}</div></div>
  </section>;
}

function ReportsScreen({ data }: { data: ReportsPayload }) {
  const toast = useToast();
  const [studentId, setStudentId] = useState(data.students[0] ? String(data.students[0].id) : '');
  const [termId, setTermId] = useState(data.current_term_id ? String(data.current_term_id) : '');
  const [downloading, setDownloading] = useState(false);

  async function downloadReport() {
    if (!studentId) return;
    setDownloading(true);
    try {
      const response = await fetch('/api/workspace/parent/report', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ student_id: studentId, term_id: termId }) });
      const report = await parseResponse<{ filename: string; content_type: string; content_base64: string }>(response);
      const binary = atob(report.content_base64); const bytes = new Uint8Array(binary.length); for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
      const url = URL.createObjectURL(new Blob([bytes], { type: report.content_type })); const anchor = document.createElement('a'); anchor.href = url; anchor.download = report.filename; anchor.click(); URL.revokeObjectURL(url); toast.success('Report downloaded', report.filename);
    } catch (reason) { toast.error('Report unavailable', reason instanceof Error ? reason.message : 'Please try again.'); }
    finally { setDownloading(false); }
  }

  return <section>
    <SectionHeading icon={<FileText size={20} />} eyebrow="Reports" title="Parent report center" description="Generate the school&apos;s official academic PDF for a linked child and academic term." />
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(300px,.85fr)]"><div className="tafiti-card p-5 sm:p-6"><div className="flex items-center gap-3 border-b border-slate-100 pb-4"><span className="grid h-11 w-11 place-items-center rounded-2xl bg-blue-50 text-blue-600"><FileText size={20} /></span><div><p className="text-sm font-extrabold text-[#10224A]">Academic result report</p><p className="mt-1 text-[10px] text-slate-500">Generated from verified results by the existing Django report service.</p></div></div><div className="mt-5 grid gap-3 sm:grid-cols-2"><Selector label="Child" value={studentId} onChange={setStudentId}><option value="">Select child</option>{data.students.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</Selector><Selector label="Academic term" value={termId} onChange={setTermId}><option value="">Current term</option>{data.terms.map((row) => <option key={row.id} value={row.id}>{row.label}</option>)}</Selector></div><div className="mt-5 rounded-2xl border border-blue-100 bg-blue-50/60 p-4"><p className="text-[10px] font-bold text-blue-800">What the PDF contains</p><div className="mt-3 grid gap-2 sm:grid-cols-2">{['Verified assessment marks','Subject grades and totals','School report formatting','Selected academic term'].map((item) => <div key={item} className="flex items-center gap-2 text-[10px] text-blue-700"><CheckCircle2 size={13} />{item}</div>)}</div></div><button type="button" onClick={downloadReport} disabled={!studentId || downloading} className="clay-button-primary mt-5">{downloading ? <LoaderCircle size={14} className="animate-spin" /> : <Download size={14} />} Generate & download PDF</button>{!data.students.length && <p className="mt-4 rounded-xl bg-amber-50 p-3 text-[10px] text-amber-700">Academic report access is not enabled for any linked child.</p>}</div><aside className="tafiti-card p-5"><p className="text-sm font-extrabold text-[#10224A]">Report access</p><p className="mt-1 text-[10px] leading-5 text-slate-500">Parents only see children explicitly linked and verified by the school. Report generation does not bypass those permissions.</p><div className="mt-4 space-y-3"><InfoRow icon={<UsersRound size={15} />} title="Linked students" value={`${data.students.length}`} /><InfoRow icon={<CalendarDays size={15} />} title="Available terms" value={`${data.terms.length}`} /><InfoRow icon={<FileText size={15} />} title="Format" value="PDF" /></div></aside></div>
  </section>;
}

function InfoRow({ icon, title, value }: { icon: ReactNode; title: string; value: string }) {
  return <div className="flex items-center gap-3 rounded-xl border border-slate-100 bg-[#F8FAFD] p-3"><span className="grid h-9 w-9 place-items-center rounded-xl bg-white text-blue-600">{icon}</span><div><p className="text-[9px] text-slate-400">{title}</p><p className="mt-0.5 text-xs font-extrabold text-slate-700">{value}</p></div></div>;
}
