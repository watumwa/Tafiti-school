'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { BookOpen, ClipboardList, Layers3, School } from 'lucide-react';

import { ReferenceAcademicSetupView } from './ReferenceAcademicSetupView';
import { ReferenceClassesWorkspace } from './ReferenceClassesWorkspace';
import { ReferenceResourceView } from './ReferenceResourceView';

const areas = [
  { key: 'periods', label: 'Years & Terms', icon: ClipboardList },
  { key: 'classes', label: 'Classes & Streams', icon: School },
  { key: 'subjects', label: 'Subjects', icon: BookOpen },
  { key: 'allocations', label: 'Teaching Setup', icon: Layers3 },
  { key: 'assessments', label: 'Assessment Setup', icon: ClipboardList },
] as const;

export function ReferenceAcademicOperationsView({ dashboardPath }: { dashboardPath: string }) {
  const searchParams = useSearchParams();
  const requested = searchParams.get('area');
  const area = areas.some((item) => item.key === requested) ? requested : 'periods';

  return (
    <section>
      <div className="mb-4 overflow-x-auto rounded-xl border border-slate-200 bg-white p-1.5 shadow-[0_5px_16px_rgba(28,55,97,.035)]">
        <div className="flex min-w-max gap-1">{areas.map((item) => { const Icon = item.icon; const active = item.key === area; return <Link key={item.key} href={`${dashboardPath}/academic-setup?area=${item.key}`} className={`inline-flex h-9 items-center gap-1.5 rounded-lg px-3 text-[10px] font-extrabold transition ${active ? 'bg-blue-600 text-white shadow-[0_5px_12px_rgba(37,99,235,.18)]' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'}`}><Icon size={13} />{item.label}</Link>; })}</div>
      </div>

      {area === 'classes' ? <ReferenceClassesWorkspace dashboardPath={dashboardPath} />
        : area === 'subjects' ? <ReferenceResourceView resource="subjects" />
          : area === 'allocations' ? <ReferenceAcademicSetupView visibleTools={['streams', 'class-streams', 'subject-allocations']} />
            : area === 'assessments' ? <ReferenceAcademicSetupView visibleTools={['assessments', 'assessment-types', 'grading']} />
              : <ReferenceAcademicSetupView visibleTools={['academic-years', 'terms']} />}
    </section>
  );
}
