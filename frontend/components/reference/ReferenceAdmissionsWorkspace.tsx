'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import {
  ArrowLeft,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  Edit3,
  GraduationCap,
  LoaderCircle,
  MessageCircle,
  Search,
  ShieldCheck,
  UserPlus,
  Users,
  XCircle,
} from 'lucide-react';

import { ResourceFormDialog } from '@/components/workspace/ResourceFormDialog';
import { useToast } from '@/components/ui/ToastProvider';
import type { WorkspaceFormSchema } from '@/lib/workspace';

type Metric = { label: string; value: number; hint: string; tone: string };
type StatusFilter = { value: string; label: string; count: number };
type Option = { id: number; label: string };
type AdmissionRow = {
  id: number;
  application_number: string;
  applicant: string;
  gender: string;
  class: string;
  stream: string;
  guardian: string;
  contact: string;
  source: string;
  source_code: string;
  status: string;
  status_code: string;
  cycle: string;
  created: string;
  updated: string;
  enrolled_student_id: number | null;
};
type AdmissionsListPayload = {
  title: string;
  description: string;
  metrics: Metric[];
  filters: { status: string; q: string; cycle: string; class_id: string; date_from: string; date_to: string };
  statuses: StatusFilter[];
  cycles: Option[];
  classes: Option[];
  rows: AdmissionRow[];
  actions: { can_create: boolean; can_change_status: boolean; can_enroll: boolean };
};
type AdmissionDetail = AdmissionRow & {
  birthdate: string;
  age: number | null;
  nationality: string;
  religion: string;
  address: string;
  previous_school: string;
  relationship: string;
  internal_notes: string;
  decision_notes: string;
  cycle_open: boolean;
  cycle_opens_on: string;
  cycle_closes_on: string;
  created_by: string;
};
type AdmissionHistory = {
  id: number;
  from_status: string;
  to_status: string;
  to_status_code: string;
  notes: string;
  changed_by: string;
  changed_at: string;
};
type AdmissionsDetailPayload = {
  application: AdmissionDetail;
  history: AdmissionHistory[];
  allowed_transitions: { value: string; label: string }[];
  can_edit: boolean;
  can_change_status: boolean;
  can_enroll: boolean;
  enrolled_student: { id: number; name: string; student_number: string } | null;
};

const pipeline = [
  ['submitted', 'Submitted'],
  ['review', 'Review'],
  ['shortlisted', 'Shortlisted'],
  ['assessment', 'Assessment'],
  ['interview', 'Interview'],
  ['accepted', 'Accepted'],
  ['enrolled', 'Enrolled'],
] as const;

function readableDate(value: string) {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }).format(parsed);
}

function statusClass(status: string) {
  const value = status.toLowerCase();
  if (value === 'enrolled' || value === 'accepted') return 'border-emerald-100 bg-emerald-50 text-emerald-700';
  if (value === 'rejected' || value === 'withdrawn') return 'border-red-100 bg-red-50 text-red-700';
  if (value === 'waitlisted') return 'border-amber-100 bg-amber-50 text-amber-700';
  if (value === 'review' || value === 'submitted') return 'border-blue-100 bg-blue-50 text-blue-700';
  return 'border-violet-100 bg-violet-50 text-violet-700';
}

function metricIcon(label: string) {
  const lower = label.toLowerCase();
  if (lower.includes('enrolled')) return GraduationCap;
  if (lower.includes('accepted')) return CheckCircle2;
  if (lower.includes('progress')) return ClipboardCheck;
  return Users;
}

function AdmissionsList({ dashboardPath }: { dashboardPath: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  const [data, setData] = useState<AdmissionsListPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState(searchParams.get('q') ?? '');
  const [createOpen, setCreateOpen] = useState(false);
  const [formSchema, setFormSchema] = useState<WorkspaceFormSchema | null>(null);
  const [formLoading, setFormLoading] = useState(false);
  const [formErrors, setFormErrors] = useState<Record<string, string[]>>({});
  const queryString = searchParams.toString();

  useEffect(() => setQuery(searchParams.get('q') ?? ''), [searchParams]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetch(`/api/workspace/admissions/applications${queryString ? `?${queryString}` : ''}`, { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Admissions could not be loaded.');
        return payload as AdmissionsListPayload;
      })
      .then((payload) => setData(payload))
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Admissions could not be loaded.');
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [queryString]);

  function updateFilter(key: string, value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value) params.set(key, value); else params.delete(key);
    params.delete('page');
    router.replace(`${pathname}${params.toString() ? `?${params.toString()}` : ''}`, { scroll: false });
  }

  function submitSearch(event: FormEvent) {
    event.preventDefault();
    updateFilter('q', query.trim());
  }

  async function openCreate() {
    setCreateOpen(true);
    setFormSchema(null);
    setFormErrors({});
    setFormLoading(true);
    try {
      const response = await fetch('/api/workspace/admissions/form', { cache: 'no-store' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'The application form could not be opened.');
      setFormSchema(payload as WorkspaceFormSchema);
    } catch (reason: unknown) {
      toast.error('Could not open application form', reason instanceof Error ? reason.message : 'Please try again.');
      setCreateOpen(false);
    } finally {
      setFormLoading(false);
    }
  }

  async function createApplication(values: Record<string, unknown>) {
    setFormLoading(true);
    setFormErrors({});
    try {
      const response = await fetch('/api/workspace/admissions/applications', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'create', values }),
      });
      const payload = await response.json();
      if (!response.ok) {
        setFormErrors((payload.errors as Record<string, string[]>) ?? { __all__: [payload.detail || 'Application could not be created.'] });
        throw new Error(payload.detail || 'Application could not be created.');
      }
      toast.success('Application created', payload.detail || 'The application is ready for review.');
      setCreateOpen(false);
      router.push(`${dashboardPath}/admissions/${payload.id}`);
    } catch (reason: unknown) {
      toast.error('Application not created', reason instanceof Error ? reason.message : 'Please check the form and try again.');
    } finally {
      setFormLoading(false);
    }
  }

  if (loading && !data) return <div className="tafiti-card grid min-h-[440px] place-items-center"><div className="text-center text-xs font-semibold text-slate-500"><LoaderCircle className="mx-auto mb-3 animate-spin text-blue-600" size={24} />Opening admissions…</div></div>;
  if (error && !data) return <div className="tafiti-card p-6 text-center"><p className="text-sm font-extrabold text-slate-800">Admissions unavailable</p><p className="mt-2 text-xs text-slate-500">{error}</p></div>;
  if (!data) return null;

  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-[9px] font-extrabold uppercase tracking-[.14em] text-blue-600">People · Admissions</p>
          <h1 className="mt-1 text-2xl font-extrabold tracking-[-0.035em] text-[#10224A]">{data.title}</h1>
          <p className="mt-1 max-w-3xl text-[11px] leading-5 text-slate-500">{data.description}</p>
        </div>
        {data.actions.can_create && <button type="button" onClick={() => void openCreate()} className="clay-button-primary"><UserPlus size={14} />New application</button>}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {data.metrics.map((metric) => {
          const Icon = metricIcon(metric.label);
          return <article key={metric.label} className="tafiti-kpi"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-blue-50 text-blue-600"><Icon size={17} /></span><div><p className="text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">{metric.label}</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{metric.value}</p><p className="mt-0.5 text-[9px] text-slate-400">{metric.hint}</p></div></div></article>;
        })}
      </div>

      <section className="tafiti-card overflow-hidden">
        <div className="overflow-x-auto border-b border-slate-100 px-3 py-2">
          <div className="flex min-w-max gap-1">
            {data.statuses.map((item) => {
              const active = data.filters.status === item.value;
              return <button key={item.value} type="button" onClick={() => updateFilter('status', item.value === 'all' ? '' : item.value)} className={`rounded-lg px-3 py-2 text-[9px] font-extrabold transition ${active ? 'bg-blue-600 text-white shadow-[0_5px_12px_rgba(37,99,235,.18)]' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'}`}>{item.label}<span className={`ml-1.5 rounded-full px-1.5 py-0.5 text-[8px] ${active ? 'bg-white/15 text-white' : 'bg-slate-100 text-slate-500'}`}>{item.count}</span></button>;
            })}
          </div>
        </div>

        <div className="grid gap-2 border-b border-slate-100 bg-[#FBFCFE] p-3 md:grid-cols-2 xl:grid-cols-[1.6fr_1fr_1fr_.8fr_.8fr]">
          <form onSubmit={submitSearch} className="relative"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search applicant, number, guardian or phone…" className="h-10 w-full rounded-xl border border-slate-200 bg-white pl-9 pr-3 text-[10px] font-semibold text-slate-700 outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-100" /></form>
          <select value={data.filters.cycle} onChange={(event) => updateFilter('cycle', event.target.value)} className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-[10px] font-bold text-slate-600 outline-none"><option value="">All admission cycles</option>{data.cycles.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select>
          <select value={data.filters.class_id} onChange={(event) => updateFilter('class_id', event.target.value)} className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-[10px] font-bold text-slate-600 outline-none"><option value="">All classes</option>{data.classes.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select>
          <input type="date" value={data.filters.date_from} onChange={(event) => updateFilter('date_from', event.target.value)} className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-[10px] font-bold text-slate-600 outline-none" title="From date" />
          <input type="date" value={data.filters.date_to} onChange={(event) => updateFilter('date_to', event.target.value)} className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-[10px] font-bold text-slate-600 outline-none" title="To date" />
        </div>

        {data.rows.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1040px] border-collapse text-left">
              <thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold uppercase tracking-[.05em] text-slate-400">Application</th><th className="px-4 py-3 text-[9px] font-extrabold uppercase tracking-[.05em] text-slate-400">Learner</th><th className="px-4 py-3 text-[9px] font-extrabold uppercase tracking-[.05em] text-slate-400">Placement</th><th className="px-4 py-3 text-[9px] font-extrabold uppercase tracking-[.05em] text-slate-400">Guardian</th><th className="px-4 py-3 text-[9px] font-extrabold uppercase tracking-[.05em] text-slate-400">Source</th><th className="px-4 py-3 text-[9px] font-extrabold uppercase tracking-[.05em] text-slate-400">Received</th><th className="px-4 py-3 text-[9px] font-extrabold uppercase tracking-[.05em] text-slate-400">Status</th><th className="w-10" /></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {data.rows.map((row) => <tr key={row.id} className="group hover:bg-blue-50/25"><td className="px-4 py-3"><Link href={`${dashboardPath}/admissions/${row.id}`} className="text-[10px] font-extrabold text-blue-700 hover:underline">{row.application_number}</Link><p className="mt-0.5 text-[9px] text-slate-400">{row.cycle}</p></td><td className="px-4 py-3"><p className="text-xs font-extrabold text-slate-800">{row.applicant}</p><p className="mt-0.5 text-[9px] text-slate-400">{row.gender}</p></td><td className="px-4 py-3"><p className="text-[10px] font-bold text-slate-700">{row.class}</p><p className="mt-0.5 text-[9px] text-slate-400">{row.stream}</p></td><td className="px-4 py-3"><p className="text-[10px] font-bold text-slate-700">{row.guardian}</p><p className="mt-0.5 text-[9px] text-slate-400">{row.contact}</p></td><td className="px-4 py-3 text-[10px] font-semibold text-slate-500">{row.source}</td><td className="px-4 py-3 text-[10px] font-semibold text-slate-500">{readableDate(row.created)}</td><td className="px-4 py-3"><span className={`inline-flex rounded-full border px-2 py-1 text-[8px] font-extrabold ${statusClass(row.status_code)}`}>{row.status}</span></td><td className="px-3"><Link href={`${dashboardPath}/admissions/${row.id}`} className="grid h-8 w-8 place-items-center rounded-lg text-slate-300 transition group-hover:bg-white group-hover:text-blue-600"><ChevronRight size={15} /></Link></td></tr>)}
              </tbody>
            </table>
          </div>
        ) : <div className="grid min-h-[260px] place-items-center p-6 text-center"><div><UserPlus className="mx-auto text-blue-300" size={28} /><p className="mt-3 text-sm font-extrabold text-slate-700">No applications match these filters</p><p className="mt-1 text-[10px] text-slate-400">Adjust the pipeline stage, dates or search criteria.</p></div></div>}
      </section>

      <ResourceFormDialog open={createOpen} schema={formSchema} loading={formLoading} errors={formErrors} onClose={() => { setCreateOpen(false); setFormErrors({}); }} onSubmit={createApplication} />
    </section>
  );
}

function DetailField({ label, value }: { label: string; value: string | number | null | undefined }) {
  return <div className="rounded-xl border border-slate-100 bg-[#FBFCFE] px-4 py-3"><p className="text-[8px] font-extrabold uppercase tracking-[.08em] text-slate-400">{label}</p><p className="mt-1.5 text-[11px] font-bold leading-5 text-slate-700">{value === null || value === undefined || value === '' ? '—' : value}</p></div>;
}

function AdmissionDetail({ id, dashboardPath }: { id: number; dashboardPath: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  const [data, setData] = useState<AdmissionsDetailPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);
  const [transition, setTransition] = useState('');
  const [notes, setNotes] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [formSchema, setFormSchema] = useState<WorkspaceFormSchema | null>(null);
  const [formErrors, setFormErrors] = useState<Record<string, string[]>>({});
  const [formLoading, setFormLoading] = useState(false);
  const [confirmEnroll, setConfirmEnroll] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    fetch(`/api/workspace/admissions/application/${id}`, { cache: 'no-store', signal: controller.signal })
      .then(async (response) => { const payload = await response.json(); if (!response.ok) throw new Error(payload.detail || 'Application could not be opened.'); return payload as AdmissionsDetailPayload; })
      .then((payload) => { setData(payload); setTransition(payload.allowed_transitions[0]?.value ?? ''); })
      .catch((reason: unknown) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Application could not be opened.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [id, reloadKey]);

  const activeTab = searchParams.get('tab') || 'applicant';
  const stageIndex = useMemo(() => data ? pipeline.findIndex(([key]) => key === data.application.status_code) : -1, [data]);

  function selectTab(tab: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set('tab', tab);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }

  async function openEdit() {
    setEditOpen(true); setFormSchema(null); setFormErrors({}); setFormLoading(true);
    try {
      const response = await fetch(`/api/workspace/admissions/form/${id}`, { cache: 'no-store' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Application form could not be opened.');
      setFormSchema(payload as WorkspaceFormSchema);
    } catch (reason: unknown) {
      toast.error('Could not open application', reason instanceof Error ? reason.message : 'Please try again.');
      setEditOpen(false);
    } finally { setFormLoading(false); }
  }

  async function saveEdit(values: Record<string, unknown>) {
    setFormLoading(true); setFormErrors({});
    try {
      const response = await fetch(`/api/workspace/admissions/application/${id}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'edit', values }) });
      const payload = await response.json();
      if (!response.ok) {
        setFormErrors((payload.errors as Record<string, string[]>) ?? { __all__: [payload.detail || 'Application could not be updated.'] });
        throw new Error(payload.detail || 'Application could not be updated.');
      }
      setData(payload.workspace as AdmissionsDetailPayload);
      setEditOpen(false);
      toast.success('Application updated', payload.detail || 'Changes were saved.');
    } catch (reason: unknown) { toast.error('Changes not saved', reason instanceof Error ? reason.message : 'Please try again.'); }
    finally { setFormLoading(false); }
  }

  async function changeStatus() {
    if (!transition) return;
    if (transition === 'rejected' && !notes.trim()) {
      toast.error('Decision note required', 'Add a short reason before rejecting an application.');
      return;
    }
    setActionLoading(true);
    try {
      const response = await fetch(`/api/workspace/admissions/application/${id}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'transition', status: transition, notes: notes.trim() }) });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Application status could not be changed.');
      const workspace = payload.workspace as AdmissionsDetailPayload;
      setData(workspace);
      setTransition(workspace.allowed_transitions[0]?.value ?? '');
      setNotes('');
      toast.success('Admissions stage updated', payload.detail || 'The workflow has moved to the next stage.');
    } catch (reason: unknown) { toast.error('Status not changed', reason instanceof Error ? reason.message : 'Please try again.'); }
    finally { setActionLoading(false); }
  }

  async function enroll() {
    setActionLoading(true);
    try {
      const response = await fetch(`/api/workspace/admissions/application/${id}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'enroll' }) });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Enrollment could not be completed.');
      toast.success('Student enrolled', payload.detail || 'The student record has been created.');
      setConfirmEnroll(false);
      if (payload.student?.id) router.push(`${dashboardPath}/students/${payload.student.id}`);
      else setReloadKey((value) => value + 1);
    } catch (reason: unknown) { toast.error('Enrollment not completed', reason instanceof Error ? reason.message : 'Please correct the blocking setup and try again.'); }
    finally { setActionLoading(false); }
  }

  if (loading && !data) return <div className="tafiti-card grid min-h-[440px] place-items-center"><div className="text-center text-xs font-semibold text-slate-500"><LoaderCircle className="mx-auto mb-3 animate-spin text-blue-600" size={24} />Opening application…</div></div>;
  if (error && !data) return <div className="tafiti-card p-6 text-center"><p className="text-sm font-extrabold text-slate-800">Application unavailable</p><p className="mt-2 text-xs text-slate-500">{error}</p></div>;
  if (!data) return null;

  const application = data.application;
  const tabs = [
    ['applicant', 'Applicant'],
    ['guardian', 'Guardian'],
    ['placement', 'Placement'],
    ['decision', 'Decision & notes'],
    ['timeline', 'Timeline'],
  ];

  return (
    <section className="space-y-4">
      <Link href={`${dashboardPath}/admissions`} className="inline-flex items-center gap-1.5 text-[10px] font-bold text-slate-500 hover:text-blue-600"><ArrowLeft size={13} />Back to admissions</Link>

      <section className="tafiti-card overflow-hidden">
        <div className="flex flex-col gap-5 px-5 py-5 lg:flex-row lg:items-start lg:justify-between sm:px-6">
          <div className="min-w-0"><p className="text-[9px] font-extrabold uppercase tracking-[.14em] text-blue-600">Admission application</p><div className="mt-1 flex flex-wrap items-center gap-2"><h1 className="text-2xl font-extrabold tracking-[-0.035em] text-[#10224A]">{application.applicant}</h1><span className={`rounded-full border px-2.5 py-1 text-[9px] font-extrabold ${statusClass(application.status_code)}`}>{application.status}</span></div><p className="mt-1 text-xs font-extrabold text-blue-700">{application.application_number}</p><div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-[10px] text-slate-500"><span><b className="text-slate-400">Class</b> · {application.class}</span><span><b className="text-slate-400">Stream</b> · {application.stream}</span><span><b className="text-slate-400">Cycle</b> · {application.cycle}</span><span><b className="text-slate-400">Source</b> · {application.source}</span></div></div>
          <div className="flex flex-wrap gap-2">{data.can_edit && <button type="button" onClick={() => void openEdit()} className="clay-button-secondary"><Edit3 size={14} />Edit application</button>}{data.enrolled_student && <Link href={`${dashboardPath}/students/${data.enrolled_student.id}`} className="clay-button-primary"><GraduationCap size={14} />Open student profile</Link>}{data.can_enroll && <button type="button" onClick={() => setConfirmEnroll(true)} className="clay-button-primary"><GraduationCap size={14} />Enroll student</button>}<Link href={`${dashboardPath}/communication?recipient=${encodeURIComponent(application.guardian)}&student=${id}`} className="clay-button-secondary"><MessageCircle size={14} />Contact guardian</Link></div>
        </div>

        <div className="border-t border-slate-100 bg-[#FBFCFE] px-4 py-4">
          <div className="flex min-w-[700px] items-center overflow-x-auto pb-1">
            {pipeline.map(([key, label], index) => {
              const done = stageIndex >= 0 && index <= stageIndex;
              const current = application.status_code === key;
              return <div key={key} className="flex flex-1 items-center last:flex-none"><div className="flex min-w-[86px] flex-col items-center"><span className={`grid h-7 w-7 place-items-center rounded-full border text-[9px] font-extrabold ${done ? 'border-blue-600 bg-blue-600 text-white' : 'border-slate-200 bg-white text-slate-400'} ${current ? 'ring-4 ring-blue-100' : ''}`}>{done ? <CheckCircle2 size={13} /> : index + 1}</span><span className={`mt-1.5 text-[8px] font-extrabold ${current ? 'text-blue-700' : done ? 'text-slate-600' : 'text-slate-400'}`}>{label}</span></div>{index < pipeline.length - 1 && <span className={`mx-1 h-0.5 min-w-6 flex-1 ${done && index < stageIndex ? 'bg-blue-500' : 'bg-slate-200'}`} />}</div>;
            })}
          </div>
          {['rejected', 'withdrawn', 'waitlisted'].includes(application.status_code) && <div className={`mt-3 rounded-xl border px-3 py-2 text-[10px] font-bold ${statusClass(application.status_code)}`}>Current exception stage: {application.status}. Review the decision notes and timeline below.</div>}
        </div>

        <div className="border-t border-slate-100 px-3 pt-2"><div className="flex min-w-max gap-1 overflow-x-auto">{tabs.map(([key, label]) => <button key={key} type="button" onClick={() => selectTab(key)} className={`relative h-10 px-3.5 text-[10px] font-extrabold ${activeTab === key ? 'text-blue-700' : 'text-slate-500 hover:text-slate-800'}`}>{label}{activeTab === key && <span className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-blue-600" />}</button>)}</div></div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
        <section className="tafiti-card p-4 sm:p-5">
          {activeTab === 'applicant' && <div><h2 className="text-sm font-extrabold text-[#10224A]">Applicant profile</h2><p className="mt-1 text-[10px] text-slate-500">Identity and background information supplied for this application.</p><div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3"><DetailField label="Full name" value={application.applicant} /><DetailField label="Gender" value={application.gender} /><DetailField label="Date of birth" value={`${readableDate(application.birthdate)}${application.age !== null ? ` · ${application.age} yrs` : ''}`} /><DetailField label="Nationality" value={application.nationality} /><DetailField label="Religion" value={application.religion} /><DetailField label="Address" value={application.address} /><DetailField label="Previous school" value={application.previous_school || 'Not provided'} /><DetailField label="Received" value={readableDate(application.created)} /><DetailField label="Created by" value={application.created_by} /></div></div>}
          {activeTab === 'guardian' && <div><h2 className="text-sm font-extrabold text-[#10224A]">Guardian details</h2><p className="mt-1 text-[10px] text-slate-500">The primary contact attached to the application.</p><div className="mt-4 grid gap-3 sm:grid-cols-2"><DetailField label="Guardian" value={application.guardian} /><DetailField label="Relationship" value={application.relationship} /><DetailField label="Contact" value={application.contact} /><DetailField label="Applicant address" value={application.address} /></div></div>}
          {activeTab === 'placement' && <div><h2 className="text-sm font-extrabold text-[#10224A]">Placement & enrollment readiness</h2><p className="mt-1 text-[10px] text-slate-500">The requested class and stream are used by Django when the accepted learner is enrolled.</p><div className="mt-4 grid gap-3 sm:grid-cols-2"><DetailField label="Admission cycle" value={application.cycle} /><DetailField label="Cycle status" value={application.cycle_open ? 'Open and active' : 'Closed or inactive'} /><DetailField label="Applying class" value={application.class} /><DetailField label="Preferred stream" value={application.stream} /><DetailField label="Cycle opens" value={readableDate(application.cycle_opens_on)} /><DetailField label="Cycle closes" value={readableDate(application.cycle_closes_on)} /></div>{data.enrolled_student && <div className="mt-4 rounded-xl border border-emerald-100 bg-emerald-50 px-4 py-3"><p className="text-[10px] font-extrabold text-emerald-800">Enrollment completed</p><p className="mt-1 text-[10px] text-emerald-700">{data.enrolled_student.name} · {data.enrolled_student.student_number}</p></div>}</div>}
          {activeTab === 'decision' && <div><h2 className="text-sm font-extrabold text-[#10224A]">Decision & internal notes</h2><p className="mt-1 text-[10px] text-slate-500">Decision notes follow the application through each controlled status change.</p><div className="mt-4 grid gap-3"><DetailField label="Latest decision note" value={application.decision_notes || 'No decision note recorded.'} /><DetailField label="Internal admissions note" value={application.internal_notes || 'No internal note recorded.'} /></div></div>}
          {activeTab === 'timeline' && <div><h2 className="text-sm font-extrabold text-[#10224A]">Application timeline</h2><p className="mt-1 text-[10px] text-slate-500">Every workflow status change is preserved for accountability.</p><div className="mt-5 space-y-0">{data.history.length ? data.history.map((item, index) => <div key={item.id} className="relative flex gap-3 pb-5 last:pb-0"><div className="relative z-10 grid h-8 w-8 shrink-0 place-items-center rounded-full border border-blue-100 bg-blue-50 text-blue-600"><ClipboardCheck size={14} /></div>{index < data.history.length - 1 && <span className="absolute left-[15px] top-8 h-[calc(100%-24px)] w-px bg-slate-200" />}<div className="min-w-0 pt-0.5"><div className="flex flex-wrap items-center gap-2"><p className="text-[11px] font-extrabold text-slate-800">{item.from_status} → {item.to_status}</p><span className="text-[8px] font-bold text-slate-400">{readableDate(item.changed_at)}</span></div><p className="mt-1 text-[9px] font-semibold text-slate-400">By {item.changed_by}</p>{item.notes && <p className="mt-2 rounded-lg bg-slate-50 px-3 py-2 text-[10px] leading-5 text-slate-600">{item.notes}</p>}</div></div>) : <p className="text-xs text-slate-400">No status history has been recorded.</p>}</div></div>}
        </section>

        <aside className="space-y-4">
          <section className="tafiti-card p-4">
            <div className="flex items-center gap-2"><ShieldCheck size={16} className="text-blue-600" /><div><h3 className="text-xs font-extrabold text-[#10224A]">Next workflow action</h3><p className="mt-0.5 text-[9px] text-slate-400">Only valid next stages are available.</p></div></div>
            {data.can_change_status && data.allowed_transitions.length ? <div className="mt-4 space-y-3"><label className="block"><span className="mb-1.5 block text-[9px] font-extrabold text-slate-500">Move application to</span><select value={transition} onChange={(event) => setTransition(event.target.value)} className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-[10px] font-bold text-slate-700 outline-none focus:border-blue-400">{data.allowed_transitions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label><label className="block"><span className="mb-1.5 block text-[9px] font-extrabold text-slate-500">Decision / workflow note</span><textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={4} placeholder="Add a concise note for the audit timeline…" className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-[10px] leading-5 text-slate-700 outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-100" /></label><button type="button" disabled={actionLoading || !transition} onClick={() => void changeStatus()} className="clay-button-primary w-full justify-center">{actionLoading ? <LoaderCircle size={14} className="animate-spin" /> : <ClipboardCheck size={14} />}Update stage</button></div> : <div className="mt-4 rounded-xl border border-slate-100 bg-slate-50 px-3 py-3 text-[10px] leading-5 text-slate-500">No manual status transition is available from <b>{application.status}</b>.{data.can_enroll ? ' Complete enrollment below.' : ''}</div>}
          </section>

          {data.can_enroll && <section className="tafiti-card border-emerald-100 p-4"><div className="flex items-start gap-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-emerald-50 text-emerald-600"><GraduationCap size={17} /></span><div><h3 className="text-xs font-extrabold text-emerald-900">Ready to enroll</h3><p className="mt-1 text-[9px] leading-4 text-emerald-700">This creates the student master record, class register entry and initial fee bill using the existing Django enrollment service.</p></div></div><button type="button" onClick={() => setConfirmEnroll(true)} className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-[10px] font-extrabold text-white shadow-[0_8px_18px_rgba(5,150,105,.18)] hover:bg-emerald-700"><GraduationCap size={14} />Complete enrollment</button></section>}
        </aside>
      </div>

      <ResourceFormDialog open={editOpen} schema={formSchema} loading={formLoading} errors={formErrors} onClose={() => { setEditOpen(false); setFormErrors({}); }} onSubmit={saveEdit} />

      {confirmEnroll && <div className="fixed inset-0 z-[95] grid place-items-center bg-[#07172B]/45 p-4 backdrop-blur-[3px]"><button type="button" aria-label="Close confirmation" className="absolute inset-0" onClick={() => !actionLoading && setConfirmEnroll(false)} /><div className="clay-dialog relative z-10 w-full max-w-md p-6"><span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-emerald-50 text-emerald-600"><GraduationCap size={22} /></span><h2 className="mt-4 text-center text-lg font-extrabold text-[#10224A]">Enroll {application.applicant}?</h2><p className="mt-2 text-center text-[11px] leading-5 text-slate-500">Enrollment will create the permanent student record, register the learner in {application.class} · {application.stream}, and generate the initial student bill. This is a controlled workflow action.</p><div className="mt-5 flex gap-2"><button type="button" disabled={actionLoading} onClick={() => setConfirmEnroll(false)} className="clay-button-secondary flex-1 justify-center">Cancel</button><button type="button" disabled={actionLoading} onClick={() => void enroll()} className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-[10px] font-extrabold text-white hover:bg-emerald-700">{actionLoading ? <LoaderCircle size={14} className="animate-spin" /> : <GraduationCap size={14} />}Enroll student</button></div></div></div>}
    </section>
  );
}

export function ReferenceAdmissionsWorkspace({ id, dashboardPath }: { id?: number | null; dashboardPath: string }) {
  return id ? <AdmissionDetail id={id} dashboardPath={dashboardPath} /> : <AdmissionsList dashboardPath={dashboardPath} />;
}
