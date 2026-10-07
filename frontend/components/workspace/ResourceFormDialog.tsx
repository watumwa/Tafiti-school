'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, LoaderCircle, Save, Search, X } from 'lucide-react';

import { ImageUploadControl } from './ImageUploadControl';

import type { WorkspaceFormField, WorkspaceFormSchema } from '@/lib/workspace';

function SearchableSelect({
  field,
  value,
  loading,
  className,
  onChange,
}: {
  field: WorkspaceFormField;
  value: string;
  loading: boolean;
  className: string;
  onChange: (value: string) => void;
}) {
  const [query, setQuery] = useState('');
  const filtered = useMemo(() => {
    const term = query.trim().toLocaleLowerCase();
    if (!term) return field.options;
    const matches = field.options.filter((option) => option.label.toLocaleLowerCase().includes(term));
    const selected = field.options.find((option) => option.value === value);
    return selected && !matches.some((option) => option.value === selected.value) ? [selected, ...matches] : matches;
  }, [field.options, query, value]);

  return (
    <div className="space-y-2">
      {field.options.length > 6 && <div className="relative"><Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input type="search" value={query} disabled={field.disabled || loading} onChange={(event) => setQuery(event.target.value)} placeholder={`Search ${field.label.toLowerCase()}…`} className="h-9 w-full rounded-xl border border-slate-200 bg-[#F8FAFD] pl-9 pr-3 text-xs text-slate-800 outline-none focus:border-[#2C5D8A] focus:ring-4 focus:ring-[#2C5D8A]/10" /></div>}
      <select value={value} disabled={field.disabled || loading} onChange={(event) => onChange(event.target.value)} className={className}>
        <option value="">Select {field.label.toLowerCase()}</option>
        {filtered.map((option) => <option key={`${field.name}-${option.value}`} value={option.value}>{option.label}</option>)}
      </select>
      {query && filtered.length === 0 && <span className="block text-[10px] text-amber-600">No matching options.</span>}
    </div>
  );
}

function initialValue(field: WorkspaceFormField) {
  if (field.type === 'checkbox') return Boolean(field.initial);
  if (field.type === 'multiselect') return Array.isArray(field.initial) ? field.initial.map(String) : [];
  if (field.type === 'image' || field.type === 'file') return null;
  return field.initial === null || field.initial === undefined ? '' : String(field.initial);
}

export function ResourceFormDialog({
  open,
  schema,
  loading,
  errors,
  onClose,
  onSubmit,
}: {
  open: boolean;
  schema: WorkspaceFormSchema | null;
  loading: boolean;
  errors: Record<string, string[]>;
  onClose: () => void;
  onSubmit: (values: Record<string, unknown>) => Promise<void>;
}) {
  const [values, setValues] = useState<Record<string, unknown>>({});

  useEffect(() => {
    if (!schema) return;
    setValues(Object.fromEntries(schema.fields.map((field) => [field.name, initialValue(field)])));
  }, [schema]);

  useEffect(() => {
    if (!open) return;
    const handle = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !loading) onClose();
    };
    window.addEventListener('keydown', handle);
    return () => window.removeEventListener('keydown', handle);
  }, [loading, onClose, open]);

  const globalErrors = useMemo(() => errors.__all__ ?? [], [errors]);
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center bg-[#07172B]/45 p-3 backdrop-blur-[3px] sm:p-6">
      <button type="button" aria-label="Close form" className="absolute inset-0" onClick={() => !loading && onClose()} />
      <div className="clay-dialog relative z-10 flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden">
        <div className="flex items-start justify-between gap-4 border-b border-slate-200/70 px-5 py-4 sm:px-6">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#2C5D8A]">Workspace form</p>
            <h2 className="mt-1 text-xl font-semibold tracking-[-0.02em] text-[#0B1F3A]">{schema?.title ?? 'Loading form…'}</h2>
          </div>
          <button type="button" disabled={loading} onClick={onClose} className="clay-icon-button" aria-label="Close"><X size={18} /></button>
        </div>

        <div className="overflow-y-auto px-5 py-5 sm:px-6">
          {!schema ? (
            <div className="grid min-h-[280px] place-items-center text-sm font-medium text-slate-500">
              <span className="inline-flex items-center gap-2"><LoaderCircle size={18} className="animate-spin text-[#2C5D8A]" /> Loading form…</span>
            </div>
          ) : (
            <form
              id="workspace-resource-form"
              className="grid grid-cols-1 gap-4 sm:grid-cols-2"
              onSubmit={(event) => {
                event.preventDefault();
                void onSubmit(values);
              }}
            >
              {globalErrors.length > 0 && (
                <div className="sm:col-span-2 rounded-2xl border border-red-200 bg-red-50/80 px-4 py-3 text-sm text-red-700">
                  <div className="flex gap-2"><AlertCircle size={17} className="mt-0.5 shrink-0" /><div>{globalErrors.map((item) => <p key={item}>{item}</p>)}</div></div>
                </div>
              )}

              {schema.fields.map((field) => {
                const fieldErrors = errors[field.name] ?? [];
                const common = 'h-11 w-full rounded-xl border bg-white/90 px-3 text-sm text-slate-900 outline-none transition focus:border-[#2C5D8A] focus:ring-4 focus:ring-[#2C5D8A]/10 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400';
                return (
                  <label key={field.name} className={field.type === 'textarea' || field.type === 'file' || field.type === 'image' ? 'sm:col-span-2' : ''}>
                    <span className="mb-1.5 flex items-center gap-1 text-xs font-semibold text-slate-700">
                      {field.label}{field.required && <span className="text-red-500">*</span>}
                    </span>

                    {field.type === 'image' ? (
                      <ImageUploadControl
                        name={field.label}
                        currentUrl={field.current_file_url}
                        value={values[field.name]}
                        required={field.required}
                        disabled={field.disabled || loading}
                        onChange={(file) => setValues((current) => ({ ...current, [field.name]: file }))}
                      />
                    ) : field.type === 'textarea' ? (
                      <textarea
                        value={String(values[field.name] ?? '')}
                        disabled={field.disabled || loading}
                        rows={4}
                        onChange={(event) => setValues((current) => ({ ...current, [field.name]: event.target.value }))}
                        className={`${common} h-auto min-h-[108px] py-3`}
                      />
                    ) : field.type === 'select' ? (
                      <SearchableSelect field={field} value={String(values[field.name] ?? '')} loading={loading} className={common} onChange={(value) => setValues((current) => ({ ...current, [field.name]: value }))} />
                    ) : field.type === 'multiselect' ? (
                      <select
                        multiple
                        value={(values[field.name] as string[]) ?? []}
                        disabled={field.disabled || loading}
                        onChange={(event) => setValues((current) => ({ ...current, [field.name]: Array.from(event.target.selectedOptions).map((item) => item.value) }))}
                        className={`${common} h-28 py-2`}
                      >
                        {field.options.map((option) => <option key={`${field.name}-${option.value}`} value={option.value}>{option.label}</option>)}
                      </select>
                    ) : field.type === 'checkbox' ? (
                      <span className="flex min-h-11 items-center gap-3 rounded-xl border border-slate-200 bg-white/90 px-3">
                        <input
                          type="checkbox"
                          checked={Boolean(values[field.name])}
                          disabled={field.disabled || loading}
                          onChange={(event) => setValues((current) => ({ ...current, [field.name]: event.target.checked }))}
                          className="h-4 w-4 accent-[#173F6B]"
                        />
                        <span className="text-sm text-slate-600">{Boolean(values[field.name]) ? 'Enabled' : 'Disabled'}</span>
                      </span>
                    ) : field.type === 'file' ? (
                      <div>
                        <input
                          type="file"
                          required={field.required}
                          disabled={field.disabled || loading}
                          onChange={(event) => setValues((current) => ({ ...current, [field.name]: event.target.files?.[0] ?? null }))}
                          className="block w-full rounded-xl border border-dashed border-slate-300 bg-white/80 px-3 py-2.5 text-xs text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-[#EAF0F7] file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-[#173F6B] hover:file:bg-[#DFE8F2]"
                        />
                        {field.help_text && <span className="mt-1 block text-[11px] leading-4 text-slate-400">{field.help_text}</span>}
                      </div>
                    ) : (
                      <input
                        type={field.type}
                        value={String(values[field.name] ?? '')}
                        disabled={field.disabled || loading}
                        required={field.required}
                        min={field.min_value ?? undefined}
                        max={field.max_value ?? undefined}
                        onChange={(event) => setValues((current) => ({ ...current, [field.name]: event.target.value }))}
                        className={common}
                      />
                    )}

                    {field.type !== 'file' && field.type !== 'image' && field.help_text && <span className="mt-1 block text-[11px] leading-4 text-slate-400">{field.help_text}</span>}
                    {fieldErrors.map((item) => <span key={item} className="mt-1 block text-xs font-medium text-red-600">{item}</span>)}
                  </label>
                );
              })}
            </form>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-slate-200/70 bg-white/70 px-5 py-4 sm:px-6">
          <button type="button" disabled={loading} onClick={onClose} className="clay-button-secondary">Cancel</button>
          <button type="submit" form="workspace-resource-form" disabled={loading || !schema} className="clay-button-primary">
            {loading ? <LoaderCircle size={16} className="animate-spin" /> : <Save size={16} />}
            {loading ? 'Saving…' : schema?.submit_label ?? 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
