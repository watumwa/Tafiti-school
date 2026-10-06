'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  BookOpen,
  CalendarDays,
  CalendarRange,
  ClipboardList,
  GraduationCap,
  Layers3,
  LoaderCircle,
  Pencil,
  Plus,
  Scale,
  School,
  Search,
  Users,
} from 'lucide-react';

import type { WorkspaceColumn, WorkspaceFormSchema } from '@/lib/workspace';
import { useToast } from '@/components/ui/ToastProvider';
import { ResourceFormDialog } from '@/components/workspace/ResourceFormDialog';

type ToolData = {
  tool: string;
  title: string;
  description: string;
  columns: WorkspaceColumn[];
  rows: Record<string, unknown>[];
  can_write: boolean;
  create_label: string;
  form: WorkspaceFormSchema;
};

const tools = [
  { key: 'academic-years', label: 'Academic Years', icon: CalendarRange },
  { key: 'terms', label: 'Terms', icon: CalendarDays },
  { key: 'streams', label: 'Streams', icon: Layers3 },
  { key: 'class-streams', label: 'Class Streams', icon: School },
  { key: 'subject-allocations', label: 'Subject Allocations', icon: Users },
  { key: 'assessments', label: 'Assessments', icon: ClipboardList },
  { key: 'assessment-types', label: 'Assessment Types', icon: BookOpen },
  { key: 'grading', label: 'Grading System', icon: Scale },
] as const;

type AcademicTool = typeof tools[number]['key'];

export function ReferenceAcademicSetupView({
  initialTool,
  visibleTools,
}: {
  initialTool?: AcademicTool;
  visibleTools?: readonly AcademicTool[];
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  const availableTools = visibleTools ? tools.filter((item) => visibleTools.includes(item.key)) : tools;
  const requested = searchParams.get('tool') || initialTool || availableTools[0]?.key || 'academic-years';
  const tool = availableTools.some((item) => item.key === requested) ? requested : availableTools[0]?.key || 'academic-years';
  const [data, setData] = useState<ToolData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [formSchema, setFormSchema] = useState<WorkspaceFormSchema | null>(null);
  const [formLoading, setFormLoading] = useState(false);
  const [formErrors, setFormErrors] = useState<Record<string, string[]>>({});
  const [editingId, setEditingId] = useState<number | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetch(`/api/workspace/academics/${tool}`, { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Academic setup could not be loaded.');
        return payload as ToolData;
      })
      .then((payload) => {
        setData(payload);
        setQuery('');
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Academic setup could not be loaded.');
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [reloadKey, tool]);

  const rows = useMemo(() => {
    const text = query.trim().toLowerCase();
    if (!text) return data?.rows ?? [];
    return (data?.rows ?? []).filter((row) => Object.values(row).some((value) => String(value ?? '').toLowerCase().includes(text)));
  }, [data, query]);

  function switchTool(next: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set('tool', next);
    router.replace(`?${params.toString()}`, { scroll: false });
  }

  function openCreate() {
    if (!data?.can_write) return;
    setEditingId(null);
    setFormSchema(data.form);
    setFormErrors({});
    setFormOpen(true);
  }

  async function openEdit(row: Record<string, unknown>) {
    if (!data?.can_write || typeof row.id !== 'number') return;
    setEditingId(row.id);
    setFormOpen(true);
    setFormSchema(null);
    setFormErrors({});
    setFormLoading(true);
    try {
      const response = await fetch(`/api/workspace/academics/${tool}/${row.id}`, { cache: 'no-store' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'The record could not be opened.');
      setFormSchema(payload as WorkspaceFormSchema);
    } catch (reason: unknown) {
      toast.error('Could not open record', reason instanceof Error ? reason.message : 'Please try again.');
      setFormOpen(false);
    } finally { setFormLoading(false); }
  }

  async function save(values: Record<string, unknown>) {
    setFormLoading(true);
    setFormErrors({});
    try {
      const path = editingId ? `/api/workspace/academics/${tool}/${editingId}` : `/api/workspace/academics/${tool}`;
      const response = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      });
      const payload = await response.json();
      if (!response.ok) {
        setFormErrors((payload.errors as Record<string, string[]>) ?? {});
        throw new Error(payload.detail || 'The record could not be saved.');
      }
      toast.success(editingId ? 'Changes saved' : 'Record created', payload.detail || 'Academic setup updated.');
      setFormOpen(false);
      setEditingId(null);
      setReloadKey((value) => value + 1);
    } catch (reason: unknown) {
      toast.error('Could not save record', reason instanceof Error ? reason.message : 'Please try again.');
    } finally { setFormLoading(false); }
  }

  const activeTool = tools.find((item) => item.key === tool) ?? tools[0];
  const ActiveIcon = activeTool.icon;

  return (
    <section>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex items-start gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-600"><GraduationCap size={21} /></span>
          <div><h1 className="text-[1.65rem] font-extrabold tracking-[-0.035em] text-[#10224A]">Academic Setup</h1><p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">Academic years, terms, classes, streams, allocations, assessments and grading are configured here instead of being scattered across separate pages.</p></div>
        </div>
        {data?.can_write && <button type="button" onClick={openCreate} className="clay-button-primary"><Plus size={14} />{data.create_label}</button>}
      </div>

      <div className="mb-4 overflow-x-auto rounded-xl border border-slate-200 bg-white p-1.5 shadow-[0_5px_16px_rgba(28,55,97,.035)]">
        <div className="flex min-w-max gap-1">{availableTools.map((item) => { const Icon = item.icon; const active = item.key === tool; return <button key={item.key} type="button" onClick={() => switchTool(item.key)} className={`inline-flex h-9 items-center gap-1.5 rounded-lg px-3 text-[10px] font-extrabold transition ${active ? 'bg-blue-600 text-white shadow-[0_5px_12px_rgba(37,99,235,.18)]' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'}`}><Icon size={13} />{item.label}</button>; })}</div>
      </div>

      <section className="tafiti-card overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-slate-100 px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between sm:px-5">
          <div className="flex items-center gap-3"><span className="grid h-9 w-9 place-items-center rounded-xl bg-blue-50 text-blue-600"><ActiveIcon size={16} /></span><div><h2 className="text-sm font-extrabold text-[#10224A]">{data?.title ?? activeTool.label}</h2><p className="mt-0.5 text-[10px] text-slate-500">{data?.description ?? 'Loading configuration…'}</p></div></div>
          <div className="relative w-full sm:max-w-[310px]"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search configuration…" className="tafiti-input h-9 w-full pl-9 pr-3 text-xs" /></div>
        </div>

        {loading && !data ? <div className="grid min-h-[320px] place-items-center"><LoaderCircle className="animate-spin text-blue-600" size={23} /></div>
          : error && !data ? <div className="px-5 py-12 text-center"><p className="text-sm font-bold text-slate-800">Academic setup unavailable</p><p className="mt-2 text-xs text-slate-500">{error}</p></div>
          : <div className="overflow-x-auto"><table className="w-full min-w-[680px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]">{data?.columns.map((column) => <th key={column.key} className="px-4 py-3 text-[9px] font-extrabold uppercase tracking-[.06em] text-slate-400">{column.label}</th>)}{data?.can_write && <th className="px-4 py-3 text-right text-[9px] font-extrabold text-slate-400">ACTION</th>}</tr></thead><tbody className="divide-y divide-slate-100">{rows.map((row, index) => <tr key={String(row.id ?? index)} className="hover:bg-blue-50/25">{data?.columns.map((column) => <td key={column.key} className={`px-4 py-3 text-xs ${index === 0 && column.key === data.columns[0]?.key ? 'font-bold text-slate-800' : 'text-slate-600'}`}>{String(row[column.key] ?? '—')}</td>)}{data?.can_write && <td className="px-4 py-3 text-right"><button type="button" onClick={() => void openEdit(row)} className="inline-flex items-center gap-1 text-[10px] font-bold text-blue-600 hover:underline"><Pencil size={12} />Edit</button></td>}</tr>)}</tbody></table></div>}
        {!loading && data && !rows.length && <div className="px-5 py-12 text-center text-xs text-slate-400">No configuration records match this view.</div>}
      </section>

      <ResourceFormDialog open={formOpen} schema={formSchema} loading={formLoading} errors={formErrors} onClose={() => { setFormOpen(false); setEditingId(null); setFormErrors({}); }} onSubmit={save} />
    </section>
  );
}
