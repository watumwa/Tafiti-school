'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { BadgeCheck, LoaderCircle, Search, ShieldCheck, UserRound, Users } from 'lucide-react';

import type { WorkspaceResource } from '@/lib/workspace';
import { ProfileAvatar } from '@/components/workspace/ProfileAvatar';

export function ReferenceUsersRolesView({ dashboardPath }: { dashboardPath: string }) {
  const [data, setData] = useState<WorkspaceResource | null>(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/workspace/resources/staff?page_size=100', { cache: 'no-store', signal: controller.signal })
      .then(async (response) => response.ok ? await response.json() as WorkspaceResource : null)
      .then(setData)
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);

  const rows = useMemo(() => {
    const text = query.trim().toLowerCase();
    if (!text) return data?.rows ?? [];
    return (data?.rows ?? []).filter((row) => Object.values(row).some((value) => String(value ?? '').toLowerCase().includes(text)));
  }, [data, query]);

  const roleSet = new Set<string>();
  (data?.rows ?? []).forEach((row) => String(row.roles ?? '').split(',').map((item) => item.trim()).filter(Boolean).forEach((item) => roleSet.add(item)));
  const active = (data?.rows ?? []).filter((row) => String(row.status ?? '').toLowerCase() === 'active').length;

  return (
    <section>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex items-start gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-600"><ShieldCheck size={21} /></span><div><h1 className="text-[1.65rem] font-extrabold tracking-[-0.035em] text-[#10224A]">Users &amp; Roles</h1><p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">View staff identities and assigned roles. Authentication and permission enforcement remain controlled by Django.</p></div></div>
        <Link href={`${dashboardPath}/staff`} className="clay-button-primary"><UserRound size={14} /> Manage staff accounts</Link>
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="tafiti-kpi"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-blue-50 text-blue-600"><Users size={18} /></span><div><p className="text-[9px] font-bold text-slate-400">TOTAL STAFF USERS</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{data?.pagination.total ?? 0}</p></div></div></div>
        <div className="tafiti-kpi"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-50 text-emerald-600"><BadgeCheck size={18} /></span><div><p className="text-[9px] font-bold text-slate-400">ACTIVE</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{active}</p></div></div></div>
        <div className="tafiti-kpi"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-violet-50 text-violet-600"><ShieldCheck size={18} /></span><div><p className="text-[9px] font-bold text-slate-400">ROLE TYPES</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{roleSet.size}</p></div></div></div>
        <div className="tafiti-kpi"><p className="text-[9px] font-bold text-slate-400">SECURITY MODEL</p><p className="mt-2 text-xs font-extrabold text-blue-700">Server-enforced RBAC</p><p className="mt-1 text-[9px] text-slate-400">Frontend visibility is not authorization.</p></div>
      </div>

      <section className="tafiti-card overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-slate-100 px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between sm:px-5"><div className="relative w-full sm:max-w-[360px]"><Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search by name, role or department…" className="tafiti-input h-9 w-full pl-9 pr-3 text-xs" /></div><div className="flex gap-1.5">{Array.from(roleSet).slice(0, 4).map((role) => <span key={role} className="rounded-full border border-blue-100 bg-blue-50 px-2.5 py-1 text-[9px] font-bold text-blue-700">{role}</span>)}</div></div>
        {loading ? <div className="grid min-h-[300px] place-items-center"><LoaderCircle className="animate-spin text-blue-600" /></div> : <div className="overflow-x-auto"><table className="w-full min-w-[760px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">USER</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">ROLE</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">DEPARTMENT</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">EMAIL</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STATUS</th><th className="px-4 py-3 text-right text-[9px] font-extrabold text-slate-400">ACTION</th></tr></thead><tbody className="divide-y divide-slate-100">{rows.map((row, index) => <tr key={String(row.id ?? index)} className="hover:bg-blue-50/25"><td className="px-4 py-3"><div className="flex items-center gap-2.5"><ProfileAvatar src={row.photo} name={String(row.name ?? 'Staff')} size="sm" /><span className="text-xs font-bold text-slate-800">{String(row.name ?? '—')}</span></div></td><td className="px-4 py-3 text-xs text-slate-600">{String(row.roles ?? '—')}</td><td className="px-4 py-3 text-xs text-slate-600">{String(row.department ?? '—')}</td><td className="px-4 py-3 text-xs text-slate-600">{String(row.email ?? '—')}</td><td className="px-4 py-3"><span className={`rounded-full border px-2 py-1 text-[9px] font-bold ${String(row.status).toLowerCase() === 'active' ? 'border-emerald-100 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-slate-50 text-slate-500'}`}>{String(row.status ?? '—')}</span></td><td className="px-4 py-3 text-right">{typeof row.id === 'number' && <Link href={`${dashboardPath}/staff/${row.id}`} className="text-[10px] font-bold text-blue-600 hover:underline">Open profile</Link>}</td></tr>)}</tbody></table></div>}
      </section>
    </section>
  );
}
