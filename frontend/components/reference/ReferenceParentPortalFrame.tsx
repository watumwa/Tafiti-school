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

import { ReferenceParentPortalContent } from './ReferenceParentPortalContent';

const items = [
  { slug: 'parent-children', label: 'My Children', icon: Users },
  { slug: 'parent-results', label: 'Academic', icon: BookOpenCheck },
  { slug: 'parent-attendance', label: 'Attendance', icon: CalendarCheck },
  { slug: 'parent-finance', label: 'Finance', icon: WalletCards },
  { slug: 'parent-communication', label: 'Communication', icon: MessageCircle },
  { slug: 'parent-calendar', label: 'Calendar', icon: CalendarDays },
  { slug: 'parent-reports', label: 'Reports', icon: FileText },
] as const;

const titles: Record<string, { title: string; subtitle: string }> = {
  'parent-children': { title: 'Your family at a glance.', subtitle: 'See each linked child and move straight into academics, attendance, fees or communication.' },
  'parent-results': { title: 'Follow academic progress clearly.', subtitle: 'Review verified results, subject performance and class comparison without searching through school records.' },
  'parent-attendance': { title: 'Stay informed about attendance.', subtitle: 'See only submitted school attendance records, with simple status summaries and child filters.' },
  'parent-finance': { title: 'Understand the fee account.', subtitle: 'Bills, balances and payment receipts are brought together in one parent-friendly statement.' },
  'parent-communication': { title: 'Keep school conversations together.', subtitle: 'Message teachers assigned to your child and continue replies in the same secure thread.' },
  'parent-calendar': { title: 'Know what is coming next.', subtitle: 'Important parent-facing school events and activities are organized in one calendar view.' },
  'parent-reports': { title: 'Official reports when you need them.', subtitle: 'Generate the school academic PDF for an authorised child and academic term.' },
};

export function ReferenceParentPortalFrame({ screen, dashboardPath }: { screen: string; dashboardPath: string }) {
  const copy = titles[screen] ?? { title: 'Stay connected to your child’s school life.', subtitle: 'Move between the school information available to your parent account.' };
  return (
    <section>
      <header className="relative mb-4 overflow-hidden rounded-[20px] border border-blue-100 bg-gradient-to-r from-[#E6F0FF] via-[#F4F8FF] to-white p-5 shadow-[0_10px_28px_rgba(37,99,235,.06)] sm:p-6">
        <div className="absolute -right-12 -top-20 h-48 w-48 rounded-full bg-blue-100/60" aria-hidden="true" />
        <div className="absolute right-16 top-4 h-20 w-20 rounded-full border-[18px] border-white/55" aria-hidden="true" />
        <div className="relative max-w-3xl">
          <p className="text-[9px] font-extrabold uppercase tracking-[.14em] text-blue-600">Parent Portal</p>
          <h1 className="mt-1.5 text-2xl font-extrabold tracking-[-.04em] text-[#10224A] sm:text-[1.75rem]">{copy.title}</h1>
          <p className="mt-2 max-w-2xl text-[11px] leading-5 text-slate-500">{copy.subtitle}</p>
        </div>
      </header>

      <div className="mb-4 overflow-x-auto rounded-xl border border-slate-200 bg-white p-1.5 shadow-[0_5px_16px_rgba(28,55,97,.035)]">
        <div className="flex min-w-max gap-1">{items.map((item) => {
          const Icon = item.icon;
          const active = screen === item.slug;
          return <Link key={item.slug} href={`${dashboardPath}/${item.slug}`} className={`inline-flex h-9 items-center gap-1.5 rounded-lg px-3 text-[10px] font-extrabold transition ${active ? 'bg-blue-600 text-white shadow-[0_5px_12px_rgba(37,99,235,.18)]' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'}`}><Icon size={13} />{item.label}</Link>;
        })}</div>
      </div>

      <ReferenceParentPortalContent screen={screen} dashboardPath={dashboardPath} />
    </section>
  );
}
