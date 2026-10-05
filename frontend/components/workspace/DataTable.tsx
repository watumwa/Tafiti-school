'use client';

import { Download, Eye, MoreHorizontal, Pencil, Power, Search, SlidersHorizontal, Trash2 } from 'lucide-react';

import type { WorkspaceActions, WorkspaceColumn } from '@/lib/workspace';
import { ProfileAvatar } from './ProfileAvatar';

function displayValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return String(value);
}

function looksLikeStatus(key: string) {
  return ['status', 'verification', 'payment'].includes(key);
}

function statusClass(value: string) {
  const normalized = value.toLowerCase();
  if (['active', 'verified', 'paid', 'returned', 'allowed', 'enrolled', 'approved', 'settled', 'present', 'successful'].some((term) => normalized.includes(term))) {
    return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  }
  if (['pending', 'draft', 'open', 'on loan', 'progress', 'late', 'review'].some((term) => normalized.includes(term))) {
    return 'border-amber-200 bg-amber-50 text-amber-800';
  }
  if (['inactive', 'rejected', 'overdue', 'blocked', 'flagged', 'unpaid', 'absent', 'failed'].some((term) => normalized.includes(term))) {
    return 'border-rose-200 bg-rose-50 text-rose-700';
  }
  return 'border-slate-200 bg-slate-50 text-slate-600';
}

function rowName(row: Record<string, unknown>) {
  return String(row.name ?? row.student ?? row.title ?? row.application ?? 'Profile');
}

export function DataTable({
  columns,
  rows,
  query,
  actions,
  onQueryChange,
  onExport,
  onView,
  onEdit,
  onDelete,
}: {
  columns: WorkspaceColumn[];
  rows: Record<string, unknown>[];
  query: string;
  actions: WorkspaceActions;
  onQueryChange: (value: string) => void;
  onExport: () => void;
  onView: (row: Record<string, unknown>) => void;
  onEdit: (row: Record<string, unknown>) => void;
  onDelete: (row: Record<string, unknown>) => void;
}) {
  const hasRowActions = actions.view || actions.edit || actions.delete;

  return (
    <div className="tafiti-table-shell">
      <div className="flex flex-col gap-3 border-b border-[#E8EEF6] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-[360px]">
          <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#8A9AB2]" size={15} aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Search records..."
            className="tafiti-input h-9 w-full pl-9 pr-3 text-xs placeholder:text-[#9AA9BE]"
          />
        </div>
        <div className="flex items-center gap-2">
          <button type="button" disabled className="clay-button-secondary opacity-55" title="Advanced filters are added per module during workflow migration">
            <SlidersHorizontal size={14} /> Filters
          </button>
          <button type="button" onClick={onExport} className="clay-button-secondary">
            <Download size={14} /> Export
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[820px] border-collapse text-left">
          <thead>
            <tr className="border-b border-[#E8EEF6] bg-[#F8FAFE]">
              {columns.map((column) => (
                <th key={column.key} className="whitespace-nowrap px-4 py-2.5 text-[10px] font-bold uppercase tracking-[0.065em] text-[#73829A]">
                  {column.label}
                </th>
              ))}
              {hasRowActions && <th className="sticky right-0 whitespace-nowrap bg-[#F8FAFE] px-4 py-2.5 text-right text-[10px] font-bold uppercase tracking-[0.065em] text-[#73829A]">Actions</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#EDF1F7]">
            {rows.map((row, index) => (
              <tr key={String(row.id ?? index)} className="group bg-white transition-colors hover:bg-[#F7FAFF]">
                {columns.map((column) => {
                  const text = displayValue(row[column.key]);
                  const isPrimary = ['name', 'student', 'title', 'class', 'application', 'batch'].includes(column.key);
                  const content = looksLikeStatus(column.key) ? (
                    <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusClass(text)}`}>{text}</span>
                  ) : (
                    <span className={isPrimary ? 'font-semibold text-[#1C2F50]' : ''}>{text}</span>
                  );
                  return (
                    <td key={column.key} className={`${column.key === 'photo' ? 'w-[64px]' : 'max-w-[340px]'} px-4 py-2.5 text-xs text-[#52647F]`}>
                      {column.key === 'photo' ? (
                        actions.view ? <button type="button" onClick={() => onView(row)} aria-label={`Open ${rowName(row)}`} className="rounded-full"><ProfileAvatar src={row[column.key]} name={rowName(row)} size="sm" /></button> : <ProfileAvatar src={row[column.key]} name={rowName(row)} size="sm" />
                      ) : isPrimary && actions.view ? (
                        <button type="button" onClick={() => onView(row)} className="text-left transition hover:text-[#2563EB] hover:underline">{content}</button>
                      ) : (
                        content
                      )}
                    </td>
                  );
                })}
                {hasRowActions && (
                  <td className="sticky right-0 bg-white px-3 py-2 group-hover:bg-[#F7FAFF]">
                    <div className="flex items-center justify-end gap-1">
                      {actions.view && (
                        <button type="button" onClick={() => onView(row)} className="clay-row-action" title="View details" aria-label="View details"><Eye size={14} /></button>
                      )}
                      {actions.edit && typeof row.id === 'number' && (
                        <button type="button" onClick={() => onEdit(row)} className="clay-row-action" title={actions.edit_label} aria-label={actions.edit_label}><Pencil size={14} /></button>
                      )}
                      {actions.delete && typeof row.id === 'number' && (
                        <button type="button" onClick={() => onDelete(row)} className="clay-row-action clay-row-action-danger" title={actions.delete_label} aria-label={actions.delete_label}>
                          {actions.delete_mode === 'delete' ? <Trash2 size={14} /> : <Power size={14} />}
                        </button>
                      )}
                      {!actions.edit && !actions.delete && actions.view && (
                        <span className="clay-row-action text-[#71809A]" aria-hidden="true"><MoreHorizontal size={14} /></span>
                      )}
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
