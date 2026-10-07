'use client';

import { useEffect, useState } from 'react';
import { AlertCircle, Download, FileSpreadsheet, LoaderCircle, Upload, X } from 'lucide-react';

type ImportTemplate = {
  columns: string[];
  sample: string[];
  max_rows: number;
  max_size_mb: number;
  accepted_gender: string[];
  accepted_nationalities: string[];
  accepted_religions: string[];
  atomic: boolean;
};

function csvValue(value: string) {
  return `"${value.replaceAll('"', '""')}"`;
}

export function StudentBulkImportDialog({
  open,
  onClose,
  onImported,
}: {
  open: boolean;
  onClose: () => void;
  onImported: (count: number, message: string) => void;
}) {
  const [template, setTemplate] = useState<ImportTemplate | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  useEffect(() => {
    if (!open) return;
    setFile(null);
    setErrors([]);
    fetch('/api/workspace/students/bulk', { cache: 'no-store' })
      .then(async (response) => {
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || 'The import template could not be loaded.');
        return result as ImportTemplate;
      })
      .then(setTemplate)
      .catch((reason: unknown) => setErrors([reason instanceof Error ? reason.message : 'The import template could not be loaded.']));
  }, [open]);

  function downloadTemplate() {
    if (!template) return;
    const content = [
      csvValue('STUDENT REGISTRATION DATA'),
      template.columns.map(csvValue).join(','),
    ].join('\n');
    const url = URL.createObjectURL(new Blob([content], { type: 'text/csv;charset=utf-8' }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'tafiti-student-registration-template.csv';
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function uploadFile() {
    if (!file) {
      setErrors(['Choose the completed CSV file first.']);
      return;
    }
    setLoading(true);
    setErrors([]);
    try {
      const body = new FormData();
      body.append('file', file);
      const response = await fetch('/api/workspace/students/bulk', { method: 'POST', body });
      const result = await response.json();
      if (!response.ok) {
        setErrors(Array.isArray(result.errors) ? result.errors.map(String) : [result.detail || 'The CSV could not be imported.']);
        return;
      }
      onImported(Number(result.created_count ?? 0), String(result.detail ?? 'Students registered successfully.'));
    } catch {
      setErrors(['The school server could not be reached. Please try again.']);
    } finally {
      setLoading(false);
    }
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[95] flex items-center justify-center bg-[#07172B]/50 p-3 backdrop-blur-[3px] sm:p-6">
      <button type="button" aria-label="Close bulk student import" className="absolute inset-0" onClick={() => !loading && onClose()} />
      <section className="clay-dialog relative z-10 flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden">
        <header className="flex items-start justify-between gap-4 border-b border-slate-200/70 px-5 py-4 sm:px-6">
          <div className="flex items-start gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-emerald-50 text-emerald-700"><FileSpreadsheet size={19} /></span>
            <div><p className="text-[10px] font-bold uppercase tracking-[.16em] text-emerald-700">Admissions gateway</p><h2 className="mt-1 text-xl font-semibold text-[#0B1F3A]">Bulk-register students</h2><p className="mt-1 text-xs text-slate-500">Download the template, complete it, then upload the CSV.</p></div>
          </div>
          <button type="button" disabled={loading} onClick={onClose} className="clay-icon-button" aria-label="Close"><X size={18} /></button>
        </header>

        <div className="overflow-y-auto px-5 py-5 sm:px-6">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-2xl border border-blue-100 bg-blue-50/60 p-4 sm:col-span-2"><p className="text-xs font-bold text-blue-900">Safe batch rules</p><p className="mt-1 text-[11px] leading-5 text-blue-700">Every row is validated before registration. If one row has an error, no students, class-register entries, or fee bills are created.</p></div>
            <button type="button" disabled={!template} onClick={downloadTemplate} className="clay-button-secondary min-h-20 justify-center"><Download size={16} /> Download CSV template</button>
          </div>

          {template && <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4"><p className="text-xs font-bold text-slate-800">Example row</p><div className="mt-3 overflow-x-auto"><table className="min-w-[900px] text-left text-[10px]"><thead><tr>{template.columns.map((column) => <th key={column} className="border-b border-slate-100 px-2 py-2 font-bold text-slate-400">{column}</th>)}</tr></thead><tbody><tr>{template.sample.map((value, index) => <td key={`${template.columns[index]}-${index}`} className="px-2 py-2 text-slate-600">{value || 'auto'}</td>)}</tr></tbody></table></div><p className="mt-3 text-[10px] text-slate-400">Up to {template.max_rows.toLocaleString()} rows / {template.max_size_mb} MB. Gender accepts {template.accepted_gender.join(', ')}.</p></div>}

          <label className="mt-4 block rounded-2xl border-2 border-dashed border-slate-200 bg-[#F8FAFD] p-5 text-center transition hover:border-blue-300">
            <Upload className="mx-auto text-blue-600" size={22} />
            <span className="mt-2 block text-xs font-bold text-slate-800">Choose completed CSV</span>
            <span className="mt-1 block text-[10px] text-slate-400">CSV UTF-8 format only</span>
            <input type="file" accept=".csv,text/csv" disabled={loading} onChange={(event) => { setFile(event.target.files?.[0] ?? null); setErrors([]); }} className="mt-3 block w-full text-xs text-slate-500 file:mr-3 file:rounded-lg file:border-0 file:bg-blue-50 file:px-3 file:py-2 file:text-xs file:font-bold file:text-blue-700" />
            {file && <span className="mt-2 block text-[10px] font-semibold text-emerald-700">Selected: {file.name}</span>}
          </label>

          {errors.length > 0 && <div className="mt-4 rounded-2xl border border-red-200 bg-red-50 p-4 text-xs text-red-700"><div className="flex items-start gap-2"><AlertCircle size={16} className="mt-0.5 shrink-0" /><div><p className="font-bold">Import blocked — no records were created</p><ul className="mt-2 max-h-40 list-disc space-y-1 overflow-y-auto pl-4">{errors.map((error, index) => <li key={`${error}-${index}`}>{error}</li>)}</ul></div></div></div>}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-slate-200/70 bg-white/70 px-5 py-4 sm:px-6"><button type="button" disabled={loading} onClick={onClose} className="clay-button-secondary">Cancel</button><button type="button" disabled={loading || !file} onClick={() => void uploadFile()} className="clay-button-primary">{loading ? <LoaderCircle size={16} className="animate-spin" /> : <Upload size={16} />}{loading ? 'Validating & registering…' : 'Validate & register'}</button></footer>
      </section>
    </div>
  );
}
