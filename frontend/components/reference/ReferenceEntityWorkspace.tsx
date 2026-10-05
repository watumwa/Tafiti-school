'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import {
  ArrowLeft,
  ChevronRight,
  CircleDollarSign,
  FileText,
  GraduationCap,
  LoaderCircle,
  Pencil,
  School,
  ShieldCheck,
  UserRound,
  Users,
} from 'lucide-react';

import type { WorkspaceEntity, WorkspaceEntityAction, WorkspaceFormSchema } from '@/lib/workspace';
import { useToast } from '@/components/ui/ToastProvider';
import { ProfileAvatar } from '@/components/workspace/ProfileAvatar';
import { ResourceFormDialog } from '@/components/workspace/ResourceFormDialog';
import { WorkspaceIcon } from '@/components/workspace/WorkspaceIcon';

function statusClass(status: string) {
  const value = status.toLowerCase();
  if (['active', 'verified', 'paid', 'enrolled', 'approved', 'current'].some((item) => value.includes(item))) return 'bg-emerald-50 text-emerald-700 border-emerald-100';
  if (['pending', 'outstanding', 'draft', 'review'].some((item) => value.includes(item))) return 'bg-amber-50 text-amber-700 border-amber-100';
  if (['inactive', 'retired', 'rejected', 'flagged'].some((item) => value.includes(item))) return 'bg-red-50 text-red-700 border-red-100';
  return 'bg-slate-50 text-slate-600 border-slate-100';
}

function actionIcon(action: WorkspaceEntityAction) {
  if (action.icon === 'edit') return <Pencil size={14} />;
  return <WorkspaceIcon name={action.icon} size={14} />;
}

function metricIcon(label: string) {
  const value = label.toLowerCase();
  if (value.includes('attendance')) return ShieldCheck;
  if (value.includes('paid') || value.includes('outstanding') || value.includes('bill')) return CircleDollarSign;
  if (value.includes('result') || value.includes('subject')) return GraduationCap;
  if (value.includes('student')) return Users;
  return FileText;
}

function detailCards(rows: Record<string, unknown>[]) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {rows.map((row, index) => (
        <div key={`${String(row.field ?? 'field')}-${index}`} className="rounded-xl border border-slate-100 bg-[#F8FAFD] p-3.5">
          <p className="text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">{String(row.field ?? 'Detail')}</p>
          <p className="mt-1.5 break-words text-xs font-bold text-slate-800">{String(row.value ?? '—')}</p>
        </div>
      ))}
    </div>
  );
}

function EntityTable({ entity, activeTab }: { entity: WorkspaceEntity; activeTab: string }) {
  const tab = entity.tabs.find((item) => item.key === activeTab) ?? entity.tabs[0];
  if (!tab) return null;
  if (!tab.rows.length) return <div className="grid min-h-[240px] place-items-center p-6 text-center"><div><FileText className="mx-auto text-blue-300" size={25} /><h3 className="mt-3 text-sm font-bold text-slate-800">{tab.empty_title}</h3><p className="mt-1 max-w-sm text-xs leading-5 text-slate-400">{tab.description}</p></div></div>;
  const profileMode = tab.columns.length === 2 && tab.columns[0]?.key === 'field' && tab.columns[1]?.key === 'value';
  if (profileMode) return <div className="p-4 sm:p-5">{detailCards(tab.rows)}</div>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-left">
        <thead><tr className="border-b border-slate-100 bg-[#F8FAFD]">{tab.columns.map((column) => <th key={column.key} className="px-4 py-3 text-[9px] font-extrabold uppercase tracking-[.07em] text-slate-400">{column.label}</th>)}</tr></thead>
        <tbody className="divide-y divide-slate-100">{tab.rows.map((row, index) => {
          const links = (row._links ?? {}) as Record<string, string>;
          return <tr key={String(row.id ?? row.reference ?? index)} className="hover:bg-blue-50/25">{tab.columns.map((column) => { const value = String(row[column.key] ?? '—'); return <td key={column.key} className="max-w-[330px] px-4 py-3 text-xs text-slate-600">{links[column.key] ? <Link href={links[column.key]} className="inline-flex items-center gap-1 font-bold text-blue-700 hover:underline">{value}<ChevronRight size={12} /></Link> : <span className={['student', 'subject', 'class', 'bill', 'teacher'].includes(column.key) ? 'font-bold text-slate-800' : ''}>{value}</span>}</td>; })}</tr>;
        })}</tbody>
      </table>
    </div>
  );
}

export function ReferenceEntityWorkspace({ resource, id, dashboardPath, onTitleChange }: { resource: string; id: number; dashboardPath: string; onTitleChange?: (title: string) => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  const [data, setData] = useState<WorkspaceEntity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);
  const [formOpen, setFormOpen] = useState(false);
  const [formSchema, setFormSchema] = useState<WorkspaceFormSchema | null>(null);
  const [formLoading, setFormLoading] = useState(false);
  const [formErrors, setFormErrors] = useState<Record<string, string[]>>({});

  const requestQuery = searchParams.toString();
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    fetch(`/api/workspace/resources/${resource}/${id}${requestQuery ? `?${requestQuery}` : ''}`, { cache: 'no-store', signal: controller.signal })
      .then(async (response) => { const result = await response.json(); if (!response.ok) throw new Error(result.detail || 'This profile could not be opened.'); return result as WorkspaceEntity; })
      .then((result) => { setData(result); onTitleChange?.(result.title); })
      .catch((reason: unknown) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'This profile could not be opened.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [id, onTitleChange, reloadKey, requestQuery, resource]);

  const activeTab = searchParams.get('tab') || data?.tabs[0]?.key || '';
  const returnPath = useMemo(() => {
    const value = searchParams.get('return');
    return value?.startsWith(`${dashboardPath}/`) ? value : `${dashboardPath}/${resource}`;
  }, [dashboardPath, resource, searchParams]);

  function selectTab(tab: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set('tab', tab);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }

  async function openEditForm() {
    setFormOpen(true); setFormSchema(null); setFormErrors({}); setFormLoading(true);
    try {
      const response = await fetch(`/api/workspace/resources/${resource}/${id}/form`, { cache: 'no-store' });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'The edit form could not be opened.');
      setFormSchema(result as WorkspaceFormSchema);
    } catch (reason: unknown) { toast.error('Could not open form', reason instanceof Error ? reason.message : 'The edit form could not be opened.'); setFormOpen(false); }
    finally { setFormLoading(false); }
  }

  async function submitForm(values: Record<string, unknown>) {
    if (!formSchema) return;
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
      const response = await fetch(`/api/workspace/resources/${resource}/${id}/form`, { method: 'PATCH', headers, body });
      const result = await response.json();
      if (!response.ok) { setFormErrors((result.errors as Record<string, string[]>) ?? {}); throw new Error(result.detail || 'The record could not be saved.'); }
      toast.success('Changes saved', result.detail || 'The record was updated.'); setFormOpen(false); setReloadKey((value) => value + 1);
    } catch (reason: unknown) { toast.error('Could not save changes', reason instanceof Error ? reason.message : 'The record could not be saved.'); }
    finally { setFormLoading(false); }
  }

  if (loading && !data) return <div className="tafiti-card grid min-h-[430px] place-items-center"><div className="text-center text-xs font-semibold text-slate-500"><LoaderCircle className="mx-auto mb-3 animate-spin text-blue-600" size={24} />Opening profile…</div></div>;
  if (error && !data) return <div className="tafiti-card grid min-h-[430px] place-items-center p-6 text-center"><div><h2 className="text-sm font-bold text-slate-900">We couldn&apos;t open this workspace</h2><p className="mt-2 text-xs text-slate-500">{error}</p><button type="button" onClick={() => setReloadKey((value) => value + 1)} className="clay-button-primary mt-4">Try again</button></div></div>;
  if (!data) return null;

  return (
    <section>
      <Link href={returnPath} className="mb-3 inline-flex items-center gap-1.5 text-[11px] font-bold text-slate-500 hover:text-blue-600"><ArrowLeft size={13} /> Back to {resource === 'fees' ? 'fee accounts' : resource}</Link>

      <section className="tafiti-card overflow-hidden">
        <div className="flex flex-col gap-5 px-5 py-5 lg:flex-row lg:items-center lg:justify-between sm:px-6">
          <div className="flex min-w-0 flex-col gap-4 sm:flex-row sm:items-center">
            <ProfileAvatar src={data.photo} name={data.title} size="xl" className="border-4 border-white shadow-[0_5px_16px_rgba(28,55,97,.12)]" />
            <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h1 className="truncate text-2xl font-extrabold tracking-[-0.035em] text-[#10224A]">{data.title}</h1><span className={`inline-flex rounded-full border px-2.5 py-1 text-[9px] font-extrabold ${statusClass(data.status)}`}>{data.status}</span></div><p className="mt-1 text-xs font-bold text-blue-700">{data.subtitle}</p><div className="mt-3 flex flex-wrap gap-x-4 gap-y-2">{data.metadata.map((item) => <span key={item.label} className="text-[10px] text-slate-500"><span className="font-bold text-slate-400">{item.label}</span> · {item.href ? <Link href={item.href} className="font-bold text-blue-700 hover:underline">{item.value}</Link> : <span className="font-bold text-slate-700">{item.value}</span>}</span>)}</div></div>
          </div>
          <div className="flex flex-wrap gap-2">{data.actions.map((action) => action.action === 'edit' ? <button key={action.label} type="button" onClick={() => void openEditForm()} className={action.primary ? 'clay-button-primary' : 'clay-button-secondary'}>{actionIcon(action)} {action.label}</button> : action.href ? <Link key={action.label} href={action.href} className={action.primary ? 'clay-button-primary' : 'clay-button-secondary'}>{actionIcon(action)} {action.label}</Link> : null)}</div>
        </div>

        <div className="border-t border-slate-100 bg-[#FBFCFE] px-3 pt-2"><div className="flex min-w-max gap-1 overflow-x-auto">{data.tabs.map((tab) => <button key={tab.key} type="button" onClick={() => selectTab(tab.key)} className={`relative h-10 px-3.5 text-[10px] font-extrabold transition ${activeTab === tab.key ? 'text-blue-700' : 'text-slate-500 hover:text-slate-800'}`}>{tab.label}{tab.count > 0 && <span className={`ml-1.5 rounded-full px-1.5 py-0.5 text-[8px] ${activeTab === tab.key ? 'bg-blue-50 text-blue-700' : 'bg-slate-100 text-slate-500'}`}>{tab.count}</span>}{activeTab === tab.key && <span className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-blue-600" />}</button>)}</div></div>
      </section>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{data.metrics.map((metric) => { const Icon = metricIcon(metric.label); return <article key={metric.label} className="tafiti-kpi"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-blue-50 text-blue-600"><Icon size={17} /></span><div className="min-w-0"><p className="text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">{metric.label}</p><p className="mt-1 truncate text-lg font-extrabold text-[#10224A]">{metric.value}</p><p className="mt-0.5 truncate text-[9px] text-slate-400">{metric.hint}</p></div></div></article>; })}</div>

      <section className="tafiti-card mt-4 overflow-hidden">
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3.5 sm:px-5"><div><h2 className="text-sm font-extrabold text-[#10224A]">{data.tabs.find((tab) => tab.key === activeTab)?.label ?? 'Overview'}</h2><p className="mt-1 text-[10px] text-slate-500">{data.tabs.find((tab) => tab.key === activeTab)?.description ?? 'Connected school information.'}</p></div><span className="grid h-8 w-8 place-items-center rounded-lg bg-blue-50 text-blue-600">{resource === 'classes' ? <School size={15} /> : resource === 'staff' ? <UserRound size={15} /> : <FileText size={15} />}</span></div>
        <EntityTable entity={data} activeTab={activeTab} />
      </section>

      <ResourceFormDialog open={formOpen} schema={formSchema} loading={formLoading} errors={formErrors} onClose={() => { setFormOpen(false); setFormErrors({}); }} onSubmit={submitForm} />
    </section>
  );
}
