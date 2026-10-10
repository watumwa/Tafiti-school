'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, Download, Landmark, LoaderCircle, RefreshCw } from 'lucide-react';

type ReportPayload = {
  category: string;
  report: string;
  generated_at: string;
  rows: Record<string, unknown>[];
  count: number;
};

function labelFor(key: string) {
  return key.replaceAll('_', ' ').replace(/\b\w/g, (character) => character.toUpperCase());
}

function csvEscape(value: unknown) {
  const text = value == null ? '' : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

export function ReferenceFinanceReportView({ report }: { report: string }) {
  const [data, setData] = useState<ReportPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetch(`/api/workspace/reports/finance?report=${encodeURIComponent(report)}`, { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'The financial report could not be loaded.');
        return payload as ReportPayload;
      })
      .then(setData)
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'The financial report could not be loaded.');
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [reload, report]);

  const columns = useMemo(() => data?.rows.length ? Object.keys(data.rows[0]) : [], [data]);
  const title = report.includes('reconciliation') ? 'Bank Reconciliation' : 'Financial Statement';

  function exportCsv() {
    if (!data?.rows.length) return;
    const body = [
      columns.map((key) => csvEscape(labelFor(key))).join(','),
      ...data.rows.map((row) => columns.map((key) => csvEscape(row[key])).join(',')),
    ].join('\n');
    const blob = new Blob([body], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `tafiti-${report}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  if (loading && !data) return <div className="tafiti-card grid min-h-[420px] place-items-center"><div className="text-center text-xs font-semibold text-slate-500"><LoaderCircle size={24} className="mx-auto mb-3 animate-spin text-blue-600" />Loading financial report…</div></div>;
  if (error && !data) return <div className="tafiti-card grid min-h-[420px] place-items-center p-6 text-center"><div><AlertCircle size={25} className="mx-auto text-red-500" /><h2 className="mt-3 text-sm font-extrabold text-slate-900">Financial report unavailable</h2><p className="mt-2 text-xs text-slate-500">{error}</p><button type="button" className="clay-button-primary mt-4" onClick={() => setReload((value) => value + 1)}>Try again</button></div></div>;
  if (!data) return null;

  return <section>
    <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="flex items-start gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-600"><Landmark size={21} /></span><div><h1 className="text-[1.65rem] font-extrabold tracking-[-0.035em] text-[#10224A]">{title}</h1><p className="mt-1 text-xs leading-5 text-slate-500">Generated from the live fee ledger, income/expense records and bank reconciliation data.</p></div></div>
      <div className="flex gap-2"><button type="button" onClick={() => setReload((value) => value + 1)} className="clay-button-secondary"><RefreshCw size={14} /> Refresh</button><button type="button" onClick={exportCsv} className="clay-button-secondary"><Download size={14} /> Export</button></div>
    </div>
    <div className="tafiti-card overflow-x-auto">
      <table className="w-full min-w-[760px] border-collapse text-left">
        <thead><tr className="border-b border-slate-100 bg-[#F8FAFD]">{columns.map((key) => <th key={key} className="px-4 py-3 text-[9px] font-extrabold uppercase tracking-[.04em] text-slate-400">{labelFor(key)}</th>)}</tr></thead>
        <tbody className="divide-y divide-slate-100">{data.rows.map((row, index) => <tr key={String(row.id ?? row.item ?? row.statement ?? index)} className="hover:bg-blue-50/20">{columns.map((key) => <td key={key} className="px-4 py-3 text-xs text-slate-600">{String(row[key] ?? '—')}</td>)}</tr>)}</tbody>
      </table>
      {!data.rows.length && <div className="px-5 py-12 text-center text-xs text-slate-400">No records are available for this report.</div>}
    </div>
  </section>;
}
