'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, ChevronLeft, ChevronRight, Database, LoaderCircle, Plus, RefreshCw } from 'lucide-react';

import type { WorkspaceFormSchema, WorkspaceResource } from '@/lib/workspace';
import { useToast } from '@/components/ui/ToastProvider';
import { ConfirmActionDialog } from './ConfirmActionDialog';
import { DataTable } from './DataTable';
import { RecordDetailsDialog } from './RecordDetailsDialog';
import { ResourceFormDialog } from './ResourceFormDialog';

function csvEscape(value: unknown) {
  const text = value === null || value === undefined ? '' : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

function rowTitle(row: Record<string, unknown> | null) {
  if (!row) return 'this record';
  for (const key of ['name', 'student', 'title', 'class', 'application', 'school', 'code']) {
    if (row[key]) return String(row[key]);
  }
  return row.id ? `record #${row.id}` : 'this record';
}

export function ResourceView({ resource }: { resource: string }) {
  const toast = useToast();
  const [data, setData] = useState<WorkspaceResource | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [queryInput, setQueryInput] = useState('');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [reloadKey, setReloadKey] = useState(0);
  const [detailsRow, setDetailsRow] = useState<Record<string, unknown> | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [formSchema, setFormSchema] = useState<WorkspaceFormSchema | null>(null);
  const [formLoading, setFormLoading] = useState(false);
  const [formErrors, setFormErrors] = useState<Record<string, string[]>>({});
  const [editingRow, setEditingRow] = useState<Record<string, unknown> | null>(null);
  const [deleteRow, setDeleteRow] = useState<Record<string, unknown> | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setPage(1);
      setQuery(queryInput.trim());
    }, 280);
    return () => window.clearTimeout(handle);
  }, [queryInput]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    const params = new URLSearchParams({ page: String(page), page_size: '25' });
    if (query) params.set('q', query);

    fetch(`/api/workspace/resources/${resource}?${params.toString()}`, {
      cache: 'no-store',
      signal: controller.signal,
    })
      .then(async (response) => {
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || 'This module could not be loaded.');
        return result as WorkspaceResource;
      })
      .then(setData)
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        const message = reason instanceof Error ? reason.message : 'This module could not be loaded.';
        setError(message);
        toast.error('Could not load module', message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [page, query, reloadKey, resource, toast]);

  const pageLabel = useMemo(() => {
    if (!data) return '';
    if (!data.pagination.total) return '0 records';
    const start = (data.pagination.page - 1) * data.pagination.page_size + 1;
    const end = Math.min(start + data.rows.length - 1, data.pagination.total);
    return `${start}–${end} of ${data.pagination.total}`;
  }, [data]);

  function exportCsv() {
    if (!data?.rows.length) {
      toast.info('Nothing to export', 'There are no rows on the current page.');
      return;
    }
    const header = data.columns.map((column) => csvEscape(column.label)).join(',');
    const lines = data.rows.map((row) => data.columns.map((column) => csvEscape(row[column.key])).join(','));
    const blob = new Blob([[header, ...lines].join('\n')], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${resource}-${new Date().toISOString().slice(0, 10)}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
    toast.success('Export ready', 'The current table page was exported as CSV.');
  }

  async function openForm(row?: Record<string, unknown>) {
    const id = row?.id;
    if (row && typeof id !== 'number') return;
    setEditingRow(row ?? null);
    setFormOpen(true);
    setFormSchema(null);
    setFormErrors({});
    setFormLoading(true);
    try {
      const path = row ? `/api/workspace/resources/${resource}/${id}/form` : `/api/workspace/resources/${resource}/form`;
      const response = await fetch(path, { cache: 'no-store' });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'The form could not be opened.');
      setFormSchema(result as WorkspaceFormSchema);
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : 'The form could not be opened.';
      toast.error('Could not open form', message);
      setFormOpen(false);
    } finally {
      setFormLoading(false);
    }
  }

  async function submitForm(values: Record<string, unknown>) {
    if (!formSchema) return;
    const id = editingRow?.id;
    const editing = formSchema.mode === 'edit' && typeof id === 'number';
    const path = editing ? `/api/workspace/resources/${resource}/${id}/form` : `/api/workspace/resources/${resource}/form`;
    setFormLoading(true);
    setFormErrors({});
    try {
      const hasFile = Object.values(values).some((value) => value instanceof File);
      let body: BodyInit;
      let headers: HeadersInit | undefined;
      if (hasFile) {
        const formData = new FormData();
        for (const [key, value] of Object.entries(values)) {
          if (value instanceof File) formData.append(key, value);
          else if (Array.isArray(value)) value.forEach((item) => formData.append(key, String(item)));
          else if (typeof value === 'boolean') formData.append(key, value ? 'true' : 'false');
          else if (value !== null && value !== undefined) formData.append(key, String(value));
        }
        body = formData;
      } else {
        headers = { 'Content-Type': 'application/json' };
        body = JSON.stringify(values);
      }
      const response = await fetch(path, {
        method: editing ? 'PATCH' : 'POST',
        headers,
        body,
      });
      const result = await response.json();
      if (!response.ok) {
        setFormErrors((result.errors as Record<string, string[]>) ?? {});
        throw new Error(result.detail || 'The record could not be saved.');
      }
      toast.success(editing ? 'Changes saved' : 'Record created', result.detail);
      setFormOpen(false);
      setEditingRow(null);
      setReloadKey((value) => value + 1);
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : 'The record could not be saved.';
      toast.error('Could not save record', message);
    } finally {
      setFormLoading(false);
    }
  }

  async function confirmDelete() {
    if (!deleteRow || typeof deleteRow.id !== 'number') return;
    setDeleteLoading(true);
    try {
      const response = await fetch(`/api/workspace/resources/${resource}/${deleteRow.id}/form`, { method: 'DELETE' });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'The action could not be completed.');
      toast.success(data?.actions.delete_mode === 'toggle-active' ? 'Student status updated' : data?.actions.delete_mode === 'toggle-status' ? 'Staff status updated' : 'Record deleted', result.detail);
      setDeleteRow(null);
      setReloadKey((value) => value + 1);
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : 'The action could not be completed.';
      toast.error('Action failed', message);
    } finally {
      setDeleteLoading(false);
    }
  }

  if (loading && !data) {
    return (
      <div className="clay-panel grid min-h-[420px] place-items-center">
        <div className="text-center text-sm font-medium text-slate-500">
          <LoaderCircle className="mx-auto mb-3 animate-spin text-[#2C5D8A]" size={24} />
          Loading school data…
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="clay-panel grid min-h-[420px] place-items-center px-5 text-center">
        <div className="max-w-sm">
          <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-red-50 text-red-700 shadow-[inset_1px_1px_0_#fff,0_7px_18px_rgba(220,38,38,.08)]"><AlertCircle size={22} /></span>
          <h2 className="mt-4 text-base font-semibold text-slate-900">We couldn’t load this module</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">{error}</p>
          <button type="button" onClick={() => setReloadKey((value) => value + 1)} className="clay-button-primary mt-5"><RefreshCw size={15} /> Try again</button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const selectedDeleteLabel = (data.actions.delete_mode === 'toggle-active' && deleteRow?.status === 'Inactive') || (data.actions.delete_mode === 'toggle-status' && deleteRow?.status === 'Retired') ? 'Reactivate' : data.actions.delete_label;
  const deleteMessage = data.actions.delete_mode === 'toggle-active'
    ? `${selectedDeleteLabel} ${rowTitle(deleteRow)}? The student record and history will be preserved.`
    : data.actions.delete_mode === 'toggle-status'
      ? `${selectedDeleteLabel} ${rowTitle(deleteRow)}? Historical staff records and assignments will be preserved.`
      : `Delete ${rowTitle(deleteRow)}? This cannot be undone and will be blocked if other school records depend on it.`;

  return (
    <section>
      <div className="mb-5 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.13em] text-[#2C5D8A]">School workspace</p>
          <h1 className="mt-1.5 text-2xl font-semibold tracking-[-0.025em] text-[#0B1F3A] sm:text-[1.8rem]">{data.title}</h1>
          <p className="mt-1.5 max-w-3xl text-sm leading-6 text-slate-500">{data.description}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 self-start sm:self-auto">
          <button type="button" onClick={() => setReloadKey((value) => value + 1)} className="clay-button-secondary">
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
          {data.actions.create && (
            <button type="button" onClick={() => void openForm()} className="clay-button-primary">
              <Plus size={16} /> {data.actions.create_label}
            </button>
          )}
        </div>
      </div>

      {!data.rows.length && !query ? (
        <div className="clay-panel grid min-h-[390px] place-items-center px-5 text-center">
          <div className="max-w-sm">
            <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-[#EAF0F7] text-[#2C5D8A] shadow-[inset_1px_1px_0_#fff,0_7px_18px_rgba(15,39,71,.08)]"><Database size={22} /></span>
            <h2 className="mt-4 text-base font-semibold text-slate-900">No records yet</h2>
            <p className="mt-2 text-sm leading-6 text-slate-500">This module is connected to the real Django data model, but there are no records to display.</p>
            {data.actions.create && <button type="button" onClick={() => void openForm()} className="clay-button-primary mt-5"><Plus size={16} /> {data.actions.create_label}</button>}
          </div>
        </div>
      ) : (
        <>
          <DataTable
            columns={data.columns}
            rows={data.rows}
            query={queryInput}
            actions={data.actions}
            onQueryChange={setQueryInput}
            onExport={exportCsv}
            onView={setDetailsRow}
            onEdit={(row) => void openForm(row)}
            onDelete={setDeleteRow}
          />
          <div className="clay-pagination mt-3 flex flex-col gap-3 px-4 py-3 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
            <span>{query && !data.pagination.total ? 'No matching records' : pageLabel}</span>
            <div className="flex items-center gap-2">
              <button type="button" disabled={data.pagination.page <= 1 || loading} onClick={() => setPage((value) => Math.max(1, value - 1))} className="clay-page-button"><ChevronLeft size={14} /> Previous</button>
              <span className="min-w-[74px] text-center font-semibold text-slate-700">Page {data.pagination.page} / {data.pagination.pages}</span>
              <button type="button" disabled={data.pagination.page >= data.pagination.pages || loading} onClick={() => setPage((value) => value + 1)} className="clay-page-button">Next <ChevronRight size={14} /></button>
            </div>
          </div>
        </>
      )}

      <RecordDetailsDialog open={Boolean(detailsRow)} title={rowTitle(detailsRow)} columns={data.columns} row={detailsRow} onClose={() => setDetailsRow(null)} />
      <ResourceFormDialog open={formOpen} schema={formSchema} loading={formLoading} errors={formErrors} onClose={() => { setFormOpen(false); setEditingRow(null); setFormErrors({}); }} onSubmit={submitForm} />
      <ConfirmActionDialog
        open={Boolean(deleteRow)}
        title={`${selectedDeleteLabel} record`}
        message={deleteMessage}
        confirmLabel={selectedDeleteLabel}
        loading={deleteLoading}
        onCancel={() => setDeleteRow(null)}
        onConfirm={() => void confirmDelete()}
      />
    </section>
  );
}
