'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { BookOpen, Landmark, WalletCards } from 'lucide-react';

import { ReferenceLibraryView } from './ReferenceLibraryView';
import { ReferenceResourceView } from './ReferenceResourceView';

type Tab = { slug: string; label: string; icon?: 'wallet' | 'finance' | 'book' };

const feesTabs: Tab[] = [
  { slug: 'fees', label: 'Student Accounts', icon: 'wallet' },
  { slug: 'fees-payments', label: 'Payments', icon: 'wallet' },
  { slug: 'fees-class-bills', label: 'Class Bills', icon: 'book' },
  { slug: 'fees-bill-items', label: 'Fee Categories', icon: 'book' },
];

const financeTabs: Tab[] = [
  { slug: 'finance', label: 'Overview', icon: 'finance' },
  { slug: 'finance-budgets', label: 'Budgets', icon: 'finance' },
  { slug: 'finance-budget-items', label: 'Allocations', icon: 'finance' },
  { slug: 'finance-expenditure-items', label: 'Expenditure Items', icon: 'finance' },
  { slug: 'finance-expenses', label: 'Expense Categories', icon: 'finance' },
  { slug: 'finance-vendors', label: 'Vendors', icon: 'finance' },
  { slug: 'finance-income', label: 'Income Sources', icon: 'finance' },
];

const groups: Record<string, Tab[]> = {
  fees: feesTabs,
  'fees-payments': feesTabs,
  'fees-class-bills': feesTabs,
  'fees-bill-items': feesTabs,
  finance: financeTabs,
  'finance-budgets': financeTabs,
  'finance-budget-items': financeTabs,
  'finance-expenditure-items': financeTabs,
  'finance-expenses': financeTabs,
  'finance-vendors': financeTabs,
  'finance-income': financeTabs,
};

function TabIcon({ icon }: { icon?: Tab['icon'] }) {
  if (icon === 'finance') return <Landmark size={13} />;
  if (icon === 'book') return <BookOpen size={13} />;
  return <WalletCards size={13} />;
}

export function ReferenceLinkedResourceView({ resource, dashboardPath }: { resource: string; dashboardPath: string }) {
  const pathname = usePathname();

  if (resource === 'library') return <ReferenceLibraryView />;

  const tabs = groups[resource];
  if (!tabs) return <ReferenceResourceView resource={resource} />;

  return (
    <section>
      <div className="mb-4 overflow-x-auto rounded-xl border border-slate-200 bg-white p-1.5 shadow-[0_5px_16px_rgba(28,55,97,.035)]">
        <div className="flex min-w-max gap-1">
          {tabs.map((tab) => {
            const href = `${dashboardPath}/${tab.slug}`;
            const active = pathname === href || pathname.startsWith(`${href}/`);
            return (
              <Link key={tab.slug} href={href} className={`inline-flex h-9 items-center gap-1.5 rounded-lg px-3 text-[10px] font-extrabold transition ${active ? 'bg-blue-600 text-white shadow-[0_5px_12px_rgba(37,99,235,.18)]' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'}`}>
                <TabIcon icon={tab.icon} />{tab.label}
              </Link>
            );
          })}
        </div>
      </div>
      <ReferenceResourceView resource={resource} />
    </section>
  );
}
