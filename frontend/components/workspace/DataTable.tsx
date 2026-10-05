'use client';

import { Download, Eye, Pencil, Power, Search, SlidersHorizontal, Trash2 } from 'lucide-react';

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
  if (['active', 'verified', 'paid', 'returned', 'allowed', 'enrolled', 'approved', 'settled'].some((term) => normalized.includes(term))) {
    return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  }
  if (['pending', 'draft', 'open', 'on loan', 'progress'].some((term) => normalized.includes(term))) {
    return 'border-amber-200 bg-amber-50 text-amber-800';
  }
  if (['inactive', 'rejected', 'overdue', 'blocked', 'flagged', 'unpaid'].some((term) => normalized.includes(term))) {
    return 'border-red-200 bg-red-50 text-red-700';
  }
  return 'border-slate-200 bg-slate-50 text-slate-600';
}

function rowName(row: Record<string, unknown>) {
  return String(row.name ?? row.student ?? row.title ?? 'Profile');
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
    <div className="clay-panel overflow-hidden">
      <div className="flex flex-col gap-3 border-b border-slate-200/70 px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between sm:px-5">
        <div className="relative w-full sm:max-w-[380px]">
          <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Search this module…"
            className="h-10 w-full rounded-xl border border-slate-200 bg-white/85 pl-9 pr-3 text-sm text-slate-900 outline-none transition focus:border-[#2C5D8A] focus:bg-white focus:ring-4 focus:ring-[#2C5D8A]/10"
          />
        </div>
        <div className="flex items-center gap-2">
          <button type="button" disabled className="clay-button-secondary opacity-55" title="Advanced filters are added per module during workflow migration">
            <SlidersHorizontal size={15} /> Filters
          </button>
          <button type="button" onClick={onExport} className="clay-button-secondary">
            <Download size={15} /> Export CSV
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[820px] border-collapse text-left">
          <thead>
            <tr className="border-b border-slate-200/70 bg-[#F4F7FB]/80">
              {columns.map((column) => (
                <th key={column.key} className="whitespace-nowrap px-5 py-3 text-[11px] font-bold uppercase tracking-[0.08em] text-slate-500">
                  {column.label}
                </th>
              ))}
              {hasRowActions && <th className="sticky right-0 whitespace-nowrap bg-[#F4F7FB]/95 px-5 py-3 text-right text-[11px] font-bold uppercase tracking-[0.08em] text-slate-500">Actions</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100/90">
            {rows.map((row, index) => (
              <tr key={String(row.id ?? index)} className="group transition-colors hover:bg-[#F7FAFD]/90">
                {columns.map((column) => {
                  const text = displayValue(row[column.key]);
                  return (
                    <td key={column.key} className={`${column.key === 'photo' ? 'w-[76px]' : 'max-w-[360px]'} px-5 py-3.5 text-sm text-slate-700`}>
                      {column.key === 'photo' ? (
                        <ProfileAvatar src={row[column.key]} name={rowName(row)} size="md" />
                      ) : looksLikeStatus(column.key) ? (
                        <span className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold ${statusClass(text)}`}>{text}</span>
                      ) : (
                        <span className={column.key === 'name' || column.key === 'student' || column.key === 'title' || column.key === 'class' ? 'font-semibold text-slate-900' : ''}>{text}</span>
                      )}
                    </td>
                  );
                })}
                {hasRowActions && (
                  <td className="sticky right-0 bg-white/95 px-4 py-2.5 group-hover:bg-[#F7FAFD]/95">
                    <div className="flex items-center justify-end gap-1.5">
                      {actions.view && (
                        <button type="button" onClick={() => onView(row)} className="clay-row-action" title="View details" aria-label="View details"><Eye size={15} /></button>
                      )}
                      {actions.edit && typeof row.id === 'number' && (
                        <button type="button" onClick={() => onEdit(row)} className="clay-row-action" title={actions.edit_label} aria-label={actions.edit_label}><Pencil size={15} /></button>
                      )}
                      {actions.delete && typeof row.id === 'number' && (
                        <button type="button" onClick={() => onDelete(row)} className="clay-row-action clay-row-action-danger" title={actions.delete_label} aria-label={actions.delete_label}>
                          {actions.delete_mode === 'delete' ? <Trash2 size={15} /> : <Power size={15} />}
                        </button>
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
