'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  Columns3,
  Download,
  Eye,
  MoreHorizontal,
  Pencil,
  Power,
  RotateCcw,
  Search,
  SlidersHorizontal,
  Trash2,
  X,
} from 'lucide-react';

import type { WorkspaceActions, WorkspaceColumn } from '@/lib/workspace';
import { ProfileAvatar } from './ProfileAvatar';

function displayValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return String(value);
}

function looksLikeStatus(key: string) {
  return ['status', 'verification', 'payment', 'reconciliation'].includes(key);
}

function statusClass(value: string) {
  const normalized = value.toLowerCase();
  if (['active', 'verified', 'paid', 'returned', 'allowed', 'enrolled', 'approved', 'settled', 'present', 'successful', 'reconciled'].some((term) => normalized.includes(term))) {
    return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  }
  if (['pending', 'draft', 'open', 'on loan', 'progress', 'late', 'review', 'partial'].some((term) => normalized.includes(term))) {
    return 'border-amber-200 bg-amber-50 text-amber-800';
  }
  if (['inactive', 'rejected', 'overdue', 'blocked', 'flagged', 'unpaid', 'absent', 'failed', 'outstanding'].some((term) => normalized.includes(term))) {
    return 'border-rose-200 bg-rose-50 text-rose-700';
  }
  return 'border-slate-200 bg-slate-50 text-slate-600';
}

function rowName(row: Record<string, unknown>) {
  return String(row.name ?? row.student ?? row.title ?? row.application ?? row.book ?? row.reference ?? 'Profile');
}

function rowKey(row: Record<string, unknown>, index: number) {
  return String(row.id ?? `${rowName(row)}-${index}`);
}

function isDateColumn(column: WorkspaceColumn) {
  const key = column.key.toLowerCase();
  return ['date', 'time', 'updated', 'issued', 'due', 'returned', 'when'].some((hint) => key.includes(hint));
}

function csvEscape(value: unknown) {
  const text = value === null || value === undefined ? '' : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

const preferredFilterKeys = new Set([
  'status', 'class', 'stream', 'term', 'year', 'department', 'roles', 'gender', 'type', 'subject',
  'teacher', 'method', 'category', 'reconciliation', 'section', 'day', 'assessment', 'grade',
  'borrower_type', 'audience', 'priority',
]);

export function DataTable({
  tableKey,
  columns,
  rows,
  query,
  actions,
  filters,
  dateFilter,
  bulkLoading = false,
  onQueryChange,
  onFiltersChange,
  onDateFilterChange,
  onExport,
  onView,
  onEdit,
  onDelete,
  onBulkDelete,
}: {
  tableKey: string;
  columns: WorkspaceColumn[];
  rows: Record<string, unknown>[];
  query: string;
  actions: WorkspaceActions;
  filters: Record<string, string>;
  dateFilter: { key: string; from: string; to: string };
  bulkLoading?: boolean;
  onQueryChange: (value: string) => void;
  onFiltersChange: (next: Record<string, string>) => void;
  onDateFilterChange: (next: { key: string; from: string; to: string }) => void;
  onExport: () => void;
  onView: (row: Record<string, unknown>) => void;
  onEdit: (row: Record<string, unknown>) => void;
  onDelete: (row: Record<string, unknown>) => void;
  onBulkDelete?: (rows: Record<string, unknown>[]) => void;
}) {
  const hasRowActions = actions.view || actions.edit || actions.delete;
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [columnsOpen, setColumnsOpen] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [visibleKeys, setVisibleKeys] = useState<string[]>(columns.map((column) => column.key));

  useEffect(() => {
    const validKeys = new Set(columns.map((column) => column.key));
    try {
      const saved = window.localStorage.getItem(`tafiti-table-columns:${tableKey}`);
      const parsed = saved ? JSON.parse(saved) as string[] : [];
      const next = parsed.filter((key) => validKeys.has(key));
      setVisibleKeys(next.length ? next : columns.map((column) => column.key));
    } catch {
      setVisibleKeys(columns.map((column) => column.key));
    }
    setSelected(new Set());
  }, [columns, tableKey]);

  const visibleColumns = useMemo(
    () => columns.filter((column) => visibleKeys.includes(column.key)),
    [columns, visibleKeys],
  );

  const dateColumns = useMemo(() => columns.filter(isDateColumn), [columns]);

  const filterColumns = useMemo(() => columns.filter((column) => {
    if (column.key === 'photo' || isDateColumn(column)) return false;
    const values = new Set(rows.map((row) => displayValue(row[column.key])).filter((value) => value !== '—'));
    return preferredFilterKeys.has(column.key) || (values.size > 1 && values.size <= 20);
  }).slice(0, 8), [columns, rows]);

  const optionsByColumn = useMemo(() => {
    const result: Record<string, string[]> = {};
    for (const column of filterColumns) {
      result[column.key] = Array.from(new Set(
        rows.map((row) => displayValue(row[column.key])).filter((value) => value !== '—'),
      )).sort((a, b) => a.localeCompare(b));
    }
    return result;
  }, [filterColumns, rows]);

  const selectedRows = useMemo(() => rows.filter((row, index) => selected.has(rowKey(row, index))), [rows, selected]);
  const selectableRows = rows.filter((row) => typeof row.id === 'number');
  const allSelected = selectableRows.length > 0 && selectableRows.every((row, index) => selected.has(rowKey(row, rows.indexOf(row)) || String(index)));
  const activeFilterCount = Object.values(filters).filter(Boolean).length + (dateFilter.from || dateFilter.to ? 1 : 0);

  function persistColumns(next: string[]) {
    setVisibleKeys(next);
    try { window.localStorage.setItem(`tafiti-table-columns:${tableKey}`, JSON.stringify(next)); } catch { /* ignore storage restrictions */ }
  }

  function toggleColumn(key: string) {
    const next = visibleKeys.includes(key) ? visibleKeys.filter((item) => item !== key) : [...visibleKeys, key];
    if (!next.length) return;
    persistColumns(next);
  }

  function toggleRow(row: Record<string, unknown>, index: number) {
    const key = rowKey(row, index);
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }

  function toggleAll() {
    if (allSelected) {
      setSelected(new Set());
      return;
    }
    setSelected(new Set(rows.map((row, index) => typeof row.id === 'number' ? rowKey(row, index) : '').filter(Boolean)));
  }

  function exportSelected() {
    if (!selectedRows.length) return;
    const exportColumns = visibleColumns.filter((column) => column.key !== 'photo');
    const lines = [
      exportColumns.map((column) => csvEscape(column.label)).join(','),
      ...selectedRows.map((row) => exportColumns.map((column) => csvEscape(row[column.key])).join(',')),
    ];
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${tableKey}-selected.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function clearAdvancedFilters() {
    onFiltersChange({});
    onDateFilterChange({ key: dateColumns[0]?.key ?? '', from: '', to: '' });
  }

  function renderValue(row: Record<string, unknown>, column: WorkspaceColumn) {
    const text = displayValue(row[column.key]);
    const primary = ['name', 'student', 'title', 'class', 'application', 'batch', 'book', 'reference'].includes(column.key);
    if (column.key === 'photo') {
      return <ProfileAvatar src={row[column.key]} name={rowName(row)} size="sm" />;
    }
    if (looksLikeStatus(column.key)) {
      return <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusClass(text)}`}>{text}</span>;
    }
    return <span className={primary ? 'font-semibold text-[#1C2F50]' : ''}>{text}</span>;
  }

  return (
    <div className="tafiti-table-shell">
      <div className="flex flex-col gap-3 border-b border-[#E8EEF6] px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="relative w-full lg:max-w-[390px]">
          <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#8A9AB2]" size={15} aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Search records..."
            className="tafiti-input h-9 w-full pl-9 pr-3 text-xs placeholder:text-[#9AA9BE]"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={() => { setFiltersOpen((value) => !value); setColumnsOpen(false); }} className={`clay-button-secondary ${filtersOpen || activeFilterCount ? '!border-blue-200 !text-blue-700' : ''}`}>
            <SlidersHorizontal size={14} /> Filters{activeFilterCount > 0 && <span className="rounded-full bg-blue-600 px-1.5 py-0.5 text-[9px] text-white">{activeFilterCount}</span>}
          </button>
          <button type="button" onClick={() => { setColumnsOpen((value) => !value); setFiltersOpen(false); }} className={`clay-button-secondary ${columnsOpen ? '!border-blue-200 !text-blue-700' : ''}`}>
            <Columns3 size={14} /> Columns
          </button>
          <button type="button" onClick={onExport} className="clay-button-secondary"><Download size={14} /> Export</button>
        </div>
      </div>

      {filtersOpen && (
        <div className="border-b border-[#E8EEF6] bg-[#FBFCFE] px-4 py-4">
          <div className="flex items-center justify-between gap-3"><div><p className="text-[10px] font-extrabold uppercase tracking-[.07em] text-slate-500">Advanced filters</p><p className="mt-1 text-[10px] text-slate-400">Filters stay in the URL so this exact view can be revisited or shared.</p></div>{activeFilterCount > 0 && <button type="button" onClick={clearAdvancedFilters} className="inline-flex items-center gap-1 text-[10px] font-bold text-blue-600"><RotateCcw size={12} /> Reset</button>}</div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {filterColumns.map((column) => {
              const options = optionsByColumn[column.key] ?? [];
              const value = filters[column.key] ?? '';
              return <label key={column.key} className="block"><span className="mb-1 block text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">{column.label}</span>{options.length > 1 && options.length <= 20 ? <select value={value} onChange={(event) => onFiltersChange({ ...filters, [column.key]: event.target.value })} className="tafiti-input h-9 w-full px-2.5 text-xs"><option value="">All</option>{options.map((option) => <option key={option} value={option}>{option}</option>)}</select> : <input value={value} onChange={(event) => onFiltersChange({ ...filters, [column.key]: event.target.value })} placeholder={`Filter ${column.label.toLowerCase()}…`} className="tafiti-input h-9 w-full px-2.5 text-xs" />}</label>;
            })}
            {dateColumns.length > 0 && <><label className="block"><span className="mb-1 block text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">Date field</span><select value={dateFilter.key || dateColumns[0].key} onChange={(event) => onDateFilterChange({ ...dateFilter, key: event.target.value })} className="tafiti-input h-9 w-full px-2.5 text-xs">{dateColumns.map((column) => <option key={column.key} value={column.key}>{column.label}</option>)}</select></label><label className="block"><span className="mb-1 block text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">From</span><input type="date" value={dateFilter.from} onChange={(event) => onDateFilterChange({ ...dateFilter, key: dateFilter.key || dateColumns[0].key, from: event.target.value })} className="tafiti-input h-9 w-full px-2.5 text-xs" /></label><label className="block"><span className="mb-1 block text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">To</span><input type="date" value={dateFilter.to} onChange={(event) => onDateFilterChange({ ...dateFilter, key: dateFilter.key || dateColumns[0].key, to: event.target.value })} className="tafiti-input h-9 w-full px-2.5 text-xs" /></label></>}
            {!filterColumns.length && !dateColumns.length && <p className="col-span-full py-2 text-xs text-slate-400">Use the search box for this table; it does not contain categorical or date fields that benefit from advanced filters.</p>}
          </div>
        </div>
      )}

      {columnsOpen && (
        <div className="border-b border-[#E8EEF6] bg-[#FBFCFE] px-4 py-4">
          <div className="flex items-center justify-between"><div><p className="text-[10px] font-extrabold uppercase tracking-[.07em] text-slate-500">Visible columns</p><p className="mt-1 text-[10px] text-slate-400">Your choice is saved on this device for this module.</p></div><button type="button" onClick={() => persistColumns(columns.map((column) => column.key))} className="text-[10px] font-bold text-blue-600">Show all</button></div>
          <div className="mt-3 flex flex-wrap gap-2">{columns.map((column) => { const checked = visibleKeys.includes(column.key); return <label key={column.key} className={`inline-flex cursor-pointer items-center gap-2 rounded-lg border px-2.5 py-2 text-[10px] font-bold ${checked ? 'border-blue-200 bg-blue-50 text-blue-700' : 'border-slate-200 bg-white text-slate-500'}`}><input type="checkbox" checked={checked} onChange={() => toggleColumn(column.key)} className="h-3.5 w-3.5 accent-blue-600" />{column.label}</label>; })}</div>
        </div>
      )}

      {selectedRows.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 border-b border-blue-100 bg-blue-50/70 px-4 py-2.5 text-[10px] font-bold text-blue-800">
          <span>{selectedRows.length} selected</span>
          <button type="button" onClick={exportSelected} className="clay-button-secondary !h-8"><Download size={13} /> Export selected</button>
          {actions.delete && onBulkDelete && selectedRows.every((row) => typeof row.id === 'number') && <button type="button" disabled={bulkLoading} onClick={() => onBulkDelete(selectedRows)} className="clay-button-secondary !h-8 !border-rose-200 !text-rose-700">{actions.delete_mode === 'delete' ? <Trash2 size={13} /> : <Power size={13} />} {actions.delete_label} selected</button>}
          <button type="button" onClick={() => setSelected(new Set())} className="ml-auto inline-flex items-center gap-1 text-slate-500"><X size={12} /> Clear</button>
        </div>
      )}

      <div className="hidden overflow-x-auto lg:block">
        <table className="w-full min-w-[820px] border-collapse text-left">
          <thead><tr className="border-b border-[#E8EEF6] bg-[#F8FAFE]"><th className="w-10 px-3 py-2.5"><input type="checkbox" checked={allSelected} onChange={toggleAll} disabled={!selectableRows.length} aria-label="Select all rows" className="h-3.5 w-3.5 accent-blue-600" /></th>{visibleColumns.map((column) => <th key={column.key} className="whitespace-nowrap px-4 py-2.5 text-[10px] font-bold uppercase tracking-[0.065em] text-[#73829A]">{column.label}</th>)}{hasRowActions && <th className="sticky right-0 whitespace-nowrap bg-[#F8FAFE] px-4 py-2.5 text-right text-[10px] font-bold uppercase tracking-[0.065em] text-[#73829A]">Actions</th>}</tr></thead>
          <tbody className="divide-y divide-[#EDF1F7]">{rows.map((row, index) => { const key = rowKey(row, index); const checked = selected.has(key); return <tr key={key} className={`group transition-colors ${checked ? 'bg-blue-50/55' : 'bg-white hover:bg-[#F7FAFF]'}`}><td className="px-3 py-2.5"><input type="checkbox" checked={checked} onChange={() => toggleRow(row, index)} disabled={typeof row.id !== 'number'} aria-label={`Select ${rowName(row)}`} className="h-3.5 w-3.5 accent-blue-600" /></td>{visibleColumns.map((column) => <td key={column.key} className={`${column.key === 'photo' ? 'w-[64px]' : 'max-w-[340px]'} px-4 py-2.5 text-xs text-[#52647F]`}>{column.key === 'photo' && actions.view ? <button type="button" onClick={() => onView(row)} className="rounded-full">{renderValue(row, column)}</button> : ['name', 'student', 'title', 'class', 'application', 'batch', 'book', 'reference'].includes(column.key) && actions.view ? <button type="button" onClick={() => onView(row)} className="text-left transition hover:text-blue-600 hover:underline">{renderValue(row, column)}</button> : renderValue(row, column)}</td>)}{hasRowActions && <td className={`sticky right-0 px-3 py-2 ${checked ? 'bg-blue-50/90' : 'bg-white group-hover:bg-[#F7FAFF]'}`}><div className="flex items-center justify-end gap-1">{actions.view && <button type="button" onClick={() => onView(row)} className="clay-row-action" title="View details"><Eye size={14} /></button>}{actions.edit && typeof row.id === 'number' && <button type="button" onClick={() => onEdit(row)} className="clay-row-action" title={actions.edit_label}><Pencil size={14} /></button>}{actions.delete && typeof row.id === 'number' && <button type="button" onClick={() => onDelete(row)} className="clay-row-action clay-row-action-danger" title={actions.delete_label}>{actions.delete_mode === 'delete' ? <Trash2 size={14} /> : <Power size={14} />}</button>}{!actions.edit && !actions.delete && actions.view && <span className="clay-row-action text-[#71809A]" aria-hidden="true"><MoreHorizontal size={14} /></span>}</div></td>}</tr>; })}{!rows.length && <tr><td colSpan={visibleColumns.length + (hasRowActions ? 2 : 1)} className="px-4 py-12 text-center text-xs text-slate-400">No records match the current search and filters.</td></tr>}</tbody>
        </table>
      </div>

      <div className="divide-y divide-slate-100 lg:hidden">
        {rows.map((row, index) => {
          const key = rowKey(row, index);
          const checked = selected.has(key);
          const photo = columns.find((column) => column.key === 'photo');
          const primary = visibleColumns.find((column) => ['name', 'student', 'title', 'application', 'book', 'reference', 'class'].includes(column.key)) ?? visibleColumns[0];
          const details = visibleColumns.filter((column) => column.key !== 'photo' && column.key !== primary?.key).slice(0, 4);
          return <article key={key} className={`p-4 ${checked ? 'bg-blue-50/60' : 'bg-white'}`}><div className="flex items-start gap-3"><input type="checkbox" checked={checked} onChange={() => toggleRow(row, index)} disabled={typeof row.id !== 'number'} aria-label={`Select ${rowName(row)}`} className="mt-2 h-4 w-4 shrink-0 accent-blue-600" />{photo && <div className="shrink-0">{renderValue(row, photo)}</div>}<div className="min-w-0 flex-1"><div className="flex items-start justify-between gap-2"><div className="min-w-0"><p className="truncate text-sm font-extrabold text-[#10224A]">{primary ? displayValue(row[primary.key]) : rowName(row)}</p>{primary && <p className="mt-0.5 text-[9px] font-bold uppercase tracking-[.05em] text-slate-400">{primary.label}</p>}</div>{looksLikeStatus('status') && row.status ? <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[9px] font-bold ${statusClass(displayValue(row.status))}`}>{displayValue(row.status)}</span> : null}</div><div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2">{details.map((column) => <div key={column.key} className="min-w-0"><p className="text-[8px] font-bold uppercase tracking-[.05em] text-slate-400">{column.label}</p><div className="mt-0.5 truncate text-[10px] font-semibold text-slate-600">{renderValue(row, column)}</div></div>)}</div>{hasRowActions && <div className="mt-3 flex flex-wrap gap-1.5">{actions.view && <button type="button" onClick={() => onView(row)} className="clay-button-secondary !h-8 !px-2.5"><Eye size={13} /> View</button>}{actions.edit && typeof row.id === 'number' && <button type="button" onClick={() => onEdit(row)} className="clay-button-secondary !h-8 !px-2.5"><Pencil size={13} /> {actions.edit_label}</button>}{actions.delete && typeof row.id === 'number' && <button type="button" onClick={() => onDelete(row)} className="clay-button-secondary !h-8 !border-rose-200 !px-2.5 !text-rose-700">{actions.delete_mode === 'delete' ? <Trash2 size={13} /> : <Power size={13} />} {actions.delete_label}</button>}</div>}</div></div></article>;
        })}
        {!rows.length && <div className="px-4 py-12 text-center text-xs text-slate-400">No records match the current search and filters.</div>}
      </div>
    </div>
  );
}
