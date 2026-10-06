'use client';

import { useEffect, useMemo, useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { Columns3, Download, Eye, MoreHorizontal, Pencil, Power, RotateCcw, Search, SlidersHorizontal, Trash2, X } from 'lucide-react';

import type { WorkspaceActions, WorkspaceColumn } from '@/lib/workspace';
import { ProfileAvatar } from './ProfileAvatar';

function displayValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return String(value);
}

function statusClass(value: string) {
  const normalized = value.toLowerCase();
  if (['active', 'verified', 'paid', 'returned', 'allowed', 'enrolled', 'approved', 'settled', 'present', 'successful', 'reconciled'].some((term) => normalized.includes(term))) return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  if (['pending', 'draft', 'open', 'on loan', 'progress', 'late', 'review', 'partial'].some((term) => normalized.includes(term))) return 'border-amber-200 bg-amber-50 text-amber-800';
  if (['inactive', 'rejected', 'overdue', 'blocked', 'flagged', 'unpaid', 'absent', 'failed', 'outstanding'].some((term) => normalized.includes(term))) return 'border-rose-200 bg-rose-50 text-rose-700';
  return 'border-slate-200 bg-slate-50 text-slate-600';
}

function looksLikeStatus(key: string) {
  return ['status', 'verification', 'payment', 'reconciliation'].includes(key);
}

function rowName(row: Record<string, unknown>) {
  return String(row.name ?? row.student ?? row.title ?? row.application ?? row.book ?? row.reference ?? 'Record');
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

export function DataTable({ columns, rows, query, actions, onQueryChange, onExport, onView, onEdit, onDelete }: {
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
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const tableKey = pathname.split('/').filter(Boolean).slice(-1)[0] || 'workspace';
  const hasRowActions = actions.view || actions.edit || actions.delete;
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [columnsOpen, setColumnsOpen] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [visibleKeys, setVisibleKeys] = useState<string[]>(columns.map((column) => column.key));

  useEffect(() => {
    const valid = new Set(columns.map((column) => column.key));
    try {
      const saved = window.localStorage.getItem(`tafiti-table-columns:${tableKey}`);
      const parsed = saved ? JSON.parse(saved) as string[] : [];
      const usable = parsed.filter((key) => valid.has(key));
      setVisibleKeys(usable.length ? usable : columns.map((column) => column.key));
    } catch {
      setVisibleKeys(columns.map((column) => column.key));
    }
    setSelected(new Set());
  }, [columns, tableKey]);

  const filters = useMemo(() => {
    const result: Record<string, string> = {};
    for (const [key, value] of searchParams.entries()) {
      if (key.startsWith('filter_') && value) result[key.slice(7)] = value;
    }
    return result;
  }, [searchParams]);

  const dateFilter = useMemo(() => ({
    key: searchParams.get('date_key') ?? '',
    from: searchParams.get('date_from') ?? '',
    to: searchParams.get('date_to') ?? '',
  }), [searchParams]);

  const visibleColumns = useMemo(() => columns.filter((column) => visibleKeys.includes(column.key)), [columns, visibleKeys]);
  const dateColumns = useMemo(() => columns.filter(isDateColumn), [columns]);
  const filterColumns = useMemo(() => columns.filter((column) => {
    if (column.key === 'photo' || isDateColumn(column)) return false;
    const values = new Set(rows.map((row) => displayValue(row[column.key])).filter((value) => value !== '—'));
    return preferredFilterKeys.has(column.key) || (values.size > 1 && values.size <= 20);
  }).slice(0, 8), [columns, rows]);
  const optionsByColumn = useMemo(() => Object.fromEntries(filterColumns.map((column) => [
    column.key,
    Array.from(new Set(rows.map((row) => displayValue(row[column.key])).filter((value) => value !== '—'))).sort((a, b) => a.localeCompare(b)),
  ])), [filterColumns, rows]);

  const selectedRows = useMemo(() => rows.filter((row, index) => selected.has(rowKey(row, index))), [rows, selected]);
  const numericRows = rows.map((row, index) => ({ row, index })).filter(({ row }) => typeof row.id === 'number');
  const allSelected = numericRows.length > 0 && numericRows.every(({ row, index }) => selected.has(rowKey(row, index)));
  const activeFilterCount = Object.values(filters).filter(Boolean).length + (dateFilter.from || dateFilter.to ? 1 : 0);

  function replaceParams(update: (params: URLSearchParams) => void) {
    const params = new URLSearchParams(searchParams.toString());
    update(params);
    params.delete('page');
    router.replace(`${pathname}${params.toString() ? `?${params.toString()}` : ''}`, { scroll: false });
  }

  function setFilter(key: string, value: string) {
    replaceParams((params) => {
      if (value) params.set(`filter_${key}`, value); else params.delete(`filter_${key}`);
    });
  }

  function setDateFilter(next: Partial<typeof dateFilter>) {
    const merged = { ...dateFilter, ...next };
    replaceParams((params) => {
      if (merged.key) params.set('date_key', merged.key); else params.delete('date_key');
      if (merged.from) params.set('date_from', merged.from); else params.delete('date_from');
      if (merged.to) params.set('date_to', merged.to); else params.delete('date_to');
    });
  }

  function clearFilters() {
    replaceParams((params) => {
      for (const key of Array.from(params.keys())) if (key.startsWith('filter_')) params.delete(key);
      params.delete('date_key'); params.delete('date_from'); params.delete('date_to');
    });
  }

  function persistColumns(next: string[]) {
    if (!next.length) return;
    setVisibleKeys(next);
    try { window.localStorage.setItem(`tafiti-table-columns:${tableKey}`, JSON.stringify(next)); } catch { /* storage unavailable */ }
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
    setSelected(allSelected ? new Set() : new Set(numericRows.map(({ row, index }) => rowKey(row, index))));
  }

  function exportSelected() {
    if (!selectedRows.length) return;
    const exportColumns = visibleColumns.filter((column) => column.key !== 'photo');
    const body = [
      exportColumns.map((column) => csvEscape(column.label)).join(','),
      ...selectedRows.map((row) => exportColumns.map((column) => csvEscape(row[column.key])).join(',')),
    ].join('\n');
    const blob = new Blob([body], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url; anchor.download = `${tableKey}-selected.csv`; anchor.click(); URL.revokeObjectURL(url);
  }

  function renderValue(row: Record<string, unknown>, column: WorkspaceColumn) {
    const text = displayValue(row[column.key]);
    const primary = ['name', 'student', 'title', 'class', 'application', 'batch', 'book', 'reference'].includes(column.key);
    if (column.key === 'photo') return <ProfileAvatar src={row[column.key]} name={rowName(row)} size="sm" />;
    if (looksLikeStatus(column.key)) return <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusClass(text)}`}>{text}</span>;
    return <span className={primary ? 'font-semibold text-[#1C2F50]' : ''}>{text}</span>;
  }

  return <div className="tafiti-table-shell">
    <div className="flex flex-col gap-3 border-b border-[#E8EEF6] px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
      <div className="relative w-full lg:max-w-[390px]"><Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#8A9AB2]" size={15} /><input type="search" value={query} onChange={(event) => onQueryChange(event.target.value)} placeholder="Search records..." className="tafiti-input h-9 w-full pl-9 pr-3 text-xs placeholder:text-[#9AA9BE]" /></div>
      <div className="flex flex-wrap items-center gap-2"><button type="button" onClick={() => { setFiltersOpen((value) => !value); setColumnsOpen(false); }} className={`clay-button-secondary ${filtersOpen || activeFilterCount ? '!border-blue-200 !text-blue-700' : ''}`}><SlidersHorizontal size={14} /> Filters{activeFilterCount > 0 && <span className="rounded-full bg-blue-600 px-1.5 py-0.5 text-[9px] text-white">{activeFilterCount}</span>}</button><button type="button" onClick={() => { setColumnsOpen((value) => !value); setFiltersOpen(false); }} className={`clay-button-secondary ${columnsOpen ? '!border-blue-200 !text-blue-700' : ''}`}><Columns3 size={14} /> Columns</button><button type="button" onClick={onExport} className="clay-button-secondary"><Download size={14} /> Export</button></div>
    </div>

    {filtersOpen && <div className="border-b border-[#E8EEF6] bg-[#FBFCFE] px-4 py-4"><div className="flex items-center justify-between gap-3"><div><p className="text-[10px] font-extrabold uppercase tracking-[.07em] text-slate-500">Advanced filters</p><p className="mt-1 text-[10px] text-slate-400">Filter state is saved in the page URL.</p></div>{activeFilterCount > 0 && <button type="button" onClick={clearFilters} className="inline-flex items-center gap-1 text-[10px] font-bold text-blue-600"><RotateCcw size={12} /> Reset</button>}</div><div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{filterColumns.map((column) => { const options = optionsByColumn[column.key] ?? []; const value = filters[column.key] ?? ''; return <label key={column.key}><span className="mb-1 block text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">{column.label}</span>{options.length > 1 && options.length <= 20 ? <select value={value} onChange={(event) => setFilter(column.key, event.target.value)} className="tafiti-input h-9 w-full px-2.5 text-xs"><option value="">All</option>{options.map((option) => <option key={option} value={option}>{option}</option>)}</select> : <input value={value} onChange={(event) => setFilter(column.key, event.target.value)} placeholder={`Filter ${column.label.toLowerCase()}…`} className="tafiti-input h-9 w-full px-2.5 text-xs" />}</label>; })}{dateColumns.length > 0 && <><label><span className="mb-1 block text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">Date field</span><select value={dateFilter.key || dateColumns[0].key} onChange={(event) => setDateFilter({ key: event.target.value })} className="tafiti-input h-9 w-full px-2.5 text-xs">{dateColumns.map((column) => <option key={column.key} value={column.key}>{column.label}</option>)}</select></label><label><span className="mb-1 block text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">From</span><input type="date" value={dateFilter.from} onChange={(event) => setDateFilter({ key: dateFilter.key || dateColumns[0].key, from: event.target.value })} className="tafiti-input h-9 w-full px-2.5 text-xs" /></label><label><span className="mb-1 block text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">To</span><input type="date" value={dateFilter.to} onChange={(event) => setDateFilter({ key: dateFilter.key || dateColumns[0].key, to: event.target.value })} className="tafiti-input h-9 w-full px-2.5 text-xs" /></label></>}{!filterColumns.length && !dateColumns.length && <p className="col-span-full py-2 text-xs text-slate-400">Use search for this table; there are no useful categorical or date fields to filter.</p>}</div></div>}

    {columnsOpen && <div className="border-b border-[#E8EEF6] bg-[#FBFCFE] px-4 py-4"><div className="flex items-center justify-between"><div><p className="text-[10px] font-extrabold uppercase tracking-[.07em] text-slate-500">Visible columns</p><p className="mt-1 text-[10px] text-slate-400">Saved on this device for this module.</p></div><button type="button" onClick={() => persistColumns(columns.map((column) => column.key))} className="text-[10px] font-bold text-blue-600">Show all</button></div><div className="mt-3 flex flex-wrap gap-2">{columns.map((column) => { const checked = visibleKeys.includes(column.key); return <label key={column.key} className={`inline-flex cursor-pointer items-center gap-2 rounded-lg border px-2.5 py-2 text-[10px] font-bold ${checked ? 'border-blue-200 bg-blue-50 text-blue-700' : 'border-slate-200 bg-white text-slate-500'}`}><input type="checkbox" checked={checked} onChange={() => persistColumns(checked ? visibleKeys.filter((key) => key !== column.key) : [...visibleKeys, column.key])} className="h-3.5 w-3.5 accent-blue-600" />{column.label}</label>; })}</div></div>}

    {selectedRows.length > 0 && <div className="flex flex-wrap items-center gap-2 border-b border-blue-100 bg-blue-50/70 px-4 py-2.5 text-[10px] font-bold text-blue-800"><span>{selectedRows.length} selected</span><button type="button" onClick={exportSelected} className="clay-button-secondary !h-8"><Download size={13} /> Export selected</button><button type="button" onClick={() => setSelected(new Set())} className="ml-auto inline-flex items-center gap-1 text-slate-500"><X size={12} /> Clear</button></div>}

    <div className="hidden overflow-x-auto lg:block"><table className="w-full min-w-[820px] border-collapse text-left"><thead><tr className="border-b border-[#E8EEF6] bg-[#F8FAFE]"><th className="w-10 px-3 py-2.5"><input type="checkbox" checked={allSelected} onChange={toggleAll} disabled={!numericRows.length} aria-label="Select all rows" className="h-3.5 w-3.5 accent-blue-600" /></th>{visibleColumns.map((column) => <th key={column.key} className="whitespace-nowrap px-4 py-2.5 text-[10px] font-bold uppercase tracking-[0.065em] text-[#73829A]">{column.label}</th>)}{hasRowActions && <th className="sticky right-0 bg-[#F8FAFE] px-4 py-2.5 text-right text-[10px] font-bold uppercase tracking-[0.065em] text-[#73829A]">Actions</th>}</tr></thead><tbody className="divide-y divide-[#EDF1F7]">{rows.map((row, index) => { const key = rowKey(row, index); const checked = selected.has(key); return <tr key={key} className={`group ${checked ? 'bg-blue-50/55' : 'bg-white hover:bg-[#F7FAFF]'}`}><td className="px-3 py-2.5"><input type="checkbox" checked={checked} onChange={() => toggleRow(row, index)} disabled={typeof row.id !== 'number'} className="h-3.5 w-3.5 accent-blue-600" /></td>{visibleColumns.map((column) => <td key={column.key} className={`${column.key === 'photo' ? 'w-[64px]' : 'max-w-[340px]'} px-4 py-2.5 text-xs text-[#52647F]`}>{column.key === 'photo' && actions.view ? <button type="button" onClick={() => onView(row)}>{renderValue(row, column)}</button> : ['name', 'student', 'title', 'class', 'application', 'batch', 'book', 'reference'].includes(column.key) && actions.view ? <button type="button" onClick={() => onView(row)} className="text-left hover:text-blue-600 hover:underline">{renderValue(row, column)}</button> : renderValue(row, column)}</td>)}{hasRowActions && <td className={`sticky right-0 px-3 py-2 ${checked ? 'bg-blue-50/90' : 'bg-white group-hover:bg-[#F7FAFF]'}`}><div className="flex items-center justify-end gap-1">{actions.view && <button type="button" onClick={() => onView(row)} className="clay-row-action"><Eye size={14} /></button>}{actions.edit && typeof row.id === 'number' && <button type="button" onClick={() => onEdit(row)} className="clay-row-action"><Pencil size={14} /></button>}{actions.delete && typeof row.id === 'number' && <button type="button" onClick={() => onDelete(row)} className="clay-row-action clay-row-action-danger">{actions.delete_mode === 'delete' ? <Trash2 size={14} /> : <Power size={14} />}</button>}{!actions.edit && !actions.delete && actions.view && <span className="clay-row-action"><MoreHorizontal size={14} /></span>}</div></td>}</tr>; })}{!rows.length && <tr><td colSpan={visibleColumns.length + (hasRowActions ? 2 : 1)} className="px-4 py-12 text-center text-xs text-slate-400">No records match the current search and filters.</td></tr>}</tbody></table></div>

    <div className="divide-y divide-slate-100 lg:hidden">{rows.map((row, index) => { const key = rowKey(row, index); const checked = selected.has(key); const photo = columns.find((column) => column.key === 'photo'); const primary = visibleColumns.find((column) => ['name', 'student', 'title', 'application', 'book', 'reference', 'class'].includes(column.key)) ?? visibleColumns[0]; const details = visibleColumns.filter((column) => column.key !== 'photo' && column.key !== primary?.key && column.key !== 'status').slice(0, 4); return <article key={key} className={`p-4 ${checked ? 'bg-blue-50/60' : 'bg-white'}`}><div className="flex items-start gap-3"><input type="checkbox" checked={checked} onChange={() => toggleRow(row, index)} disabled={typeof row.id !== 'number'} className="mt-2 h-4 w-4 shrink-0 accent-blue-600" />{photo && <div className="shrink-0">{renderValue(row, photo)}</div>}<div className="min-w-0 flex-1"><div className="flex items-start justify-between gap-2"><div className="min-w-0"><p className="truncate text-sm font-extrabold text-[#10224A]">{primary ? displayValue(row[primary.key]) : rowName(row)}</p>{primary && <p className="mt-0.5 text-[9px] font-bold uppercase tracking-[.05em] text-slate-400">{primary.label}</p>}</div>{row.status ? <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[9px] font-bold ${statusClass(displayValue(row.status))}`}>{displayValue(row.status)}</span> : null}</div><div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2">{details.map((column) => <div key={column.key} className="min-w-0"><p className="text-[8px] font-bold uppercase tracking-[.05em] text-slate-400">{column.label}</p><div className="mt-0.5 truncate text-[10px] font-semibold text-slate-600">{renderValue(row, column)}</div></div>)}</div>{hasRowActions && <div className="mt-3 flex flex-wrap gap-1.5">{actions.view && <button type="button" onClick={() => onView(row)} className="clay-button-secondary !h-8 !px-2.5"><Eye size={13} /> View</button>}{actions.edit && typeof row.id === 'number' && <button type="button" onClick={() => onEdit(row)} className="clay-button-secondary !h-8 !px-2.5"><Pencil size={13} /> {actions.edit_label}</button>}{actions.delete && typeof row.id === 'number' && <button type="button" onClick={() => onDelete(row)} className="clay-button-secondary !h-8 !border-rose-200 !px-2.5 !text-rose-700">{actions.delete_mode === 'delete' ? <Trash2 size={13} /> : <Power size={13} />} {actions.delete_label}</button>}</div>}</div></div></article>; })}{!rows.length && <div className="px-4 py-12 text-center text-xs text-slate-400">No records match the current search and filters.</div>}</div>
  </div>;
}
