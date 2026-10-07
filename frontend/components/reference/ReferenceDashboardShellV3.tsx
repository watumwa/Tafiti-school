'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
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
import { EntityWorkspace } from '@/components/workspace/EntityWorkspace';
import { NotificationDrawer } from '@/components/workspace/NotificationDrawer';
import { WorkspaceFlowBar } from '@/components/workspace/WorkspaceFlowBar';
import { WorkspaceHistoryMenu } from '@/components/workspace/WorkspaceHistoryMenu';
import { WorkspaceIcon } from '@/components/workspace/WorkspaceIcon';
import type { AuthFailure, AuthSuccess } from '@/lib/auth';
import type { WorkspaceBootstrap, WorkspaceNavGroup, WorkspaceNavItem } from '@/lib/workspace';
import { ReferenceDashboardOverview } from './ReferenceDashboardOverview';
import { ReferenceEntityWorkspace } from './ReferenceEntityWorkspace';
import { ReferenceFeeAccountWorkspace } from './ReferenceFeeAccountWorkspace';
import { ReferenceLinkedResourceView } from './ReferenceLinkedResourceView';
import { ReferenceParentPortalFrame } from './ReferenceParentPortalFrame';
import { ReferenceReportsCenter } from './ReferenceReportsCenter';
import { ReferenceUsersRolesView } from './ReferenceUsersRolesView';

function LoadingWorkspace() {
  return (
    <main className="grid min-h-dvh place-items-center bg-[#F3F7FC]">
      <div className="text-center">
        <Logo accent="blue" />
        <div className="mt-5 inline-flex items-center gap-2 rounded-xl border border-blue-100 bg-white px-4 py-3 text-xs font-bold text-slate-500 shadow-sm">
          <LoaderCircle className="animate-spin text-blue-600" size={17} />Opening Tafiti workspace…
        </div>
      </div>
    </main>
  );
}

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase();
}

type SearchParamReader = { get(name: string): string | null };

function navigationHref(dashboardPath: string, item: WorkspaceNavItem) {
  if (item.path) return `${dashboardPath}/${item.path}`;
  return item.slug === 'overview' ? dashboardPath : `${dashboardPath}/${item.slug}`;
}

function navigationItemIsActive(item: WorkspaceNavItem, pathname: string, searchParams: SearchParamReader, dashboardPath: string) {
  const target = item.path ?? item.slug;
  const [targetPath, targetQuery = ''] = target.split('?');
  const expectedPath = targetPath === 'overview' ? dashboardPath : `${dashboardPath}/${targetPath}`;
  if (pathname !== expectedPath) return false;

  return Array.from(new URLSearchParams(targetQuery).entries()).every(
    ([key, value]) => searchParams.get(key) === value,
  );
}

function buildNavigation(bootstrap: WorkspaceBootstrap): WorkspaceNavGroup[] {
  if (bootstrap.user.role.label === 'Parent') return bootstrap.navigation;

  const groups = bootstrap.navigation.map((group) => ({ ...group, items: [...group.items] }));

  if (['Admin', 'Head Teacher'].includes(bootstrap.user.role.label)) {
    const coreGroup = groups.find((group) => group.key === 'core_operations');
    if (coreGroup && !coreGroup.items.some((item) => item.slug === 'users-roles')) {
      coreGroup.items.push({ slug: 'users-roles', label: 'Users & roles', icon: 'shield-check', resource: null });
    }
  }

  return groups;
}

export function ReferenceDashboardShellV3() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  const [bootstrap, setBootstrap] = useState<WorkspaceBootstrap | null>(null);
  const [loading, setLoading] = useState(true);
  const [fatalError, setFatalError] = useState('');
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [collapsedGroupKeys, setCollapsedGroupKeys] = useState<string[]>([]);
  const [entityTitle, setEntityTitle] = useState('');
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    const keyboard = (event: KeyboardEvent) => {
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
    };
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
        const session = await sessionResponse.json() as AuthSuccess | AuthFailure;
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

        const response = await fetch('/api/workspace/bootstrap', { cache: 'no-store' });
        const result = await response.json();
        if (!response.ok) {
          if (response.status === 401) {
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
    return () => { active = false; };
  }, [pathname, retryKey, router, toast]);

  const moduleSlug = useMemo(() => {
    const segments = pathname.split('/').filter(Boolean);
    return segments.length >= 3 ? segments[2] : 'overview';
  }, [pathname]);

  const entityId = useMemo(() => {
    const segments = pathname.split('/').filter(Boolean);
    return segments.length >= 4 && /^\d+$/.test(segments[3]) ? Number(segments[3]) : null;
  }, [pathname]);

  useEffect(() => setEntityTitle(''), [pathname]);
  const handleEntityTitle = useCallback((title: string) => setEntityTitle(title), []);

  const navigation = useMemo<WorkspaceNavGroup[]>(() => bootstrap ? buildNavigation(bootstrap) : [], [bootstrap]);

  useEffect(() => {
    if (bootstrap) setCollapsedGroupKeys(navigation.map((group) => group.key));
  }, [bootstrap, navigation]);

  const selectedItem = useMemo<WorkspaceNavItem | null>(() => {
    if (!bootstrap) return null;
    const sidebarItem = navigation.flatMap((group) => group.items).find(
      (item) => navigationItemIsActive(item, pathname, searchParams, bootstrap.user.dashboard_path),
    );
    if (sidebarItem) return sidebarItem;
    return bootstrap.navigation.flatMap((group) => group.items).find((item) => item.slug === moduleSlug) ?? null;
  }, [bootstrap, moduleSlug, navigation, pathname, searchParams]);

  async function signOut() {
    await fetch('/api/auth/logout', { method: 'POST' });
    router.replace('/login');
    router.refresh();
  }

  if (loading && !bootstrap) return <LoadingWorkspace />;
  if (fatalError && !bootstrap) {
    return (
      <main className="grid min-h-dvh place-items-center bg-[#F3F7FC] p-5">
        <div className="tafiti-card max-w-md p-6 text-center">
          <p className="text-sm font-extrabold text-[#10224A]">We couldn&apos;t open Tafiti</p>
          <p className="mt-2 text-xs leading-5 text-slate-500">{fatalError}</p>
          <button type="button" onClick={() => setRetryKey((value) => value + 1)} className="clay-button-primary mt-4">Try again</button>
        </div>
      </main>
    );
  }
  if (!bootstrap) return null;

  const userInitials = initials(bootstrap.user.name) || 'U';
  const verificationEntity = Boolean(entityId && selectedItem?.resource === 'results');
  const historyLabel = entityId
    ? (entityTitle || selectedItem?.label || 'Record')
    : (selectedItem?.label ?? (moduleSlug === 'reports' ? 'Reports' : 'Dashboard'));

  return (
    <main className="min-h-dvh bg-[#F3F7FC] text-slate-900 lg:flex">
      <button type="button" onClick={() => setMobileNavOpen(false)} aria-label="Close navigation" className={`fixed inset-0 z-40 bg-slate-950/35 backdrop-blur-[1px] transition-opacity lg:hidden ${mobileNavOpen ? 'opacity-100' : 'pointer-events-none opacity-0'}`} />

      <aside className={`fixed inset-y-0 left-0 z-50 flex w-[256px] flex-col overflow-hidden bg-[#071F46] text-white shadow-[12px_0_35px_rgba(7,31,70,.14)] transition-transform duration-300 lg:sticky lg:top-0 lg:h-dvh lg:translate-x-0 ${mobileNavOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="relative flex h-[72px] items-center justify-between border-b border-white/[.08] px-4"><div className="absolute -bottom-24 -left-20 h-56 w-56 rounded-full border-[34px] border-blue-400/[.06]" /><Logo inverted /><button type="button" onClick={() => setMobileNavOpen(false)} className="grid h-8 w-8 place-items-center rounded-lg text-slate-300 hover:bg-white/10 lg:hidden"><X size={17} /></button></div>
        <nav className="relative z-10 flex-1 overflow-y-auto px-2.5 py-3" aria-label="Main navigation">
          {navigation.map((group) => {
            const containsActiveItem = group.items.some((item) => navigationItemIsActive(item, pathname, searchParams, bootstrap.user.dashboard_path));
            const collapsed = collapsedGroupKeys.includes(group.key) && !containsActiveItem;

            return (
              <section key={group.key} className="mb-2">
                <div className="flex h-7 items-center gap-2 px-2.5">
                  <span className="h-px w-3 shrink-0 bg-blue-200/25" aria-hidden="true" />
                  <p className="whitespace-nowrap text-[8px] font-extrabold uppercase tracking-[.13em] text-blue-100/45">{group.label}</p>
                  <span className="h-px min-w-0 flex-1 bg-blue-200/15" aria-hidden="true" />
                  <button
                    type="button"
                    onClick={() => setCollapsedGroupKeys((keys) => keys.includes(group.key) ? keys.filter((key) => key !== group.key) : [...keys, group.key])}
                    aria-expanded={!collapsed}
                    aria-label={`${collapsed ? 'Expand' : 'Collapse'} ${group.label}`}
                    className="grid h-6 w-6 shrink-0 place-items-center rounded-md text-blue-100/45 transition hover:bg-white/[.07] hover:text-blue-50"
                  >
                    <ChevronDown size={12} className={`transition-transform ${collapsed ? '-rotate-90' : ''}`} />
                  </button>
                </div>
                {!collapsed && <div className="space-y-0.5">{group.items.map((item) => {
                  const active = navigationItemIsActive(item, pathname, searchParams, bootstrap.user.dashboard_path);
                  const href = navigationHref(bootstrap.user.dashboard_path, item);
                  return <Link key={item.slug} href={href} onClick={() => setMobileNavOpen(false)} className={`group flex h-9 items-center gap-2.5 rounded-lg px-2.5 text-[11px] font-bold transition ${active ? 'bg-[#1E64F0] text-white shadow-[0_8px_16px_rgba(30,100,240,.24)]' : 'text-blue-50/75 hover:bg-white/[.07] hover:text-white'}`}><WorkspaceIcon name={item.icon} size={15} className={active ? 'text-white' : 'text-blue-100/55 group-hover:text-white'} /><span className="min-w-0 flex-1 truncate">{item.label}</span>{active && <ChevronRight size={12} className="text-white/70" />}</Link>;
                })}</div>}
              </section>
            );
          })}
        </nav>
        <div className="relative z-10 border-t border-white/[.08] p-3"><div className="rounded-xl border border-white/[.08] bg-white/[.05] p-3"><p className="text-[8px] font-bold uppercase tracking-[.1em] text-blue-100/45">Academic year</p><p className="mt-1 text-[11px] font-bold text-white">{bootstrap.academic_context.year || 'Not set'}</p><div className="my-2 h-px bg-white/[.07]" /><p className="text-[8px] font-bold uppercase tracking-[.1em] text-blue-100/45">Current term</p><p className="mt-1 text-[11px] font-bold text-white">{bootstrap.academic_context.term || 'Not set'}</p></div></div>
      </aside>

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-30 flex h-[62px] items-center gap-3 border-b border-[#E6ECF4] bg-white/95 px-3.5 backdrop-blur-xl sm:px-5 lg:px-6">
          <button type="button" onClick={() => setMobileNavOpen(true)} className="grid h-8 w-8 place-items-center rounded-lg border border-slate-200 text-slate-600 lg:hidden"><Menu size={17} /></button>
          <button type="button" onClick={() => setCommandOpen(true)} className="hidden h-9 min-w-[220px] items-center gap-2 rounded-lg border border-[#E2E9F3] bg-[#F8FAFD] px-3 text-left text-[10px] text-slate-400 md:flex xl:min-w-[300px]"><Search size={14} /><span className="flex-1">Search anything…</span><kbd className="rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[9px] font-bold">⌘K</kbd></button>
          <div className="ml-auto flex items-center gap-2"><div className="hidden rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-[10px] font-bold text-slate-600 sm:block">{bootstrap.academic_context.year || 'Year'}</div><div className="hidden rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-[10px] font-bold text-slate-600 sm:block">{bootstrap.academic_context.term || 'Term'}</div><WorkspaceHistoryMenu dashboardPath={bootstrap.user.dashboard_path} currentPath={pathname} currentLabel={historyLabel} /><button type="button" onClick={() => setNotificationsOpen(true)} className="relative grid h-9 w-9 place-items-center rounded-lg border border-slate-200 bg-white text-slate-600"><Bell size={16} />{bootstrap.notification_count > 0 && <span className="absolute -right-1 -top-1 grid min-h-[16px] min-w-[16px] place-items-center rounded-full border-2 border-white bg-red-500 px-1 text-[8px] font-extrabold text-white">{bootstrap.notification_count > 9 ? '9+' : bootstrap.notification_count}</span>}</button><div className="relative"><button type="button" onClick={() => setProfileOpen((value) => !value)} className="flex items-center gap-2 rounded-lg px-1.5 py-1 hover:bg-slate-50"><span className="grid h-8 w-8 place-items-center rounded-full bg-gradient-to-br from-blue-100 to-blue-200 text-[10px] font-extrabold text-blue-800">{userInitials}</span><span className="hidden text-left md:block"><span className="block max-w-[130px] truncate text-[10px] font-extrabold text-[#10224A]">{bootstrap.user.name}</span><span className="mt-0.5 block text-[8px] font-semibold text-slate-400">{bootstrap.user.role.label}</span></span><ChevronDown size={12} className="text-slate-400" /></button>{profileOpen && <div className="absolute right-0 mt-2 w-56 overflow-hidden rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl"><div className="border-b border-slate-100 px-3 py-2"><p className="truncate text-[10px] font-bold text-slate-800">{bootstrap.user.name}</p><p className="mt-0.5 truncate text-[9px] text-slate-400">{bootstrap.user.email || bootstrap.user.username}</p><p className="mt-1 text-[9px] font-bold text-blue-600">{bootstrap.user.role.label}</p></div>{bootstrap.user.role.label === 'Parent' && <Link href={`${bootstrap.user.dashboard_path}/parent-profile`} className="mt-1 flex items-center gap-2 rounded-lg px-3 py-2 text-[10px] font-bold text-slate-600 hover:bg-slate-50"><UserRound size={13} />My profile</Link>}{bootstrap.user.roles.length > 1 && <Link href="/choose-role?switch=1" className="mt-1 flex items-center gap-2 rounded-lg px-3 py-2 text-[10px] font-bold text-blue-700 hover:bg-blue-50"><ShieldCheck size={13} />Switch workspace</Link>}<Link href="/account/change-password" className="flex items-center gap-2 rounded-lg px-3 py-2 text-[10px] font-bold text-slate-600 hover:bg-slate-50"><KeyRound size={13} />Change password</Link><button type="button" onClick={signOut} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-[10px] font-bold text-red-600 hover:bg-red-50"><LogOut size={13} />Sign out</button></div>}</div></div>
        </header>

        <div className="border-b border-[#E9EEF5] bg-[#F8FAFD] px-4 py-2 sm:px-6"><div className="flex items-center gap-1.5 text-[9px] text-slate-400"><Link href={bootstrap.user.dashboard_path} className="hover:text-blue-600">Home</Link><ChevronRight size={10} />{entityId && selectedItem ? <><Link href={navigationHref(bootstrap.user.dashboard_path, selectedItem)} className="font-semibold hover:text-blue-600">{selectedItem.label}</Link><ChevronRight size={10} /><span className="font-bold text-slate-600">{entityTitle || 'Record'}</span></> : <span className="font-bold text-slate-600">{selectedItem?.label ?? (moduleSlug === 'reports' ? 'Reports' : 'Dashboard')}</span>}</div></div>

        <WorkspaceFlowBar currentResource={selectedItem?.resource} currentSlug={moduleSlug} dashboardPath={bootstrap.user.dashboard_path} navigation={bootstrap.navigation} />

        <div className="mx-auto w-full max-w-[1600px] p-4 sm:p-5 lg:p-6">
          {moduleSlug === 'overview' ? <ReferenceDashboardOverview bootstrap={bootstrap} />
            : moduleSlug === 'reports' ? <ReferenceReportsCenter dashboardPath={bootstrap.user.dashboard_path} />
            : moduleSlug === 'users-roles' ? <ReferenceUsersRolesView dashboardPath={bootstrap.user.dashboard_path} />
            : bootstrap.user.role.label === 'Parent' && selectedItem?.resource?.startsWith('parent-') ? <ReferenceParentPortalFrame screen={selectedItem.resource} dashboardPath={bootstrap.user.dashboard_path} />
            : entityId && selectedItem?.resource === 'fees' ? <ReferenceFeeAccountWorkspace id={entityId} dashboardPath={bootstrap.user.dashboard_path} onTitleChange={handleEntityTitle} />
            : entityId && selectedItem?.resource && (selectedItem.resource === 'attendance' || verificationEntity) ? <EntityWorkspace resource={selectedItem.resource} id={entityId} dashboardPath={bootstrap.user.dashboard_path} onTitleChange={handleEntityTitle} />
            : entityId && selectedItem?.resource ? <ReferenceEntityWorkspace resource={selectedItem.resource} id={entityId} dashboardPath={bootstrap.user.dashboard_path} onTitleChange={handleEntityTitle} />
            : selectedItem?.resource ? <ReferenceLinkedResourceView resource={selectedItem.resource} dashboardPath={bootstrap.user.dashboard_path} />
            : <div className="tafiti-card grid min-h-[420px] place-items-center p-6 text-center"><div><ShieldCheck className="mx-auto text-blue-400" size={28} /><p className="mt-3 text-sm font-extrabold text-slate-800">This workspace is not available</p><p className="mt-1 text-xs text-slate-400">The route is not assigned to your active role.</p></div></div>}
        </div>
      </div>

      <NotificationDrawer open={notificationsOpen} onClose={() => setNotificationsOpen(false)} notifications={bootstrap.notifications} onViewAll={bootstrap.user.role.label === 'Parent' ? () => { setNotificationsOpen(false); router.push(`${bootstrap.user.dashboard_path}/parent-notifications`); } : undefined} />
      <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} groups={navigation} dashboardPath={bootstrap.user.dashboard_path} />
    </main>
  );
}
