'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  AlertCircle,
  BadgeCheck,
  Check,
  ChevronRight,
  Clock3,
  LoaderCircle,
  LockKeyhole,
  Pencil,
  Plus,
  Power,
  PowerOff,
  Search,
  ShieldCheck,
  UserCog,
  UserRound,
  Users,
  X,
} from 'lucide-react';

import { useToast } from '@/components/ui/ToastProvider';
import { ProfileAvatar } from '@/components/workspace/ProfileAvatar';

type ManagedUser = {
  id: number;
  name: string;
  username: string;
  email: string;
  photo: string;
  department: string;
  staff_id: number | null;
  account_type: 'Staff' | 'Parent';
  roles: string[];
  active: boolean;
  superuser: boolean;
  last_login: string;
  date_joined: string;
  parent_links: number;
  can_edit_roles: boolean;
};

type RoleMatrixRow = {
  label: string;
  assignable: boolean;
  access: Record<string, boolean>;
};

type UserRolesPayload = {
  users: ManagedUser[];
  roles: RoleMatrixRow[];
  modules: { key: string; label: string }[];
  summary: {
    total_users: number;
    active_users: number;
    role_types: number;
    staff_without_accounts: number;
  };
  can_manage: boolean;
};

function dateLabel(value: string) {
  if (!value) return 'Never';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', year: 'numeric' }).format(parsed);
}

function roleTone(role: string) {
  const value = role.toLowerCase();
  if (value.includes('admin') || value.includes('head')) return 'border-violet-100 bg-violet-50 text-violet-700';
  if (value.includes('teacher') || value.includes('studies')) return 'border-blue-100 bg-blue-50 text-blue-700';
  if (value.includes('bursar')) return 'border-emerald-100 bg-emerald-50 text-emerald-700';
  if (value.includes('librar')) return 'border-amber-100 bg-amber-50 text-amber-700';
  if (value.includes('parent')) return 'border-cyan-100 bg-cyan-50 text-cyan-700';
  return 'border-slate-200 bg-slate-50 text-slate-600';
}

export function ReferenceUsersRolesView({ dashboardPath }: { dashboardPath: string }) {
  const toast = useToast();
  const [data, setData] = useState<UserRolesPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [tab, setTab] = useState<'users' | 'roles'>('users');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [roleFilter, setRoleFilter] = useState('all');
  const [editing, setEditing] = useState<ManagedUser | null>(null);
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetch('/api/workspace/users-roles', { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Users and roles could not be loaded.');
        return payload as UserRolesPayload;
      })
      .then(setData)
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Users and roles could not be loaded.');
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [reloadKey]);

  const rows = useMemo(() => {
    if (!data) return [];
    const text = query.trim().toLowerCase();
    return data.users.filter((row) => {
      if (statusFilter === 'active' && !row.active) return false;
      if (statusFilter === 'inactive' && row.active) return false;
      if (roleFilter !== 'all' && !row.roles.includes(roleFilter)) return false;
      if (!text) return true;
      return [row.name, row.username, row.email, row.department, row.account_type, ...row.roles]
        .some((value) => String(value || '').toLowerCase().includes(text));
    });
  }, [data, query, roleFilter, statusFilter]);

  const assignableRoles = useMemo(() => data?.roles.filter((role) => role.assignable) ?? [], [data]);

  function openRoleEditor(user: ManagedUser) {
    setEditing(user);
    setSelectedRoles(user.roles.filter((role) => assignableRoles.some((item) => item.label === role)));
  }

  async function updateStatus(user: ManagedUser) {
    if (!data?.can_manage || saving) return;
    setSaving(true);
    try {
      const response = await fetch(`/api/workspace/users-roles/${user.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'status', active: !user.active }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Account status could not be changed.');
      toast.success(user.active ? 'Account deactivated' : 'Account activated', payload.detail);
      setReloadKey((value) => value + 1);
    } catch (reason: unknown) {
      toast.error('Account not updated', reason instanceof Error ? reason.message : 'Please try again.');
    } finally {
      setSaving(false);
    }
  }

  async function saveRoles() {
    if (!editing || !data?.can_manage || saving) return;
    setSaving(true);
    try {
      const response = await fetch(`/api/workspace/users-roles/${editing.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'roles', roles: selectedRoles }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Roles could not be changed.');
      toast.success('Roles updated', `${payload.detail} Staff with two or more roles can now switch workspace from their profile menu without signing in again.`);
      setEditing(null);
      setReloadKey((value) => value + 1);
    } catch (reason: unknown) {
      toast.error('Roles not updated', reason instanceof Error ? reason.message : 'Please try again.');
    } finally {
      setSaving(false);
    }
  }

  if (loading && !data) {
    return <div className="tafiti-card grid min-h-[460px] place-items-center"><div className="text-center text-xs font-semibold text-slate-500"><LoaderCircle className="mx-auto mb-3 animate-spin text-blue-600" size={24} />Loading users and roles…</div></div>;
  }

  if (error && !data) {
    return <div className="tafiti-card grid min-h-[420px] place-items-center p-6 text-center"><div><AlertCircle className="mx-auto text-red-500" size={25} /><h2 className="mt-3 text-sm font-bold text-slate-900">Users &amp; Roles unavailable</h2><p className="mt-2 text-xs text-slate-500">{error}</p><button type="button" onClick={() => setReloadKey((value) => value + 1)} className="clay-button-primary mt-4">Try again</button></div></div>;
  }

  if (!data) return null;

  return (
    <section>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex items-start gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-600"><ShieldCheck size={21} /></span>
          <div><h1 className="text-[1.65rem] font-extrabold tracking-[-0.035em] text-[#10224A]">Users &amp; Roles</h1><p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">Manage account access and staff role assignments. Staff with at least two assigned roles automatically get <strong className="font-extrabold text-slate-700">Switch workspace</strong> in their profile menu.</p></div>
        </div>
        <Link href={`${dashboardPath}/staff`} className="clay-button-secondary"><UserRound size={14} /> Staff directory</Link>
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="tafiti-kpi"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-blue-50 text-blue-600"><Users size={18} /></span><div><p className="text-[9px] font-bold text-slate-400">TOTAL USERS</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{data.summary.total_users}</p><p className="mt-0.5 text-[9px] text-slate-400">Staff and parent accounts</p></div></div></div>
        <div className="tafiti-kpi"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-50 text-emerald-600"><BadgeCheck size={18} /></span><div><p className="text-[9px] font-bold text-slate-400">ACTIVE ACCOUNTS</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{data.summary.active_users}</p><p className="mt-0.5 text-[9px] text-slate-400">Can authenticate now</p></div></div></div>
        <div className="tafiti-kpi"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-violet-50 text-violet-600"><UserCog size={18} /></span><div><p className="text-[9px] font-bold text-slate-400">ROLE TYPES</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{data.summary.role_types}</p><p className="mt-0.5 text-[9px] text-slate-400">Server-defined access profiles</p></div></div></div>
        <div className="tafiti-kpi"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-amber-50 text-amber-600"><LockKeyhole size={18} /></span><div><p className="text-[9px] font-bold text-slate-400">NO LOGIN ACCOUNT</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{data.summary.staff_without_accounts}</p><p className="mt-0.5 text-[9px] text-slate-400">Staff records without portal accounts</p></div></div></div>
      </div>

      <div className="mb-4 flex w-fit gap-1 rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
        <button type="button" onClick={() => setTab('users')} className={`rounded-lg px-4 py-2 text-[11px] font-extrabold ${tab === 'users' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-500 hover:bg-slate-50'}`}>Users</button>
        <button type="button" onClick={() => setTab('roles')} className={`rounded-lg px-4 py-2 text-[11px] font-extrabold ${tab === 'roles' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-500 hover:bg-slate-50'}`}>Roles &amp; Permissions</button>
      </div>

      {tab === 'users' ? (
        <section className="tafiti-card overflow-hidden">
          <div className="flex flex-col gap-3 border-b border-slate-100 px-4 py-3.5 lg:flex-row lg:items-center lg:justify-between sm:px-5">
            <div className="relative w-full lg:max-w-[360px]"><Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search name, email, department or role…" className="tafiti-input h-9 w-full pl-9 pr-3 text-xs" /></div>
            <div className="flex flex-wrap gap-2">
              <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as 'all' | 'active' | 'inactive')} className="tafiti-input h-9 px-3 text-[10px] font-bold"><option value="all">All statuses</option><option value="active">Active</option><option value="inactive">Inactive</option></select>
              <select value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)} className="tafiti-input h-9 px-3 text-[10px] font-bold"><option value="all">All roles</option>{data.roles.map((role) => <option key={role.label} value={role.label}>{role.label}</option>)}</select>
            </div>
          </div>

          <div className="hidden overflow-x-auto md:block">
            <table className="w-full min-w-[1040px] border-collapse text-left">
              <thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">USER</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">ROLES</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">DEPARTMENT</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">LAST LOGIN</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STATUS</th><th className="px-4 py-3 text-right text-[9px] font-extrabold text-slate-400">ACTIONS</th></tr></thead>
              <tbody className="divide-y divide-slate-100">{rows.map((row) => <tr key={row.id} className="hover:bg-blue-50/20"><td className="px-4 py-3"><div className="flex items-center gap-2.5"><ProfileAvatar src={row.photo} name={row.name} size="sm" /><div className="min-w-0"><p className="truncate text-xs font-bold text-slate-800">{row.name}</p><p className="mt-0.5 truncate text-[9px] text-slate-400">{row.email || row.username} · {row.account_type}</p></div></div></td><td className="px-4 py-3"><div className="flex max-w-[280px] flex-wrap gap-1">{row.roles.map((role) => <span key={role} className={`rounded-full border px-2 py-1 text-[8px] font-bold ${roleTone(role)}`}>{role}</span>)}</div></td><td className="px-4 py-3 text-xs text-slate-600">{row.department || '—'}</td><td className="px-4 py-3"><div className="flex items-center gap-1.5 text-[10px] text-slate-500"><Clock3 size={12} />{dateLabel(row.last_login)}</div></td><td className="px-4 py-3"><span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[9px] font-bold ${row.active ? 'border-emerald-100 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-slate-50 text-slate-500'}`}><span className={`h-1.5 w-1.5 rounded-full ${row.active ? 'bg-emerald-500' : 'bg-slate-400'}`} />{row.active ? 'Active' : 'Inactive'}</span></td><td className="px-4 py-3"><div className="flex justify-end gap-1.5">{row.staff_id && <Link href={`${dashboardPath}/staff/${row.staff_id}`} className="clay-row-action" title="Open staff profile"><ChevronRight size={13} /></Link>}{data.can_manage && row.can_edit_roles && <button type="button" onClick={() => openRoleEditor(row)} className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-blue-100 bg-blue-50 px-2.5 text-[9px] font-extrabold text-blue-700 transition hover:border-blue-200 hover:bg-blue-100" title="Add another role or manage assigned roles"><Plus size={12} /> Add another role</button>}{data.can_manage && !row.superuser && <button type="button" disabled={saving} onClick={() => void updateStatus(row)} className={`clay-row-action ${row.active ? 'clay-row-action-danger' : ''}`} title={row.active ? 'Deactivate account' : 'Activate account'}>{row.active ? <PowerOff size={13} /> : <Power size={13} />}</button>}</div></td></tr>)}</tbody>
            </table>
          </div>

          <div className="space-y-3 p-3 md:hidden">{rows.map((row) => <article key={row.id} className="rounded-2xl border border-slate-100 bg-[#FBFCFE] p-4"><div className="flex items-start gap-3"><ProfileAvatar src={row.photo} name={row.name} size="md" /><div className="min-w-0 flex-1"><div className="flex items-center justify-between gap-2"><h3 className="truncate text-sm font-extrabold text-slate-900">{row.name}</h3><span className={`rounded-full px-2 py-1 text-[8px] font-bold ${row.active ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>{row.active ? 'Active' : 'Inactive'}</span></div><p className="mt-1 truncate text-[10px] text-slate-500">{row.email || row.username}</p><p className="mt-1 text-[9px] text-slate-400">{row.department || row.account_type} · Last login {dateLabel(row.last_login)}</p></div></div><div className="mt-3 flex flex-wrap gap-1">{row.roles.map((role) => <span key={role} className={`rounded-full border px-2 py-1 text-[8px] font-bold ${roleTone(role)}`}>{role}</span>)}</div><div className="mt-3 flex gap-2">{row.staff_id && <Link href={`${dashboardPath}/staff/${row.staff_id}`} className="clay-button-secondary flex-1">Open profile</Link>}{data.can_manage && row.can_edit_roles && <button type="button" onClick={() => openRoleEditor(row)} className="clay-button-primary flex-1"><Plus size={13} /> Add another role</button>}</div></article>)}</div>
          {!rows.length && <div className="px-5 py-12 text-center text-xs text-slate-400">No user accounts match these filters.</div>}
        </section>
      ) : (
        <section className="tafiti-card overflow-hidden">
          <div className="border-b border-slate-100 px-4 py-4 sm:px-5"><div className="flex items-start gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-violet-50 text-violet-600"><ShieldCheck size={18} /></span><div><h2 className="text-sm font-extrabold text-[#10224A]">Role access matrix</h2><p className="mt-1 max-w-3xl text-[10px] leading-4 text-slate-500">This matrix reflects the server-side module registry. Assigning a role changes which existing Django workspaces the user can enter; it does not create new permissions in the browser.</p></div></div></div>
          <div className="overflow-x-auto"><table className="w-full min-w-[1320px] border-collapse text-center"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="sticky left-0 z-10 min-w-[190px] bg-[#F8FAFD] px-4 py-3 text-left text-[9px] font-extrabold text-slate-400">ROLE</th><th className="px-3 py-3 text-[9px] font-extrabold text-slate-400">USERS</th>{data.modules.map((module) => <th key={module.key} className="min-w-[92px] px-2 py-3 text-[8px] font-extrabold uppercase tracking-[.04em] text-slate-400">{module.label}</th>)}</tr></thead><tbody className="divide-y divide-slate-100">{data.roles.map((role) => { const assigned = data.users.filter((user) => user.roles.includes(role.label)).length; return <tr key={role.label} className="hover:bg-blue-50/15"><td className="sticky left-0 z-10 bg-white px-4 py-3 text-left"><div className="flex items-center gap-2"><span className={`grid h-8 w-8 place-items-center rounded-lg border ${roleTone(role.label)}`}><ShieldCheck size={14} /></span><div><p className="text-xs font-extrabold text-slate-800">{role.label}</p><p className="mt-0.5 text-[8px] text-slate-400">{role.assignable ? 'Staff role' : 'Managed separately'}</p></div></div></td><td className="px-3 py-3 text-xs font-extrabold text-slate-700">{assigned}</td>{data.modules.map((module) => <td key={module.key} className="px-2 py-3">{role.access[module.key] ? <span className="mx-auto grid h-6 w-6 place-items-center rounded-full bg-emerald-50 text-emerald-600"><Check size={13} /></span> : <span className="mx-auto block h-1.5 w-1.5 rounded-full bg-slate-200" />}</td>)}</tr>; })}</tbody></table></div>
          <div className="border-t border-slate-100 bg-[#FBFCFE] px-4 py-3 text-[10px] text-slate-500 sm:px-5"><LockKeyhole size={12} className="mr-1.5 inline text-blue-600" />Only an active <strong className="text-slate-700">Admin</strong> can change account status or staff role assignments. Head Teacher access is read-only.</div>
        </section>
      )}

      {editing && (
        <div className="fixed inset-0 z-[80] grid place-items-center bg-slate-950/35 p-4 backdrop-blur-[2px]" role="dialog" aria-modal="true">
          <div className="w-full max-w-lg overflow-hidden rounded-[22px] border border-slate-200 bg-white shadow-[0_30px_90px_rgba(7,22,51,.25)]">
            <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-4"><div><p className="text-[9px] font-extrabold uppercase tracking-[.1em] text-blue-600">Add another role</p><h2 className="mt-1 text-lg font-extrabold text-[#10224A]">{editing.name}</h2><p className="mt-1 text-[10px] text-slate-500">Keep the existing roles checked and select any additional workspace roles this staff member should have.</p>{editing.roles.length > 0 && <p className="mt-2 text-[9px] font-bold text-blue-700">Currently assigned: {editing.roles.join(', ')}</p>}</div><button type="button" onClick={() => setEditing(null)} className="clay-icon-button"><X size={15} /></button></div>
            <div className="max-h-[55vh] space-y-2 overflow-y-auto p-5">{assignableRoles.map((role) => { const checked = selectedRoles.includes(role.label); return <label key={role.label} className={`flex cursor-pointer items-center gap-3 rounded-xl border p-3.5 transition ${checked ? 'border-blue-200 bg-blue-50/60' : 'border-slate-100 bg-[#FBFCFE] hover:border-slate-200'}`}><input type="checkbox" checked={checked} onChange={() => setSelectedRoles((current) => checked ? current.filter((value) => value !== role.label) : [...current, role.label])} className="h-4 w-4 accent-blue-600" /><span className={`grid h-9 w-9 place-items-center rounded-xl border ${roleTone(role.label)}`}><ShieldCheck size={15} /></span><div className="min-w-0 flex-1"><p className="text-xs font-extrabold text-slate-800">{role.label}</p><p className="mt-0.5 text-[9px] text-slate-400">{Object.values(role.access).filter(Boolean).length} module groups available</p></div>{checked && <Check size={16} className="text-blue-600" />}</label>; })}</div>
            <div className="flex items-center justify-between gap-3 border-t border-slate-100 bg-[#FBFCFE] px-5 py-4"><p className="max-w-[230px] text-[9px] leading-4 text-slate-400">Once two or more roles are assigned, <strong className="text-slate-600">Switch workspace</strong> appears automatically in that user&apos;s profile menu. Parent access is managed separately.</p><div className="flex gap-2"><button type="button" onClick={() => setEditing(null)} className="clay-button-secondary">Cancel</button><button type="button" disabled={saving || !selectedRoles.length} onClick={() => void saveRoles()} className="clay-button-primary">{saving ? <LoaderCircle size={14} className="animate-spin" /> : <UserCog size={14} />} Save roles</button></div></div>
          </div>
        </div>
      )}
    </section>
  );
}
