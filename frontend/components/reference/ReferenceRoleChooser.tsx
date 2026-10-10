'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  ArrowLeft,
  ArrowRight,
  BadgeDollarSign,
  BookOpenCheck,
  Check,
  GraduationCap,
  Library,
  LoaderCircle,
  Search,
  ShieldCheck,
  UserRoundCheck,
  UsersRound,
} from 'lucide-react';

import { Logo } from '@/components/brand/Logo';
import { LoadingEmblem } from '@/components/brand/LoadingEmblem';
import type { AuthFailure, AuthRole, AuthSuccess, AuthUser } from '@/lib/auth';

const roleMeta: Record<string, { description: string; icon: typeof ShieldCheck }> = {
  Admin: { description: 'Manage the whole school, people, academics, finance and system settings.', icon: ShieldCheck },
  'Head Teacher': { description: 'Lead school operations, approvals, performance and oversight.', icon: UserRoundCheck },
  'Director of Studies': { description: 'Manage academics, classes, assessments, results and timetables.', icon: GraduationCap },
  Bursar: { description: 'Work with fees, payments, budgets, expenses and reconciliation.', icon: BadgeDollarSign },
  'Class Teacher': { description: 'Manage your class, attendance, marks and student progress.', icon: UsersRound },
  Teacher: { description: 'Work with assigned classes, attendance, marks and timetable.', icon: BookOpenCheck },
  'Admissions Officer': { description: 'Review applications and move approved learners into enrolment.', icon: UserRoundCheck },
  Librarian: { description: 'Manage books, loans, returns, fines and library activity.', icon: Library },
  'Library Assistant': { description: 'Handle day-to-day book circulation and member support.', icon: Library },
  Parent: { description: 'View your children, results, attendance, fees and communication.', icon: UsersRound },
  'Support Staff': { description: 'Access the staff workspace and school communication tools.', icon: UserRoundCheck },
  Staff: { description: 'Access your assigned school workspace and communication tools.', icon: UserRoundCheck },
};

function metaFor(role: AuthRole) {
  return roleMeta[role.label] ?? { description: 'Continue with the permissions assigned to this role.', icon: ShieldCheck };
}

export function ReferenceRoleChooser() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isSwitching = searchParams.get('switch') === '1';
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [selecting, setSelecting] = useState('');
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/auth/session', { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const payload = await response.json() as AuthSuccess | AuthFailure;
        if (!response.ok || !('user' in payload)) throw new Error('session_expired');
        return payload.user;
      })
      .then((nextUser) => {
        if (nextUser.must_change_password) {
          router.replace('/account/change-password');
          return;
        }
        if (nextUser.roles.length <= 1) {
          router.replace(nextUser.dashboard_path);
          return;
        }
        setUser(nextUser);
      })
      .catch(() => router.replace('/login?notice=session-expired'))
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [router]);

  const roles = useMemo(() => {
    const text = query.trim().toLowerCase();
    if (!user) return [];
    return user.roles.filter((role) => !text || role.label.toLowerCase().includes(text));
  }, [query, user]);

  async function choose(role: AuthRole) {
    if (!user || selecting) return;
    if (role.code === user.role.code) {
      router.replace(user.dashboard_path);
      return;
    }

    setSelecting(role.code);
    setError('');
    try {
      const response = await fetch('/api/auth/switch-role', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: role.code }),
      });
      const payload = await response.json() as AuthSuccess | AuthFailure;
      if (!response.ok || !('user' in payload)) {
        if (response.status === 401) {
          router.replace('/login?notice=session-expired');
          return;
        }
        throw new Error(payload.detail || 'The workspace could not be opened.');
      }
      try { localStorage.setItem('tafiti_recent_role', role.code); } catch { /* preference only */ }
      router.replace(payload.user.dashboard_path);
      router.refresh();
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'The workspace could not be opened.');
    } finally {
      setSelecting('');
    }
  }

  if (loading || !user) {
    return (
      <main className="grid min-h-dvh place-items-center bg-[#F2F6FC]">
        <div className="text-center"><LoadingEmblem className="mx-auto" /><div className="mt-5 inline-flex items-center gap-2 rounded-xl border border-blue-100 bg-white px-4 py-3 text-xs font-bold text-slate-500 shadow-sm"><LoaderCircle size={16} className="animate-spin text-blue-600" />Loading your workspaces…</div></div>
      </main>
    );
  }

  return (
    <main className="min-h-dvh bg-[#F2F6FC] text-[#10224A] lg:grid lg:grid-cols-[360px_minmax(0,1fr)]">
      <aside className="relative hidden overflow-hidden bg-[#071F46] p-10 text-white lg:flex lg:min-h-dvh lg:flex-col lg:justify-between">
        <div className="absolute -left-28 bottom-[-120px] h-[360px] w-[360px] rounded-full border-[44px] border-blue-400/[.07]" aria-hidden="true" />
        <div className="relative"><Logo inverted /></div>
        <div className="relative">
          <span className="inline-flex items-center gap-2 rounded-full border border-blue-300/20 bg-blue-400/10 px-3 py-1.5 text-[9px] font-extrabold uppercase tracking-[.12em] text-blue-100"><ShieldCheck size={12} /> Secure access</span>
          <h1 className="mt-5 text-4xl font-extrabold tracking-[-.045em]">Your account. The right workspace.</h1>
          <p className="mt-4 text-xs leading-6 text-blue-100/65">Tafiti only shows roles actually assigned to your account. Switching workspace changes your active role context only — you stay signed in and your password is not requested again.</p>
        </div>
        <p className="relative text-[9px] font-semibold text-blue-100/40">Tafiti School Management System</p>
      </aside>

      <section className="flex min-h-dvh items-center justify-center px-4 py-8 sm:px-8 lg:px-12">
        <div className="w-full max-w-[880px]">
          <div className="mb-6 flex items-center justify-between gap-3">
            <div>
              <div className="mb-4 lg:hidden"><Logo accent="blue" /></div>
              <p className="text-[9px] font-extrabold uppercase tracking-[.12em] text-blue-600">{isSwitching ? 'Switch workspace' : 'Choose workspace'}</p>
              <h2 className="mt-1 text-3xl font-extrabold tracking-[-.04em] text-[#10224A]">{isSwitching ? 'Switch to another assigned role' : 'Choose how you want to continue'}</h2>
              <p className="mt-2 text-xs text-slate-500">Signed in as <span className="font-bold text-slate-700">{user.name}</span>. Only roles assigned to this account are shown.</p>
              {isSwitching && <p className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-blue-100 bg-blue-50 px-2.5 py-1.5 text-[10px] font-bold text-blue-700"><ShieldCheck size={12} /> No sign-out or password required.</p>}
            </div>
            {isSwitching && <button type="button" onClick={() => router.back()} className="clay-button-secondary"><ArrowLeft size={14} /> Back</button>}
          </div>

          {user.roles.length > 6 && (
            <div className="relative mb-4 max-w-sm"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search your roles…" className="tafiti-input h-10 w-full pl-9 pr-3 text-xs" /></div>
          )}

          {error && <div className="mb-4 rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-xs font-semibold text-red-700">{error}</div>}

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {roles.map((role) => {
              const meta = metaFor(role);
              const Icon = meta.icon;
              const active = role.code === user.role.code;
              const busy = selecting === role.code;
              return (
                <button key={role.code} type="button" disabled={Boolean(selecting)} onClick={() => void choose(role)} className={`group relative min-h-[168px] overflow-hidden rounded-2xl border bg-white p-5 text-left shadow-[0_8px_24px_rgba(28,55,97,.055)] transition hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-[0_14px_32px_rgba(37,99,235,.1)] disabled:cursor-wait disabled:opacity-70 ${active ? 'border-blue-200 ring-2 ring-blue-100' : 'border-[#E4EBF4]'}`}>
                  <div className="flex items-start justify-between gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-600"><Icon size={20} /></span>{active && <span className="inline-flex items-center gap-1 rounded-full border border-emerald-100 bg-emerald-50 px-2 py-1 text-[8px] font-extrabold text-emerald-700"><Check size={10} /> Current</span>}</div>
                  <h3 className="mt-4 text-sm font-extrabold text-[#10224A]">{role.label}</h3>
                  <p className="mt-1.5 text-[10px] leading-4 text-slate-500">{meta.description}</p>
                  <span className="mt-4 inline-flex items-center gap-1 text-[10px] font-extrabold text-blue-600">{busy ? <><LoaderCircle size={12} className="animate-spin" />Opening…</> : active ? <>Open current workspace <ArrowRight size={12} className="transition group-hover:translate-x-0.5" /></> : <>Switch workspace <ArrowRight size={12} className="transition group-hover:translate-x-0.5" /></>}</span>
                </button>
              );
            })}
          </div>

          {!roles.length && <div className="tafiti-card mt-4 p-8 text-center text-xs text-slate-500">No assigned role matches your search.</div>}
        </div>
      </section>
    </main>
  );
}
