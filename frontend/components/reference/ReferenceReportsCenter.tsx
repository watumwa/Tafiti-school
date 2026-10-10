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
    title: 'Academics',
    icon: GraduationCap,
    description: 'Performance, verified results and report-card analysis.',
    items: [
      ['Class performance', 'results?view=performance&group=class'],
      ['Student performance', 'results?view=report-cards'],
      ['Subject performance', 'results?view=performance&group=subject'],
      ['Results summary', 'results'],
      ['Verification queue', 'results?view=verification'],
      ['Report cards', 'results?view=report-cards'],
    ],
    roles: ['Admin', 'Head Teacher', 'Director of Studies', 'Teacher', 'Class Teacher'],
  },
  {
    title: 'Attendance',
    icon: CalendarCheck,
    description: 'Daily, weekly and monthly attendance plus absenteeism follow-up.',
    items: [
      ['Daily attendance', 'attendance?report=daily'],
      ['Weekly attendance', 'attendance?report=weekly'],
      ['Monthly attendance', 'attendance?report=monthly'],
      ['Student absenteeism', 'attendance?report=absenteeism'],
      ['Class attendance', 'attendance?report=class'],
    ],
    roles: ['Admin', 'Head Teacher', 'Director of Studies', 'Teacher', 'Class Teacher'],
  },
  {
    title: 'Finance',
    icon: ReceiptText,
    description: 'Collections, debtors, statements, expenditure and budget control.',
    items: [
      ['Collections', 'fees-payments?report=collections'],
      ['Outstanding fees', 'fees?status=outstanding'],
      ['Payment methods', 'fees-payments?report=methods'],
      ['Debtor list', 'fees?status=outstanding&report=debtors'],
      ['Student statements', 'fees?report=statements'],
      ['Income & collections', 'finance?report=income'],
      ['Expenses', 'finance?report=expenses'],
      ['Budget vs actual', 'finance-budgets?report=variance'],
      ['Daily cashier closing', 'fees-payments?report=cashier-closing'],
      ['Outstanding-fee aging', 'fees?report=aging'],
    ],
    roles: ['Admin', 'Head Teacher', 'Bursar'],
  },
  {
    title: 'Admissions',
    icon: Users,
    description: 'Application funnel, decisions and enrolment conversion.',
    items: [
      ['All applicants', 'admissions?report=applicants'],
      ['Enrolled applicants', 'admissions?status=enrolled'],
      ['Rejected applicants', 'admissions?status=rejected'],
      ['Waitlisted applicants', 'admissions?status=waitlisted'],
      ['Conversion rate', 'admissions?report=conversion'],
    ],
    roles: ['Admin', 'Head Teacher', 'Admissions Officer'],
  },
  {
    title: 'Library',
    icon: Library,
    description: 'Borrowing activity, overdue items and financial penalties.',
    items: [
      ['Borrowed books', 'library?view=loans&status=active'],
      ['Overdue books', 'library?view=loans&status=overdue'],
      ['Library fines', 'library?view=fines'],
      ['Most borrowed books', 'library?view=reports&report=popular'],
    ],
    roles: ['Admin', 'Head Teacher', 'Librarian'],
  },
  {
    title: 'HR & Staff',
    icon: FileBarChart,
    description: 'Staffing, attendance, leave, teaching load and payroll readiness.',
    items: [
      ['Staff list', 'staff?report=directory'],
      ['Staff attendance', 'staff?report=attendance'],
      ['Leave report', 'staff?report=leave'],
      ['Teaching allocations', 'staff?report=allocations'],
      ['Salary history', 'staff?report=salary-history'],
      ['Payroll', 'staff?report=payroll'],
    ],
    roles: ['Admin', 'Head Teacher', 'Director of Studies'],
  },
  {
    title: 'Student Administration',
    icon: FileBarChart,
    description: 'Registers, lifecycle movements and document completeness.',
    items: [
      ['Student directory', 'students'],
      ['Class lists', 'classes'],
      ['Transfers & leavers', 'students?report=lifecycle'],
      ['Student documents', 'students?report=documents'],
    ],
    roles: ['Admin', 'Head Teacher', 'Director of Studies', 'Admissions Officer'],
  },
] as const;

export function ReferenceReportsCenter({ dashboardPath, role }: { dashboardPath: string; role: string }) {
  return (
    <section>
      <div className="mb-5 flex items-start gap-3">
        <span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-600"><BarChart3 size={21} /></span>
        <div>
          <h1 className="text-[1.65rem] font-extrabold tracking-[-0.035em] text-[#10224A]">Report Center</h1>
          <p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">A dedicated reporting hub for academics, attendance, finance, admissions, library and HR. Operational pages open with the relevant report filters already selected.</p>
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
