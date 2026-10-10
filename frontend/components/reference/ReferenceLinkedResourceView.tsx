'use client';

import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';
import { Landmark, MessagesSquare, Send, Settings2 } from 'lucide-react';

import { ReferenceAcademicSetupView } from './ReferenceAcademicSetupView';
import { ReferenceClassesWorkspace } from './ReferenceClassesWorkspace';
import { ReferenceAdmissionsWorkspace } from './ReferenceAdmissionsWorkspace';
import { ReferenceAttendanceHub } from './ReferenceAttendanceHub';
import { ReferenceCommunicationConsoleView } from './ReferenceCommunicationConsoleView';
import { ReferenceFinanceReportView } from './ReferenceFinanceReportView';
import { ReferenceLibraryConsoleView } from './ReferenceLibraryConsoleView';
import { ReferenceOutboundCommunicationView } from './ReferenceOutboundCommunicationView';
import { ReferenceReportCardsWorkspace } from './ReferenceReportCardsWorkspace';
import { ReferenceResourceView } from './ReferenceResourceView';
import { ReferenceResultsOperations } from './ReferenceResultsOperations';
import { ReferenceStudentAccountsView } from './ReferenceStudentAccountsView';
import { ReferenceTimetableWorkspace } from './ReferenceTimetableWorkspace';

type Tab = { slug: string; label: string };

const financeTabs: Tab[] = [
  { slug: 'finance', label: 'Overview' },
  { slug: 'finance-budgets', label: 'Budgets' },
  { slug: 'finance-budget-items', label: 'Allocations' },
  { slug: 'finance-expenditure-items', label: 'Expenditure Items' },
  { slug: 'finance-expenses', label: 'Expense Categories' },
  { slug: 'finance-vendors', label: 'Vendors' },
  { slug: 'finance-income', label: 'Income Sources' },
];

const groups: Record<string, Tab[]> = {
  finance: financeTabs,
  'finance-budgets': financeTabs,
  'finance-budget-items': financeTabs,
  'finance-expenditure-items': financeTabs,
  'finance-expenses': financeTabs,
  'finance-vendors': financeTabs,
  'finance-income': financeTabs,
};

export function ReferenceLinkedResourceView({ resource, dashboardPath }: { resource: string; dashboardPath: string }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  if (resource === 'admissions') return <ReferenceAdmissionsWorkspace dashboardPath={dashboardPath} />;
  if (resource === 'classes') return <ReferenceClassesWorkspace dashboardPath={dashboardPath} />;
  if (resource === 'attendance') return <ReferenceAttendanceHub dashboardPath={dashboardPath} />;
  if (resource === 'timetable') return <ReferenceTimetableWorkspace />;
  if (resource === 'communication') {
    const outbound = searchParams.get('view') === 'outbound';
    return <section>
      <div className="mb-4 flex w-fit gap-1 rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
        <Link href={`${dashboardPath}/communication`} className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-[10px] font-extrabold ${!outbound ? 'bg-blue-600 text-white' : 'text-slate-500 hover:bg-slate-50'}`}><MessagesSquare size={13} /> Internal communication</Link>
        <Link href={`${dashboardPath}/communication?view=outbound`} className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-[10px] font-extrabold ${outbound ? 'bg-blue-600 text-white' : 'text-slate-500 hover:bg-slate-50'}`}><Send size={13} /> Outbound notifications</Link>
      </div>
      {outbound ? <ReferenceOutboundCommunicationView /> : <ReferenceCommunicationConsoleView />}
    </section>;
  }
  if (resource === 'library') return <ReferenceLibraryConsoleView />;
  if (resource === 'results') {
    const view = searchParams.get('view');
    const configMode = view === 'config';
    const reportCardsMode = view === 'report-cards';
    return (
      <section>
        <div className="mb-3 flex justify-end">
          <Link href={configMode ? `${dashboardPath}/results` : `${dashboardPath}/results?view=config`} className="clay-button-secondary">
            <Settings2 size={14} />{configMode ? 'Back to Results' : 'Academic Setup'}
          </Link>
        </div>
        {configMode ? <ReferenceAcademicSetupView /> : reportCardsMode ? <ReferenceReportCardsWorkspace dashboardPath={dashboardPath} /> : <ReferenceResultsOperations dashboardPath={dashboardPath} />}
      </section>
    );
  }

  if (resource === 'fees') return <ReferenceStudentAccountsView dashboardPath={dashboardPath} />;
  if (['fees-payments', 'fees-class-bills', 'fees-bill-items'].includes(resource)) {
    return <ReferenceResourceView resource={resource} />;
  }

  const financeReport = resource === 'finance' ? searchParams.get('report') : null;
  if (financeReport && ['financial-statement', 'statement', 'income-expense', 'reconciliation', 'bank-reconciliation'].includes(financeReport)) {
    return <ReferenceFinanceReportView report={financeReport} />;
  }

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
                <Landmark size={13} />{tab.label}
              </Link>
            );
          })}
        </div>
      </div>
      <ReferenceResourceView resource={resource} />
    </section>
  );
}
