'use client';

import { AlertTriangle, LoaderCircle, Trash2, X } from 'lucide-react';

export function ConfirmActionDialog({
  open,
  title,
  message,
  confirmLabel,
  loading,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  loading: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[95] flex items-center justify-center bg-[#07172B]/50 p-4 backdrop-blur-[3px]">
      <button type="button" className="absolute inset-0" aria-label="Cancel" onClick={() => !loading && onCancel()} />
      <div className="clay-dialog relative z-10 w-full max-w-md p-5 sm:p-6">
        <div className="flex items-start gap-4">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-red-50 text-red-600 shadow-[inset_1px_1px_0_#fff,0_7px_16px_rgba(220,38,38,.08)]"><AlertTriangle size={20} /></span>
          <div className="min-w-0 flex-1"><h2 className="text-lg font-semibold text-slate-900">{title}</h2><p className="mt-2 text-sm leading-6 text-slate-600">{message}</p></div>
          <button type="button" disabled={loading} onClick={onCancel} className="clay-icon-button"><X size={17} /></button>
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <button type="button" disabled={loading} onClick={onCancel} className="clay-button-secondary">Cancel</button>
          <button type="button" disabled={loading} onClick={onConfirm} className="inline-flex h-10 items-center gap-2 rounded-xl bg-red-600 px-4 text-xs font-semibold text-white shadow-[0_8px_18px_rgba(220,38,38,.18),inset_0_1px_0_rgba(255,255,255,.25)] transition hover:bg-red-700 disabled:opacity-60">
            {loading ? <LoaderCircle size={15} className="animate-spin" /> : <Trash2 size={15} />} {loading ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
