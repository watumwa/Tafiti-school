'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  ArrowRight,
  BellRing,
  BookOpen,
  CalendarCheck,
  CalendarDays,
  ChartNoAxesColumnIncreasing,
  CircleDollarSign,
  Clock3,
  FileText,
  GraduationCap,
  Library,
  LoaderCircle,
  Plus,
  ReceiptText,
  Sparkles,
  UserPlus,
  Users,
  WalletCards,
} from 'lucide-react';

import type { WorkspaceBootstrap, WorkspaceDashboard, WorkspaceResource, WorkspaceStat } from '@/lib/workspace';
import { ProfileAvatar } from '@/components/workspace/ProfileAvatar';
import { WorkspaceIcon } from '@/components/workspace/WorkspaceIcon';
import { ClassTeacherDashboardPanel } from './ReferenceClassTeacherWorkspace';

const toneStyles: Record<WorkspaceStat['tone'], { bg: string; icon: string; accent: string }> = {
  green: { bg: 'bg-emerald-50', icon: 'text-emerald-600', accent: 'text-emerald-600' },
  blue: { bg: 'bg-blue-50', icon: 'text-blue-600', accent: 'text-blue-600' },
  gold: { bg: 'bg-amber-50', icon: 'text-amber-600', accent: 'text-amber-600' },
  violet: { bg: 'bg-violet-50', icon: 'text-violet-600', accent: 'text-violet-600' },
};

function statIcon(label: string) {
  const value = label.toLowerCase();
  if (value.includes('student') || value.includes('child')) return Users;
  if (value.includes('staff') || value.includes('class')) return GraduationCap;
  if (value.includes('attendance')) return CalendarCheck;
  if (value.includes('fee') || value.includes('collect') || value.includes('credit')) return CircleDollarSign;
  if (value.includes('result') || value.includes('mark')) return ChartNoAxesColumnIncreasing;
  if (value.includes('book') || value.includes('loan')) return BookOpen;
  if (value.includes('admission') || value.includes('application')) return UserPlus;
  if (value.includes('reconcil')) return ReceiptText;
  return Sparkles;
}

function displayStat(stat: WorkspaceStat) {
  if (!stat.currency) return String(stat.value);
  const numeric = Number(stat.value);
  if (Number.isNaN(numeric)) return String(stat.value).startsWith('UGX') ? String(stat.value) : `UGX ${stat.value}`;
  return new Intl.NumberFormat('en-UG', { style: 'currency', currency: 'UGX', maximumFractionDigits: 0 }).format(numeric);
}

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

function prettyDate() {
  return new Intl.DateTimeFormat(undefined, { weekday: 'long', day: '2-digit', month: 'short', year: 'numeric' }).format(new Date());
}

function TrendChart({ points, title }: { points: { label: string; value: number; detail?: string }[]; title: string }) {
  const max = Math.max(...points.map((item) => item.value), 1);
  return (
    <section className="tafiti-card p-4 sm:p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-[#10224A]">{title}</h2>
          <p className="mt-1 text-[11px] text-slate-500">Live values from the existing Django records.</p>
        </div>
        <span className="rounded-lg border border-blue-100 bg-blue-50 px-2.5 py-1 text-[10px] font-bold text-blue-700">Current term</span>
      </div>
      <div className="mt-5 flex h-[170px] items-end gap-2 border-b border-slate-100 pb-2">
        {points.length ? points.map((point) => (
          <div key={point.label} className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-1.5" title={point.detail || String(point.value)}>
            <span className="text-[9px] font-bold text-slate-500">{point.value}</span>
            <div className="flex w-full flex-1 items-end rounded-t-lg bg-blue-50/55 px-1">
              <div className="w-full rounded-t-md bg-gradient-to-t from-[#2563EB] to-[#62A8FF]" style={{ height: `${Math.max(4, (point.value / max) * 100)}%` }} />
            </div>
            <span className="max-w-full truncate text-[9px] font-semibold text-slate-400">{point.label}</span>
          </div>
        )) : (
          <div className="grid h-full w-full place-items-center text-xs text-slate-400">No chart data yet.</div>
        )}
      </div>
    </section>
  );
}

function QuickAction({ href, label, icon }: { href: string; label: string; icon: string }) {
  return (
    <Link href={href} className="group flex items-center gap-3 rounded-xl border border-slate-100 bg-white px-3.5 py-3 shadow-[0_4px_12px_rgba(28,55,97,.035)] transition hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-[0_10px_22px_rgba(37,99,235,.08)]">
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-blue-50 text-blue-600"><WorkspaceIcon name={icon} size={17} /></span>
      <span className="min-w-0 flex-1 text-xs font-bold text-[#233653]">{label}</span>
      <ArrowRight size={14} className="text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-blue-600" />
    </Link>
  );
}

function TeacherPanel({ resource }: { resource: WorkspaceResource | null }) {
  const rows = resource?.rows ?? [];
  const classes = Array.from(new Set(rows.map((row) => String(row.class ?? '')).filter(Boolean))).slice(0, 4);
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(280px,.8fr)]">
      <section className="tafiti-card overflow-hidden">
        <div className="border-b border-slate-100 px-4 py-3.5 sm:px-5"><h2 className="text-sm font-bold text-[#10224A]">Today&apos;s schedule</h2><p className="mt-1 text-[11px] text-slate-500">Your timetable from the existing school schedule.</p></div>
        <div className="divide-y divide-slate-100">
          {rows.slice(0, 6).map((row, index) => (
            <div key={String(row.id ?? index)} className="flex items-center gap-3 px-4 py-3 sm:px-5">
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-blue-50 text-blue-600"><Clock3 size={16} /></span>
              <div className="min-w-0 flex-1"><p className="truncate text-xs font-bold text-slate-800">{String(row.subject ?? 'Lesson')}</p><p className="mt-0.5 truncate text-[10px] text-slate-500">{String(row.class ?? 'Class')} · {String(row.room ?? 'Room not set')}</p></div>
              <span className="text-[10px] font-semibold text-slate-500">{String(row.time ?? '')}</span>
            </div>
          ))}
          {!rows.length && <div className="px-5 py-10 text-center text-xs text-slate-400">No timetable entries are assigned yet.</div>}
        </div>
      </section>
      <section className="tafiti-card p-4 sm:p-5">
        <div className="flex items-center justify-between"><h2 className="text-sm font-bold text-[#10224A]">My classes</h2><GraduationCap size={18} className="text-blue-600" /></div>
        <div className="mt-4 space-y-2.5">
          {classes.map((className, index) => (
            <div key={className} className="flex items-center gap-3 rounded-xl border border-slate-100 bg-[#F8FAFD] p-3">
              <span className={`grid h-9 w-9 place-items-center rounded-xl ${index % 2 ? 'bg-violet-50 text-violet-600' : 'bg-blue-50 text-blue-600'}`}><Users size={16} /></span>
              <div><p className="text-xs font-bold text-slate-800">{className}</p><p className="mt-0.5 text-[10px] text-slate-500">Open class workspace</p></div>
            </div>
          ))}
          {!classes.length && <p className="py-7 text-center text-xs text-slate-400">Assigned classes will appear here.</p>}
        </div>
      </section>
    </div>
  );
}

function ParentPanel({ data, dashboardPath }: { data: WorkspaceDashboard; dashboardPath: string }) {
  const children = data.parent_portal?.children ?? [];
  const events = data.parent_portal?.upcoming_events ?? [];
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(300px,.7fr)]">
      <section className="tafiti-card p-4 sm:p-5">
        <div className="flex items-center justify-between"><div><h2 className="text-sm font-bold text-[#10224A]">My children</h2><p className="mt-1 text-[11px] text-slate-500">Linked student profiles and current progress.</p></div><Link href={`${dashboardPath}/parent-children`} className="text-[11px] font-bold text-blue-600">View all</Link></div>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {children.map((child) => (
            <article key={child.id} className="rounded-2xl border border-slate-100 bg-[#F8FAFD] p-3.5">
              <div className="flex items-center gap-3"><ProfileAvatar src={child.photo} name={child.name} size="md" /><div className="min-w-0 flex-1"><h3 className="truncate text-sm font-bold text-slate-900">{child.name}</h3><p className="mt-0.5 truncate text-[10px] text-slate-500">{child.class}{child.stream ? ` · ${child.stream}` : ''}</p></div><ArrowRight size={14} className="text-slate-300" /></div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-center"><div className="rounded-xl bg-white p-2"><p className="text-sm font-extrabold text-blue-700">{child.attendance_percent ?? '—'}{child.attendance_percent !== null ? '%' : ''}</p><p className="text-[9px] text-slate-400">Attendance</p></div><div className="rounded-xl bg-white p-2"><p className="text-sm font-extrabold text-violet-700">{child.academic_average ?? '—'}{child.academic_average !== null ? '%' : ''}</p><p className="text-[9px] text-slate-400">Average</p></div><div className="rounded-xl bg-white p-2"><p className="truncate text-[11px] font-extrabold text-amber-700">{child.outstanding_balance ? `UGX ${child.outstanding_balance}` : '—'}</p><p className="text-[9px] text-slate-400">Balance</p></div></div>
            </article>
          ))}
        </div>
      </section>
      <section className="tafiti-card p-4 sm:p-5">
        <div className="flex items-center gap-2"><CalendarDays size={17} className="text-blue-600" /><h2 className="text-sm font-bold text-[#10224A]">Upcoming events</h2></div>
        <div className="mt-4 space-y-2.5">
          {events.slice(0, 5).map((event) => (
            <div key={event.id} className="rounded-xl border border-slate-100 bg-[#F8FAFD] p-3"><p className="text-xs font-bold text-slate-800">{event.title}</p><p className="mt-1 text-[10px] text-slate-500">{new Date(event.starts_at).toLocaleDateString()} · {event.location || 'School'}</p></div>
          ))}
          {!events.length && <p className="py-7 text-center text-xs text-slate-400">No upcoming events.</p>}
        </div>
      </section>
    </div>
  );
}

export function ReferenceDashboardOverview({ bootstrap }: { bootstrap: WorkspaceBootstrap }) {
  const [data, setData] = useState<WorkspaceDashboard | null>(null);
  const [supplement, setSupplement] = useState<WorkspaceResource | null>(null);
  const [loading, setLoading] = useState(true);

  const role = bootstrap.user.role.label;
  const firstName = bootstrap.user.name.split(/\s+/)[0] || bootstrap.user.username;

  const supplementResource = useMemo(() => {
    if (role === 'Teacher') return 'timetable';
    if (role === 'Admissions Officer') return 'admissions';
    if (role === 'Librarian' || role === 'Library Assistant') return 'library';
    if (role === 'Bursar') return 'fees-payments';
    return '';
  }, [role]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    Promise.all([
      fetch('/api/workspace/dashboard', { cache: 'no-store', signal: controller.signal }).then(async (response) => {
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || 'Dashboard unavailable.');
        return result as WorkspaceDashboard;
      }),
      supplementResource
        ? fetch(`/api/workspace/resources/${supplementResource}?page_size=12`, { cache: 'no-store', signal: controller.signal }).then(async (response) => response.ok ? await response.json() as WorkspaceResource : null)
        : Promise.resolve(null),
    ]).then(([dashboard, extra]) => {
      setData(dashboard);
      setSupplement(extra);
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [supplementResource]);

  const quickActions = useMemo(() => {
    const items = bootstrap.navigation.flatMap((group) => group.items).filter((item) => item.resource);
    const preferred: Record<string, string[]> = {
      'Admin': ['students', 'attendance', 'results', 'fees-payments', 'admissions'],
      'Head Teacher': ['students', 'attendance', 'results', 'admissions'],
      'Teacher': ['attendance', 'results', 'timetable', 'students'],
      'Class Teacher': ['my-class', 'attendance', 'results', 'timetable', 'students'],
      'Bursar': ['fees-payments', 'fees', 'finance', 'finance-budgets'],
      'Admissions Officer': ['admissions', 'students', 'communication'],
      'Librarian': ['library', 'students', 'communication'],
      'Library Assistant': ['library', 'students', 'communication'],
      'Parent': ['parent-children', 'parent-results', 'parent-attendance', 'parent-finance'],
    };
    const order = preferred[role] ?? items.map((item) => item.slug);
    return order.map((slug) => items.find((item) => item.slug === slug)).filter((item): item is NonNullable<typeof item> => Boolean(item)).slice(0, 5);
  }, [bootstrap.navigation, role]);

  const attendancePoints = data?.analytics?.attendance_trend ?? [];
  const collectionPoints = data?.analytics?.collection_trend ?? [];

  return (
    <section className="space-y-4">
      <header className="relative overflow-hidden rounded-[18px] border border-blue-100 bg-gradient-to-r from-[#EFF6FF] via-[#F7FAFF] to-white px-5 py-5 shadow-[0_8px_24px_rgba(37,99,235,.055)] sm:px-6">
        <div className="absolute -right-10 -top-16 h-44 w-44 rounded-full bg-blue-100/50" aria-hidden="true" />
        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div><h1 className="text-2xl font-extrabold tracking-[-0.035em] text-[#10224A]">{greeting()}, {firstName} <span aria-hidden="true">👋</span></h1><p className="mt-1 text-xs text-slate-500">Here&apos;s what&apos;s happening at {bootstrap.school.name} today.</p></div>
          <div className="text-left sm:text-right"><p className="text-[11px] font-bold text-slate-600">{prettyDate()}</p><p className="mt-1 text-[10px] text-slate-400">{bootstrap.academic_context.year || 'Academic year'} · {bootstrap.academic_context.term || 'Term not set'}</p></div>
        </div>
      </header>

      <div className={`grid gap-3 sm:grid-cols-2 ${data?.stats.length && data.stats.length > 4 ? 'xl:grid-cols-6' : 'xl:grid-cols-4'}`}>
        {loading && !data ? Array.from({ length: 4 }).map((_, index) => <div key={index} className="h-28 animate-pulse rounded-2xl border border-slate-100 bg-white" />) : data?.stats.map((stat) => {
          const style = toneStyles[stat.tone];
          const Icon = statIcon(stat.label);
          return (
            <article key={stat.label} className="tafiti-kpi min-w-0">
              <div className="relative z-10 flex items-start gap-3"><span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${style.bg} ${style.icon}`}><Icon size={18} /></span><div className="min-w-0"><p className="truncate text-[10px] font-bold uppercase tracking-[0.06em] text-slate-400">{stat.label}</p><p className="mt-1 truncate text-xl font-extrabold tracking-[-0.03em] text-[#10224A]">{displayStat(stat)}</p><p className={`mt-1 truncate text-[9px] font-semibold ${style.accent}`}>{stat.hint}</p></div></div>
            </article>
          );
        })}
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(280px,.7fr)]">
        {attendancePoints.length ? <TrendChart points={attendancePoints} title="School overview" /> : collectionPoints.length ? <TrendChart points={collectionPoints} title="Collection overview" /> : <section className="tafiti-card p-5"><div className="grid min-h-[170px] place-items-center text-center"><div><ChartNoAxesColumnIncreasing className="mx-auto text-blue-400" size={28} /><p className="mt-3 text-sm font-bold text-slate-800">Analytics will appear here</p><p className="mt-1 text-xs text-slate-400">The dashboard uses live school records only.</p></div></div></section>}
        <section className="tafiti-card p-4 sm:p-5"><div className="flex items-center justify-between"><div><h2 className="text-sm font-bold text-[#10224A]">Quick actions</h2><p className="mt-1 text-[10px] text-slate-500">Jump directly to your common tasks.</p></div><Plus size={17} className="text-blue-600" /></div><div className="mt-4 space-y-2.5">{quickActions.map((item) => <QuickAction key={item.slug} href={`${bootstrap.user.dashboard_path}/${item.slug}`} label={item.label} icon={item.icon} />)}</div></section>
      </div>

      {role === 'Teacher' && <TeacherPanel resource={supplement} />}
      {role === 'Class Teacher' && <ClassTeacherDashboardPanel dashboardPath={bootstrap.user.dashboard_path} />}
      {role === 'Parent' && data && <ParentPanel data={data} dashboardPath={bootstrap.user.dashboard_path} />}

      {(role === 'Admissions Officer' || role === 'Librarian' || role === 'Library Assistant' || role === 'Bursar') && (
        <section className="tafiti-card overflow-hidden">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3.5 sm:px-5"><div><h2 className="text-sm font-bold text-[#10224A]">Recent workspace activity</h2><p className="mt-1 text-[10px] text-slate-500">Recent live records for your role.</p></div>{role === 'Bursar' ? <WalletCards size={18} className="text-blue-600" /> : role === 'Admissions Officer' ? <UserPlus size={18} className="text-blue-600" /> : <Library size={18} className="text-blue-600" />}</div>
          <div className="divide-y divide-slate-100">{supplement?.rows.slice(0, 6).map((row, index) => <div key={String(row.id ?? index)} className="flex items-center gap-3 px-4 py-3 sm:px-5"><span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-blue-50 text-blue-600">{role === 'Admissions Officer' ? <UserPlus size={15} /> : role === 'Bursar' ? <ReceiptText size={15} /> : <BookOpen size={15} />}</span><div className="min-w-0 flex-1"><p className="truncate text-xs font-bold text-slate-800">{String(row.student ?? row.book ?? row.application ?? row.reference ?? 'Record')}</p><p className="mt-0.5 truncate text-[10px] text-slate-500">{String(row.status ?? row.reconciliation ?? row.class ?? '')}</p></div></div>) ?? null}{!supplement?.rows.length && <div className="px-5 py-10 text-center text-xs text-slate-400">No recent records.</div>}</div>
        </section>
      )}

      {!!data?.attention.length && (
        <section className="tafiti-card p-4 sm:p-5"><div className="flex items-center gap-2"><BellRing size={17} className="text-amber-500" /><h2 className="text-sm font-bold text-[#10224A]">Needs attention</h2></div><div className="mt-3 grid gap-2.5 md:grid-cols-2">{data.attention.slice(0, 6).map((item, index) => <Link key={`${item.resource}-${index}`} href={`${bootstrap.user.dashboard_path}/${item.resource}`} className="flex items-center gap-3 rounded-xl border border-slate-100 bg-[#F8FAFD] p-3 text-xs font-semibold text-slate-700 hover:border-blue-200"><span className={`h-2 w-2 rounded-full ${item.severity === 'danger' ? 'bg-red-500' : item.severity === 'warning' ? 'bg-amber-500' : 'bg-blue-500'}`} />{item.title}<ArrowRight className="ml-auto text-slate-300" size={13} /></Link>)}</div></section>
      )}

      {!!data?.notifications.length && (
        <section className="tafiti-card p-4 sm:p-5"><div className="flex items-center gap-2"><FileText size={17} className="text-violet-600" /><h2 className="text-sm font-bold text-[#10224A]">Recent notices</h2></div><div className="mt-3 grid gap-2.5 md:grid-cols-2">{data.notifications.slice(0, 4).map((notice) => <div key={notice.id} className="rounded-xl border border-slate-100 bg-[#F8FAFD] p-3"><p className="text-xs font-bold text-slate-800">{notice.title}</p><p className="mt-1 line-clamp-2 text-[10px] leading-4 text-slate-500">{notice.message}</p></div>)}</div></section>
      )}
    </section>
  );
}
