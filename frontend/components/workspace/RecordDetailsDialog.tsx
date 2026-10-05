'use client';

import { X } from 'lucide-react';

import type { WorkspaceColumn } from '@/lib/workspace';
import { ProfileAvatar } from './ProfileAvatar';

function display(value: unknown) {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return String(value);
}

export function RecordDetailsDialog({
  open,
  title,
  columns,
  row,
  onClose,
}: {
  open: boolean;
  title: string;
  columns: WorkspaceColumn[];
  row: Record<string, unknown> | null;
  onClose: () => void;
}) {
  if (!open || !row) return null;
  const photoColumn = columns.find((column) => column.key === 'photo');
  const detailColumns = columns.filter((column) => column.key !== 'photo');

  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center bg-[#07172B]/45 p-3 backdrop-blur-[3px] sm:p-6">
      <button type="button" aria-label="Close details" className="absolute inset-0" onClick={onClose} />
      <div className="clay-dialog relative z-10 w-full max-w-2xl overflow-hidden">
        <div className="flex items-center justify-between border-b border-slate-200/70 px-5 py-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-4">
            {photoColumn && <ProfileAvatar src={row[photoColumn.key]} name={title} size="lg" />}
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#2C5D8A]">Record details</p>
              <h2 className="mt-1 truncate text-xl font-semibold text-[#0B1F3A]">{title}</h2>
            </div>
          </div>
          <button type="button" onClick={onClose} className="clay-icon-button" aria-label="Close"><X size={18} /></button>
        </div>
        <div className="grid max-h-[70vh] grid-cols-1 gap-3 overflow-y-auto p-5 sm:grid-cols-2 sm:p-6">
          {detailColumns.map((column) => (
            <div key={column.key} className="rounded-2xl border border-white/80 bg-white/75 px-4 py-3 shadow-[inset_1px_1px_0_rgba(255,255,255,.9),0_8px_18px_rgba(15,39,71,.05)]">
              <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-slate-400">{column.label}</p>
              <p className="mt-1 break-words text-sm font-semibold text-slate-800">{display(row[column.key])}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
