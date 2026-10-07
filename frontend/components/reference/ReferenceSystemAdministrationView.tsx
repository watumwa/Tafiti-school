'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { ArrowRight, History, Settings2, ShieldCheck } from 'lucide-react';

import { ReferenceResourceView } from './ReferenceResourceView';
import { ReferenceUsersRolesView } from './ReferenceUsersRolesView';

const tools = [
  { key: 'settings', label: 'School Settings', description: 'School identity, branding, contacts and education-level configuration.', icon: Settings2 },
  { key: 'users', label: 'Users & Roles', description: 'Account access, assigned roles and controlled workspace permissions.', icon: ShieldCheck },
  { key: 'audit', label: 'System Audit Trail', description: 'Administrative changes, security events and operational accountability.', icon: History },
] as const;

export function ReferenceSystemAdministrationView({ dashboardPath }: { dashboardPath: string }) {
  const searchParams = useSearchParams();
  const view = searchParams.get('view');
  const active = tools.find((tool) => tool.key === view);

  return (
    <section>
      <div className="mb-5 flex items-start gap-3">
        <span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-600"><Settings2 size={21} /></span>
        <div><h1 className="text-[1.65rem] font-extrabold tracking-[-.035em] text-[#10224A]">System Administration</h1><p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">Administrator-only controls for school configuration, identity access and audit oversight.</p></div>
      </div>

      <div className="mb-5 grid gap-3 md:grid-cols-3">
        {tools.map((tool) => { const Icon = tool.icon; const selected = active?.key === tool.key; return <Link key={tool.key} href={`${dashboardPath}/system-administration?view=${tool.key}`} className={`group rounded-2xl border p-4 transition ${selected ? 'border-blue-200 bg-blue-50/70 shadow-[0_8px_20px_rgba(37,99,235,.08)]' : 'border-slate-200 bg-white hover:border-blue-200 hover:bg-blue-50/30'}`}><div className="flex items-start gap-3"><span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${selected ? 'bg-blue-600 text-white' : 'bg-[#F3F7FC] text-slate-600 group-hover:text-blue-600'}`}><Icon size={18} /></span><div className="min-w-0 flex-1"><p className="text-xs font-extrabold text-[#10224A]">{tool.label}</p><p className="mt-1 text-[10px] leading-4 text-slate-500">{tool.description}</p></div><ArrowRight size={14} className="mt-1 shrink-0 text-slate-300 group-hover:text-blue-600" /></div></Link>; })}
      </div>

      {!active ? <div className="tafiti-card grid min-h-[260px] place-items-center p-6 text-center"><div><ShieldCheck className="mx-auto text-blue-300" size={30} /><p className="mt-3 text-sm font-extrabold text-slate-800">Choose an administration tool</p><p className="mt-1 text-xs text-slate-500">These controls remain visible to administrators only.</p></div></div>
        : active.key === 'users' ? <ReferenceUsersRolesView dashboardPath={dashboardPath} />
          : <ReferenceResourceView resource={active.key} />}
    </section>
  );
}
