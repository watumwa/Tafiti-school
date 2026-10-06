'use client';

import { useEffect, useMemo, useState } from 'react';
import { KeyRound, LoaderCircle, Power, PowerOff, RefreshCw, Search, ShieldCheck, UserPlus, X } from 'lucide-react';

import { useToast } from '@/components/ui/ToastProvider';

type AccessRow = {
  id: number;
  user_id: number;
  parent: string;
  username: string;
  student_id: number;
  student: string;
  student_number: string;
  guardian: string;
  contact: string;
  active: boolean;
  verified: boolean;
  must_change_password: boolean;
  password_expires_at: string;
  permissions: { academics: boolean; finance: boolean; attendance: boolean };
};

type Candidate = { id: number; student: string; student_number: string; guardian: string; contact: string; class: string; stream: string };
type Payload = {
  title: string;
  description: string;
  can_write: boolean;
  summary: { links: number; active_links: number; parent_accounts: number; students_without_access: number };
  rows: AccessRow[];
  candidates: Candidate[];
};

type Credential = { username: string; temporary_password: string | null; expires_at: string; display_once: boolean };

export function ReferenceParentAccessWorkspace() {
  const toast = useToast();
  const [data, setData] = useState<Payload | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [query, setQuery] = useState('');
  const [candidateId, setCandidateId] = useState<number | ''>('');
  const [credential, setCredential] = useState<Credential | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetch('/api/workspace/parent-access', { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Parent access could not be loaded.');
        setData(payload as Payload);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) toast.error('Parent access unavailable', reason instanceof Error ? reason.message : 'Please try again.');
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [reloadKey, toast]);

  const rows = useMemo(() => {
    const text = query.trim().toLowerCase();
    if (!text) return data?.rows ?? [];
    return (data?.rows ?? []).filter((row) => [row.parent, row.username, row.student, row.student_number, row.guardian, row.contact].some((value) => value.toLowerCase().includes(text)));
  }, [data, query]);

  async function action(body: Record<string, unknown>, successTitle: string) {
    setSaving(true);
    try {
      const response = await fetch('/api/workspace/parent-access', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Parent access action failed.');
      toast.success(successTitle, payload.detail || 'Parent access updated.');
      if (payload.credential) setCredential(payload.credential as Credential);
      setCandidateId('');
      setReloadKey((value) => value + 1);
    } catch (reason: unknown) {
      toast.error('Parent access action failed', reason instanceof Error ? reason.message : 'Please try again.');
    } finally { setSaving(false); }
  }

  if (loading && !data) return <div className="tafiti-card grid min-h-[420px] place-items-center"><LoaderCircle className="animate-spin text-blue-600" size={24} /></div>;
  if (!data) return null;

  return (
    <section>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div><h1 className="text-[1.65rem] font-extrabold tracking-[-0.035em] text-[#10224A]">Parent Access</h1><p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">Activate guardian accounts, control child visibility and manage first-login credentials from one connected workspace.</p></div>
        <button type="button" onClick={() => setReloadKey((value) => value + 1)} className="clay-button-secondary"><RefreshCw size={14} />Refresh</button>
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          ['Parent links', data.summary.links], ['Active links', data.summary.active_links], ['Parent accounts', data.summary.parent_accounts], ['Students without access', data.summary.students_without_access],
        ].map(([label, value]) => <article key={String(label)} className="tafiti-kpi"><p className="text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">{String(label)}</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{String(value)}</p></article>)}
      </div>

      {data.can_write && (
        <section className="tafiti-card mb-4 p-4 sm:p-5">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
            <div className="flex-1"><label className="mb-1 block text-[10px] font-bold text-slate-500">Activate parent access for student</label><select value={candidateId} onChange={(event) => setCandidateId(event.target.value ? Number(event.target.value) : '')} className="tafiti-input h-10 w-full px-3 text-xs"><option value="">Choose student…</option>{data.candidates.map((row) => <option key={row.id} value={row.id}>{row.student} · {row.student_number} · {row.guardian} · {row.contact}</option>)}</select></div>
            <button type="button" disabled={!candidateId || saving} onClick={() => void action({ action: 'activate', student_id: candidateId }, 'Parent access activated')} className="clay-button-primary disabled:cursor-not-allowed disabled:opacity-50"><UserPlus size={14} />Activate access</button>
          </div>
        </section>
      )}

      <section className="tafiti-card overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-slate-100 px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between sm:px-5"><div className="relative w-full sm:max-w-[360px]"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search parent, student or contact…" className="tafiti-input h-9 w-full pl-9 pr-3 text-xs" /></div></div>
        <div className="overflow-x-auto"><table className="w-full min-w-[1120px] text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] text-slate-400">PARENT / LOGIN</th><th className="px-4 py-3 text-[9px] text-slate-400">STUDENT</th><th className="px-4 py-3 text-[9px] text-slate-400">PERMISSIONS</th><th className="px-4 py-3 text-[9px] text-slate-400">STATUS</th><th className="px-4 py-3 text-right text-[9px] text-slate-400">ACTIONS</th></tr></thead><tbody className="divide-y divide-slate-100">{rows.map((row) => <tr key={row.id}><td className="px-4 py-3"><p className="text-xs font-bold text-slate-800">{row.parent}</p><p className="mt-0.5 text-[9px] text-slate-400">{row.username} · {row.contact}</p></td><td className="px-4 py-3"><p className="text-xs font-bold text-slate-700">{row.student}</p><p className="mt-0.5 text-[9px] text-slate-400">{row.student_number}</p></td><td className="px-4 py-3"><div className="flex flex-wrap gap-1.5">{(['academics', 'finance', 'attendance'] as const).map((permission) => <button key={permission} type="button" disabled={!data.can_write || saving} onClick={() => void action({ action: 'permissions', access_id: row.id, ...row.permissions, [permission]: !row.permissions[permission] }, 'Parent permissions updated')} className={`rounded-full border px-2 py-1 text-[8px] font-bold ${row.permissions[permission] ? 'border-emerald-100 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-slate-50 text-slate-400'}`}><ShieldCheck size={9} className="mr-1 inline" />{permission}</button>)}</div></td><td className="px-4 py-3"><span className={`rounded-full border px-2.5 py-1 text-[9px] font-bold ${row.active && row.verified ? 'border-emerald-100 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-slate-50 text-slate-500'}`}>{row.active && row.verified ? 'Active' : 'Inactive'}</span>{row.must_change_password && <p className="mt-1 text-[8px] font-semibold text-amber-600">Password change required</p>}</td><td className="px-4 py-3 text-right"><div className="inline-flex items-center gap-2">{data.can_write && row.active && <button type="button" disabled={saving} onClick={() => void action({ action: 'reset_password', access_id: row.id }, 'Password reset')} className="inline-flex items-center gap-1 text-[10px] font-bold text-blue-600"><KeyRound size={12} />Reset</button>}{data.can_write && row.active && <button type="button" disabled={saving} onClick={() => void action({ action: 'deactivate', access_id: row.id }, 'Access deactivated')} className="inline-flex items-center gap-1 text-[10px] font-bold text-red-600"><PowerOff size={12} />Deactivate</button>}{data.can_write && !row.active && <button type="button" disabled={saving} onClick={() => void action({ action: 'reactivate', access_id: row.id }, 'Access reactivated')} className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-600"><Power size={12} />Reactivate</button>}</div></td></tr>)}</tbody></table></div>
      </section>

      {credential && <div className="fixed inset-0 z-[90] grid place-items-center bg-slate-950/40 p-4"><div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl"><div className="flex items-start justify-between gap-3"><div><h2 className="text-sm font-extrabold text-[#10224A]">One-time parent credential</h2><p className="mt-1 text-[10px] leading-4 text-amber-700">Copy this now. Tafiti does not store or show the plaintext temporary password again.</p></div><button type="button" onClick={() => setCredential(null)} className="grid h-8 w-8 place-items-center rounded-lg text-slate-500 hover:bg-slate-100"><X size={15} /></button></div><div className="mt-4 rounded-xl border border-slate-200 bg-[#F8FAFD] p-4"><p className="text-[9px] font-bold uppercase text-slate-400">Username</p><p className="mt-1 break-all text-sm font-extrabold text-slate-800">{credential.username}</p><p className="mt-3 text-[9px] font-bold uppercase text-slate-400">Temporary password</p><p className="mt-1 break-all font-mono text-base font-extrabold text-blue-700">{credential.temporary_password || 'Existing account — password unchanged'}</p>{credential.expires_at && <p className="mt-3 text-[9px] text-slate-500">Expires: {new Date(credential.expires_at).toLocaleString()}</p>}</div><button type="button" onClick={() => setCredential(null)} className="clay-button-primary mt-4 w-full justify-center">I have saved it</button></div></div>}
    </section>
  );
}
