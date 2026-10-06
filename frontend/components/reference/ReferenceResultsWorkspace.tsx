'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  FileText,
  GraduationCap,
  LoaderCircle,
  LockKeyhole,
  RefreshCw,
  Save,
  Search,
  ShieldCheck,
} from 'lucide-react';

import { useToast } from '@/components/ui/ToastProvider';
import { ReferenceResourceView } from './ReferenceResourceView';

type HubAssessment = {
  assessment_id: number;
  class: string;
  class_id: number;
  term: string;
  academic_year: string;
  subject: string;
  subject_id: number;
  assessment_type: string;
  out_of: number;
  date: string;
  status: string;
  status_label: string;
  entered: number;
  total_students: number;
  missing: number;
  progress: number;
  note: string;
};

type MarksHub = {
  role: string;
  can_enter: boolean;
  blocked_reason: string;
  verification_enabled: boolean;
  can_manage_verification: boolean;
  academic_year: string;
  term: string;
  metrics: { assessments: number; need_marks: number; ready: number; flagged: number };
  assessments: HubAssessment[];
};

type MarksDetail = {
  assessment: {
    id: number;
    class: string;
    class_id: number;
    academic_year: string;
    term: string;
    subject: string;
    subject_id: number;
    assessment_type: string;
    date: string;
    out_of: number;
  };
  batch: {
    id: number;
    status: string;
    status_label: string;
    rejection_reason: string;
    submitted_by: string;
    submitted_at: string;
  };
  role: string;
  mode: string;
  editable: boolean;
  can_unlock: boolean;
  verification_enabled: boolean;
  total_students: number;
  entered: number;
  missing: number;
  submission_errors: string[];
  grading_bands: { min_score: number; max_score: number; grade: string; points: number }[];
  rows: {
    index: number;
    student_id: number;
    display_id: string;
    student: string;
    score: string;
    grade: string;
    points: string;
    status: string;
    audit: string;
  }[];
};

function statusClass(status: string) {
  const value = status.toLowerCase();
  if (value.includes('verified')) return 'border-emerald-100 bg-emerald-50 text-emerald-700';
  if (value.includes('flagged')) return 'border-red-100 bg-red-50 text-red-700';
  if (value.includes('pending')) return 'border-amber-100 bg-amber-50 text-amber-700';
  if (value.includes('missing')) return 'border-slate-200 bg-slate-50 text-slate-500';
  return 'border-blue-100 bg-blue-50 text-blue-700';
}

function ResultsTabs({ dashboardPath, view }: { dashboardPath: string; view: string }) {
  const base = `${dashboardPath}/results`;
  const items = [
    ['overview', 'Overview', base],
    ['marks', 'Marks Entry', `${base}?view=marks`],
    ['verification', 'Verification', `${base}?view=verification`],
    ['reports', 'Report Center', `${dashboardPath}/reports`],
  ] as const;
  return (
    <div className="mb-4 overflow-x-auto rounded-xl border border-slate-200 bg-white p-1.5 shadow-[0_5px_16px_rgba(28,55,97,.035)]">
      <div className="flex min-w-max gap-1">
        {items.map(([key, label, href]) => <Link key={key} href={href} className={`rounded-lg px-3.5 py-2 text-[10px] font-extrabold transition ${view === key ? 'bg-blue-600 text-white shadow-[0_5px_12px_rgba(37,99,235,.18)]' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'}`}>{label}</Link>)}
      </div>
    </div>
  );
}

function VerificationModeControl() {
  const toast = useToast();
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [canManage, setCanManage] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/workspace/results/marks', { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Verification setting could not be loaded.');
        return payload as MarksHub;
      })
      .then((payload) => {
        setEnabled(Boolean(payload.verification_enabled));
        setCanManage(Boolean(payload.can_manage_verification));
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) toast.error('Verification setting unavailable', reason instanceof Error ? reason.message : 'Please try again.');
      });
    return () => controller.abort();
  }, [toast]);

  async function toggle() {
    if (enabled === null || !canManage || saving) return;
    const next = !enabled;
    setSaving(true);
    try {
      const response = await fetch('/api/workspace/results/marks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'set_verification_mode', enabled: next }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Verification setting could not be changed.');
      setEnabled(Boolean(payload.verification_enabled));
      toast.success(next ? 'Script verification enabled' : 'Script verification disabled', payload.detail || 'Results workflow updated.');
    } catch (reason: unknown) {
      toast.error('Setting not changed', reason instanceof Error ? reason.message : 'Please try again.');
    } finally {
      setSaving(false);
    }
  }

  if (enabled === null) return null;

  return (
    <section className={`mb-4 flex flex-col gap-4 rounded-2xl border p-4 sm:flex-row sm:items-center sm:justify-between ${enabled ? 'border-emerald-100 bg-emerald-50/70' : 'border-slate-200 bg-slate-50'}`}>
      <div className="flex items-start gap-3">
        <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600'}`}><ShieldCheck size={18} /></span>
        <div><div className="flex flex-wrap items-center gap-2"><h2 className="text-sm font-extrabold text-[#10224A]">Script verification</h2><span className={`rounded-full px-2 py-1 text-[9px] font-extrabold ${enabled ? 'bg-emerald-600 text-white' : 'bg-slate-600 text-white'}`}>{enabled ? 'ON' : 'OFF'}</span></div><p className="mt-1 max-w-2xl text-[10px] leading-4 text-slate-600">{enabled ? 'Submitted marks must pass independent verification before they become available to reports.' : 'Submitted marks are verified automatically and released directly to reports.'}</p></div>
      </div>
      {canManage && <button type="button" role="switch" aria-checked={enabled} disabled={saving} onClick={() => void toggle()} className={`relative h-7 w-12 shrink-0 rounded-full transition ${enabled ? 'bg-emerald-600' : 'bg-slate-300'} disabled:opacity-60`}><span className={`absolute top-1 h-5 w-5 rounded-full bg-white shadow transition-all ${enabled ? 'left-6' : 'left-1'}`} /></button>}
    </section>
  );
}

function MarksHubView({ dashboardPath }: { dashboardPath: string }) {
  const [data, setData] = useState<MarksHub | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    fetch('/api/workspace/results/marks', { cache: 'no-store', signal: controller.signal })
      .then(async (response) => { const payload = await response.json(); if (!response.ok) throw new Error(payload.detail || 'Marks queue could not be loaded.'); return payload as MarksHub; })
      .then(setData)
      .catch((reason: unknown) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Marks queue could not be loaded.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);

  const rows = useMemo(() => {
    const text = query.trim().toLowerCase();
    return (data?.assessments ?? []).filter((row) => !text || [row.class, row.subject, row.assessment_type, row.status_label].some((value) => value.toLowerCase().includes(text)));
  }, [data, query]);

  if (loading && !data) return <div className="tafiti-card grid min-h-[420px] place-items-center"><div className="text-center text-xs font-semibold text-slate-500"><LoaderCircle className="mx-auto mb-3 animate-spin text-blue-600" size={24} />Loading marks queue…</div></div>;
  if (error && !data) return <div className="tafiti-card p-6 text-center"><AlertCircle className="mx-auto text-red-500" size={22} /><p className="mt-3 text-sm font-bold text-slate-800">Marks queue unavailable</p><p className="mt-2 text-xs text-slate-500">{error}</p></div>;
  if (!data) return null;

  return (
    <section>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex items-start gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-600"><GraduationCap size={21} /></span><div><h1 className="text-[1.65rem] font-extrabold tracking-[-0.035em] text-[#10224A]">Marks Entry</h1><p className="mt-1 text-xs leading-5 text-slate-500">Pick an assessment and continue where you stopped. {data.academic_year} · {data.term}</p></div></div>
      </div>

      {!data.can_enter && data.blocked_reason && <div className="mb-4 flex items-start gap-3 rounded-xl border border-amber-100 bg-amber-50 p-4 text-xs leading-5 text-amber-800"><AlertCircle size={17} className="mt-0.5 shrink-0" />{data.blocked_reason}</div>}

      <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          ['Assessments', data.metrics.assessments, 'bg-blue-50 text-blue-600'],
          ['Need marks', data.metrics.need_marks, 'bg-amber-50 text-amber-600'],
          ['Ready to submit', data.metrics.ready, 'bg-emerald-50 text-emerald-600'],
          ['Flagged', data.metrics.flagged, 'bg-red-50 text-red-600'],
        ].map(([label, value, cls]) => <article key={String(label)} className="tafiti-kpi"><div className="flex items-center gap-3"><span className={`grid h-10 w-10 place-items-center rounded-xl ${String(cls)}`}><FileText size={17} /></span><div><p className="text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">{String(label)}</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{String(value)}</p></div></div></article>)}
      </div>

      <section className="tafiti-card overflow-hidden">
        <div className="border-b border-slate-100 px-4 py-3.5 sm:px-5"><div className="relative max-w-[390px]"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search class, subject or assessment…" className="tafiti-input h-9 w-full pl-9 pr-3 text-xs" /></div></div>
        <div className="overflow-x-auto"><table className="w-full min-w-[920px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]"><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">CLASS / SUBJECT</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">ASSESSMENT</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">PROGRESS</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STATUS</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">NOTE</th><th className="px-4 py-3 text-right text-[9px] font-extrabold text-slate-400">ACTION</th></tr></thead><tbody className="divide-y divide-slate-100">{rows.map((row) => <tr key={row.assessment_id} className="hover:bg-blue-50/25"><td className="px-4 py-3"><p className="text-xs font-bold text-slate-800">{row.class}</p><p className="mt-0.5 text-[10px] text-slate-500">{row.subject}</p></td><td className="px-4 py-3"><p className="text-xs font-semibold text-slate-700">{row.assessment_type}</p><p className="mt-0.5 text-[9px] text-slate-400">Out of {row.out_of} · {row.date}</p></td><td className="px-4 py-3"><div className="w-[150px]"><div className="flex items-center justify-between text-[9px] font-semibold text-slate-500"><span>{row.entered}/{row.total_students}</span><span>{row.progress}%</span></div><div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-blue-600" style={{ width: `${row.progress}%` }} /></div></div></td><td className="px-4 py-3"><span className={`rounded-full border px-2 py-1 text-[9px] font-bold ${statusClass(row.status)}`}>{row.status_label}</span></td><td className="max-w-[260px] px-4 py-3 text-[10px] leading-4 text-slate-500">{row.note}</td><td className="px-4 py-3 text-right"><Link href={`${dashboardPath}/results?view=marks&assessment=${row.assessment_id}`} className="inline-flex items-center gap-1 text-[10px] font-bold text-blue-600 hover:underline">{row.status === 'VERIFIED' || row.status === 'PENDING' ? 'View' : row.status === 'FLAGGED' ? 'Correct' : row.entered ? 'Continue' : 'Start'} <ArrowRight size={12} /></Link></td></tr>)}</tbody></table></div>
        {!rows.length && <div className="px-5 py-12 text-center text-xs text-slate-400">No assessments match your current role and academic period.</div>}
      </section>
    </section>
  );
}

function MarksEntrySheet({ assessmentId, dashboardPath }: { assessmentId: number; dashboardPath: string }) {
  const toast = useToast();
  const router = useRouter();
  const [data, setData] = useState<MarksDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [scores, setScores] = useState<Record<string, string>>({});
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<'draft' | 'submit' | 'unlock' | ''>('');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    fetch(`/api/workspace/results/marks/${assessmentId}`, { cache: 'no-store', signal: controller.signal })
      .then(async (response) => { const payload = await response.json(); if (!response.ok) throw new Error(payload.detail || 'Marks sheet could not be loaded.'); return payload as MarksDetail; })
      .then((payload) => {
        setData(payload);
        setScores(Object.fromEntries(payload.rows.map((row) => [String(row.student_id), row.score])));
        setReasons({});
      })
      .catch((reason: unknown) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Marks sheet could not be loaded.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [assessmentId, reloadKey]);

  const completion = useMemo(() => {
    if (!data) return { entered: 0, missing: 0 };
    const entered = data.rows.filter((row) => String(scores[String(row.student_id)] ?? '').trim() !== '').length;
    return { entered, missing: Math.max(data.total_students - entered, 0) };
  }, [data, scores]);

  function preview(scoreText: string) {
    if (!data || !scoreText.trim()) return { grade: '—', points: '—' };
    const score = Number(scoreText);
    if (!Number.isFinite(score)) return { grade: '—', points: '—' };
    const band = data.grading_bands.find((item) => score >= item.min_score && score <= item.max_score);
    return band ? { grade: band.grade, points: String(band.points) } : { grade: 'N/A', points: '0' };
  }

  async function perform(action: 'draft' | 'submit' | 'unlock') {
    if (!data) return;
    setSaving(action);
    try {
      const body = action === 'unlock'
        ? { action: 'unlock' }
        : {
            action: 'save_draft',
            submit_after_save: action === 'submit',
            rows: data.rows.map((row) => ({ student_id: row.student_id, score: scores[String(row.student_id)] ?? '', reason: reasons[String(row.student_id)] ?? '' })),
          };
      const response = await fetch(`/api/workspace/results/marks/${assessmentId}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Marks could not be updated.');
      toast.success(action === 'submit' ? 'Marks submitted' : action === 'unlock' ? 'Batch unlocked' : 'Draft saved', payload.detail || 'Results updated successfully.');
      setReloadKey((value) => value + 1);
    } catch (reason: unknown) {
      toast.error('Marks not updated', reason instanceof Error ? reason.message : 'Please try again.');
    } finally { setSaving(''); }
  }

  if (loading && !data) return <div className="tafiti-card grid min-h-[440px] place-items-center"><div className="text-center text-xs font-semibold text-slate-500"><LoaderCircle className="mx-auto mb-3 animate-spin text-blue-600" size={24} />Loading marks sheet…</div></div>;
  if (error && !data) return <div className="tafiti-card p-6 text-center"><AlertCircle className="mx-auto text-red-500" /><p className="mt-3 text-sm font-bold text-slate-800">Marks sheet unavailable</p><p className="mt-2 text-xs text-slate-500">{error}</p></div>;
  if (!data) return null;

  const flagged = data.batch.status === 'FLAGGED';
  const locked = !data.editable;

  return (
    <section>
      <button type="button" onClick={() => router.push(`${dashboardPath}/results?view=marks`)} className="mb-3 inline-flex items-center gap-1.5 text-[10px] font-bold text-slate-500 hover:text-blue-600"><ArrowLeft size={13} />Back to marks queue</button>
      <section className="tafiti-card overflow-hidden">
        <div className="flex flex-col gap-4 border-b border-slate-100 px-4 py-4 sm:px-5 lg:flex-row lg:items-center lg:justify-between">
          <div><div className="flex flex-wrap items-center gap-2"><h1 className="text-xl font-extrabold tracking-[-.03em] text-[#10224A]">{data.assessment.subject}</h1><span className={`rounded-full border px-2.5 py-1 text-[9px] font-bold ${statusClass(data.batch.status)}`}>{data.batch.status_label}</span></div><p className="mt-1 text-xs font-bold text-blue-700">{data.assessment.class} · {data.assessment.assessment_type}</p><p className="mt-1 text-[10px] text-slate-400">{data.assessment.academic_year} · {data.assessment.term} · Out of {data.assessment.out_of}</p></div>
          <div className="flex flex-wrap gap-2"><Link href={`${dashboardPath}/results?view=verification`} className="clay-button-secondary"><ShieldCheck size={14} />Verification</Link>{data.can_unlock && <button type="button" disabled={Boolean(saving)} onClick={() => void perform('unlock')} className="clay-button-secondary"><RefreshCw size={14} />Unlock batch</button>}</div>
        </div>

        {flagged && data.batch.rejection_reason && <div className="flex items-start gap-3 border-b border-red-100 bg-red-50 px-4 py-3 text-xs leading-5 text-red-700 sm:px-5"><AlertCircle size={16} className="mt-0.5 shrink-0" /><div><p className="font-bold">Corrections required</p><p className="mt-0.5">{data.batch.rejection_reason}</p></div></div>}
        {locked && <div className="flex items-center gap-2 border-b border-amber-100 bg-amber-50 px-4 py-3 text-xs font-semibold text-amber-700 sm:px-5"><LockKeyhole size={15} />This batch is locked because it has already been submitted or verified.</div>}

        <div className="grid gap-3 border-b border-slate-100 bg-[#FBFCFE] p-4 sm:grid-cols-2 xl:grid-cols-4 sm:p-5">{[
          ['Students', data.total_students, 'text-blue-700'], ['Entered', completion.entered, 'text-emerald-700'], ['Missing', completion.missing, completion.missing ? 'text-amber-700' : 'text-emerald-700'], ['Mode', data.mode.replace('_',' '), 'text-violet-700'],
        ].map(([label,value,cls]) => <div key={String(label)} className="rounded-xl border border-slate-100 bg-white p-3.5"><p className="text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">{String(label)}</p><p className={`mt-1 text-lg font-extrabold ${String(cls)}`}>{String(value)}</p></div>)}</div>

        <div className="overflow-x-auto"><table className="w-full min-w-[980px] border-collapse text-left"><thead><tr className="sticky top-0 border-b border-slate-100 bg-[#F8FAFD]"><th className="px-3 py-3 text-center text-[9px] font-extrabold text-slate-400">#</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STUDENT</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">SCORE</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">GRADE</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">POINTS</th><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">STATUS</th>{flagged && <th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">CORRECTION REASON</th>}<th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">AUDIT</th></tr></thead><tbody className="divide-y divide-slate-100">{data.rows.map((row) => { const key = String(row.student_id); const currentScore = scores[key] ?? ''; const band = preview(currentScore); return <tr key={row.student_id} className="hover:bg-blue-50/20"><td className="px-3 py-3 text-center text-[10px] font-bold text-slate-400">{row.index}</td><td className="px-4 py-3"><p className="text-xs font-bold text-slate-800">{row.student}</p><p className="mt-0.5 text-[9px] text-slate-400">{row.display_id}</p></td><td className="px-4 py-3"><div className="relative w-[118px]"><input type="number" min={0} max={data.assessment.out_of} step="0.01" value={currentScore} disabled={locked || Boolean(saving)} onChange={(event) => setScores((current) => ({ ...current, [key]: event.target.value }))} className="tafiti-input h-9 w-full px-3 pr-10 text-xs font-bold" placeholder="—" /><span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[9px] text-slate-400">/{data.assessment.out_of}</span></div></td><td className="px-4 py-3 text-xs font-extrabold text-blue-700">{band.grade}</td><td className="px-4 py-3 text-xs font-semibold text-slate-600">{band.points}</td><td className="px-4 py-3"><span className={`rounded-full border px-2 py-1 text-[9px] font-bold ${statusClass(currentScore ? row.status : 'MISSING')}`}>{currentScore ? row.status : 'MISSING'}</span></td>{flagged && <td className="px-4 py-3"><input value={reasons[key] ?? ''} disabled={locked || Boolean(saving)} onChange={(event) => setReasons((current) => ({ ...current, [key]: event.target.value }))} placeholder="Required when correcting a changed mark" className="tafiti-input h-9 min-w-[230px] px-3 text-[10px]" /></td>}<td className="px-4 py-3 text-[10px] text-slate-400">{row.audit}</td></tr>; })}</tbody></table></div>

        <div className="sticky bottom-0 flex flex-col gap-3 border-t border-slate-100 bg-white/95 px-4 py-4 backdrop-blur sm:flex-row sm:items-center sm:justify-between sm:px-5"><div className="flex flex-wrap gap-3 text-[10px] font-bold"><span className="text-slate-500">{data.total_students} students</span><span className="text-emerald-600">{completion.entered} entered</span><span className={completion.missing ? 'text-amber-600' : 'text-emerald-600'}>{completion.missing} missing</span></div><div className="flex flex-wrap gap-2">{data.editable && <><button type="button" disabled={Boolean(saving)} onClick={() => void perform('draft')} className="clay-button-secondary">{saving === 'draft' ? <LoaderCircle className="animate-spin" size={14} /> : <Save size={14} />}Save draft</button><button type="button" disabled={Boolean(saving) || completion.missing > 0} onClick={() => void perform('submit')} className="clay-button-primary">{saving === 'submit' ? <LoaderCircle className="animate-spin" size={14} /> : <CheckCircle2 size={14} />}Save &amp; submit</button></>}</div></div>
      </section>
    </section>
  );
}

export function ReferenceResultsWorkspace({ dashboardPath }: { dashboardPath: string }) {
  const searchParams = useSearchParams();
  const view = searchParams.get('view') || 'overview';
  const assessment = Number(searchParams.get('assessment') || '0');

  return (
    <section>
      <ResultsTabs dashboardPath={dashboardPath} view={view === 'marks' ? 'marks' : view === 'verification' ? 'verification' : 'overview'} />
      {view === 'marks'
        ? (assessment > 0 ? <MarksEntrySheet assessmentId={assessment} dashboardPath={dashboardPath} /> : <MarksHubView dashboardPath={dashboardPath} />)
        : <><VerificationModeControl /><ReferenceResourceView resource="results" /></>}
    </section>
  );
}
