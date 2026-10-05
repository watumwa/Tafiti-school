'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  Bell,
  ChevronDown,
  ChevronRight,
  KeyRound,
  LoaderCircle,
  LogOut,
  Menu,
  Search,
  ShieldCheck,
  UserRound,
  X,
} from 'lucide-react';

import { Logo } from '@/components/brand/Logo';
import { useToast } from '@/components/ui/ToastProvider';
import { CommandPalette } from '@/components/workspace/CommandPalette';
import { DashboardOverview } from '@/components/workspace/DashboardOverview';
import { EntityWorkspace } from '@/components/workspace/EntityWorkspace';
import { NotificationDrawer } from '@/components/workspace/NotificationDrawer';
import { ParentPortalView } from '@/components/workspace/ParentPortalView';
import { ResourceView } from '@/components/workspace/ResourceView';
import { WorkspaceIcon } from '@/components/workspace/WorkspaceIcon';
import type { AuthFailure, AuthSuccess } from '@/lib/auth';
import type { WorkspaceBootstrap, WorkspaceNavItem } from '@/lib/workspace';

function LoadingWorkspace() {
  return (
    <main className="grid min-h-dvh place-items-center bg-[#EDF2F7] px-5 text-[#102A43]">
      <div className="text-center">
        <div className="mx-auto mb-5 flex justify-center"><Logo /></div>
        <div className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-600 shadow-sm">
          <LoaderCircle className="animate-spin text-emerald-700" size={18} />
          Opening your school workspace…
        </div>
      </div>
    </main>
  );
}

export function DashboardShell() {
  const pathname = usePathname();
  const router = useRouter();
  const toast = useToast();
  const [bootstrap, setBootstrap] = useState<WorkspaceBootstrap | null>(null);
  const [loading, setLoading] = useState(true);
  const [fatalError, setFatalError] = useState('');
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [retryKey, setRetryKey] = useState(0);
  const [entityTitle, setEntityTitle] = useState('');

  useEffect(() => {
    function keyboard(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setCommandOpen((value) => !value);
      }
      if (event.key === 'Escape') {
        setCommandOpen(false);
        setNotificationsOpen(false);
        setMobileNavOpen(false);
        setProfileOpen(false);
      }
    }
    window.addEventListener('keydown', keyboard);
    return () => window.removeEventListener('keydown', keyboard);
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setFatalError('');

    async function loadWorkspace() {
      try {
        const sessionResponse = await fetch('/api/auth/session', { cache: 'no-store' });
        const session = (await sessionResponse.json()) as AuthSuccess | AuthFailure;
        if (!sessionResponse.ok || !('user' in session)) {
          router.replace('/login?notice=session-expired');
          return;
        }

        if (session.user.must_change_password) {
          router.replace('/account/change-password');
          return;
        }

        if (pathname !== session.user.dashboard_path && !pathname.startsWith(`${session.user.dashboard_path}/`)) {
          router.replace(session.user.dashboard_path);
          return;
        }

        const bootstrapResponse = await fetch('/api/workspace/bootstrap', { cache: 'no-store' });
        const result = await bootstrapResponse.json();
        if (!bootstrapResponse.ok) {
          if (bootstrapResponse.status === 401) {
            router.replace('/login?notice=session-expired');
            return;
          }
          throw new Error(result.detail || 'The workspace could not be opened.');
        }
        if (active) setBootstrap(result as WorkspaceBootstrap);
      } catch (reason: unknown) {
        if (!active) return;
        const message = reason instanceof Error ? reason.message : 'The workspace could not be opened.';
        setFatalError(message);
        toast.error('Workspace unavailable', message);
      } finally {
        if (active) setLoading(false);
      }
    }

    void loadWorkspace();
    return () => {
      active = false;
    };
  }, [pathname, retryKey, router, toast]);

  const moduleSlug = useMemo(() => {
    const segments = pathname.split('/').filter(Boolean);
    return segments.length >= 3 ? segments[2] : 'overview';
  }, [pathname]);

  const entityId = useMemo(() => {
    const segments = pathname.split('/').filter(Boolean);
    if (segments.length < 4 || !/^\d+$/.test(segments[3])) return null;
    return Number(segments[3]);
  }, [pathname]);

  useEffect(() => setEntityTitle(''), [pathname]);
  const handleEntityTitle = useCallback((title: string) => setEntityTitle(title), []);

  const selectedItem = useMemo<WorkspaceNavItem | null>(() => {
    if (!bootstrap) return null;
    return bootstrap.navigation.flatMap((group) => group.items).find((item) => item.slug === moduleSlug) ?? null;
  }, [bootstrap, moduleSlug]);

  const initials = useMemo(() => {
    if (!bootstrap) return '';
    return bootstrap.user.name
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0])
      .join('')
      .toUpperCase();
  }, [bootstrap]);

  async function signOut() {
    await fetch('/api/auth/logout', { method: 'POST' });
    router.replace('/login');
    router.refresh();
  }

  if (loading && !bootstrap) return <LoadingWorkspace />;

  if (fatalError && !bootstrap) {
    return (
      <main className="grid min-h-dvh place-items-center bg-[#EDF2F7] px-5">
        <div className="w-full max-w-md rounded-2xl border border-red-200 bg-white p-6 text-center shadow-sm">
          <p className="text-base font-semibold text-slate-900">We couldn’t open Tafiti</p>
          <p className="mt-2 text-sm leading-6 text-slate-600">{fatalError}</p>
          <button type="button" onClick={() => setRetryKey((value) => value + 1)} className="mt-5 h-10 rounded-xl bg-[#102A43] px-4 text-xs font-semibold text-white hover:bg-[#0C2238]">Try again</button>
        </div>
      </main>
    );
  }

  if (!bootstrap) return null;

  return (
    <main className="min-h-dvh bg-[#EDF2F7] text-slate-900 lg:flex">
      <button
        type="button"
        onClick={() => setMobileNavOpen(false)}
        aria-label="Close navigation"
        className={`fixed inset-0 z-40 bg-slate-950/35 backdrop-blur-[1px] transition-opacity lg:hidden ${mobileNavOpen ? 'opacity-100' : 'pointer-events-none opacity-0'}`}
      />

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-[286px] flex-col bg-[#0F2747] text-white shadow-[14px_0_38px_rgba(15,39,71,0.14)] transition-transform duration-300 lg:sticky lg:top-0 lg:h-dvh lg:translate-x-0 ${mobileNavOpen ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <div className="flex h-[74px] items-center justify-between border-b border-white/[0.08] px-5">
          <Logo inverted />
          <button type="button" onClick={() => setMobileNavOpen(false)} className="grid h-9 w-9 place-items-center rounded-xl text-slate-300 hover:bg-white/10 lg:hidden" aria-label="Close navigation"><X size={18} /></button>
        </div>

        <div className="border-b border-white/[0.07] px-5 py-4">
          <p className="truncate text-sm font-semibold text-white">{bootstrap.school.name}</p>
          <div className="mt-1.5 flex items-center gap-2 text-[11px] font-medium text-slate-400">
            <ShieldCheck size={13} className="text-emerald-400" />
            {bootstrap.user.role.label} workspace
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4" aria-label="Main navigation">
          {bootstrap.navigation.map((group) => (
            <div key={group.key} className="mb-5 last:mb-0">
              <p className="mb-1.5 px-3 text-[10px] font-bold uppercase tracking-[0.15em] text-slate-500">{group.label}</p>
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const active = item.slug === moduleSlug;
                  const href = item.slug === 'overview' ? bootstrap.user.dashboard_path : `${bootstrap.user.dashboard_path}/${item.slug}`;
                  return (
                    <Link
                      key={item.slug}
                      href={href}
                      onClick={() => setMobileNavOpen(false)}
                      className={`group flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium transition ${active ? 'bg-white text-[#0F2747] shadow-[0_4px_16px_rgba(0,0,0,0.08)]' : 'text-slate-300 hover:bg-white/[0.07] hover:text-white'}`}
                    >
                      <WorkspaceIcon name={item.icon} size={17} className={active ? 'text-emerald-700' : 'text-slate-400 group-hover:text-slate-200'} />
                      <span className="min-w-0 flex-1 truncate">{item.label}</span>
                      {active && <ChevronRight size={14} className="text-slate-400" />}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t border-white/[0.08] p-3">
          <button type="button" onClick={() => setProfileOpen((value) => !value)} className="flex w-full items-center gap-3 rounded-xl px-2.5 py-2.5 text-left transition hover:bg-white/[0.07]">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-white/10 text-xs font-bold text-white">{initials || <UserRound size={16} />}</span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-xs font-semibold text-white">{bootstrap.user.name}</span>
              <span className="mt-0.5 block truncate text-[10px] text-slate-400">{bootstrap.user.email || bootstrap.user.username}</span>
            </span>
            <ChevronDown size={14} className={`text-slate-400 transition ${profileOpen ? 'rotate-180' : ''}`} />
          </button>
          {profileOpen && (
            <div className="mt-2 overflow-hidden rounded-xl border border-white/10 bg-[#132F53] p-1.5 shadow-xl">
              {bootstrap.user.role.label === 'Parent' && <Link href={`${bootstrap.user.dashboard_path}/parent-profile`} className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium text-slate-200 hover:bg-white/10"><UserRound size={14} /> My profile</Link>}
              <Link href="/account/change-password" className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium text-slate-200 hover:bg-white/10"><KeyRound size={14} /> Change password</Link>
              <button type="button" onClick={signOut} className="mt-0.5 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs font-medium text-red-200 hover:bg-red-400/10"><LogOut size={14} /> Sign out</button>
            </div>
          )}
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-30 flex h-[66px] items-center gap-3 border-b border-white/80 bg-[#F7F9FC]/90 px-4 shadow-[0_8px_22px_rgba(15,39,71,.045)] backdrop-blur-xl sm:px-6 lg:px-8">
          <button type="button" onClick={() => setMobileNavOpen(true)} className="grid h-9 w-9 place-items-center rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50 lg:hidden" aria-label="Open navigation"><Menu size={18} /></button>

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <span className="hidden truncate sm:inline">{bootstrap.school.name}</span>
              <ChevronRight size={12} className="hidden sm:block" />
              {entityId && selectedItem ? (
                <>
                  <Link href={`${bootstrap.user.dashboard_path}/${selectedItem.slug}`} className="hidden font-medium text-slate-500 transition hover:text-[#3157D5] sm:inline">{selectedItem.label}</Link>
                  <ChevronRight size={12} className="hidden sm:block" />
                  <span className="truncate font-semibold text-slate-700">{entityTitle || 'Opening record…'}</span>
                </>
              ) : (
                <span className="truncate font-semibold text-slate-700">{selectedItem?.label ?? 'Overview'}</span>
              )}
            </div>
          </div>

          <button type="button" onClick={() => setCommandOpen(true)} className="hidden h-9 min-w-[220px] items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 text-left text-xs text-slate-400 transition hover:border-slate-300 hover:bg-white md:flex xl:min-w-[280px]">
            <Search size={15} />
            <span className="flex-1">Search school records…</span>
            <kbd className="rounded-md border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] font-semibold text-slate-400">⌘K</kbd>
          </button>

          <div className="hidden rounded-xl border border-slate-200 bg-white px-3 py-2 text-right xl:block">
            <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-slate-400">Academic period</p>
            <p className="mt-0.5 text-xs font-semibold text-slate-700">{bootstrap.academic_context.year || 'Not set'} {bootstrap.academic_context.term ? `· ${bootstrap.academic_context.term}` : ''}</p>
          </div>

          <button type="button" onClick={() => setCommandOpen(true)} className="grid h-9 w-9 place-items-center rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50 md:hidden" aria-label="Search modules"><Search size={17} /></button>

          <button type="button" onClick={() => setNotificationsOpen(true)} className="relative grid h-9 w-9 place-items-center rounded-xl border border-slate-200 text-slate-600 transition hover:bg-slate-50" aria-label="Open notifications">
            <Bell size={17} />
            {bootstrap.notification_count > 0 && (
              <span className="absolute -right-1 -top-1 grid min-h-[18px] min-w-[18px] place-items-center rounded-full border-2 border-white bg-red-500 px-1 text-[9px] font-bold text-white">{bootstrap.notification_count > 9 ? '9+' : bootstrap.notification_count}</span>
            )}
          </button>
        </header>

        <div className="mx-auto w-full max-w-[1560px] p-4 sm:p-6 lg:p-7 xl:p-8">
          {moduleSlug === 'overview' ? (
            <DashboardOverview bootstrap={bootstrap} />
          ) : bootstrap.user.role.label === 'Parent' && selectedItem?.resource?.startsWith('parent-') ? (
            <ParentPortalView screen={selectedItem.resource} dashboardPath={bootstrap.user.dashboard_path} />
          ) : entityId && selectedItem?.resource ? (
            <EntityWorkspace resource={selectedItem.resource} id={entityId} dashboardPath={bootstrap.user.dashboard_path} onTitleChange={handleEntityTitle} />
          ) : selectedItem?.resource ? (
            <ResourceView resource={selectedItem.resource} />
          ) : (
            <div className="grid min-h-[460px] place-items-center rounded-2xl border border-slate-200 bg-white px-5 text-center">
              <div className="max-w-md">
                <p className="text-lg font-semibold text-slate-900">This module is not available in your workspace</p>
                <p className="mt-2 text-sm leading-6 text-slate-500">The route is either not assigned to your active role or has not been migrated yet.</p>
                <Link href={bootstrap.user.dashboard_path} className="mt-5 inline-flex h-10 items-center rounded-xl bg-[#102A43] px-4 text-xs font-semibold text-white">Back to overview</Link>
              </div>
            </div>
          )}
        </div>
      </div>

      <NotificationDrawer
        open={notificationsOpen}
        onClose={() => setNotificationsOpen(false)}
        notifications={bootstrap.notifications}
        onViewAll={bootstrap.user.role.label === 'Parent' ? () => {
          setNotificationsOpen(false);
          router.push(`${bootstrap.user.dashboard_path}/parent-notifications`);
        } : undefined}
      />
      <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} groups={bootstrap.navigation} dashboardPath={bootstrap.user.dashboard_path} />
    </main>
  );
}
