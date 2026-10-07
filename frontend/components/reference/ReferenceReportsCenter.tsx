'use client';

import Link from 'next/link';
import {
  BarChart3,
  BookOpenCheck,
  CalendarCheck,
  FileBarChart,
  FileText,
  GraduationCap,
  Library,
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
    roles: ['Admin', 'Head Teacher', 'Director of Studies', 'Teacher', 'Class Teacher'],
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
    roles: ['Admin', 'Head Teacher', 'Director of Studies', 'Teacher', 'Class Teacher'],
  },
  {
    title: 'Attendance',
    icon: CalendarCheck,
    description: 'Attendance sessions and class attendance history.',
    items: [
      ['Attendance workspace', 'attendance'],
      ['Class attendance', 'classes'],
    ],
    roles: ['Admin', 'Head Teacher', 'Director of Studies', 'Teacher', 'Class Teacher'],
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
    roles: ['Admin', 'Head Teacher'],
  },
  {
    title: 'Staff',
    icon: FileBarChart,
    description: 'Staff profiles, roles and teaching allocations.',
    items: [
      ['Staff directory', 'staff'],
      ['Users & roles', 'users-roles'],
      ['Timetable', 'timetable'],
    ],
    roles: ['Admin', 'Head Teacher', 'Director of Studies'],
  },
  {
    title: 'Library',
    icon: Library,
    description: 'Loans, returns, overdue records and borrower activity.',
    items: [
      ['Library workspace', 'library'],
    ],
    roles: ['Admin', 'Head Teacher'],
  },
] as const;

export function ReferenceReportsCenter({ dashboardPath, role }: { dashboardPath: string; role: string }) {
  return (
    <section>
      <div className="mb-5 flex items-start gap-3">
        <span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-600"><BarChart3 size={21} /></span>
        <div>
          <h1 className="text-[1.65rem] font-extrabold tracking-[-0.035em] text-[#10224A]">Report Center</h1>
          <p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">One place to reach operational and management reports without filling the sidebar with dozens of report links.</p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {groups.filter((group) => (group.roles as readonly string[]).includes(role)).map((group) => {
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
                  <Link key={label} href={`${dashboardPath}/${href}`} className="group flex items-center gap-3 px-4 py-3 text-xs font-bold text-slate-700 transition hover:bg-blue-50/40 sm:px-5">
                    <span className="grid h-8 w-8 place-items-center rounded-lg bg-[#F5F8FC] text-slate-500 group-hover:bg-blue-100 group-hover:text-blue-700">{index % 2 === 0 ? <FileText size={14} /> : <BookOpenCheck size={14} />}</span>
                    <span className="flex-1">{label}</span>
                    <span className="text-[10px] font-semibold text-blue-600 opacity-0 transition group-hover:opacity-100">Open</span>
                  </Link>
                ))}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
