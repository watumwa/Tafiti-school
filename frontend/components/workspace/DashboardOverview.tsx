'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  ArrowRight,
  Bell,
  CalendarDays,
  ChevronRight,
  GraduationCap,
  LoaderCircle,
  MapPin,
  RefreshCw,
  Sparkles,
  WalletCards,
} from 'lucide-react';

import type { WorkspaceBootstrap, WorkspaceDashboard, WorkspaceStat } from '@/lib/workspace';
import { useToast } from '@/components/ui/ToastProvider';
import { WorkspaceIcon } from './WorkspaceIcon';

const toneClasses: Record<WorkspaceStat['tone'], { card: string; value: string; dot: string }> = {
  green: { card: 'border-emerald-200/80 bg-emerald-50/55', value: 'text-emerald-950', dot: 'bg-emerald-600' },
  blue: { card: 'border-blue-200/80 bg-blue-50/55', value: 'text-blue-950', dot: 'bg-blue-600' },
  gold: { card: 'border-amber-200/80 bg-amber-50/60', value: 'text-amber-950', dot: 'bg-amber-600' },
  violet: { card: 'border-violet-200/80 bg-violet-50/55', value: 'text-violet-950', dot: 'bg-violet-600' },
};

function displayStat(stat: WorkspaceStat) {
  if (stat.currency) {
    const numeric = Number(stat.value);
    if (!Number.isNaN(numeric)) {
      return new Intl.NumberFormat('en-UG', { style: 'currency', currency: 'UGX', maximumFractionDigits: 0 }).format(numeric);
    }
  }
  return String(stat.value);
}

function TrendPanel({
  title,
  description,
  points,
  currency = false,
}: {
  title: string;
  description: string;
  points: { label: string; value: number; detail?: string }[];
  currency?: boolean;
}) {
  const max = Math.max(...points.map((point) => point.value), 1);
  const hasValues = points.some((point) => point.value > 0);
  const formatValue = (value: number) => currency
    ? new Intl.NumberFormat('en-UG', { notation: 'compact', maximumFractionDigits: 1 }).format(value)
    : `${value}%`;
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_5px_18px_rgba(15,23,42,0.025)] sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div><h2 className="text-sm font-semibold text-slate-950">{title}</h2><p className="mt-1 text-[11px] text-slate-500">{description}</p></div>
        <span className="rounded-lg bg-blue-50 px-2 py-1 text-[10px] font-semibold text-blue-700">Recent trend</span>
      </div>
      {hasValues ? (
        <div className="mt-5 flex h-36 items-end gap-2 border-b border-slate-100 pb-2" role="img" aria-label={`${title}: ${points.map((point) => `${point.label} ${formatValue(point.value)}`).join(', ')}`}>
          {points.map((point) => (
            <div key={point.label} className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-1" title={point.detail ? `${point.detail} · ${formatValue(point.value)}` : formatValue(point.value)}>
              <span className="truncate text-[9px] font-semibold text-slate-600">{formatValue(point.value)}</span>
              <div className="flex w-full flex-1 items-end">
                <div className="w-full rounded-t-md bg-gradient-to-t from-blue-600 to-sky-400 transition-[height] duration-200" style={{ height: `${Math.max(3, point.value / max * 100)}%` }} />
              </div>
              <span className="text-[9px] font-medium text-slate-400">{point.label}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-5 grid h-36 place-items-center rounded-xl bg-slate-50 text-center"><p className="text-xs text-slate-500">Chart data will appear as records are added.</p></div>
      )}
    </article>
  );
}

function formatShortDate(value: string) {
  if (!value) return 'Date not set';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short' }).format(date);
}

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

  const quickModules = useMemo(
    () => bootstrap.navigation.flatMap((group) => group.items).filter((item) => item.resource).slice(0, 6),
    [bootstrap.navigation],
  );

  const firstName = bootstrap.user.name.split(/\s+/)[0] || bootstrap.user.username;
  const parentPortal = data?.parent_portal;
  const parentPath = bootstrap.user.dashboard_path;

  return (
    <section>
      <div className="relative overflow-hidden rounded-[26px] bg-[#102A43] px-5 py-6 text-white shadow-[0_18px_55px_rgba(15,39,71,0.16)] sm:px-7 sm:py-7 lg:px-8">
        <div className="absolute -right-16 -top-24 h-64 w-64 rounded-full border border-white/10" aria-hidden="true" />
        <div className="absolute -bottom-28 right-28 h-52 w-52 rounded-full bg-emerald-500/10 blur-2xl" aria-hidden="true" />
        <div className="relative flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.07] px-3 py-1.5 text-[11px] font-semibold text-slate-200">
              <Sparkles size={13} className="text-amber-300" />
              {data?.role || bootstrap.user.role.label} workspace
            </div>
            <h1 className="mt-4 text-2xl font-semibold tracking-[-0.025em] sm:text-[2rem]">Good to see you, {firstName}</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
              {bootstrap.school.name} · {bootstrap.academic_context.year || 'Academic year not set'} {bootstrap.academic_context.term ? `· ${bootstrap.academic_context.term}` : ''}
            </p>
          </div>
          <button type="button" onClick={() => setReloadKey((value) => value + 1)} className="inline-flex h-10 items-center gap-2 self-start rounded-xl border border-white/15 bg-white/[0.06] px-3 text-xs font-semibold text-white transition hover:bg-white/[0.11] sm:self-auto">
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {loading && !data
          ? Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="h-[126px] animate-pulse rounded-2xl border border-slate-200 bg-white p-5"><div className="h-3 w-24 rounded bg-slate-100" /><div className="mt-5 h-7 w-28 rounded bg-slate-100" /><div className="mt-3 h-3 w-36 rounded bg-slate-100" /></div>
            ))
          : data?.stats.map((stat) => {
              const tone = toneClasses[stat.tone];
              return (
                <article key={stat.label} className={`rounded-2xl border p-5 ${tone.card}`}>
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-xs font-semibold text-slate-600">{stat.label}</p>
                    <span className={`h-2 w-2 rounded-full ${tone.dot}`} />
                  </div>
                  <p className={`mt-3 text-2xl font-semibold tracking-[-0.025em] ${tone.value}`}>{displayStat(stat)}</p>
                  <p className="mt-2 text-[11px] font-medium text-slate-500">{stat.hint}</p>
                </article>
              );
            })}
      </div>

      {!!(data?.analytics?.attendance_trend?.length || data?.analytics?.collection_trend?.length) && (
        <div className="mt-5 grid gap-4 xl:grid-cols-2">
          {data.analytics.attendance_trend?.length ? <TrendPanel title="Attendance trend" description="Share of marked attendance records present, late or excused this week." points={data.analytics.attendance_trend} /> : null}
          {data.analytics.collection_trend?.length ? <TrendPanel title="Fee collection trend" description="Recorded payment totals over the last six months." points={data.analytics.collection_trend} currency /> : null}
        </div>
      )}

      <div className="mt-6 grid gap-5 xl:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.8fr)]">
        <div>
          <div className="mb-3 flex items-end justify-between gap-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.12em] text-emerald-700">Quick access</p>
              <h2 className="mt-1 text-lg font-semibold tracking-[-0.015em] text-slate-950">Your modules</h2>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {quickModules.map((item) => (
              <Link key={item.slug} href={`${bootstrap.user.dashboard_path}/${item.slug}`} className="group flex min-h-[104px] items-start gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_5px_18px_rgba(15,23,42,0.025)] transition hover:-translate-y-0.5 hover:border-emerald-200 hover:shadow-[0_12px_28px_rgba(15,23,42,0.06)]">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#EEF6F3] text-emerald-800 transition group-hover:bg-emerald-100"><WorkspaceIcon name={item.icon} /></span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold text-slate-900">{item.label}</span>
                  <span className="mt-1 block text-xs leading-5 text-slate-500">Open {item.label.toLowerCase()} workspace</span>
                </span>
                <ArrowRight size={16} className="mt-1 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-emerald-700" />
              </Link>
            ))}
          </div>
        </div>

        <aside className="rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_5px_18px_rgba(15,23,42,0.025)] sm:p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.12em] text-amber-700">Attention</p>
              <h2 className="mt-1 text-lg font-semibold tracking-[-0.015em] text-slate-950">Needs a look</h2>
            </div>
            <AlertTriangle size={19} className="text-amber-500" />
          </div>
          <div className="mt-4 space-y-2">
            {data?.attention.length ? data.attention.map((item, index) => (
              <Link key={`${item.resource}-${index}`} href={`${bootstrap.user.dashboard_path}/${item.resource}`} className="flex items-start gap-3 rounded-xl border border-slate-100 bg-slate-50/70 p-3 transition hover:border-slate-200 hover:bg-slate-50">
                <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${item.severity === 'warning' ? 'bg-amber-500' : item.severity === 'danger' ? 'bg-red-500' : 'bg-blue-500'}`} />
                <span className="text-xs font-medium leading-5 text-slate-700">{item.title}</span>
              </Link>
            )) : (
              <div className="rounded-xl border border-dashed border-slate-200 px-4 py-8 text-center">
                <p className="text-sm font-semibold text-slate-800">Nothing urgent</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">No major workflow items are waiting right now.</p>
              </div>
            )}
          </div>

          {!!data?.notifications.length && (
            <div className="mt-5 border-t border-slate-100 pt-4">
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-700"><Bell size={15} className="text-slate-400" /> Recent notice</div>
              <p className="mt-2 text-sm font-semibold text-slate-900">{data.notifications[0].title}</p>
              <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{data.notifications[0].message}</p>
            </div>
          )}
        </aside>
      </div>

      {data?.role === 'Parent' && parentPortal && (
        <section className="mt-8 space-y-7" aria-label="Parent portal overview">
          <div>
            <div className="mb-3 flex items-end justify-between gap-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.12em] text-emerald-700">Family</p>
                <h2 className="mt-1 text-lg font-semibold tracking-[-0.015em] text-slate-950">Your children</h2>
              </div>
              <Link href={`${parentPath}/parent-children`} className="inline-flex items-center gap-1 text-xs font-semibold text-[#3157D5] hover:text-blue-800">
                View all <ChevronRight size={15} />
              </Link>
            </div>
            {parentPortal.children.length ? (
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {parentPortal.children.map((child) => (
                  <article key={child.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_5px_18px_rgba(15,23,42,0.025)]">
                    <div className="flex items-center gap-3">
                      {child.photo ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={child.photo} alt="" className="h-12 w-12 rounded-2xl object-cover" />
                      ) : (
                        <span className="grid h-12 w-12 place-items-center rounded-2xl bg-blue-50 text-blue-700"><GraduationCap size={21} /></span>
                      )}
                      <div className="min-w-0 flex-1">
                        <h3 className="truncate text-sm font-semibold text-slate-950">{child.name}</h3>
                        <p className="mt-0.5 truncate text-xs text-slate-500">{child.class}{child.stream ? ` · ${child.stream}` : ''}</p>
                        <p className="mt-1 text-[10px] font-medium text-slate-400">{child.student_id}</p>
                      </div>
                      <Link href={`${parentPath}/parent-children`} className="grid h-8 w-8 place-items-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label={`Open ${child.name}'s profile`}><ChevronRight size={17} /></Link>
                    </div>
                    <div className="mt-4 grid grid-cols-3 gap-2 border-t border-slate-100 pt-3">
                      <div>
                        <p className="text-[10px] text-slate-500">Attendance</p>
                        <p className="mt-1 text-sm font-semibold text-slate-800">{child.attendance_percent === null ? '—' : `${child.attendance_percent}%`}</p>
                      </div>
                      <div>
                        <p className="text-[10px] text-slate-500">Average</p>
                        <p className="mt-1 text-sm font-semibold text-slate-800">{child.academic_average === null ? '—' : `${child.academic_average}%`}</p>
                      </div>
                      <div>
                        <p className="text-[10px] text-slate-500">Balance</p>
                        <p className="mt-1 inline-flex items-center gap-1 text-sm font-semibold text-slate-800">
                          {child.outstanding_balance === null ? '—' : <><WalletCards size={13} /> {Number(child.outstanding_balance).toLocaleString('en-UG')}</>}
                        </p>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-5 py-8 text-center text-sm text-slate-500">No active children are linked to this account.</div>
            )}
          </div>

          <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
            <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_5px_18px_rgba(15,23,42,0.025)] sm:p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.12em] text-blue-700">Academics</p>
                  <h2 className="mt-1 text-lg font-semibold text-slate-950">Recent verified results</h2>
                </div>
                <Link href={`${parentPath}/parent-results`} className="text-xs font-semibold text-[#3157D5] hover:text-blue-800">View results</Link>
              </div>
              {parentPortal.recent_results.length ? (
                <div className="mt-4 divide-y divide-slate-100">
                  {parentPortal.recent_results.map((result) => (
                    <div key={result.id} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
                      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-blue-50 text-blue-700"><GraduationCap size={17} /></span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-semibold text-slate-900">{result.subject} <span className="font-normal text-slate-500">· {result.student}</span></p>
                        <p className="mt-1 truncate text-[11px] text-slate-500">{result.assessment} · {formatShortDate(result.date)}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-semibold text-slate-900">{result.percentage}%</p>
                        <p className="text-[10px] font-medium text-slate-500">Grade {result.grade}</p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-4 rounded-xl bg-slate-50 px-4 py-7 text-center text-xs text-slate-500">Verified results will appear here when published.</p>
              )}
            </section>

            <section className="space-y-5">
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_5px_18px_rgba(15,23,42,0.025)] sm:p-5">
                <div className="flex items-center gap-2">
                  <CalendarDays size={17} className="text-emerald-700" />
                  <h2 className="text-sm font-semibold text-slate-950">Upcoming events</h2>
                </div>
                {parentPortal.upcoming_events.length ? (
                  <div className="mt-3 space-y-2">
                    {parentPortal.upcoming_events.map((event) => (
                      <div key={event.id} className="flex items-start gap-3 rounded-xl bg-slate-50 p-3">
                        <span className="min-w-[42px] rounded-lg bg-white px-2 py-1.5 text-center text-[10px] font-bold text-blue-700">{formatShortDate(event.starts_at)}</span>
                        <div className="min-w-0">
                          <p className="text-xs font-semibold text-slate-800">{event.title}</p>
                          {event.location && <p className="mt-1 inline-flex items-center gap-1 text-[10px] text-slate-500"><MapPin size={11} /> {event.location}</p>}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : <p className="mt-3 rounded-xl bg-slate-50 px-3 py-5 text-center text-xs text-slate-500">No upcoming events have been announced.</p>}
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_5px_18px_rgba(15,23,42,0.025)] sm:p-5">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-sm font-semibold text-slate-950">School announcements</h2>
                  <Link href={`${parentPath}/parent-communication`} className="text-xs font-semibold text-[#3157D5] hover:text-blue-800">All</Link>
                </div>
                {parentPortal.announcements.length ? (
                  <div className="mt-3 space-y-3">
                    {parentPortal.announcements.map((announcement) => (
                      <article key={announcement.id} className="border-l-2 border-emerald-500 pl-3">
                        <div className="flex items-center justify-between gap-2">
                          <h3 className="text-xs font-semibold text-slate-800">{announcement.title}</h3>
                          <span className="shrink-0 text-[10px] text-slate-400">{formatShortDate(announcement.starts_at)}</span>
                        </div>
                        <p className="mt-1 line-clamp-2 text-[11px] leading-5 text-slate-500">{announcement.body}</p>
                      </article>
                    ))}
                  </div>
                ) : <p className="mt-3 rounded-xl bg-slate-50 px-3 py-5 text-center text-xs text-slate-500">No active announcements.</p>}
              </div>
            </section>
          </div>
        </section>
      )}
    </section>
  );
}
