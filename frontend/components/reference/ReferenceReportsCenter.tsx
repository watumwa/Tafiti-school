'use client';

import Link from 'next/link';
import {
  BarChart3,
  BookOpenCheck,
  CalendarCheck,
  Download,
  FileBarChart,
  FileText,
  GraduationCap,
  Library,
  Printer,
  ReceiptText,
  Users,
} from 'lucide-react';

const groups = [
  {
    title: 'Students',
    icon: Users,
    description: 'Student registers, enrolment and demographic views.',
    items: [
      ['Student directory', 'students'],
      ['Admissions', 'admissions'],
      ['Class lists', 'classes'],
    ],
  },
  {
    title: 'Academics',
    icon: GraduationCap,
    description: 'Results, verification, performance and report preparation.',
    items: [
      ['Results overview', 'results'],
      ['Verification queue', 'results?view=verification'],
      ['Subjects', 'subjects'],
      ['Classes & streams', 'classes'],
    ],
  },
  {
    title: 'Attendance',
    icon: CalendarCheck,
    description: 'Attendance sessions and class attendance history.',
    items: [
      ['Attendance workspace', 'attendance'],
      ['Class attendance', 'classes'],
    ],
  },
  {
    title: 'Finance',
    icon: ReceiptText,
    description: 'Fees, payments, budgets and expenditure reporting.',
    items: [
      ['Student fee accounts', 'fees'],
      ['Payments', 'fees-payments'],
      ['Finance', 'finance'],
      ['Budgets', 'finance-budgets'],
    ],
  },
  {
    title: 'Staff',
    icon: FileBarChart,
    description: 'Staff profiles, roles and teaching allocations.',
    items: [
      ['Staff directory', 'staff'],
      ['Timetable', 'timetable'],
    ],
  },
  {
    title: 'Library',
    icon: Library,
    description: 'Loans, returns, overdue records and borrower activity.',
    items: [
      ['Library workspace', 'library'],
    ],
  },
] as const;

function exportHref(itemHref: string, format: 'csv' | 'print') {
  const [resource, query = ''] = itemHref.split('?');
  const params = new URLSearchParams(query);
  params.set('format', format);
  return `/api/workspace/export/${resource}?${params.toString()}`;
}

export function ReferenceReportsCenter({ dashboardPath }: { dashboardPath: string }) {
  return (
    <section>
      <div className="mb-5 flex items-start gap-3">
        <span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-600"><BarChart3 size={21} /></span>
        <div>
          <h1 className="text-[1.65rem] font-extrabold tracking-[-0.035em] text-[#10224A]">Report Center</h1>
          <p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">Open live operational reports, export the same permission-scoped data to CSV, or prepare a print-friendly copy without navigating through separate legacy report pages.</p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {groups.map((group) => {
          const Icon = group.icon;
          return (
            <article key={group.title} className="tafiti-card overflow-hidden">
              <div className="border-b border-slate-100 p-4 sm:p-5">
                <div className="flex items-start gap-3">
                  <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-blue-50 text-blue-600"><Icon size={18} /></span>
                  <div><h2 className="text-sm font-extrabold text-[#10224A]">{group.title}</h2><p className="mt-1 text-[10px] leading-4 text-slate-500">{group.description}</p></div>
                </div>
              </div>
              <div className="divide-y divide-slate-100">
                {group.items.map(([label, href], index) => (
                  <div key={label} className="group flex items-center gap-2 px-4 py-2.5 transition hover:bg-blue-50/40 sm:px-5">
                    <Link href={`${dashboardPath}/${href}`} className="flex min-w-0 flex-1 items-center gap-3 py-0.5 text-xs font-bold text-slate-700">
                      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-[#F5F8FC] text-slate-500 group-hover:bg-blue-100 group-hover:text-blue-700">{index % 2 === 0 ? <FileText size={14} /> : <BookOpenCheck size={14} />}</span>
                      <span className="truncate">{label}</span>
                    </Link>
                    <a href={exportHref(href, 'csv')} className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-slate-200 bg-white text-slate-400 transition hover:border-blue-200 hover:text-blue-600" title={`Export ${label} CSV`} aria-label={`Export ${label} CSV`}><Download size={13} /></a>
                    <a href={exportHref(href, 'print')} target="_blank" rel="noreferrer" className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-slate-200 bg-white text-slate-400 transition hover:border-blue-200 hover:text-blue-600" title={`Print ${label}`} aria-label={`Print ${label}`}><Printer size={13} /></a>
                  </div>
                ))}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
