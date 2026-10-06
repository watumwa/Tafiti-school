'use client';

import Link from 'next/link';
import { ArrowRight, Workflow } from 'lucide-react';

import type { WorkspaceNavGroup, WorkspaceNavItem } from '@/lib/workspace';

type Props = {
  currentResource?: string | null;
  currentSlug: string;
  dashboardPath: string;
  navigation: WorkspaceNavGroup[];
};

const RELATED_WORK: Record<string, string[]> = {
  students: ['admissions', 'classes', 'attendance', 'results', 'fees', 'communication'],
  staff: ['classes', 'subjects', 'timetable', 'attendance', 'communication'],
  admissions: ['students', 'classes', 'communication'],
  parents: ['students', 'communication'],
  classes: ['students', 'subjects', 'attendance', 'timetable', 'results'],
  subjects: ['classes', 'staff', 'timetable', 'results'],
  results: ['students', 'classes', 'subjects', 'attendance', 'reports'],
  attendance: ['students', 'classes', 'timetable', 'results'],
  timetable: ['classes', 'subjects', 'staff', 'attendance'],
  fees: ['fees-payments', 'fees-class-bills', 'fees-bill-items', 'finance', 'communication'],
  'fees-payments': ['fees', 'fees-class-bills', 'finance'],
  'fees-class-bills': ['fees', 'fees-payments', 'fees-bill-items'],
  'fees-bill-items': ['fees-class-bills', 'fees', 'fees-payments'],
  finance: ['fees', 'fees-payments', 'finance-budgets', 'finance-vendors'],
  'finance-budgets': ['finance', 'finance-budget-items', 'finance-expenditure-items'],
  'finance-budget-items': ['finance-budgets', 'finance-expenditure-items', 'finance'],
  'finance-expenditure-items': ['finance-budgets', 'finance-budget-items', 'finance-expenses', 'finance-vendors'],
  'finance-expenses': ['finance-expenditure-items', 'finance', 'finance-vendors'],
  'finance-vendors': ['finance-expenditure-items', 'finance-expenses', 'finance'],
  'finance-income': ['finance', 'finance-budgets'],
  library: ['students', 'communication', 'reports'],
  communication: ['students', 'admissions', 'staff'],
  settings: ['users-roles', 'classes', 'subjects', 'staff'],
  'parent-children': ['parent-results', 'parent-attendance', 'parent-finance', 'parent-communication'],
  'parent-results': ['parent-children', 'parent-attendance', 'parent-reports'],
  'parent-attendance': ['parent-children', 'parent-results', 'parent-calendar'],
  'parent-finance': ['parent-children', 'parent-communication'],
  'parent-communication': ['parent-children', 'parent-calendar'],
  'parent-calendar': ['parent-children', 'parent-communication'],
};

function flattenNavigation(navigation: WorkspaceNavGroup[]): WorkspaceNavItem[] {
  const unique = new Map<string, WorkspaceNavItem>();
  navigation.flatMap((group) => group.items).forEach((item) => unique.set(item.slug, item));
  return Array.from(unique.values());
}

function moduleHref(dashboardPath: string, item: WorkspaceNavItem) {
  return item.slug === 'overview' ? dashboardPath : `${dashboardPath}/${item.slug}`;
}

export function WorkspaceFlowBar({ currentResource, currentSlug, dashboardPath, navigation }: Props) {
  if (currentSlug === 'overview') return null;

  const items = flattenNavigation(navigation);
  const candidates = RELATED_WORK[currentResource || currentSlug] ?? [];
  const related = candidates
    .map((slug) => items.find((item) => item.slug === slug))
    .filter((item): item is WorkspaceNavItem => item !== undefined)
    .filter((item) => item.slug !== currentSlug)
    .slice(0, 5);

  if (!related.length) return null;

  return (
    <div className="border-b border-[#E9EEF5] bg-white px-4 py-2.5 sm:px-6">
      <div className="mx-auto flex w-full max-w-[1600px] items-center gap-2 overflow-x-auto">
        <span className="mr-1 inline-flex shrink-0 items-center gap-1.5 text-[9px] font-extrabold uppercase tracking-[.09em] text-slate-400">
          <Workflow size={13} className="text-blue-500" /> Related work
        </span>
        {related.map((item) => (
          <Link
            key={item.slug}
            href={moduleHref(dashboardPath, item)}
            className="group inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 bg-[#FBFCFE] px-2.5 text-[9px] font-bold text-slate-600 transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
          >
            {item.label}
            <ArrowRight size={11} className="text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-blue-500" />
          </Link>
        ))}
      </div>
    </div>
  );
}
