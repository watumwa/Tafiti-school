'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, ChevronDown, LoaderCircle, Plus, Save, Search, X } from 'lucide-react';

import { ImageUploadControl } from './ImageUploadControl';

import type { WorkspaceFormField, WorkspaceFormSchema } from '@/lib/workspace';

const UGANDA_LIN_PATTERN = /^U\d{2}[MF]\d{4}A\d{5}$/;

function normalizeUgandaLinInput(value: string) {
  return value.replace(/\s+/g, '').toUpperCase().slice(0, 14);
}

function genderLabel(value: string) {
  if (value === 'M') return 'Male';
  if (value === 'F') return 'Female';
  return value;
}

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
  if (field.type === 'multiselect') {
    if (Array.isArray(field.initial)) return field.initial.map(String);
    return field.initial === null || field.initial === undefined || field.initial === '' ? [] : [String(field.initial)];
  }
  if (field.type === 'image' || field.type === 'file') return null;
  return field.initial === null || field.initial === undefined ? '' : String(field.initial);
}

function stringArray(value: unknown) {
  return Array.isArray(value) ? value.map(String) : [];
}

function MultiSelectChips({
  field,
  value,
  loading,
  onChange,
}: {
  field: WorkspaceFormField;
  value: string[];
  loading: boolean;
  onChange: (value: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const selected = field.options.filter((option) => value.includes(option.value));
  const available = field.options.filter((option) => !value.includes(option.value));
  const roleField = field.name === 'roles';
  const addLabel = roleField ? 'Add another role' : `Add ${field.label.toLowerCase()}`;

  function add(optionValue: string) {
    if (!optionValue || value.includes(optionValue)) return;
    onChange([...value, optionValue]);
    setOpen(false);
  }

  function remove(optionValue: string) {
    onChange(value.filter((item) => item !== optionValue));
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white/90 p-2.5">
      <div className="flex min-h-10 flex-wrap items-center gap-2">
        {selected.map((option) => (
          <span key={option.value} className="inline-flex items-center gap-1.5 rounded-lg border border-blue-100 bg-blue-50 px-2.5 py-1.5 text-xs font-bold text-blue-800">
            {option.label}
            <button
              type="button"
              aria-label={`Remove ${option.label}`}
              disabled={field.disabled || loading}
              onClick={() => remove(option.value)}
              className="rounded p-0.5 text-blue-600 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50"
            ><X size={12} /></button>
          </span>
        ))}
        {!selected.length && <span className="px-1 text-xs text-slate-400">No {field.label.toLowerCase()} selected.</span>}
        {available.length > 0 && (
          <div className="relative">
            <button
              type="button"
              disabled={field.disabled || loading}
              onClick={() => setOpen((current) => !current)}
              className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-dashed border-blue-300 bg-white px-2.5 text-[11px] font-bold text-blue-700 transition hover:border-blue-500 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50"
            ><Plus size={13} />{addLabel}<ChevronDown size={12} /></button>
            {open && (
              <div className="absolute left-0 z-20 mt-2 max-h-52 w-56 overflow-y-auto rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl">
                {available.map((option) => (
                  <button key={option.value} type="button" onClick={() => add(option.value)} className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs font-semibold text-slate-700 hover:bg-blue-50 hover:text-blue-800"><Plus size={13} className="text-blue-600" />{option.label}</button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
      {roleField && <p className="mt-2 px-1 text-[10px] leading-4 text-slate-400">Use <strong className="font-bold text-slate-500">+ Add another role</strong> to give this staff member more than one workspace.</p>}
    </div>
  );
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
  const hasLinField = Boolean(schema?.fields.some((field) => field.name === 'lin_number'));
  const linValue = String(values.lin_number ?? '').trim().toUpperCase();
  const linValid = !linValue || UGANDA_LIN_PATTERN.test(linValue);
  const linInvalid = hasLinField && Boolean(linValue) && !linValid;
  const recordedGender = String(values.gender ?? '').trim().toUpperCase();
  const linGenderMarker = linValid && linValue ? linValue[3] ?? '' : '';
  const linGenderMismatch = Boolean(
    hasLinField
      && linValue
      && (recordedGender === 'M' || recordedGender === 'F')
      && (linGenderMarker === 'M' || linGenderMarker === 'F')
      && recordedGender !== linGenderMarker,
  );

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
                if (linInvalid) return;
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
                const isLinField = field.name === 'lin_number';
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
                      <MultiSelectChips
                        field={field}
                        value={stringArray(values[field.name])}
                        loading={loading}
                        onChange={(value) => setValues((current) => ({ ...current, [field.name]: value }))}
                      />
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
                        maxLength={isLinField ? 14 : undefined}
                        autoCapitalize={isLinField ? 'characters' : undefined}
                        autoComplete={isLinField ? 'off' : undefined}
                        spellCheck={isLinField ? false : undefined}
                        aria-invalid={isLinField && linInvalid ? true : undefined}
                        onChange={(event) => {
                          const nextValue = isLinField
                            ? normalizeUgandaLinInput(event.target.value)
                            : event.target.value;
                          setValues((current) => ({ ...current, [field.name]: nextValue }));
                        }}
                        className={`${common} ${isLinField && linInvalid ? 'border-red-300 focus:border-red-400 focus:ring-red-100' : ''}`}
                      />
                    )}

                    {field.type !== 'file' && field.type !== 'image' && field.help_text && <span className="mt-1 block text-[11px] leading-4 text-slate-400">{field.help_text}</span>}
                    {isLinField && linInvalid && <span className="mt-1 block text-xs font-medium text-red-600">LIN must follow the 14-character format U00M0000A00000 or U00F0000A00000, for example U13F0921A44760.</span>}
                    {isLinField && linGenderMismatch && <span className="mt-1 block rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-2 text-[11px] leading-4 text-amber-800">The LIN gender marker is <strong>{linGenderMarker} ({genderLabel(linGenderMarker)})</strong>, while the student gender is <strong>{genderLabel(recordedGender)}</strong>. Verify the official LIN against EMIS. This warning does not block saving.</span>}
                    {fieldErrors.map((item) => <span key={item} className="mt-1 block text-xs font-medium text-red-600">{item}</span>)}
                  </label>
                );
              })}
            </form>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-slate-200/70 bg-white/70 px-5 py-4 sm:px-6">
          <button type="button" disabled={loading} onClick={onClose} className="clay-button-secondary">Cancel</button>
          <button type="submit" form="workspace-resource-form" disabled={loading || !schema || linInvalid} className="clay-button-primary">
            {loading ? <LoaderCircle size={16} className="animate-spin" /> : <Save size={16} />}
            {loading ? 'Saving…' : schema?.submit_label ?? 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
