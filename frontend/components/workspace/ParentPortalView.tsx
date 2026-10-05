'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import type { ReactNode } from 'react';
import {
  AlertCircle,
  Bell,
  BookOpenCheck,
  CalendarDays,
  Check,
  CheckCheck,
  Download,
  FileText,
  LoaderCircle,
  Mail,
  MessageCircle,
  Send,
  ShieldCheck,
  UserRound,
  UsersRound,
  WalletCards,
} from 'lucide-react';

import { useToast } from '@/components/ui/ToastProvider';

type ParentProfilePayload = {
  profile: { first_name: string; last_name: string; email: string; username: string };
  children: {
    id: number;
    name: string;
    student_id: string;
    class: string;
    stream: string;
    photo: string;
    can_view_academics: boolean;
    can_view_finance: boolean;
    can_view_attendance: boolean;
  }[];
};

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

type ParentResultPayload = {
  term: { id: number; label: string } | null;
  terms: { id: number; label: string }[];
  students: { id: number; name: string }[];
  results: {
    id: number;
    student_id: number;
    student: string;
    subject: string;
    assessment: string;
    date: string;
    score: string;
    out_of: number;
    percentage: number;
    grade: string;
  }[];
  performance: {
    student_id: number;
    student: string;
    subject: string;
    average: number | null;
    class_average: number | null;
    rank: number | null;
    class_size: number;
    grade: string;
    assessment_count: number;
  }[];
};

type ParentAttendancePayload = {
  students: { id: number; name: string }[];
  totals: { present: number; absent: number; late: number; excused: number };
  records: {
    id: number;
    student_id: number;
    student: string;
    date: string;
    class: string;
    subject: string;
    status: string;
    remarks: string;
  }[];
};

type ParentFinancePayload = {
  students: { id: number; name: string }[];
  summary: { billed: string; paid: string; balance: string };
  bills: {
    id: number;
    student_id: number;
    student: string;
    term: string;
    date: string;
    due_date: string;
    billed: string;
    paid: string;
    balance: string;
    status: string;
    items: { description: string; amount: string }[];
  }[];
  payments: {
    id: number;
    student_id: number;
    student: string;
    date: string;
    amount: string;
    method: string;
    reference: string;
  }[];
};

type ParentCalendarPayload = {
  events: {
    id: number;
    title: string;
    description: string;
    location: string;
    start: string;
    end: string;
  }[];
};

type ParentMessagePayload = {
  children: { id: number; name: string }[];
  teachers: Record<string, { id: number; name: string }[]>;
  conversations: {
    id: number;
    student_id: number;
    student: string;
    teacher: string;
    subject: string;
    updated_at: string;
    active: boolean;
    messages: {
      id: number;
      sender: string;
      from_parent: boolean;
      body: string;
      created_at: string;
    }[];
  }[];
};

type ParentNotification = {
  id: number;
  student: string;
  kind: string;
  title: string;
  message: string;
  destination: string;
  created_at: string;
  read: boolean;
};

type ParentReportsPayload = {
  students: { id: number; name: string }[];
  terms: { id: number; label: string }[];
  current_term_id: number | null;
};

type ApiResult = { detail?: string; errors?: Record<string, string[]> };

function readableDate(value: string, withTime = false) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, withTime
    ? { dateStyle: 'medium', timeStyle: 'short' }
    : { day: 'numeric', month: 'short', year: 'numeric' }).format(parsed);
}

function childPhoto(photo: string) {
  return photo.startsWith('/') ? `/api/media${photo}` : photo;
}

async function responsePayload<T>(response: Response): Promise<T> {
  const payload = await response.json() as T & ApiResult;
  if (!response.ok) {
    throw new Error(payload.detail || Object.values(payload.errors ?? {}).flat()[0] || 'The request could not be completed.');
  }
  return payload;
}

function PageHeading({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return (
    <header className="mb-6">
      <p className="text-xs font-bold uppercase tracking-[0.12em] text-blue-700">{eyebrow}</p>
      <h1 className="mt-1 text-2xl font-semibold tracking-[-0.025em] text-slate-950">{title}</h1>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">{description}</p>
    </header>
  );
}

function LoadingCard() {
  return <div className="h-36 animate-pulse rounded-2xl border border-slate-200 bg-white" />;
}

export function ParentPortalView({
  screen,
  dashboardPath,
}: {
  screen: string;
  dashboardPath: string;
}) {
  const toast = useToast();
  const [data, setData] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);
  const [search, setSearch] = useState('');

  const action = screen.replace(/^parent-/, '');
  const query = useMemo(() => {
    if (action !== 'results') return '';
    const params = new URLSearchParams();
    const student = searchParamsValue('student');
    const term = searchParamsValue('term');
    if (student) params.set('student', student);
    if (term) params.set('term', term);
    return params.toString();
  }, [action, reloadKey, search]);

  function searchParamsValue(key: string) {
    if (typeof window === 'undefined') return '';
    return new URLSearchParams(window.location.search).get(key) ?? '';
  }

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetch(`/api/workspace/parent/${action}${query ? `?${query}` : ''}`, {
      cache: 'no-store',
      signal: controller.signal,
    })
      .then((response) => responsePayload<unknown>(response))
      .then(setData)
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        const message = reason instanceof Error ? reason.message : 'Parent workspace data could not be loaded.';
        setError(message);
        toast.error('Could not load this page', message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [action, query, reloadKey, toast]);

  if (loading && !data) {
    return <div className="space-y-5"><div className="h-24 animate-pulse rounded-2xl bg-white" /><div className="grid gap-4 md:grid-cols-2"><LoadingCard /><LoadingCard /></div></div>;
  }
  if (error && !data) {
    return (
      <div className="rounded-2xl border border-red-200 bg-white p-6">
        <div className="flex gap-3"><AlertCircle className="shrink-0 text-red-600" size={19} /><div><h1 className="font-semibold text-slate-900">Parent workspace unavailable</h1><p className="mt-1 text-sm text-slate-600">{error}</p><button type="button" onClick={() => setReloadKey((value) => value + 1)} className="mt-4 rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white">Try again</button></div></div>
      </div>
    );
  }

  if (action === 'profile') {
    return <ParentProfile data={data as ParentProfilePayload} reload={() => setReloadKey((value) => value + 1)} />;
  }
  if (action === 'children') {
    return <ParentChildren data={data as { term: string; children: ParentChild[] }} dashboardPath={dashboardPath} />;
  }
  if (action === 'attendance') {
    return <ParentAttendance data={data as ParentAttendancePayload} />;
  }
  if (action === 'finance') {
    return <ParentFinance data={data as ParentFinancePayload} />;
  }
  if (action === 'calendar') {
    return <ParentCalendar data={data as ParentCalendarPayload} />;
  }
  if (action === 'results') {
    return <ParentResults data={data as ParentResultPayload} search={search} setSearch={setSearch} reload={() => setReloadKey((value) => value + 1)} />;
  }
  if (action === 'communication') {
    return <ParentCommunication data={data as ParentMessagePayload} reload={() => setReloadKey((value) => value + 1)} />;
  }
  if (action === 'notifications') {
    return <ParentNotifications data={data as { notifications: ParentNotification[] }} reload={() => setReloadKey((value) => value + 1)} />;
  }
  if (action === 'reports') {
    return <ParentReports data={data as ParentReportsPayload} />;
  }
  return <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600">This parent screen is not available.</div>;
}

function ParentProfile({ data, reload }: { data: ParentProfilePayload; reload: () => void }) {
  const toast = useToast();
  const [profile, setProfile] = useState(data.profile);
  const [saving, setSaving] = useState(false);

  useEffect(() => setProfile(data.profile), [data.profile]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    try {
      const updated = await responsePayload<{ profile: ParentProfilePayload['profile'] }>(await fetch('/api/workspace/parent/profile', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profile),
      }));
      setProfile(updated.profile);
      toast.success('Profile saved', 'Your contact details were updated.');
      reload();
    } catch (reason) {
      toast.error('Profile not saved', reason instanceof Error ? reason.message : 'Try again.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <section>
      <PageHeading eyebrow="Account" title="My profile" description="Manage your parent account details and review the children and school-data access linked to it." />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(330px,0.9fr)]">
        <form onSubmit={save} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="flex items-center gap-3 border-b border-slate-100 pb-4">
            <span className="grid h-11 w-11 place-items-center rounded-2xl bg-blue-50 text-blue-700"><UserRound size={21} /></span>
            <div><h2 className="text-base font-semibold text-slate-950">Personal information</h2><p className="mt-0.5 text-xs text-slate-500">Changes apply to your sign-in profile.</p></div>
          </div>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <label className="text-xs font-semibold text-slate-600">First name<input value={profile.first_name} onChange={(event) => setProfile({ ...profile, first_name: event.target.value })} required maxLength={150} className="mt-1.5 h-10 w-full rounded-xl border border-slate-200 px-3 text-sm font-normal text-slate-900 outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-100" /></label>
            <label className="text-xs font-semibold text-slate-600">Last name<input value={profile.last_name} onChange={(event) => setProfile({ ...profile, last_name: event.target.value })} maxLength={150} className="mt-1.5 h-10 w-full rounded-xl border border-slate-200 px-3 text-sm font-normal text-slate-900 outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-100" /></label>
            <label className="text-xs font-semibold text-slate-600 sm:col-span-2">Email<input type="email" value={profile.email} onChange={(event) => setProfile({ ...profile, email: event.target.value })} maxLength={254} className="mt-1.5 h-10 w-full rounded-xl border border-slate-200 px-3 text-sm font-normal text-slate-900 outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-100" /></label>
            <label className="text-xs font-semibold text-slate-600 sm:col-span-2">Username<input value={profile.username} readOnly className="mt-1.5 h-10 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 text-sm font-normal text-slate-500" /></label>
          </div>
          <button type="submit" disabled={saving} className="mt-5 inline-flex h-10 items-center gap-2 rounded-xl bg-[#1769EF] px-4 text-xs font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-60">{saving && <LoaderCircle size={15} className="animate-spin" />}Save profile</button>
        </form>

        <aside className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="flex items-center gap-3 border-b border-slate-100 pb-4">
            <span className="grid h-11 w-11 place-items-center rounded-2xl bg-emerald-50 text-emerald-700"><UsersRound size={21} /></span>
            <div><h2 className="text-base font-semibold text-slate-950">Linked children</h2><p className="mt-0.5 text-xs text-slate-500">{data.children.length} verified school link{data.children.length === 1 ? '' : 's'}</p></div>
          </div>
          <div className="mt-4 space-y-3">
            {data.children.map((child) => (
              <article key={child.id} className="rounded-xl border border-slate-100 bg-slate-50/70 p-3.5">
                <h3 className="text-sm font-semibold text-slate-900">{child.name}</h3>
                <p className="mt-1 text-xs text-slate-500">{child.student_id} · {child.class}{child.stream ? ` · ${child.stream}` : ''}</p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {child.can_view_academics && <PermissionTag label="Academics" />}
                  {child.can_view_finance && <PermissionTag label="Finance" />}
                  {child.can_view_attendance && <PermissionTag label="Attendance" />}
                </div>
              </article>
            ))}
            {!data.children.length && <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-500">No children are linked to this account.</p>}
          </div>
          <p className="mt-4 flex gap-2 text-[11px] leading-5 text-slate-500"><ShieldCheck className="mt-0.5 shrink-0 text-emerald-700" size={14} />Access permissions are managed by the school. Contact the school office to request changes.</p>
        </aside>
      </div>
    </section>
  );
}

function PermissionTag({ label }: { label: string }) {
  return <span className="inline-flex items-center gap-1 rounded-full bg-white px-2 py-1 text-[10px] font-semibold text-slate-600"><Check size={11} className="text-emerald-600" />{label}</span>;
}

function ParentChildren({ data, dashboardPath }: { data: { term: string; children: ParentChild[] }; dashboardPath: string }) {
  return (
    <section>
      <PageHeading eyebrow="Family" title="My children" description={`View each child's school progress and the records your account is allowed to see${data.term ? ` for ${data.term}` : ''}.`} />
      {data.children.length ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {data.children.map((child) => (
            <article key={child.id} className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
              <div className="flex items-center gap-4 bg-gradient-to-r from-blue-50 to-white p-5">
                {child.photo ? <img src={childPhoto(child.photo)} alt="" className="h-14 w-14 rounded-2xl object-cover" /> : <span className="grid h-14 w-14 place-items-center rounded-2xl bg-blue-100 text-blue-700"><UsersRound size={23} /></span>}
                <div className="min-w-0 flex-1"><h2 className="truncate text-base font-semibold text-slate-950">{child.name}</h2><p className="mt-1 text-xs text-slate-500">{child.student_id} · {child.class}{child.stream ? ` · ${child.stream}` : ''}</p></div>
              </div>
              <div className="grid grid-cols-2 gap-3 p-5 sm:grid-cols-4">
                <ChildMetric label="Attendance" value={child.attendance_percent === null ? 'Not available' : `${child.attendance_percent}%`} icon={<CalendarDays size={15} />} />
                <ChildMetric label="Academic average" value={child.academic_average === null ? 'Not available' : `${child.academic_average}%`} icon={<BookOpenCheck size={15} />} />
                <ChildMetric label="Outstanding fees" value={child.outstanding_balance === null ? 'Not available' : `UGX ${Number(child.outstanding_balance).toLocaleString('en-UG')}`} icon={<WalletCards size={15} />} />
                <ChildMetric label="Library loans" value={`${child.active_loans}${child.overdue_loans ? ` · ${child.overdue_loans} overdue` : ''}`} icon={<BookOpenCheck size={15} />} />
              </div>
              <div className="flex flex-wrap gap-2 border-t border-slate-100 px-5 py-4">
                {child.permissions.academics && <Link href={`${dashboardPath}/parent-results?student=${child.id}`} className="rounded-lg border border-blue-100 px-3 py-2 text-[11px] font-semibold text-blue-700 hover:bg-blue-50">Academic results</Link>}
                {child.permissions.attendance && <Link href={`${dashboardPath}/parent-attendance?student=${child.id}`} className="rounded-lg border border-slate-200 px-3 py-2 text-[11px] font-semibold text-slate-600 hover:bg-slate-50">Attendance</Link>}
                {child.permissions.finance && <Link href={`${dashboardPath}/parent-finance?student=${child.id}`} className="rounded-lg border border-slate-200 px-3 py-2 text-[11px] font-semibold text-slate-600 hover:bg-slate-50">Fee statement</Link>}
              </div>
            </article>
          ))}
        </div>
      ) : <p className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">No active children are linked to this account.</p>}
    </section>
  );
}

function ChildMetric({ label, value, icon }: { label: string; value: string; icon: ReactNode }) {
  return <div className="min-w-0 rounded-xl bg-slate-50 p-3"><span className="text-blue-700">{icon}</span><p className="mt-2 text-[10px] text-slate-500">{label}</p><p className="mt-1 truncate text-xs font-semibold text-slate-800">{value}</p></div>;
}

function ParentAttendance({ data }: { data: ParentAttendancePayload }) {
  const [student, setStudent] = useState(() => searchParamsInitial('student'));
  const records = data.records.filter((row) => !student || String(row.student_id) === student);
  const count = (status: string) => records.filter((row) => row.status.toLowerCase() === status).length;
  const tiles = [
    { label: 'Present', value: count('present'), tone: 'text-emerald-700 bg-emerald-50' },
    { label: 'Absent', value: count('absent'), tone: 'text-rose-700 bg-rose-50' },
    { label: 'Late', value: count('late'), tone: 'text-amber-700 bg-amber-50' },
    { label: 'Excused', value: count('excused'), tone: 'text-blue-700 bg-blue-50' },
  ];
  return (
    <section>
      <PageHeading eyebrow="Family" title="Attendance" description="Review submitted attendance records for your linked children." />
      <div className="mb-4 flex justify-end rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
        <label className="w-full max-w-xs text-xs font-semibold text-slate-600">Child
          <select value={student} onChange={(event) => setStudent(event.target.value)} className="mt-1.5 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs font-normal">
            <option value="">All children</option>{data.students.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </label>
      </div>
      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {tiles.map((tile) => <div key={tile.label} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"><span className={`inline-flex rounded-lg px-2 py-1 text-[10px] font-semibold ${tile.tone}`}>{tile.label}</span><p className="mt-3 text-2xl font-semibold text-slate-950">{tile.value}</p><p className="mt-1 text-[10px] text-slate-500">Submitted records</p></div>)}
      </div>
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 px-4 py-4"><h2 className="text-sm font-semibold text-slate-900">Attendance history</h2><p className="mt-1 text-xs text-slate-500">Unsubmitted sessions are not shown.</p></div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-xs">
            <thead className="bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500"><tr>{['Date', 'Student', 'Class', 'Subject', 'Status', 'Remarks'].map((label) => <th key={label} className="px-4 py-3">{label}</th>)}</tr></thead>
            <tbody className="divide-y divide-slate-100">{records.map((row) => <tr key={row.id}><td className="px-4 py-3 text-slate-600">{readableDate(row.date)}</td><td className="px-4 py-3 font-medium text-slate-800">{row.student}</td><td className="px-4 py-3 text-slate-600">{row.class}</td><td className="px-4 py-3 text-slate-600">{row.subject}</td><td className="px-4 py-3"><span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-semibold text-slate-700">{row.status}</span></td><td className="px-4 py-3 text-slate-500">{row.remarks || '—'}</td></tr>)}</tbody>
          </table>
        </div>
        {!records.length && <p className="px-4 py-9 text-center text-xs text-slate-500">No submitted attendance records are available.</p>}
      </div>
    </section>
  );
}

function ParentFinance({ data }: { data: ParentFinancePayload }) {
  const [student, setStudent] = useState(() => searchParamsInitial('student'));
  const [tab, setTab] = useState<'statement' | 'payments'>('statement');
  const bills = data.bills.filter((row) => !student || String(row.student_id) === student);
  const payments = data.payments.filter((row) => !student || String(row.student_id) === student);
  const billed = bills.reduce((sum, row) => sum + Number(row.billed), 0);
  const paid = bills.reduce((sum, row) => sum + Number(row.paid), 0);
  const balance = bills.reduce((sum, row) => sum + Math.max(0, Number(row.balance)), 0);
  const money = (value: number | string) => `UGX ${Number(value).toLocaleString('en-UG', { maximumFractionDigits: 2 })}`;
  return (
    <section>
      <PageHeading eyebrow="Family" title="Finance" description="Review fee balances, billed items and recorded payments for children with finance access." />
      <div className="mb-4 flex justify-end rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
        <label className="w-full max-w-xs text-xs font-semibold text-slate-600">Child
          <select value={student} onChange={(event) => setStudent(event.target.value)} className="mt-1.5 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs font-normal">
            <option value="">All children</option>{data.students.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </label>
      </div>
      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        {[['Total billed', money(billed), 'bg-blue-50 text-blue-700'], ['Total paid', money(paid), 'bg-emerald-50 text-emerald-700'], ['Outstanding', money(balance), 'bg-amber-50 text-amber-700']].map(([label, value, tone]) => <div key={label} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"><span className={`rounded-lg px-2 py-1 text-[10px] font-semibold ${tone}`}>{label}</span><p className="mt-3 text-xl font-semibold text-slate-950">{value}</p><p className="mt-1 text-[10px] text-slate-500">Across selected children</p></div>)}
      </div>
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-3"><div><h2 className="text-sm font-semibold text-slate-900">Fee account</h2><p className="mt-1 text-xs text-slate-500">Read-only statement and receipts.</p></div><div className="flex gap-1 rounded-xl bg-slate-100 p-1"><button type="button" onClick={() => setTab('statement')} className={`rounded-lg px-3 py-2 text-[11px] font-semibold ${tab === 'statement' ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-500'}`}>Statement</button><button type="button" onClick={() => setTab('payments')} className={`rounded-lg px-3 py-2 text-[11px] font-semibold ${tab === 'payments' ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-500'}`}>Payments</button></div></div>
        <div className="overflow-x-auto">
          {tab === 'statement' ? <table className="w-full min-w-[700px] text-left text-xs"><thead className="bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500"><tr>{['Date', 'Student', 'Term', 'Billed', 'Paid', 'Balance', 'Status'].map((label) => <th key={label} className="px-4 py-3">{label}</th>)}</tr></thead><tbody className="divide-y divide-slate-100">{bills.map((row) => <tr key={row.id}><td className="px-4 py-3">{readableDate(row.date)}</td><td className="px-4 py-3 font-medium">{row.student}</td><td className="px-4 py-3">{row.term}</td><td className="px-4 py-3">{money(row.billed)}</td><td className="px-4 py-3">{money(row.paid)}</td><td className="px-4 py-3 font-semibold">{money(row.balance)}</td><td className="px-4 py-3"><span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-semibold">{row.status}</span></td></tr>)}</tbody></table> : <table className="w-full min-w-[650px] text-left text-xs"><thead className="bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500"><tr>{['Date', 'Student', 'Receipt', 'Method', 'Amount'].map((label) => <th key={label} className="px-4 py-3">{label}</th>)}</tr></thead><tbody className="divide-y divide-slate-100">{payments.map((row) => <tr key={row.id}><td className="px-4 py-3">{readableDate(row.date)}</td><td className="px-4 py-3 font-medium">{row.student}</td><td className="px-4 py-3">{row.reference}</td><td className="px-4 py-3">{row.method}</td><td className="px-4 py-3 font-semibold">{money(row.amount)}</td></tr>)}</tbody></table>}
        </div>
        {tab === 'statement' && !bills.length && <p className="px-4 py-9 text-center text-xs text-slate-500">No fee bills are available for these children.</p>}
        {tab === 'payments' && !payments.length && <p className="px-4 py-9 text-center text-xs text-slate-500">No payment receipts are available for these children.</p>}
      </div>
    </section>
  );
}

function ParentCalendar({ data }: { data: ParentCalendarPayload }) {
  const groupedEvents = data.events.reduce<Record<string, ParentCalendarPayload['events']>>((groups, event) => {
    const day = new Date(event.start).toLocaleDateString(undefined, { year: 'numeric', month: 'long' });
    groups[day] = [...(groups[day] ?? []), event];
    return groups;
  }, {});
  return (
    <section>
      <PageHeading eyebrow="School life" title="Calendar" description="Upcoming school activities and parent events for the next six months." />
      <div className="space-y-5">
        {Object.entries(groupedEvents).map(([month, events]) => <section key={month} className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"><header className="border-b border-slate-100 bg-slate-50/70 px-4 py-3"><h2 className="text-xs font-semibold text-slate-800">{month}</h2></header><div className="divide-y divide-slate-100">{events.map((event) => <article key={event.id} className="flex gap-4 p-4"><time className="flex h-12 w-12 shrink-0 flex-col items-center justify-center rounded-xl bg-blue-50 text-blue-700"><span className="text-[9px] font-semibold uppercase">{new Date(event.start).toLocaleDateString(undefined, { month: 'short' })}</span><span className="text-base font-bold leading-5">{new Date(event.start).getDate()}</span></time><div className="min-w-0 flex-1"><h3 className="text-sm font-semibold text-slate-900">{event.title}</h3><p className="mt-1 text-xs text-slate-500">{readableDate(event.start, true)}{event.location ? ` · ${event.location}` : ''}</p>{event.description && <p className="mt-2 text-xs leading-5 text-slate-600">{event.description}</p>}</div></article>)}</div></section>)}
        {!data.events.length && <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center"><CalendarDays size={26} className="mx-auto text-slate-300" /><p className="mt-3 text-sm font-semibold text-slate-800">No upcoming events</p><p className="mt-1 text-xs text-slate-500">School events for parents will appear here.</p></div>}
      </div>
    </section>
  );
}

function ParentResults({ data, search, setSearch, reload }: { data: ParentResultPayload; search: string; setSearch: (value: string) => void; reload: () => void }) {
  const [student, setStudent] = useState(() => searchParamsInitial('student'));
  const [term, setTerm] = useState(() => searchParamsInitial('term') || (data.term ? String(data.term.id) : ''));
  const filteredRows = data.results.filter((row) => !student || String(row.student_id) === student);
  const performance = data.performance.filter((row) => !student || String(row.student_id) === student);
  const average = filteredRows.length ? filteredRows.reduce((sum, row) => sum + row.percentage, 0) / filteredRows.length : null;

  function updateFilter(nextStudent: string, nextTerm: string) {
    const params = new URLSearchParams();
    if (nextStudent) params.set('student', nextStudent);
    if (nextTerm) params.set('term', nextTerm);
    window.history.replaceState(null, '', `${window.location.pathname}${params.size ? `?${params.toString()}` : ''}`);
    setSearch(`${nextStudent}:${nextTerm}`);
    reload();
  }

  useEffect(() => {
    setStudent(searchParamsInitial('student'));
    setTerm(searchParamsInitial('term') || (data.term ? String(data.term.id) : ''));
  }, [data.term]);

  return (
    <section>
      <PageHeading eyebrow="Academics" title="Student results" description="Review verified marks and subject-level progress for your linked children." />
      <div className="mb-5 flex flex-wrap items-end gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <label className="min-w-[180px] flex-1 text-xs font-semibold text-slate-600">Child<select value={student} onChange={(event) => { setStudent(event.target.value); updateFilter(event.target.value, term); }} className="mt-1.5 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm font-normal text-slate-800 outline-none focus:border-blue-500"><option value="">All children</option>{data.students.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
        <label className="min-w-[180px] flex-1 text-xs font-semibold text-slate-600">Academic term<select value={term} onChange={(event) => { setTerm(event.target.value); updateFilter(student, event.target.value); }} className="mt-1.5 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm font-normal text-slate-800 outline-none focus:border-blue-500"><option value="">Current term</option>{data.terms.map((row) => <option key={row.id} value={row.id}>{row.label}</option>)}</select></label>
      </div>
      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        <SummaryTile label="Verified assessments" value={filteredRows.length} icon={<CheckCheck size={17} />} />
        <SummaryTile label="Average score" value={average === null ? '—' : `${average.toFixed(1)}%`} icon={<BookOpenCheck size={17} />} />
        <SummaryTile label="Subjects reported" value={performance.length} icon={<UsersRound size={17} />} />
      </div>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(300px,0.8fr)]">
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 px-4 py-4"><h2 className="text-sm font-semibold text-slate-900">Subject results</h2><p className="mt-1 text-xs text-slate-500">Only marks verified by the school are shown.</p></div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] text-left text-xs">
              <thead className="bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500"><tr><th className="px-4 py-3">Student</th><th className="px-4 py-3">Subject</th><th className="px-4 py-3">Assessment</th><th className="px-4 py-3">Score</th><th className="px-4 py-3">Percent</th><th className="px-4 py-3">Grade</th></tr></thead>
              <tbody className="divide-y divide-slate-100">{filteredRows.map((row) => <tr key={row.id}><td className="px-4 py-3 font-medium text-slate-800">{row.student}</td><td className="px-4 py-3 text-slate-600">{row.subject}</td><td className="px-4 py-3 text-slate-600">{row.assessment}<span className="mt-1 block text-[10px] text-slate-400">{readableDate(row.date)}</span></td><td className="px-4 py-3 text-slate-600">{row.score} / {row.out_of}</td><td className="px-4 py-3 font-semibold text-slate-800">{row.percentage}%</td><td className="px-4 py-3"><span className="rounded-lg bg-emerald-50 px-2 py-1 font-semibold text-emerald-800">{row.grade}</span></td></tr>)}</tbody>
            </table>
          </div>
          {!filteredRows.length && <p className="px-4 py-9 text-center text-xs text-slate-500">No verified results are available for these filters.</p>}
        </div>
        <aside className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
          <h2 className="text-sm font-semibold text-slate-900">Subject performance</h2><p className="mt-1 text-xs text-slate-500">Student average compared with the class.</p>
          <div className="mt-4 space-y-4">{performance.map((row) => <div key={`${row.student_id}-${row.subject}`}><div className="flex justify-between gap-3"><span className="truncate text-xs font-medium text-slate-700">{row.subject}</span><span className="text-xs font-semibold text-slate-900">{row.average === null ? '—' : `${row.average}%`}</span></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-blue-600" style={{ width: `${Math.min(100, Math.max(0, row.average ?? 0))}%` }} /></div><p className="mt-1 text-[10px] text-slate-400">{row.rank ? `Rank ${row.rank} of ${row.class_size}` : 'Class rank unavailable'}{row.class_average !== null ? ` · Class average ${row.class_average}%` : ''}</p></div>)}</div>
          {!performance.length && <p className="mt-5 text-xs text-slate-500">Subject analysis appears when verified results are available.</p>}
        </aside>
      </div>
    </section>
  );
}

function searchParamsInitial(key: string) {
  if (typeof window === 'undefined') return '';
  return new URLSearchParams(window.location.search).get(key) ?? '';
}

function SummaryTile({ label, value, icon }: { label: string; value: number | string; icon: ReactNode }) {
  return <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"><span className="grid h-10 w-10 place-items-center rounded-xl bg-blue-50 text-blue-700">{icon}</span><div><p className="text-[11px] text-slate-500">{label}</p><p className="mt-1 text-lg font-semibold text-slate-900">{value}</p></div></div>;
}

function ParentCommunication({ data, reload }: { data: ParentMessagePayload; reload: () => void }) {
  const toast = useToast();
  const [activeId, setActiveId] = useState<number | null>(data.conversations[0]?.id ?? null);
  const [newMessage, setNewMessage] = useState(false);
  const [studentId, setStudentId] = useState(data.children[0] ? String(data.children[0].id) : '');
  const [teacherId, setTeacherId] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);
  const activeConversation = data.conversations.find((row) => row.id === activeId) ?? null;
  const teacherOptions = data.teachers[studentId] ?? [];

  useEffect(() => {
    if (!data.conversations.some((row) => row.id === activeId)) setActiveId(data.conversations[0]?.id ?? null);
  }, [activeId, data.conversations]);
  useEffect(() => setTeacherId(teacherOptions[0] ? String(teacherOptions[0].id) : ''), [studentId, teacherOptions]);

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSending(true);
    try {
      const response = await fetch(`/api/workspace/parent/${newMessage ? 'message' : 'reply'}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newMessage
          ? { student_id: studentId, teacher_id: teacherId, subject, message: body }
          : { conversation_id: activeId, message: body }),
      });
      const result = await responsePayload<{ detail: string; conversation_id?: number }>(response);
      toast.success('Message sent', result.detail);
      setBody('');
      setSubject('');
      setNewMessage(false);
      if (result.conversation_id) setActiveId(result.conversation_id);
      reload();
    } catch (reason) {
      toast.error('Message not sent', reason instanceof Error ? reason.message : 'Try again.');
    } finally {
      setSending(false);
    }
  }

  return (
    <section>
      <PageHeading eyebrow="Stay connected" title="Communication center" description="Message your child's assigned teachers and review their replies. The school can only be contacted through teachers assigned to your child." />
      <div className="grid min-h-[540px] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm lg:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="border-b border-slate-100 lg:border-b-0 lg:border-r">
          <div className="flex items-center justify-between border-b border-slate-100 p-4"><div><h2 className="text-sm font-semibold text-slate-900">Messages</h2><p className="mt-1 text-[11px] text-slate-500">{data.conversations.length} conversation{data.conversations.length === 1 ? '' : 's'}</p></div><button type="button" onClick={() => setNewMessage(true)} className="grid h-9 w-9 place-items-center rounded-xl bg-blue-600 text-white hover:bg-blue-700" aria-label="Compose message"><Mail size={16} /></button></div>
          <div className="max-h-[240px] overflow-y-auto p-2 lg:max-h-[450px]">{data.conversations.map((conversation) => <button key={conversation.id} type="button" onClick={() => { setNewMessage(false); setActiveId(conversation.id); }} className={`mb-1 w-full rounded-xl p-3 text-left transition ${activeId === conversation.id && !newMessage ? 'bg-blue-50' : 'hover:bg-slate-50'}`}><p className="truncate text-xs font-semibold text-slate-800">{conversation.subject}</p><p className="mt-1 truncate text-[10px] text-slate-500">{conversation.student} · {conversation.teacher}</p><p className="mt-1 line-clamp-1 text-[10px] text-slate-400">{conversation.messages.at(-1)?.body ?? 'No messages yet'}</p></button>)}
            {!data.conversations.length && <p className="p-4 text-xs leading-5 text-slate-500">No conversations yet. Use the compose button to contact an assigned teacher.</p>}
          </div>
        </aside>
        <div className="flex min-h-[450px] flex-col">
          {newMessage ? (
            <form onSubmit={send} className="flex flex-1 flex-col p-4 sm:p-6">
              <h2 className="text-sm font-semibold text-slate-900">New message to a teacher</h2>
              <p className="mt-1 text-xs text-slate-500">Choose the child and an assigned teacher.</p>
              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <label className="text-xs font-semibold text-slate-600">Child<select required value={studentId} onChange={(event) => setStudentId(event.target.value)} className="mt-1.5 h-10 w-full rounded-xl border border-slate-200 px-3 text-xs"><option value="">Select child</option>{data.children.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
                <label className="text-xs font-semibold text-slate-600">Assigned teacher<select required value={teacherId} onChange={(event) => setTeacherId(event.target.value)} className="mt-1.5 h-10 w-full rounded-xl border border-slate-200 px-3 text-xs"><option value="">Select teacher</option>{teacherOptions.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
              </div>
              {!teacherOptions.length && studentId && <p className="mt-3 text-xs text-amber-700">There are no active teacher messaging accounts assigned to this child.</p>}
              <label className="mt-4 text-xs font-semibold text-slate-600">Subject<input value={subject} onChange={(event) => setSubject(event.target.value)} maxLength={200} placeholder="What would you like to discuss?" className="mt-1.5 h-10 w-full rounded-xl border border-slate-200 px-3 text-xs" /></label>
              <label className="mt-4 flex-1 text-xs font-semibold text-slate-600">Message<textarea required maxLength={2000} value={body} onChange={(event) => setBody(event.target.value)} placeholder="Write a message…" className="mt-1.5 min-h-40 w-full resize-y rounded-xl border border-slate-200 p-3 text-xs font-normal leading-5 outline-none focus:border-blue-500" /></label>
              <button type="submit" disabled={sending || !teacherId} className="mt-4 inline-flex h-10 items-center justify-center gap-2 self-end rounded-xl bg-blue-600 px-4 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50">{sending ? <LoaderCircle size={15} className="animate-spin" /> : <Send size={14} />}Send message</button>
            </form>
          ) : activeConversation ? (
            <>
              <header className="border-b border-slate-100 px-4 py-4 sm:px-6"><h2 className="text-sm font-semibold text-slate-900">{activeConversation.subject}</h2><p className="mt-1 text-xs text-slate-500">{activeConversation.student} · {activeConversation.teacher}</p></header>
              <div className="flex-1 space-y-3 overflow-y-auto bg-slate-50/55 p-4 sm:p-6">{activeConversation.messages.map((message) => <div key={message.id} className={`flex ${message.from_parent ? 'justify-end' : 'justify-start'}`}><article className={`max-w-[88%] rounded-2xl px-4 py-3 ${message.from_parent ? 'bg-blue-600 text-white' : 'border border-slate-200 bg-white text-slate-800'}`}><p className={`mb-1 text-[10px] font-semibold ${message.from_parent ? 'text-blue-100' : 'text-slate-500'}`}>{message.sender}</p><p className="whitespace-pre-wrap text-xs leading-5">{message.body}</p><p className={`mt-2 text-right text-[9px] ${message.from_parent ? 'text-blue-100' : 'text-slate-400'}`}>{readableDate(message.created_at, true)}</p></article></div>)}
                {!activeConversation.messages.length && <p className="py-8 text-center text-xs text-slate-500">Start the conversation by sending a message.</p>}
              </div>
              <form onSubmit={send} className="flex items-end gap-2 border-t border-slate-100 p-3 sm:p-4"><textarea required maxLength={2000} value={body} onChange={(event) => setBody(event.target.value)} placeholder={activeConversation.active ? 'Write a reply…' : 'This conversation is closed'} disabled={!activeConversation.active} rows={2} className="min-h-11 flex-1 resize-y rounded-xl border border-slate-200 p-3 text-xs outline-none focus:border-blue-500 disabled:bg-slate-50" /><button type="submit" disabled={sending || !activeConversation.active} className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50" aria-label="Send reply">{sending ? <LoaderCircle size={15} className="animate-spin" /> : <Send size={15} />}</button></form>
            </>
          ) : <div className="grid flex-1 place-items-center p-8 text-center"><div><MessageCircle size={30} className="mx-auto text-blue-300" /><p className="mt-3 text-sm font-semibold text-slate-800">Your school conversations</p><p className="mt-1 text-xs text-slate-500">Select a message or contact an assigned teacher.</p></div></div>}
        </div>
      </div>
    </section>
  );
}

function ParentNotifications({ data, reload }: { data: { notifications: ParentNotification[] }; reload: () => void }) {
  const toast = useToast();
  const [filter, setFilter] = useState('all');
  const [saving, setSaving] = useState(false);
  const filters = ['all', 'academic', 'attendance', 'finance', 'activities', 'system', 'unread'];
  const categoryFor = (kind: string) => {
    const value = kind.toLowerCase();
    if (['result', 'results', 'academic', 'verification'].includes(value)) return 'academic';
    if (value.includes('attendance')) return 'attendance';
    if (['finance', 'fee', 'fees', 'payment', 'bill'].some((term) => value.includes(term))) return 'finance';
    if (['announcement', 'event', 'activity', 'message', 'communication'].some((term) => value.includes(term))) return 'activities';
    return 'system';
  };
  const notices = data.notifications.filter((row) => (
    filter === 'all'
    || (filter === 'unread' ? !row.read : categoryFor(row.kind) === filter)
  ));
  const groupedNotices = notices.reduce<Record<string, ParentNotification[]>>((groups, notice) => {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const noticeDate = new Date(notice.created_at).getTime();
    const day = Number.isNaN(noticeDate) ? 8 : Math.floor((today - new Date(new Date(notice.created_at).getFullYear(), new Date(notice.created_at).getMonth(), new Date(notice.created_at).getDate()).getTime()) / 86_400_000);
    const group = day <= 0 ? 'Today' : day === 1 ? 'Yesterday' : day < 7 ? 'This Week' : 'Earlier';
    groups[group] = [...(groups[group] ?? []), notice];
    return groups;
  }, {});

  async function markRead(notificationId: number | 'all') {
    setSaving(true);
    try {
      const response = await fetch('/api/workspace/parent/notifications-read', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notification_id: notificationId }),
      });
      const result = await responsePayload<{ detail: string }>(response);
      toast.success('Notifications updated', result.detail);
      reload();
    } catch (reason) {
      toast.error('Could not update notifications', reason instanceof Error ? reason.message : 'Try again.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <section>
      <PageHeading eyebrow="Updates" title="Notification center" description="School notices, results, attendance updates and messages connected to your linked children." />
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="flex flex-wrap gap-1.5">{filters.map((value) => <button key={value} type="button" onClick={() => setFilter(value)} className={`rounded-lg px-3 py-2 text-[11px] font-semibold capitalize ${filter === value ? 'bg-blue-600 text-white' : 'bg-slate-50 text-slate-600 hover:bg-slate-100'}`}>{value === 'all' ? 'All' : value.replaceAll('_', ' ')}</button>)}</div>
        <button type="button" disabled={saving || !data.notifications.some((row) => !row.read)} onClick={() => markRead('all')} className="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-[11px] font-semibold text-blue-700 hover:bg-blue-50 disabled:opacity-40"><CheckCheck size={14} />Mark all as read</button>
      </div>
      <div className="space-y-5">{['Today', 'Yesterday', 'This Week', 'Earlier'].map((group) => groupedNotices[group]?.length ? <section key={group}><h2 className="mb-2 px-1 text-xs font-semibold text-slate-500">{group}</h2><div className="space-y-2">{groupedNotices[group].map((notice) => <article key={notice.id} className={`flex gap-3 rounded-2xl border p-4 ${notice.read ? 'border-slate-200 bg-white' : 'border-blue-200 bg-blue-50/50'}`}><span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${notice.read ? 'bg-slate-100 text-slate-500' : 'bg-blue-100 text-blue-700'}`}><Bell size={17} /></span><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><h3 className="text-sm font-semibold text-slate-900">{notice.title}</h3>{!notice.read && <span className="rounded-full bg-blue-600 px-2 py-0.5 text-[9px] font-semibold text-white">New</span>}</div><p className="mt-1 text-xs leading-5 text-slate-600">{notice.message}</p><p className="mt-2 text-[10px] text-slate-400">{notice.student ? `${notice.student} · ` : ''}{readableDate(notice.created_at, true)}</p>{notice.destination.startsWith('/') && !notice.destination.startsWith('//') && <Link href={notice.destination} className="mt-2 inline-block text-[10px] font-semibold text-blue-700 hover:text-blue-900">View details</Link>}</div>{!notice.read && <button type="button" disabled={saving} onClick={() => markRead(notice.id)} className="self-center rounded-lg p-2 text-blue-700 hover:bg-white" aria-label={`Mark ${notice.title} as read`}><Check size={16} /></button>}</article>)}</div></section> : null)}
        {!notices.length && <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center"><Bell size={26} className="mx-auto text-slate-300" /><p className="mt-3 text-sm font-semibold text-slate-800">No notifications here</p><p className="mt-1 text-xs text-slate-500">New school updates will appear in this list.</p></div>}
      </div>
    </section>
  );
}

function ParentReports({ data }: { data: ParentReportsPayload }) {
  const toast = useToast();
  const [studentId, setStudentId] = useState(data.students[0] ? String(data.students[0].id) : '');
  const [termId, setTermId] = useState(data.current_term_id ? String(data.current_term_id) : '');
  const [downloading, setDownloading] = useState(false);

  async function downloadReport() {
    if (!studentId) return;
    setDownloading(true);
    try {
      const response = await fetch('/api/workspace/parent/report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ student_id: studentId, term_id: termId }),
      });
      const report = await responsePayload<{ filename: string; content_type: string; content_base64: string }>(response);
      const binary = atob(report.content_base64);
      const bytes = new Uint8Array(binary.length);
      for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
      const url = URL.createObjectURL(new Blob([bytes], { type: report.content_type }));
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = report.filename;
      anchor.click();
      URL.revokeObjectURL(url);
      toast.success('Report downloaded', report.filename);
    } catch (reason) {
      toast.error('Report unavailable', reason instanceof Error ? reason.message : 'Try again.');
    } finally {
      setDownloading(false);
    }
  }

  return (
    <section>
      <PageHeading eyebrow="Downloads" title="Report center" description="Generate a PDF report from verified assessment results for a child and academic term you can access." />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(300px,0.72fr)]">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="flex items-center gap-3 border-b border-slate-100 pb-4"><span className="grid h-11 w-11 place-items-center rounded-2xl bg-blue-50 text-blue-700"><FileText size={21} /></span><div><h2 className="text-base font-semibold text-slate-900">Academic report</h2><p className="mt-1 text-xs text-slate-500">Verified subject marks in a downloadable PDF.</p></div></div>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <label className="text-xs font-semibold text-slate-600">Child<select value={studentId} onChange={(event) => setStudentId(event.target.value)} className="mt-1.5 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs font-normal"><option value="">Select child</option>{data.students.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
            <label className="text-xs font-semibold text-slate-600">Academic term<select value={termId} onChange={(event) => setTermId(event.target.value)} className="mt-1.5 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs font-normal"><option value="">Current term</option>{data.terms.map((row) => <option key={row.id} value={row.id}>{row.label}</option>)}</select></label>
          </div>
          <button type="button" onClick={downloadReport} disabled={!studentId || downloading} className="mt-5 inline-flex h-10 items-center gap-2 rounded-xl bg-blue-600 px-4 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50">{downloading ? <LoaderCircle size={15} className="animate-spin" /> : <Download size={15} />}Generate & download report</button>
          {!data.students.length && <p className="mt-4 rounded-xl bg-amber-50 p-3 text-xs text-amber-800">Academic report access is not enabled for any linked child.</p>}
        </div>
        <aside className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <h2 className="text-sm font-semibold text-slate-900">Available reports</h2>
          <div className="mt-4 space-y-3">
            <div className="flex gap-3 rounded-xl border border-slate-100 p-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-blue-50 text-blue-700"><BookOpenCheck size={16} /></span><div><p className="text-xs font-semibold text-slate-800">Academic result report</p><p className="mt-1 text-[10px] leading-4 text-slate-500">Verified assessment marks, generated by the existing school report service.</p></div></div>
            <div className="flex gap-3 rounded-xl border border-slate-100 p-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-emerald-50 text-emerald-700"><CalendarDays size={16} /></span><div><p className="text-xs font-semibold text-slate-800">Attendance</p><p className="mt-1 text-[10px] leading-4 text-slate-500">Review attendance details from each child's attendance screen.</p></div></div>
            <div className="flex gap-3 rounded-xl border border-slate-100 p-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-amber-50 text-amber-700"><WalletCards size={16} /></span><div><p className="text-xs font-semibold text-slate-800">Fee statement</p><p className="mt-1 text-[10px] leading-4 text-slate-500">Review balances and receipts where finance access is enabled.</p></div></div>
          </div>
          <p className="mt-4 text-[10px] leading-4 text-slate-400">Only records your parent account is authorised to view are included.</p>
        </aside>
      </div>
    </section>
  );
}
