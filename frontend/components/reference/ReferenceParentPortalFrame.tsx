'use client';

import Link from 'next/link';
import {
  BookOpenCheck,
  CalendarCheck,
  CalendarDays,
  FileText,
  MessageCircle,
  Users,
  WalletCards,
} from 'lucide-react';

import { ParentPortalView } from '@/components/workspace/ParentPortalView';

const items = [
  { slug: 'parent-children', label: 'My Children', icon: Users },
  { slug: 'parent-results', label: 'Academic', icon: BookOpenCheck },
  { slug: 'parent-attendance', label: 'Attendance', icon: CalendarCheck },
  { slug: 'parent-finance', label: 'Finance', icon: WalletCards },
  { slug: 'parent-communication', label: 'Communication', icon: MessageCircle },
  { slug: 'parent-calendar', label: 'Calendar', icon: CalendarDays },
  { slug: 'parent-reports', label: 'Reports', icon: FileText },
] as const;

export function ReferenceParentPortalFrame({ screen, dashboardPath }: { screen: string; dashboardPath: string }) {
  return (
    <section>
      <header className="relative mb-4 overflow-hidden rounded-[18px] border border-blue-100 bg-gradient-to-r from-[#EAF3FF] via-[#F6F9FF] to-white p-5 shadow-[0_8px_24px_rgba(37,99,235,.05)] sm:p-6">
        <div className="absolute -right-10 -top-16 h-44 w-44 rounded-full bg-blue-100/55" aria-hidden="true" />
        <div className="relative"><p className="text-[9px] font-extrabold uppercase tracking-[.12em] text-blue-600">Parent Portal</p><h1 className="mt-1 text-2xl font-extrabold tracking-[-.035em] text-[#10224A]">Stay connected to your child&apos;s school life.</h1><p className="mt-2 max-w-2xl text-xs leading-5 text-slate-500">Move between academics, attendance, finance and communication without returning to the dashboard or searching for your child again.</p></div>
      </header>

      <div className="mb-4 overflow-x-auto rounded-xl border border-slate-200 bg-white p-1.5 shadow-[0_5px_16px_rgba(28,55,97,.035)]">
        <div className="flex min-w-max gap-1">{items.map((item) => { const Icon = item.icon; const active = screen === item.slug; return <Link key={item.slug} href={`${dashboardPath}/${item.slug}`} className={`inline-flex h-9 items-center gap-1.5 rounded-lg px-3 text-[10px] font-extrabold transition ${active ? 'bg-blue-600 text-white shadow-[0_5px_12px_rgba(37,99,235,.18)]' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'}`}><Icon size={13} />{item.label}</Link>; })}</div>
      </div>

      <ParentPortalView screen={screen} dashboardPath={dashboardPath} />
    </section>
  );
}
