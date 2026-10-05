'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  ArrowRight,
  Bell,
  CalendarDays,
  CheckCircle2,
  Clock3,
  LoaderCircle,
  RefreshCw,
  Sparkles,
  TrendingUp,
} from 'lucide-react';

import type { WorkspaceBootstrap, WorkspaceDashboard, WorkspaceStat } from '@/lib/workspace';
import { useToast } from '@/components/ui/ToastProvider';
import { WorkspaceIcon } from './WorkspaceIcon';

const toneMap: Record<WorkspaceStat['tone'], { icon: string; value: string; chip: string; bar: string }> = {
  green: { icon: 'bg-emerald-50 text-emerald-600', value: 'text-[#163A2B]', chip: 'text-emerald-600', bar: 'from-emerald-400 to-emerald-500' },
  blue: { icon: 'bg-blue-50 text-blue-600', value: 'text-[#18315F]', chip: 'text-blue-600', bar: 'from-blue-400 to-blue-600' },
  gold: { icon: 'bg-amber-50 text-amber-600', value: 'text-[#5A3C16]', chip: 'text-amber-600', bar: 'from-amber-300 to-amber-500' },
  violet: { icon: 'bg-violet-50 text-violet-600', value: 'text-[#3F2C67]', chip: 'text-violet-600', bar: 'from-violet-400 to-violet-600' },
};

function displayStat(stat: WorkspaceStat) {
  if (stat.currency) {
    const numeric = Number(stat.value);
    if (!Number.isNaN(numeric)) {
      if (Math.abs(numeric) >= 1_000_000) return `UGX ${(numeric / 1_000_000).toFixed(numeric >= 10_000_000 ? 1 : 2)}M`;
      return new Intl.NumberFormat('en-UG', { style: 'currency', currency: 'UGX', maximumFractionDigits: 0 }).format(numeric);
    }
  }
  return String(stat.value);
}

function friendlyDate() {
  return new Intl.DateTimeFormat(undefined, { weekday: 'long', day: '2-digit', month: 'short', year: 'numeric' }).format(new Date());
}

function BarChart({ points, currency = false }: { points: { label: string; value: number; detail?: string }[]; currency?: boolean }) {
  const max = Math.max(...points.map((point) => point.value), 1);
  const format = (value: number) => currency
    ? new Intl.NumberFormat('en-UG', { notation: 'compact', maximumFractionDigits: 1 }).format(value)
    : `${Math.round(value)}%`;

  return (
    <div className="mt-4 flex h-44 items-end gap-2 border-b border-[#EDF1F7] pb-2">
      {points.map((point, index) => (
        <div key={`${point.label}-${index}`} className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-1.5">
          <span className="text-[9px] font-semibold text-[#7687A2]">{format(point.value)}</span>
          <div className="flex w-full flex-1 items-end">
            <div className="w-full rounded-t-md bg-gradient-to-t from-[#2563EB] to-[#69A8FF] shadow-[0_3px_10px_rgba(37,99,235,.12)]" style={{ height: `${Math.max(5, (point.value / max) * 100)}%` }} />
          </div>
          <span className="truncate text-[9px] font-medium text-[#7B8BA4]">{point.label}</span>
        </div>
      ))}
    </div>
  );
}

const quickLabels: Record<string, string[]> = {
  Teacher: ['attendance', 'results', 'timetable', 'students', 'communication'],
  'Class Teacher': ['attendance', 'results', 'timetable', 'students', 'communication'],
  Bursar: ['fees', 'fees-payments', 'finance', 'budgets', 'reports'],
  Librarian: ['library', 'students', 'communication', 'reports'],
  'Library Assistant': ['library', 'students', 'communication'],
  'Admissions Officer': ['admissions', 'students', 'parents', 'communication'],
  Parent: ['parent-children', 'parent-results', 'parent-attendance', 'parent-fees', 'parent-communication'],
};

export function DashboardOverview({ bootstrap }: { bootstrap: WorkspaceBootstrap }) {
  const toast = useToast();
  const [data, setData] = useState<WorkspaceDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetch('/api/workspace/dashboard', { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || 'Dashboard data could not be loaded.');
        return result as WorkspaceDashboard;
      })
      .then(setData)
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        toast.error('Dashboard unavailable', reason instanceof Error ? reason.message : 'Dashboard data could not be loaded.');
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [reloadKey, toast]);

  const allModules = useMemo(() => bootstrap.navigation.flatMap((group) => group.items).filter((item) => item.resource), [bootstrap.navigation]);
  const preferred = quickLabels[bootstrap.user.role.label] ?? ['students', 'admissions', 'attendance', 'results', 'fees', 'reports'];
  const quickModules = useMemo(() => {
    const ordered = preferred.map((slug) => allModules.find((item) => item.slug === slug)).filter(Boolean);
    const remaining = allModules.filter((item) => !ordered.some((entry) => entry?.slug === item.slug));
    return [...ordered, ...remaining].slice(0, 6) as typeof allModules;
  }, [allModules, preferred]);

  const firstName = bootstrap.user.name.split(/\s+/)[0] || bootstrap.user.username;
  const attendance = data?.analytics?.attendance_trend ?? [];
  const collection = data?.analytics?.collection_trend ?? [];
  const chart = attendance.length ? attendance : collection;
  const chartCurrency = !attendance.length && collection.length > 0;

  return (
    <section className="space-y-4">
      <div className="relative overflow-hidden rounded-[20px] border border-blue-100 bg-gradient-to-r from-[#EAF3FF] via-[#F1F7FF] to-[#E7F1FF] px-5 py-5 sm:px-6">
        <div className="pointer-events-none absolute -right-12 -top-16 h-48 w-48 rounded-full border border-blue-200/50" />
        <div className="pointer-events-none absolute right-16 top-4 h-24 w-24 rounded-full bg-blue-300/15 blur-2xl" />
        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-white text-[#2563EB] shadow-[0_8px_20px_rgba(37,99,235,.10)]"><Sparkles size={22} /></span>
            <div>
              <h1 className="text-xl font-bold tracking-[-0.025em] text-[#10224A] sm:text-[1.55rem]">Good {new Date().getHours() < 12 ? 'morning' : new Date().getHours() < 18 ? 'afternoon' : 'evening'}, {firstName} 👋</h1>
              <p className="mt-1 text-xs text-[#647694]">Here’s what’s happening at {bootstrap.school.name} today.</p>
            </div>
          </div>
          <div className="flex items-center gap-3 self-start text-right sm:self-auto">
            <div className="hidden sm:block">
              <p className="text-[10px] font-semibold text-[#7285A3]">{friendlyDate()}</p>
              <p className="mt-1 text-[10px] text-[#8A9AB2]">{bootstrap.academic_context.year || 'Academic year not set'}{bootstrap.academic_context.term ? ` · ${bootstrap.academic_context.term}` : ''}</p>
            </div>
            <button type="button" onClick={() => setReloadKey((value) => value + 1)} className="clay-icon-button" aria-label="Refresh dashboard"><RefreshCw size={15} className={loading ? 'animate-spin' : ''} /></button>
          </div>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {loading && !data ? Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="h-[112px] animate-pulse rounded-2xl border border-[#E6EDF6] bg-white p-4"><div className="h-3 w-24 rounded bg-slate-100" /><div className="mt-4 h-6 w-28 rounded bg-slate-100" /><div className="mt-3 h-2.5 w-32 rounded bg-slate-100" /></div>
        )) : data?.stats.slice(0, 8).map((stat, index) => {
          const tone = toneMap[stat.tone];
          const iconName = quickModules[index % Math.max(quickModules.length, 1)]?.icon ?? 'dashboard';
          return (
            <article key={stat.label} className="tafiti-kpi min-h-[108px]">
              <div className="relative z-10 flex items-start justify-between gap-3">
                <span className={`grid h-9 w-9 place-items-center rounded-xl ${tone.icon}`}><WorkspaceIcon name={iconName} size={17} /></span>
                <span className={`inline-flex items-center gap-1 text-[9px] font-bold ${tone.chip}`}><TrendingUp size={11} /> Live</span>
              </div>
              <p className={`relative z-10 mt-3 text-xl font-bold tracking-[-0.025em] ${tone.value}`}>{displayStat(stat)}</p>
              <p className="relative z-10 mt-0.5 text-[10px] font-semibold text-[#71819B]">{stat.label}</p>
              <p className="relative z-10 mt-1 truncate text-[9px] text-[#97A4B7]">{stat.hint}</p>
            </article>
          );
        })}
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.45fr)_minmax(310px,.75fr)]">
        <article className="tafiti-card p-4 sm:p-5">
          <div className="flex items-center justify-between gap-3">
            <div><h2 className="text-sm font-bold text-[#142747]">School Overview</h2><p className="mt-1 text-[10px] text-[#8190A8]">Recent school performance and activity trend.</p></div>
            <span className="rounded-lg border border-[#E4EBF5] bg-[#F8FAFD] px-2.5 py-1 text-[10px] font-semibold text-[#62738F]">{bootstrap.academic_context.term || 'Current term'}</span>
          </div>
          {chart.length ? <BarChart points={chart} currency={chartCurrency} /> : <div className="mt-4 grid h-44 place-items-center rounded-xl bg-[#F8FAFD] text-xs text-[#8190A8]">Chart data will appear as school records are added.</div>}
        </article>

        <article className="tafiti-card p-4 sm:p-5">
          <div className="flex items-center justify-between gap-3"><div><h2 className="text-sm font-bold text-[#142747]">Quick Actions</h2><p className="mt-1 text-[10px] text-[#8190A8]">Jump straight into your most common tasks.</p></div><CheckCircle2 size={17} className="text-[#2563EB]" /></div>
          <div className="mt-4 grid grid-cols-2 gap-2.5">
            {quickModules.map((item, index) => (
              <Link key={item.slug} href={`${bootstrap.user.dashboard_path}/${item.slug}`} className="group flex min-h-[62px] items-center gap-2.5 rounded-xl border border-[#E7EDF6] bg-[#FAFCFF] px-3 py-2.5 transition hover:-translate-y-0.5 hover:border-blue-200 hover:bg-white hover:shadow-[0_8px_18px_rgba(37,99,235,.07)]">
                <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg ${index % 4 === 0 ? 'bg-blue-50 text-blue-600' : index % 4 === 1 ? 'bg-emerald-50 text-emerald-600' : index % 4 === 2 ? 'bg-amber-50 text-amber-600' : 'bg-violet-50 text-violet-600'}`}><WorkspaceIcon name={item.icon} size={15} /></span>
                <span className="min-w-0 flex-1 text-[10px] font-bold leading-4 text-[#43536C] group-hover:text-[#2563EB]">{item.label}</span>
              </Link>
            ))}
          </div>
        </article>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <article className="tafiti-card overflow-hidden">
          <div className="flex items-center justify-between border-b border-[#EDF1F7] px-4 py-3.5 sm:px-5"><div><h2 className="text-sm font-bold text-[#142747]">Recent Activity</h2><p className="mt-1 text-[10px] text-[#8190A8]">Latest workflow updates and school notices.</p></div><Bell size={16} className="text-[#71819B]" /></div>
          <div className="divide-y divide-[#F0F3F8]">
            {(data?.notifications ?? []).slice(0, 5).map((note, index) => (
              <div key={note.id || index} className="flex items-start gap-3 px-4 py-3 sm:px-5">
                <span className={`mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg ${index % 4 === 0 ? 'bg-blue-50 text-blue-600' : index % 4 === 1 ? 'bg-emerald-50 text-emerald-600' : index % 4 === 2 ? 'bg-amber-50 text-amber-600' : 'bg-violet-50 text-violet-600'}`}><Bell size={13} /></span>
                <div className="min-w-0 flex-1"><p className="truncate text-[11px] font-bold text-[#344761]">{note.title}</p><p className="mt-0.5 line-clamp-1 text-[10px] text-[#8795A9]">{note.message}</p></div>
              </div>
            ))}
            {!data?.notifications?.length && <div className="px-5 py-8 text-center text-xs text-[#8795A9]">No recent activity to show yet.</div>}
          </div>
        </article>

        <article className="tafiti-card overflow-hidden">
          <div className="flex items-center justify-between border-b border-[#EDF1F7] px-4 py-3.5 sm:px-5"><div><h2 className="text-sm font-bold text-[#142747]">Needs Attention</h2><p className="mt-1 text-[10px] text-[#8190A8]">Items that may need action from your role.</p></div><Clock3 size={16} className="text-[#71819B]" /></div>
          <div className="divide-y divide-[#F0F3F8]">
            {(data?.attention ?? []).slice(0, 5).map((item, index) => (
              <Link key={`${item.resource}-${index}`} href={`${bootstrap.user.dashboard_path}/${item.resource}`} className="group flex items-center gap-3 px-4 py-3 transition hover:bg-[#F8FAFE] sm:px-5">
                <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl ${item.severity === 'danger' ? 'bg-rose-50 text-rose-600' : item.severity === 'warning' ? 'bg-amber-50 text-amber-600' : 'bg-blue-50 text-blue-600'}`}><CalendarDays size={15} /></span>
                <span className="min-w-0 flex-1 text-[11px] font-semibold text-[#4A5B76]">{item.title}</span>
                <ArrowRight size={14} className="text-[#A0ADBF] transition group-hover:translate-x-0.5 group-hover:text-[#2563EB]" />
              </Link>
            ))}
            {!data?.attention?.length && <div className="px-5 py-8 text-center text-xs text-[#8795A9]">Nothing urgent right now.</div>}
          </div>
        </article>
      </div>
    </section>
  );
}
