'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  ArrowLeft,
  BookOpen,
  CalendarCheck,
  CalendarDays,
  GraduationCap,
  Layers3,
  LoaderCircle,
  Plus,
  School,
  Search,
  Users,
} from 'lucide-react';

import { ResourceFormDialog } from '@/components/workspace/ResourceFormDialog';
import { useToast } from '@/components/ui/ToastProvider';
import type { WorkspaceFormSchema, WorkspaceResource } from '@/lib/workspace';
import { ReferenceAcademicSetupView } from './ReferenceAcademicSetupView';

const setupTools = ['streams', 'class-streams', 'subject-allocations'] as const;

export function ReferenceClassesWorkspace({ dashboardPath }: { dashboardPath: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  const setupMode = searchParams.get('setup') === '1';
  const [data, setData] = useState<WorkspaceResource | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [year, setYear] = useState('');
  const [reloadKey, setReloadKey] = useState(0);
  const [formOpen, setFormOpen] = useState(false);
  const [formSchema, setFormSchema] = useState<WorkspaceFormSchema | null>(null);
  const [formLoading, setFormLoading] = useState(false);
  const [formErrors, setFormErrors] = useState<Record<string, string[]>>({});

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetch('/api/workspace/classes?page=1&page_size=100', { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || 'Classes could not be loaded.');
        return result as WorkspaceResource;
      })
      .then(setData)
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Classes could not be loaded.');
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [reloadKey]);

  const years = useMemo(() => [...new Set((data?.rows ?? []).map((row) => String(row.year ?? '')).filter(Boolean))], [data]);
  const rows = useMemo(() => {
    const text = query.trim().toLocaleLowerCase();
    return (data?.rows ?? []).filter((row) => (!year || String(row.year ?? '') === year)
      && (!text || Object.values(row).some((value) => String(value ?? '').toLocaleLowerCase().includes(text))));
  }, [data, query, year]);

  function setSetup(tool?: typeof setupTools[number]) {
    const params = new URLSearchParams(searchParams.toString());
    if (tool) {
      params.set('setup', '1');
      params.set('tool', tool);
    } else {
      params.delete('setup');
      params.delete('tool');
    }
    router.replace(`${dashboardPath}/classes${params.size ? `?${params}` : ''}`, { scroll: false });
  }

  async function openCreateForm() {
    setFormOpen(true);
    setFormSchema(null);
    setFormErrors({});
    setFormLoading(true);
    try {
      const response = await fetch('/api/workspace/resources/classes/form', { cache: 'no-store' });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'The class form could not be opened.');
      setFormSchema(result as WorkspaceFormSchema);
    } catch (reason: unknown) {
      toast.error('Could not open form', reason instanceof Error ? reason.message : 'The class form could not be opened.');
      setFormOpen(false);
    } finally {
      setFormLoading(false);
    }
  }

  async function createClass(values: Record<string, unknown>) {
    setFormLoading(true);
    setFormErrors({});
    try {
      const response = await fetch('/api/workspace/resources/classes/form', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      });
      const result = await response.json();
      if (!response.ok) {
        setFormErrors((result.errors as Record<string, string[]>) ?? {});
        throw new Error(result.detail || 'The academic class could not be created.');
      }
      toast.success('Academic class created', result.detail || 'The class is ready for streams and registration.');
      setFormOpen(false);
      setReloadKey((value) => value + 1);
    } catch (reason: unknown) {
      toast.error('Could not create class', reason instanceof Error ? reason.message : 'The academic class could not be created.');
    } finally {
      setFormLoading(false);
    }
  }

  if (setupMode) {
    return (
      <section>
        <button type="button" onClick={() => setSetup()} className="mb-3 inline-flex items-center gap-1.5 text-[11px] font-bold text-slate-500 hover:text-blue-600">
          <ArrowLeft size={13} /> Back to classes
        </button>
        <ReferenceAcademicSetupView initialTool="streams" visibleTools={setupTools} />
      </section>
    );
  }

  const canCreate = data?.actions.create ?? false;
  return (
    <section>
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex items-start gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-600"><School size={21} /></span>
          <div>
            <h1 className="text-[1.65rem] font-extrabold tracking-[-0.035em] text-[#10224A]">Classes &amp; Streams</h1>
            <p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">Set up academic classes, assign stream teachers, manage registers and open related learning workflows in context.</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => setSetup('streams')} className="clay-button-secondary"><Layers3 size={14} /> Streams &amp; teachers</button>
          {canCreate && <button type="button" onClick={() => void openCreateForm()} className="clay-button-primary"><Plus size={14} /> Add academic class</button>}
        </div>
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <div className="tafiti-kpi"><p className="text-[9px] font-extrabold uppercase tracking-[.06em] text-slate-400">Academic classes</p><p className="mt-1.5 text-xl font-extrabold text-[#10224A]">{data?.pagination.total ?? '—'}</p><p className="mt-1 text-[9px] text-slate-400">Across the selected school level</p></div>
        <div className="tafiti-kpi"><p className="text-[9px] font-extrabold uppercase tracking-[.06em] text-slate-400">Configured streams</p><p className="mt-1.5 text-xl font-extrabold text-[#10224A]">{data ? rows.filter((row) => String(row.streams ?? '').trim() !== '—').length : '—'}</p><p className="mt-1 text-[9px] text-slate-400">Classes with at least one stream</p></div>
        <div className="tafiti-kpi"><p className="text-[9px] font-extrabold uppercase tracking-[.06em] text-slate-400">Academic years</p><p className="mt-1.5 text-xl font-extrabold text-[#10224A]">{years.length || '—'}</p><p className="mt-1 text-[9px] text-slate-400">Year and term context is preserved</p></div>
      </div>

      <section className="tafiti-card overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-slate-100 px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between sm:px-5">
          <div><h2 className="text-sm font-extrabold text-[#10224A]">Academic class register</h2><p className="mt-1 text-[10px] text-slate-500">Open a class to reach its stream register, teachers, subjects, attendance, results and timetable.</p></div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <label className="relative block"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search classes or streams" className="tafiti-input h-9 w-full pl-9 pr-3 text-xs sm:w-[220px]" /></label>
            <select aria-label="Filter by academic year" value={year} onChange={(event) => setYear(event.target.value)} className="tafiti-input h-9 text-xs sm:w-[150px]"><option value="">All years</option>{years.map((item) => <option key={item} value={item}>{item}</option>)}</select>
          </div>
        </div>
        {loading && !data ? <div className="grid min-h-[300px] place-items-center"><LoaderCircle className="animate-spin text-blue-600" size={23} /></div>
          : error && !data ? <div className="px-5 py-12 text-center"><p className="text-sm font-bold text-slate-800">Classes unavailable</p><p className="mt-2 text-xs text-slate-500">{error}</p><button type="button" onClick={() => setReloadKey((value) => value + 1)} className="clay-button-primary mt-4">Try again</button></div>
            : rows.length ? <div className="overflow-x-auto"><table className="w-full min-w-[820px] border-collapse text-left">
              <thead><tr className="border-b border-slate-100 bg-[#F8FAFD]">{[['class', 'Class'], ['section', 'Section'], ['year', 'Academic year'], ['term', 'Term'], ['streams', 'Streams'], ['fees', 'Class fee']].map(([key, label]) => <th key={key} className="px-4 py-3 text-[9px] font-extrabold uppercase tracking-[.06em] text-slate-400">{label}</th>)}<th className="px-4 py-3 text-right text-[9px] font-extrabold uppercase tracking-[.06em] text-slate-400">Workspace</th></tr></thead>
              <tbody className="divide-y divide-slate-100">{rows.map((row) => <tr key={String(row.id)} className="hover:bg-blue-50/25">
                <td className="px-4 py-3 text-xs font-bold text-slate-800">{String(row.class ?? '—')}</td><td className="px-4 py-3 text-xs text-slate-600">{String(row.section ?? '—')}</td><td className="px-4 py-3 text-xs text-slate-600">{String(row.year ?? '—')}</td><td className="px-4 py-3 text-xs text-slate-600">{String(row.term ?? '—')}</td><td className="max-w-[230px] px-4 py-3 text-xs text-slate-600">{String(row.streams ?? '—')}</td><td className="px-4 py-3 text-xs text-slate-600">{String(row.fees ?? '0')}</td>
                <td className="px-4 py-3 text-right"><Link href={`${dashboardPath}/classes/${String(row.id)}`} className="inline-flex items-center gap-1.5 text-[10px] font-extrabold text-blue-700 hover:underline">Open class <GraduationCap size={13} /></Link></td>
              </tr>)}</tbody>
            </table></div>
              : <div className="px-5 py-12 text-center"><p className="text-sm font-bold text-slate-800">No classes match this view</p><p className="mt-1 text-xs text-slate-500">Change the year or search filters, or configure an academic class first.</p></div>}
      </section>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { label: 'Streams & class teachers', href: `${dashboardPath}/classes?setup=1&tool=class-streams`, icon: Users, detail: 'Assign a teacher to each configured class stream.' },
          { label: 'Subject allocations', href: `${dashboardPath}/classes?setup=1&tool=subject-allocations`, icon: BookOpen, detail: 'Connect subjects and subject teachers to each stream.' },
          { label: 'Attendance', href: `${dashboardPath}/attendance`, icon: CalendarCheck, detail: 'Take and review attendance with class context.' },
          { label: 'Timetable', href: `${dashboardPath}/timetable`, icon: CalendarDays, detail: 'View lessons, subjects, teachers and rooms.' },
        ].map(({ label, href, icon: Icon, detail }) => <Link key={label} href={href} className="tafiti-soft-card flex items-start gap-3 p-4 transition hover:border-blue-200 hover:bg-blue-50/40"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-blue-50 text-blue-600"><Icon size={16} /></span><span><span className="block text-xs font-extrabold text-[#10224A]">{label}</span><span className="mt-1 block text-[10px] leading-4 text-slate-500">{detail}</span></span></Link>)}
      </div>

      <ResourceFormDialog open={formOpen} schema={formSchema} loading={formLoading} errors={formErrors} onClose={() => { setFormOpen(false); setFormErrors({}); }} onSubmit={createClass} />
    </section>
  );
}
