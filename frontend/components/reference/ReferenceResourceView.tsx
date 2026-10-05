'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import {
  AlertCircle,
  BookOpen,
  CalendarCheck,
  CalendarDays,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleDollarSign,
  Clock3,
  Download,
  FileText,
  Filter,
  History,
  Landmark,
  Library,
  LoaderCircle,
  Pencil,
  Plus,
  RefreshCw,
  Settings2,
  ShieldCheck,
  UserPlus,
  Users,
  WalletCards,
} from 'lucide-react';

import type { WorkspaceFormSchema, WorkspaceResource, WorkspaceStat } from '@/lib/workspace';
import { useToast } from '@/components/ui/ToastProvider';
import { ConfirmActionDialog } from '@/components/workspace/ConfirmActionDialog';
import { DataTable } from '@/components/workspace/DataTable';
import { ResourceFormDialog } from '@/components/workspace/ResourceFormDialog';

const contextResources = new Set(['students', 'staff', 'admissions', 'classes', 'subjects', 'fees', 'attendance']);

const toneStyles: Record<WorkspaceStat['tone'], string> = {
  green: 'bg-emerald-50 text-emerald-700 border-emerald-100',
  blue: 'bg-blue-50 text-blue-700 border-blue-100',
  gold: 'bg-amber-50 text-amber-700 border-amber-100',
  violet: 'bg-violet-50 text-violet-700 border-violet-100',
};

function rowTitle(row: Record<string, unknown> | null) {
  if (!row) return 'this record';
  for (const key of ['name', 'student', 'title', 'class', 'application', 'school', 'book', 'reference']) {
    if (row[key]) return String(row[key]);
  }
  return typeof row.id === 'number' ? `record #${row.id}` : 'this record';
}

function csvEscape(value: unknown) {
  const text = value === null || value === undefined ? '' : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

function metricIcon(label: string) {
  const value = label.toLowerCase();
  if (value.includes('bill') || value.includes('collect') || value.includes('outstanding')) return CircleDollarSign;
  if (value.includes('paid') || value.includes('reconcil')) return CheckCircle2;
  if (value.includes('student') || value.includes('application')) return Users;
  if (value.includes('attendance')) return CalendarCheck;
  return ShieldCheck;
}

function HeaderIcon({ resource }: { resource: string }) {
  if (resource === 'admissions') return <UserPlus size={21} />;
  if (resource === 'attendance') return <CalendarCheck size={21} />;
  if (resource === 'results') return <FileText size={21} />;
  if (resource === 'timetable') return <CalendarDays size={21} />;
  if (resource === 'fees' || resource === 'fees-payments') return <WalletCards size={21} />;
  if (resource === 'library') return <Library size={21} />;
  if (resource === 'audit') return <History size={21} />;
  if (resource === 'settings') return <Settings2 size={21} />;
  if (resource.startsWith('finance')) return <Landmark size={21} />;
  if (resource === 'subjects') return <BookOpen size={21} />;
  return <Users size={21} />;
}

function Metrics({ metrics }: { metrics: WorkspaceStat[] }) {
  if (!metrics.length) return null;
  return (
    <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric) => {
        const Icon = metricIcon(metric.label);
        return (
          <article key={metric.label} className="tafiti-kpi">
            <div className="relative z-10 flex items-start gap-3">
              <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl border ${toneStyles[metric.tone]}`}><Icon size={18} /></span>
              <div className="min-w-0"><p className="text-[10px] font-bold uppercase tracking-[.06em] text-slate-400">{metric.label}</p><p className="mt-1 truncate text-xl font-extrabold text-[#10224A]">{metric.value}</p><p className="mt-1 truncate text-[9px] font-semibold text-slate-400">{metric.hint}</p></div>
            </div>
          </article>
        );
      })}
    </div>
  );
}

function Pipeline({ rows }: { rows: Record<string, unknown>[] }) {
  const stages = ['All', 'New', 'Under Review', 'Interviewed', 'Approved', 'Enrolled', 'Rejected'];
  const count = (stage: string) => {
    if (stage === 'All') return rows.length;
    const normalized = stage.toLowerCase();
    return rows.filter((row) => String(row.status ?? '').toLowerCase().includes(normalized.replace('under review', 'review'))).length;
  };
  return (
    <div className="mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
      {stages.map((stage, index) => (
        <div key={stage} className="tafiti-soft-card flex items-center gap-3 px-3 py-3">
          <span className={`grid h-9 w-9 place-items-center rounded-xl ${index === 0 ? 'bg-blue-50 text-blue-600' : index === 1 ? 'bg-amber-50 text-amber-600' : index === 4 || index === 5 ? 'bg-emerald-50 text-emerald-600' : index === 6 ? 'bg-red-50 text-red-600' : 'bg-violet-50 text-violet-600'}`}><UserPlus size={16} /></span>
          <div><p className="text-lg font-extrabold leading-none text-[#10224A]">{count(stage)}</p><p className="mt-1 text-[9px] font-semibold text-slate-500">{stage}</p></div>
        </div>
      ))}
    </div>
  );
}

function AttendanceSummary({ rows }: { rows: Record<string, unknown>[] }) {
  const present = rows.reduce((sum, row) => sum + Number(row.present ?? 0), 0);
  const absent = rows.reduce((sum, row) => sum + Number(row.absent ?? 0), 0);
  const late = rows.reduce((sum, row) => sum + Number(row.late ?? 0), 0);
  const open = rows.filter((row) => String(row.status ?? '').toLowerCase() === 'open').length;
  const values = [
    ['Present', present, 'bg-emerald-50 text-emerald-600'],
    ['Absent', absent, 'bg-red-50 text-red-600'],
    ['Late', late, 'bg-amber-50 text-amber-600'],
    ['Open sessions', open, 'bg-blue-50 text-blue-600'],
  ] as const;
  return <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{values.map(([label, value, cls]) => <div key={label} className="tafiti-kpi"><div className="flex items-center gap-3"><span className={`grid h-10 w-10 place-items-center rounded-xl ${cls}`}><CalendarCheck size={18} /></span><div><p className="text-xl font-extrabold text-[#10224A]">{value}</p><p className="mt-0.5 text-[10px] font-semibold text-slate-500">{label}</p></div></div></div>)}</div>;
}

function TimetableGrid({ rows }: { rows: Record<string, unknown>[] }) {
  const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
  const times = Array.from(new Set(rows.map((row) => String(row.time ?? '')).filter(Boolean))).slice(0, 8);
  const palette = ['bg-blue-50 border-blue-100 text-blue-800', 'bg-emerald-50 border-emerald-100 text-emerald-800', 'bg-violet-50 border-violet-100 text-violet-800', 'bg-amber-50 border-amber-100 text-amber-800', 'bg-rose-50 border-rose-100 text-rose-800'];
  return (
    <section className="tafiti-card mb-4 overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-3.5 sm:px-5"><div><h2 className="text-sm font-extrabold text-[#10224A]">Timetable builder workspace</h2><p className="mt-1 text-[10px] text-slate-500">The grid below uses the existing timetable and allocation rules.</p></div><div className="flex items-center gap-2"><span className="rounded-lg bg-blue-50 px-2.5 py-1.5 text-[10px] font-bold text-blue-700">Week</span><span className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[10px] font-bold text-slate-500">List</span></div></div>
      <div className="overflow-x-auto">
        <div className="min-w-[920px] p-4">
          <div className="grid grid-cols-[95px_repeat(5,minmax(150px,1fr))] gap-2">
            <div />{days.map((day) => <div key={day} className="rounded-xl bg-[#F5F8FC] px-3 py-2 text-center text-[10px] font-extrabold text-slate-600">{day}</div>)}
            {times.map((time) => (
              <div key={time} className="contents">
                <div className="flex items-center justify-center rounded-xl border border-slate-100 bg-white px-2 text-center text-[10px] font-bold text-slate-500">{time}</div>
                {days.map((day, dayIndex) => {
                  const lesson = rows.find((row) => String(row.day ?? '') === day && String(row.time ?? '') === time);
                  return <div key={`${time}-${day}`} className={`min-h-[78px] rounded-xl border p-2.5 ${lesson ? palette[dayIndex % palette.length] : 'border-dashed border-slate-100 bg-[#FBFCFE]'}`}>{lesson ? <><p className="text-[11px] font-extrabold">{String(lesson.subject ?? '')}</p><p className="mt-1 text-[9px] opacity-75">{String(lesson.class ?? '')}</p><p className="mt-2 text-[9px] opacity-70">{String(lesson.teacher ?? '')} · {String(lesson.room ?? '')}</p></> : <span className="text-[9px] text-slate-300">—</span>}</div>;
                })}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function ResultsTabs({ verification }: { verification: boolean }) {
  return (
    <div className="mb-4 flex flex-wrap gap-1 rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
      <Link href="?" className={`rounded-lg px-3 py-2 text-[11px] font-bold ${!verification ? 'bg-blue-600 text-white' : 'text-slate-500 hover:bg-slate-50'}`}>Results overview</Link>
      <Link href="?view=verification" className={`rounded-lg px-3 py-2 text-[11px] font-bold ${verification ? 'bg-blue-600 text-white' : 'text-slate-500 hover:bg-slate-50'}`}>Verification queue</Link>
      <span className="rounded-lg px-3 py-2 text-[11px] font-bold text-slate-400">Marks entry uses existing results workflow</span>
    </div>
  );
}

function LibrarySummary({ rows }: { rows: Record<string, unknown>[] }) {
  const active = rows.filter((row) => String(row.status ?? '') === 'On loan').length;
  const overdue = rows.filter((row) => String(row.status ?? '') === 'Overdue').length;
  const returned = rows.filter((row) => String(row.status ?? '') === 'Returned').length;
  return <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><div className="tafiti-kpi"><p className="text-[10px] font-bold text-slate-400">LOAN RECORDS</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{rows.length}</p></div><div className="tafiti-kpi"><p className="text-[10px] font-bold text-slate-400">ON LOAN</p><p className="mt-1 text-xl font-extrabold text-blue-700">{active}</p></div><div className="tafiti-kpi"><p className="text-[10px] font-bold text-slate-400">OVERDUE</p><p className="mt-1 text-xl font-extrabold text-red-600">{overdue}</p></div><div className="tafiti-kpi"><p className="text-[10px] font-bold text-slate-400">RETURNED</p><p className="mt-1 text-xl font-extrabold text-emerald-600">{returned}</p></div></div>;
}

function AuditSummary({ rows }: { rows: Record<string, unknown>[] }) {
  const created = rows.filter((row) => String(row.action ?? '').toLowerCase().includes('create')).length;
  const updated = rows.filter((row) => String(row.action ?? '').toLowerCase().includes('update')).length;
  const deleted = rows.filter((row) => String(row.action ?? '').toLowerCase().includes('delete')).length;
  return <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><div className="tafiti-kpi"><p className="text-[10px] font-bold text-slate-400">ACTIVITIES</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{rows.length}</p></div><div className="tafiti-kpi"><p className="text-[10px] font-bold text-slate-400">CREATED</p><p className="mt-1 text-xl font-extrabold text-emerald-600">{created}</p></div><div className="tafiti-kpi"><p className="text-[10px] font-bold text-slate-400">UPDATED</p><p className="mt-1 text-xl font-extrabold text-blue-600">{updated}</p></div><div className="tafiti-kpi"><p className="text-[10px] font-bold text-slate-400">DELETED</p><p className="mt-1 text-xl font-extrabold text-red-600">{deleted}</p></div></div>;
}

function SettingsOverview({ row, onEdit }: { row: Record<string, unknown> | undefined; onEdit: () => void }) {
  if (!row) return null;
  const fields = [
    ['School name', row.school], ['Motto', row.motto], ['Email address', row.email], ['Phone number', row.mobile], ['City', row.city], ['Country', row.country], ['Education levels', row.levels],
  ];
  return (
    <section className="tafiti-card mb-4 overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-4 sm:px-5"><div><h2 className="text-sm font-extrabold text-[#10224A]">School profile</h2><p className="mt-1 text-[10px] text-slate-500">Core school identity and configuration from Django settings.</p></div><button type="button" onClick={onEdit} className="clay-button-primary"><Pencil size={14} /> Edit school settings</button></div>
      <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3 sm:p-5">{fields.map(([label, value]) => <div key={String(label)} className="rounded-xl border border-slate-100 bg-[#F8FAFD] p-3.5"><p className="text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">{label}</p><p className="mt-1.5 text-xs font-bold text-slate-800">{String(value ?? '—')}</p></div>)}</div>
    </section>
  );
}

export function ReferenceResourceView({ resource }: { resource: string }) {
  const toast = useToast();
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlQuery = searchParams.get('q') ?? '';
  const parsedPage = Number(searchParams.get('page') ?? '1');
  const page = Number.isInteger(parsedPage) && parsedPage > 0 ? parsedPage : 1;
  const [data, setData] = useState<WorkspaceResource | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [queryInput, setQueryInput] = useState(urlQuery);
  const [reloadKey, setReloadKey] = useState(0);
  const [formOpen, setFormOpen] = useState(false);
  const [formSchema, setFormSchema] = useState<WorkspaceFormSchema | null>(null);
  const [formLoading, setFormLoading] = useState(false);
  const [formErrors, setFormErrors] = useState<Record<string, string[]>>({});
  const [editingRow, setEditingRow] = useState<Record<string, unknown> | null>(null);
  const [deleteRow, setDeleteRow] = useState<Record<string, unknown> | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  useEffect(() => setQueryInput(urlQuery), [resource, urlQuery]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      const next = queryInput.trim();
      if (next === urlQuery) return;
      const params = new URLSearchParams(searchParams.toString());
      if (next) params.set('q', next); else params.delete('q');
      params.delete('page');
      router.replace(`${pathname}${params.toString() ? `?${params.toString()}` : ''}`, { scroll: false });
    }, 260);
    return () => window.clearTimeout(handle);
  }, [pathname, queryInput, router, searchParams, urlQuery]);

  const requestQuery = useMemo(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.set('page', String(page));
    params.set('page_size', ['admissions', 'timetable', 'library', 'audit'].includes(resource) ? '100' : '25');
    params.delete('return');
    params.delete('tab');
    return params.toString();
  }, [page, resource, searchParams]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetch(`/api/workspace/resources/${resource}?${requestQuery}`, { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || 'This module could not be loaded.');
        return result as WorkspaceResource;
      })
      .then(setData)
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setError(reason instanceof Error ? reason.message : 'This module could not be loaded.');
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [reloadKey, requestQuery, resource]);

  const pageLabel = useMemo(() => {
    if (!data?.pagination.total) return '0 records';
    const start = (data.pagination.page - 1) * data.pagination.page_size + 1;
    const end = Math.min(start + data.rows.length - 1, data.pagination.total);
    return `${start}–${end} of ${data.pagination.total}`;
  }, [data]);

  function exportCsv() {
    if (!data?.rows.length) return toast.info('Nothing to export', 'There are no rows on this page.');
    const header = data.columns.map((column) => csvEscape(column.label)).join(',');
    const lines = data.rows.map((row) => data.columns.map((column) => csvEscape(row[column.key])).join(','));
    const blob = new Blob([[header, ...lines].join('\n')], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url; anchor.download = `${resource}-${new Date().toISOString().slice(0, 10)}.csv`; anchor.click(); URL.revokeObjectURL(url);
  }

  function setCurrentPage(nextPage: number) {
    const params = new URLSearchParams(searchParams.toString());
    if (nextPage > 1) params.set('page', String(nextPage)); else params.delete('page');
    router.replace(`${pathname}${params.toString() ? `?${params.toString()}` : ''}`, { scroll: false });
  }

  function openRow(row: Record<string, unknown>) {
    if (typeof row.id !== 'number') return;
    const verification = resource === 'results' && data?.view === 'verification';
    if (!contextResources.has(resource) && !verification) return;
    const params = new URLSearchParams();
    if (verification) params.set('view', 'verification');
    params.set('return', `${pathname}${searchParams.toString() ? `?${searchParams.toString()}` : ''}`);
    router.push(`${pathname}/${row.id}?${params.toString()}`);
  }

  async function openForm(row?: Record<string, unknown>) {
    const id = row?.id;
    if (row && typeof id !== 'number') return;
    setEditingRow(row ?? null); setFormOpen(true); setFormSchema(null); setFormErrors({}); setFormLoading(true);
    try {
      const response = await fetch(row ? `/api/workspace/resources/${resource}/${id}/form` : `/api/workspace/resources/${resource}/form`, { cache: 'no-store' });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'The form could not be opened.');
      setFormSchema(result as WorkspaceFormSchema);
    } catch (reason: unknown) {
      toast.error('Could not open form', reason instanceof Error ? reason.message : 'The form could not be opened.');
      setFormOpen(false);
    } finally { setFormLoading(false); }
  }

  async function submitForm(values: Record<string, unknown>) {
    if (!formSchema) return;
    const id = editingRow?.id;
    const editing = formSchema.mode === 'edit' && typeof id === 'number';
    const path = editing ? `/api/workspace/resources/${resource}/${id}/form` : `/api/workspace/resources/${resource}/form`;
    setFormLoading(true); setFormErrors({});
    try {
      const hasFile = Object.values(values).some((value) => value instanceof File);
      let body: BodyInit; let headers: HeadersInit | undefined;
      if (hasFile) {
        const formData = new FormData();
        Object.entries(values).forEach(([key, value]) => {
          if (value instanceof File) formData.append(key, value);
          else if (Array.isArray(value)) value.forEach((item) => formData.append(key, String(item)));
          else if (typeof value === 'boolean') formData.append(key, value ? 'true' : 'false');
          else if (value !== null && value !== undefined) formData.append(key, String(value));
        });
        body = formData;
      } else { headers = { 'Content-Type': 'application/json' }; body = JSON.stringify(values); }
      const response = await fetch(path, { method: editing ? 'PATCH' : 'POST', headers, body });
      const result = await response.json();
      if (!response.ok) { setFormErrors((result.errors as Record<string, string[]>) ?? {}); throw new Error(result.detail || 'The record could not be saved.'); }
      toast.success(editing ? 'Changes saved' : 'Record created', result.detail || 'Saved successfully.');
      setFormOpen(false); setEditingRow(null); setReloadKey((value) => value + 1);
      if (typeof result.id === 'number' && contextResources.has(resource)) {
        const params = new URLSearchParams({ return: `${pathname}${searchParams.toString() ? `?${searchParams.toString()}` : ''}` });
        router.push(`${pathname}/${result.id}?${params.toString()}`);
      }
    } catch (reason: unknown) { toast.error('Could not save record', reason instanceof Error ? reason.message : 'The record could not be saved.'); }
    finally { setFormLoading(false); }
  }

  async function confirmDelete() {
    if (!deleteRow || typeof deleteRow.id !== 'number') return;
    setDeleteLoading(true);
    try {
      const response = await fetch(`/api/workspace/resources/${resource}/${deleteRow.id}/form`, { method: 'DELETE' });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'The action could not be completed.');
      toast.success('Record updated', result.detail || 'The action was completed.'); setDeleteRow(null); setReloadKey((value) => value + 1);
    } catch (reason: unknown) { toast.error('Action failed', reason instanceof Error ? reason.message : 'The action could not be completed.'); }
    finally { setDeleteLoading(false); }
  }

  if (loading && !data) return <div className="tafiti-card grid min-h-[420px] place-items-center"><div className="text-center text-xs font-semibold text-slate-500"><LoaderCircle className="mx-auto mb-3 animate-spin text-blue-600" size={24} />Loading school data…</div></div>;
  if (error && !data) return <div className="tafiti-card grid min-h-[420px] place-items-center p-6 text-center"><div><AlertCircle className="mx-auto text-red-500" size={25} /><h2 className="mt-3 text-sm font-bold text-slate-900">We couldn&apos;t load this module</h2><p className="mt-2 text-xs text-slate-500">{error}</p><button type="button" onClick={() => setReloadKey((value) => value + 1)} className="clay-button-primary mt-4"><RefreshCw size={14} /> Try again</button></div></div>;
  if (!data) return null;

  const verification = resource === 'results' && data.view === 'verification';
  const selectedDeleteLabel = ((data.actions.delete_mode === 'toggle-active' && deleteRow?.status === 'Inactive') || (data.actions.delete_mode === 'toggle-status' && deleteRow?.status === 'Retired')) ? 'Reactivate' : data.actions.delete_label;
  const deleteMessage = data.actions.delete_mode === 'toggle-active' ? `${selectedDeleteLabel} ${rowTitle(deleteRow)}? Student history will be preserved.` : data.actions.delete_mode === 'toggle-status' ? `${selectedDeleteLabel} ${rowTitle(deleteRow)}? Staff history will be preserved.` : `Delete ${rowTitle(deleteRow)}? This is blocked when dependent school records exist.`;

  return (
    <section>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex items-start gap-3">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-blue-50 text-blue-600"><HeaderIcon resource={resource} /></span>
          <div><h1 className="text-[1.65rem] font-extrabold tracking-[-0.035em] text-[#10224A]">{data.title}</h1><p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">{data.description}</p></div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={() => setReloadKey((value) => value + 1)} className="clay-button-secondary"><RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh</button>
          <button type="button" onClick={exportCsv} className="clay-button-secondary"><Download size={14} /> Export</button>
          {resource === 'fees' && <Link href={pathname.replace(/\/fees$/, '/fees-payments')} className="clay-button-primary"><Plus size={14} /> Record payment</Link>}
          {data.actions.create && <button type="button" onClick={() => void openForm()} className="clay-button-primary"><Plus size={14} /> {data.actions.create_label}</button>}
        </div>
      </div>

      <Metrics metrics={data.metrics ?? []} />
      {resource === 'admissions' && <Pipeline rows={data.rows} />}
      {resource === 'attendance' && <AttendanceSummary rows={data.rows} />}
      {resource === 'timetable' && <TimetableGrid rows={data.rows} />}
      {resource === 'results' && <ResultsTabs verification={verification} />}
      {resource === 'library' && <LibrarySummary rows={data.rows} />}
      {resource === 'audit' && <AuditSummary rows={data.rows} />}
      {resource === 'settings' && <SettingsOverview row={data.rows[0]} onEdit={() => data.rows[0] && void openForm(data.rows[0])} />}

      {data.filters?.length ? <div className="mb-3 flex flex-wrap items-center gap-1.5 rounded-xl border border-slate-200 bg-white p-1.5">{data.filters.map((filter) => { const params = new URLSearchParams(searchParams.toString()); params.set('status', filter.value); params.delete('page'); return <Link key={filter.value} href={`${pathname}?${params.toString()}`} className={`rounded-lg px-3 py-2 text-[10px] font-bold ${data.active_filter === filter.value ? 'bg-blue-600 text-white' : 'text-slate-500 hover:bg-slate-50'}`}>{filter.label} <span className="ml-1 opacity-70">{filter.count}</span></Link>; })}</div> : null}

      {resource !== 'settings' && (
        <>
          <DataTable columns={data.columns} rows={data.rows} query={queryInput} actions={data.actions} onQueryChange={setQueryInput} onExport={exportCsv} onView={openRow} onEdit={(row) => void openForm(row)} onDelete={setDeleteRow} />
          <div className="clay-pagination mt-3 flex flex-col gap-3 px-4 py-3 text-[11px] text-slate-500 sm:flex-row sm:items-center sm:justify-between"><span>{pageLabel}</span><div className="flex items-center gap-2"><button type="button" disabled={data.pagination.page <= 1 || loading} onClick={() => setCurrentPage(Math.max(1, data.pagination.page - 1))} className="clay-page-button"><ChevronLeft size={13} /> Previous</button><span className="min-w-[68px] text-center font-bold text-slate-600">{data.pagination.page} / {data.pagination.pages}</span><button type="button" disabled={data.pagination.page >= data.pagination.pages || loading} onClick={() => setCurrentPage(data.pagination.page + 1)} className="clay-page-button">Next <ChevronRight size={13} /></button></div></div>
        </>
      )}

      <ResourceFormDialog open={formOpen} schema={formSchema} loading={formLoading} errors={formErrors} onClose={() => { setFormOpen(false); setEditingRow(null); setFormErrors({}); }} onSubmit={submitForm} />
      <ConfirmActionDialog open={Boolean(deleteRow)} title={`${selectedDeleteLabel} record`} message={deleteMessage} confirmLabel={selectedDeleteLabel} loading={deleteLoading} onCancel={() => setDeleteRow(null)} onConfirm={() => void confirmDelete()} />
    </section>
  );
}
