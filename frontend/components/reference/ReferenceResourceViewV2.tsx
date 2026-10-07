'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import {
  AlertCircle,
  CalendarCheck,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Download,
  FileText,
  History,
  Landmark,
  Library,
  LoaderCircle,
  Pencil,
  Plus,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Upload,
  UserPlus,
  Users,
  WalletCards,
} from 'lucide-react';

import type { WorkspaceFormSchema, WorkspaceResource, WorkspaceStat } from '@/lib/workspace';
import { useToast } from '@/components/ui/ToastProvider';
import { ConfirmActionDialog } from '@/components/workspace/ConfirmActionDialog';
import { DataTable } from '@/components/workspace/DataTable';
import { ResourceFormDialog } from '@/components/workspace/ResourceFormDialog';
import { StudentBulkImportDialog } from '@/components/workspace/StudentBulkImportDialog';

const contextual = new Set(['students', 'staff', 'admissions', 'classes', 'subjects', 'fees', 'attendance']);

function resourceIcon(resource: string) {
  if (resource === 'admissions') return UserPlus;
  if (resource === 'attendance') return CalendarCheck;
  if (resource === 'timetable') return CalendarDays;
  if (resource === 'library') return Library;
  if (resource === 'audit') return History;
  if (resource === 'settings') return Settings2;
  if (resource.startsWith('fees')) return WalletCards;
  if (resource.startsWith('finance')) return Landmark;
  if (resource === 'results') return FileText;
  return Users;
}

function rowTitle(row: Record<string, unknown> | null) {
  if (!row) return 'this record';
  for (const key of ['name', 'student', 'title', 'class', 'application', 'school', 'book', 'reference']) {
    if (row[key]) return String(row[key]);
  }
  return typeof row.id === 'number' ? `record #${row.id}` : 'this record';
}

function csvValue(value: unknown) {
  const text = value == null ? '' : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

function Metrics({ metrics }: { metrics: WorkspaceStat[] }) {
  if (!metrics.length) return null;
  return <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{metrics.map((metric) => <article key={metric.label} className="tafiti-kpi"><p className="text-[9px] font-extrabold uppercase tracking-[.06em] text-slate-400">{metric.label}</p><p className="mt-1.5 truncate text-xl font-extrabold text-[#10224A]">{String(metric.value)}</p><p className="mt-1 truncate text-[9px] text-slate-400">{metric.hint}</p></article>)}</div>;
}

function AdmissionPipeline({ rows }: { rows: Record<string, unknown>[] }) {
  const stages = ['All', 'New', 'Under Review', 'Approved', 'Enrolled', 'Rejected'];
  const count = (stage: string) => stage === 'All' ? rows.length : rows.filter((row) => String(row.status ?? '').toLowerCase().includes(stage.toLowerCase().replace('under review', 'review'))).length;
  return <div className="mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">{stages.map((stage, index) => <div key={stage} className="tafiti-soft-card flex items-center gap-3 px-3 py-3"><span className={`grid h-9 w-9 place-items-center rounded-xl ${index === 0 ? 'bg-blue-50 text-blue-600' : index >= 3 && index <= 4 ? 'bg-emerald-50 text-emerald-600' : index === 5 ? 'bg-red-50 text-red-600' : 'bg-amber-50 text-amber-600'}`}><UserPlus size={16} /></span><div><p className="text-lg font-extrabold leading-none text-[#10224A]">{count(stage)}</p><p className="mt-1 text-[9px] font-semibold text-slate-500">{stage}</p></div></div>)}</div>;
}

function TimetableBoard({ rows }: { rows: Record<string, unknown>[] }) {
  const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
  const times = Array.from(new Set(rows.map((row) => String(row.time ?? '')).filter(Boolean))).slice(0, 9);
  return <section className="tafiti-card mb-4 overflow-hidden"><div className="flex items-center justify-between border-b border-slate-100 px-4 py-3.5"><div><h2 className="text-sm font-extrabold text-[#10224A]">Timetable builder</h2><p className="mt-1 text-[10px] text-slate-500">Existing lessons, teachers, rooms and subjects in one weekly grid.</p></div><span className="rounded-lg bg-blue-50 px-2.5 py-1 text-[9px] font-bold text-blue-700">Week view</span></div><div className="overflow-x-auto p-4"><div className="grid min-w-[900px] grid-cols-[95px_repeat(5,minmax(145px,1fr))] gap-2"><div />{days.map((day) => <div key={day} className="rounded-xl bg-[#F8FAFD] p-2 text-center text-[9px] font-extrabold text-slate-600">{day}</div>)}{times.map((time) => <div key={time} className="contents"><div className="grid place-items-center rounded-xl border border-slate-100 bg-white text-[9px] font-bold text-slate-500">{time}</div>{days.map((day, dayIndex) => { const item = rows.find((row) => String(row.day ?? '') === day && String(row.time ?? '') === time); const tones = ['bg-blue-50 border-blue-100', 'bg-emerald-50 border-emerald-100', 'bg-violet-50 border-violet-100', 'bg-amber-50 border-amber-100', 'bg-rose-50 border-rose-100']; return <div key={`${time}-${day}`} className={`min-h-[72px] rounded-xl border p-2.5 ${item ? tones[dayIndex % tones.length] : 'border-dashed border-slate-100 bg-[#FBFCFE]'}`}>{item ? <><p className="text-[10px] font-extrabold text-slate-800">{String(item.subject ?? '')}</p><p className="mt-1 text-[9px] text-slate-500">{String(item.class ?? '')}</p><p className="mt-2 text-[8px] text-slate-400">{String(item.teacher ?? '')} · {String(item.room ?? '')}</p></> : <span className="text-[9px] text-slate-300">—</span>}</div>; })}</div>)}</div></div></section>;
}

function SummaryCards({ resource, rows }: { resource: string; rows: Record<string, unknown>[] }) {
  if (resource === 'library') {
    const loan = rows.filter((row) => String(row.status ?? '') === 'On loan').length;
    const overdue = rows.filter((row) => String(row.status ?? '') === 'Overdue').length;
    const returned = rows.filter((row) => String(row.status ?? '') === 'Returned').length;
    return <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{[['Loan records', rows.length], ['On loan', loan], ['Overdue', overdue], ['Returned', returned]].map(([label, value]) => <div key={String(label)} className="tafiti-kpi"><p className="text-[9px] font-bold text-slate-400">{String(label).toUpperCase()}</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{String(value)}</p></div>)}</div>;
  }
  if (resource === 'audit') {
    const creates = rows.filter((row) => String(row.action ?? '').toLowerCase().includes('create')).length;
    const updates = rows.filter((row) => String(row.action ?? '').toLowerCase().includes('update')).length;
    return <div className="mb-4 grid gap-3 sm:grid-cols-3"><div className="tafiti-kpi"><p className="text-[9px] font-bold text-slate-400">ACTIVITIES</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{rows.length}</p></div><div className="tafiti-kpi"><p className="text-[9px] font-bold text-slate-400">CREATED</p><p className="mt-1 text-xl font-extrabold text-emerald-600">{creates}</p></div><div className="tafiti-kpi"><p className="text-[9px] font-bold text-slate-400">UPDATED</p><p className="mt-1 text-xl font-extrabold text-blue-600">{updates}</p></div></div>;
  }
  return null;
}

function SettingsPanel({ row, onEdit }: { row?: Record<string, unknown>; onEdit: () => void }) {
  if (!row) return null;
  const fields: Array<[string, unknown]> = [['School name', row.school], ['Motto', row.motto], ['Email', row.email], ['Phone', row.mobile], ['City', row.city], ['Country', row.country], ['Education levels', row.levels]];
  return <section className="tafiti-card overflow-hidden"><div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-4"><div><h2 className="text-sm font-extrabold text-[#10224A]">School profile</h2><p className="mt-1 text-[10px] text-slate-500">Identity, contact details and education-level configuration.</p></div><button type="button" onClick={onEdit} className="clay-button-primary"><Pencil size={14} /> Edit settings</button></div><div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3">{fields.map(([label, value]) => <div key={label} className="rounded-xl border border-slate-100 bg-[#F8FAFD] p-3.5"><p className="text-[9px] font-extrabold uppercase text-slate-400">{label}</p><p className="mt-1.5 text-xs font-bold text-slate-800">{String(value ?? '—')}</p></div>)}</div></section>;
}

export function ReferenceResourceView({ resource }: { resource: string }) {
  const toast = useToast();
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [data, setData] = useState<WorkspaceResource | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState(searchParams.get('q') ?? '');
  const [reload, setReload] = useState(0);
  const [formOpen, setFormOpen] = useState(false);
  const [formSchema, setFormSchema] = useState<WorkspaceFormSchema | null>(null);
  const [formLoading, setFormLoading] = useState(false);
  const [formErrors, setFormErrors] = useState<Record<string, string[]>>({});
  const [editingRow, setEditingRow] = useState<Record<string, unknown> | null>(null);
  const [deleteRow, setDeleteRow] = useState<Record<string, unknown> | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [bulkImportOpen, setBulkImportOpen] = useState(false);
  const page = Math.max(1, Number(searchParams.get('page') ?? 1) || 1);

  useEffect(() => setQuery(searchParams.get('q') ?? ''), [resource, searchParams]);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams(searchParams.toString());
      const current = params.get('q') ?? '';
      if (current === query.trim()) return;
      if (query.trim()) params.set('q', query.trim()); else params.delete('q');
      params.delete('page');
      router.replace(`${pathname}${params.toString() ? `?${params.toString()}` : ''}`, { scroll: false });
    }, 260);
    return () => window.clearTimeout(timer);
  }, [pathname, query, router, searchParams]);

  const requestQuery = useMemo(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.set('page', String(page));
    params.set('page_size', ['admissions', 'timetable', 'library', 'audit'].includes(resource) ? '100' : '25');
    params.delete('return'); params.delete('tab');
    return params.toString();
  }, [page, resource, searchParams]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    fetch(`/api/workspace/resources/${resource}?${requestQuery}`, { cache: 'no-store', signal: controller.signal })
      .then(async (response) => { const result = await response.json(); if (!response.ok) throw new Error(result.detail || 'This module could not be loaded.'); return result as WorkspaceResource; })
      .then(setData)
      .catch((reason: unknown) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'This module could not be loaded.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [reload, requestQuery, resource]);

  const pageLabel = useMemo(() => {
    if (!data?.pagination.total) return '0 records';
    const start = (data.pagination.page - 1) * data.pagination.page_size + 1;
    return `${start}–${Math.min(start + data.rows.length - 1, data.pagination.total)} of ${data.pagination.total}`;
  }, [data]);

  function exportCsv() {
    if (!data?.rows.length) return;
    const header = data.columns.map((column) => csvValue(column.label)).join(',');
    const rows = data.rows.map((row) => data.columns.map((column) => csvValue(row[column.key])).join(','));
    const blob = new Blob([[header, ...rows].join('\n')], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = `${resource}.csv`; anchor.click(); URL.revokeObjectURL(url);
  }

  function changePage(next: number) {
    const params = new URLSearchParams(searchParams.toString());
    if (next > 1) params.set('page', String(next)); else params.delete('page');
    router.replace(`${pathname}${params.toString() ? `?${params.toString()}` : ''}`, { scroll: false });
  }

  function openRow(row: Record<string, unknown>) {
    if (typeof row.id !== 'number') return;
    const verification = resource === 'results' && data?.view === 'verification';
    if (!contextual.has(resource) && !verification) return;
    const params = new URLSearchParams({ return: `${pathname}${searchParams.toString() ? `?${searchParams.toString()}` : ''}` });
    if (verification) params.set('view', 'verification');
    router.push(`${pathname}/${row.id}?${params.toString()}`);
  }

  async function openForm(row?: Record<string, unknown>) {
    if (row && typeof row.id !== 'number') return;
    setEditingRow(row ?? null); setFormOpen(true); setFormSchema(null); setFormErrors({}); setFormLoading(true);
    try {
      const path = row ? `/api/workspace/resources/${resource}/${row.id}/form` : `/api/workspace/resources/${resource}/form`;
      const response = await fetch(path, { cache: 'no-store' }); const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'The form could not be opened.');
      setFormSchema(result as WorkspaceFormSchema);
    } catch (reason: unknown) { toast.error('Could not open form', reason instanceof Error ? reason.message : 'Please try again.'); setFormOpen(false); }
    finally { setFormLoading(false); }
  }

  async function submitForm(values: Record<string, unknown>) {
    if (!formSchema) return;
    const editing = formSchema.mode === 'edit' && typeof editingRow?.id === 'number';
    const path = editing ? `/api/workspace/resources/${resource}/${editingRow?.id}/form` : `/api/workspace/resources/${resource}/form`;
    setFormLoading(true); setFormErrors({});
    try {
      const hasFile = Object.values(values).some((value) => value instanceof File);
      let body: BodyInit; let headers: HeadersInit | undefined;
      if (hasFile) { const formData = new FormData(); Object.entries(values).forEach(([key, value]) => { if (value instanceof File) formData.append(key, value); else if (Array.isArray(value)) value.forEach((item) => formData.append(key, String(item))); else if (typeof value === 'boolean') formData.append(key, value ? 'true' : 'false'); else if (value != null) formData.append(key, String(value)); }); body = formData; }
      else { headers = { 'Content-Type': 'application/json' }; body = JSON.stringify(values); }
      const response = await fetch(path, { method: editing ? 'PATCH' : 'POST', headers, body }); const result = await response.json();
      if (!response.ok) { setFormErrors((result.errors as Record<string, string[]>) ?? {}); throw new Error(result.detail || 'The record could not be saved.'); }
      toast.success(editing ? 'Changes saved' : 'Record created', result.detail || 'Saved successfully.'); setFormOpen(false); setEditingRow(null); setReload((value) => value + 1);
      if (typeof result.id === 'number' && contextual.has(resource)) { const params = new URLSearchParams({ return: `${pathname}${searchParams.toString() ? `?${searchParams.toString()}` : ''}` }); router.push(`${pathname}/${result.id}?${params.toString()}`); }
    } catch (reason: unknown) { toast.error('Could not save record', reason instanceof Error ? reason.message : 'Please try again.'); }
    finally { setFormLoading(false); }
  }

  async function deleteRecord() {
    if (!deleteRow || typeof deleteRow.id !== 'number') return;
    setDeleteLoading(true);
    try { const response = await fetch(`/api/workspace/resources/${resource}/${deleteRow.id}/form`, { method: 'DELETE' }); const result = await response.json(); if (!response.ok) throw new Error(result.detail || 'The action could not be completed.'); toast.success('Record updated', result.detail || 'Action completed.'); setDeleteRow(null); setReload((value) => value + 1); }
    catch (reason: unknown) { toast.error('Action failed', reason instanceof Error ? reason.message : 'Please try again.'); }
    finally { setDeleteLoading(false); }
  }

  if (loading && !data) return <div className="tafiti-card grid min-h-[420px] place-items-center"><LoaderCircle className="animate-spin text-blue-600" /></div>;
  if (error && !data) return <div className="tafiti-card grid min-h-[420px] place-items-center p-6 text-center"><div><AlertCircle className="mx-auto text-red-500" /><p className="mt-3 text-sm font-bold text-slate-800">Unable to load module</p><p className="mt-1 text-xs text-slate-400">{error}</p><button type="button" onClick={() => setReload((value) => value + 1)} className="clay-button-primary mt-4"><RefreshCw size={14} /> Retry</button></div></div>;
  if (!data) return null;

  const Icon = resourceIcon(resource);
  const reactivate = ((data.actions.delete_mode === 'toggle-active' && deleteRow?.status === 'Inactive') || (data.actions.delete_mode === 'toggle-status' && deleteRow?.status === 'Retired'));
  const deleteLabel = reactivate ? 'Reactivate' : data.actions.delete_label;

  return <section><div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div className="flex items-start gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-600"><Icon size={21} /></span><div><h1 className="text-[1.65rem] font-extrabold tracking-[-.035em] text-[#10224A]">{data.title}</h1><p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">{data.description}</p></div></div><div className="flex flex-wrap gap-2"><button type="button" onClick={() => setReload((value) => value + 1)} className="clay-button-secondary"><RefreshCw size={14} /> Refresh</button><button type="button" onClick={exportCsv} className="clay-button-secondary"><Download size={14} /> Export</button>{resource === 'students' && data.actions.bulk_import && <button type="button" onClick={() => setBulkImportOpen(true)} className="clay-button-secondary"><Upload size={14} /> Bulk upload</button>}{resource === 'fees' && <Link href={pathname.replace(/\/fees$/, '/fees-payments')} className="clay-button-primary"><Plus size={14} /> Record payment</Link>}{data.actions.create && <button type="button" onClick={() => void openForm()} className="clay-button-primary"><Plus size={14} /> {data.actions.create_label}</button>}</div></div><Metrics metrics={data.metrics ?? []} />{resource === 'admissions' && <AdmissionPipeline rows={data.rows} />}{resource === 'timetable' && <TimetableBoard rows={data.rows} />}{resource === 'library' || resource === 'audit' ? <SummaryCards resource={resource} rows={data.rows} /> : null}{resource === 'results' && <div className="mb-3 flex gap-1 rounded-xl border border-slate-200 bg-white p-1"><Link href="?" className={`rounded-lg px-3 py-2 text-[10px] font-bold ${data.view !== 'verification' ? 'bg-blue-600 text-white' : 'text-slate-500'}`}>Results</Link><Link href="?view=verification" className={`rounded-lg px-3 py-2 text-[10px] font-bold ${data.view === 'verification' ? 'bg-blue-600 text-white' : 'text-slate-500'}`}>Verification queue</Link></div>}{resource === 'settings' ? <SettingsPanel row={data.rows[0]} onEdit={() => data.rows[0] && void openForm(data.rows[0])} /> : <><DataTable columns={data.columns} rows={data.rows} query={query} actions={data.actions} onQueryChange={setQuery} onExport={exportCsv} onView={openRow} onEdit={(row) => void openForm(row)} onDelete={setDeleteRow} /><div className="clay-pagination mt-3 flex flex-col gap-3 px-4 py-3 text-[10px] text-slate-500 sm:flex-row sm:items-center sm:justify-between"><span>{pageLabel}</span><div className="flex items-center gap-2"><button disabled={data.pagination.page <= 1 || loading} onClick={() => changePage(Math.max(1, data.pagination.page - 1))} className="clay-page-button"><ChevronLeft size={13} /> Previous</button><span className="font-bold">{data.pagination.page} / {data.pagination.pages}</span><button disabled={data.pagination.page >= data.pagination.pages || loading} onClick={() => changePage(data.pagination.page + 1)} className="clay-page-button">Next <ChevronRight size={13} /></button></div></div></>}<StudentBulkImportDialog open={bulkImportOpen} onClose={() => setBulkImportOpen(false)} onImported={(count, message) => { setBulkImportOpen(false); setReload((value) => value + 1); toast.success('Students registered', message || `${count} student(s) added.`); }} /><ResourceFormDialog open={formOpen} schema={formSchema} loading={formLoading} errors={formErrors} onClose={() => { setFormOpen(false); setEditingRow(null); setFormErrors({}); }} onSubmit={submitForm} /><ConfirmActionDialog open={Boolean(deleteRow)} title={`${deleteLabel} record`} message={`${deleteLabel} ${rowTitle(deleteRow)}? Historical school records will be protected by the existing Django rules.`} confirmLabel={deleteLabel} loading={deleteLoading} onCancel={() => setDeleteRow(null)} onConfirm={() => void deleteRecord()} /></section>;
}
