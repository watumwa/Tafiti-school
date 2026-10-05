'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  ArrowRight,
  Bell,
  LoaderCircle,
  RefreshCw,
  Sparkles,
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
    </section>
  );
}
