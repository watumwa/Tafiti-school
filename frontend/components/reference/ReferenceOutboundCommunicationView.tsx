'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, LoaderCircle, Mail, MessageCircle, RefreshCw, Send, Smartphone } from 'lucide-react';

import { useToast } from '@/components/ui/ToastProvider';

type StudentRow = {
  id: number;
  student: string;
  reg_no: string;
  class: string;
  guardian: string;
  guardian_phone: string;
  guardian_email: string;
  whatsapp_number: string;
  sms_enabled: boolean;
  email_enabled: boolean;
  whatsapp_enabled: boolean;
  opted_out: boolean;
  outstanding: string;
};

type DeliveryRow = {
  id: number;
  student: string;
  reg_no: string;
  channel: string;
  recipient: string;
  template: string;
  status: string;
  attempts: number;
  created: string;
  sent: string;
  provider_response: string;
};

type Payload = {
  role: string;
  can_send_fee: boolean;
  can_send_report: boolean;
  students: StudentRow[];
  rows: DeliveryRow[];
  channels: string[];
};

function money(value: string) {
  const amount = Number(value || 0);
  return Number.isFinite(amount) ? new Intl.NumberFormat('en-UG').format(amount) : value;
}

function statusTone(status: string) {
  const value = status.toLowerCase();
  if (value === 'sent') return 'border-emerald-100 bg-emerald-50 text-emerald-700';
  if (value === 'failed') return 'border-red-100 bg-red-50 text-red-700';
  if (value === 'skipped') return 'border-slate-200 bg-slate-50 text-slate-600';
  return 'border-amber-100 bg-amber-50 text-amber-700';
}

export function ReferenceOutboundCommunicationView() {
  const toast = useToast();
  const [data, setData] = useState<Payload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);
  const [studentId, setStudentId] = useState<number | ''>('');
  const [channel, setChannel] = useState('SMS');
  const [notificationType, setNotificationType] = useState<'fee_reminder' | 'report_notice'>('fee_reminder');
  const [portalUrl, setPortalUrl] = useState('');
  const [sending, setSending] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetch('/api/workspace/communication-outbound', { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Outbound notifications could not be loaded.');
        return payload as Payload;
      })
      .then((payload) => {
        setData(payload);
        if (!studentId && payload.students.length) setStudentId(payload.students[0].id);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Outbound notifications could not be loaded.');
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [reload]);

  const selected = useMemo(() => data?.students.find((student) => student.id === studentId) ?? null, [data, studentId]);
  const canSend = notificationType === 'fee_reminder' ? Boolean(data?.can_send_fee) : Boolean(data?.can_send_report);

  async function sendNotification() {
    if (!studentId || !canSend || sending) return;
    setSending(true);
    try {
      const response = await fetch('/api/workspace/communication-outbound', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: notificationType,
          student_id: studentId,
          channel,
          portal_url: portalUrl.trim(),
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Notification could not be sent.');
      toast.success('Notification processed', payload.detail || 'Delivery request completed.');
      setReload((value) => value + 1);
    } catch (reason: unknown) {
      toast.error('Notification not sent', reason instanceof Error ? reason.message : 'Please try again.');
    } finally {
      setSending(false);
    }
  }

  if (loading && !data) return <div className="tafiti-card grid min-h-[420px] place-items-center"><div className="text-center text-xs font-semibold text-slate-500"><LoaderCircle className="mx-auto mb-3 animate-spin text-blue-600" size={24} />Loading outbound notifications…</div></div>;
  if (error && !data) return <div className="tafiti-card grid min-h-[420px] place-items-center p-6 text-center"><div><AlertCircle className="mx-auto text-red-500" size={25} /><h2 className="mt-3 text-sm font-extrabold text-slate-900">Outbound notifications unavailable</h2><p className="mt-2 text-xs text-slate-500">{error}</p><button type="button" onClick={() => setReload((value) => value + 1)} className="clay-button-primary mt-4">Try again</button></div></div>;
  if (!data) return null;

  return <section>
    <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div><p className="text-[9px] font-extrabold uppercase tracking-[.1em] text-blue-600">Parent communication</p><h1 className="mt-1 text-[1.65rem] font-extrabold tracking-[-.035em] text-[#10224A]">Outbound Notifications</h1><p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">Send fee-balance reminders or report-ready notices using the configured SMS, email or WhatsApp provider. Every attempt is recorded below.</p></div>
      <button type="button" onClick={() => setReload((value) => value + 1)} className="clay-button-secondary"><RefreshCw size={14} /> Refresh</button>
    </div>

    <div className="mb-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
      <section className="tafiti-card p-4 sm:p-5">
        <h2 className="text-sm font-extrabold text-[#10224A]">Send notification</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="sm:col-span-2"><span className="mb-1 block text-[9px] font-extrabold uppercase tracking-[.05em] text-slate-400">Student</span><select value={studentId} onChange={(event) => setStudentId(Number(event.target.value))} className="tafiti-input h-10 w-full px-3 text-xs"><option value="">Choose student</option>{data.students.map((student) => <option key={student.id} value={student.id}>{student.student} · {student.reg_no} · {student.class}</option>)}</select></label>
          <label><span className="mb-1 block text-[9px] font-extrabold uppercase tracking-[.05em] text-slate-400">Notification</span><select value={notificationType} onChange={(event) => setNotificationType(event.target.value as 'fee_reminder' | 'report_notice')} className="tafiti-input h-10 w-full px-3 text-xs"><option value="fee_reminder">Fee balance reminder</option><option value="report_notice">Report ready notice</option></select></label>
          <label><span className="mb-1 block text-[9px] font-extrabold uppercase tracking-[.05em] text-slate-400">Channel</span><select value={channel} onChange={(event) => setChannel(event.target.value)} className="tafiti-input h-10 w-full px-3 text-xs">{data.channels.map((item) => <option key={item}>{item}</option>)}</select></label>
          {notificationType === 'report_notice' && <label className="sm:col-span-2"><span className="mb-1 block text-[9px] font-extrabold uppercase tracking-[.05em] text-slate-400">Parent portal link (optional)</span><input value={portalUrl} onChange={(event) => setPortalUrl(event.target.value)} placeholder="https://school.example.com/parent" className="tafiti-input h-10 w-full px-3 text-xs" /></label>}
        </div>
        {!canSend && <div className="mt-3 rounded-xl border border-amber-100 bg-amber-50 px-3 py-2.5 text-[10px] font-semibold text-amber-800">Your current workspace can view delivery activity but cannot send this notification type.</div>}
        <button type="button" disabled={!studentId || !canSend || sending} onClick={() => void sendNotification()} className="clay-button-primary mt-4 disabled:cursor-not-allowed disabled:opacity-50">{sending ? <LoaderCircle size={14} className="animate-spin" /> : <Send size={14} />} Send notification</button>
      </section>

      <aside className="tafiti-card p-4 sm:p-5">
        <h2 className="text-sm font-extrabold text-[#10224A]">Selected student</h2>
        {selected ? <div className="mt-4 space-y-3 text-[10px]"><div><p className="font-extrabold text-slate-800">{selected.student}</p><p className="mt-0.5 text-slate-400">{selected.reg_no} · {selected.class}</p></div><div className="rounded-xl bg-[#F8FAFD] p-3"><p className="text-slate-400">Outstanding fees</p><p className="mt-1 text-base font-extrabold text-[#10224A]">UGX {money(selected.outstanding)}</p></div><div className="space-y-2"><p className="flex items-center gap-2 text-slate-600"><Smartphone size={13} className="text-blue-600" />{selected.guardian_phone || 'No phone configured'} {selected.sms_enabled ? '' : '· SMS disabled'}</p><p className="flex items-center gap-2 text-slate-600"><Mail size={13} className="text-blue-600" />{selected.guardian_email || 'No email configured'} {selected.email_enabled ? '' : '· Email disabled'}</p><p className="flex items-center gap-2 text-slate-600"><MessageCircle size={13} className="text-blue-600" />{selected.whatsapp_number || selected.guardian_phone || 'No WhatsApp number'} {selected.whatsapp_enabled ? '' : '· WhatsApp disabled'}</p></div>{selected.opted_out && <p className="rounded-lg bg-red-50 px-2.5 py-2 font-bold text-red-700">Guardian has opted out of outbound communication.</p>}</div> : <p className="mt-4 text-xs text-slate-400">Choose a student to see communication details.</p>}
      </aside>
    </div>

    <section className="tafiti-card overflow-hidden">
      <div className="border-b border-slate-100 px-4 py-4 sm:px-5"><h2 className="text-sm font-extrabold text-[#10224A]">Delivery history</h2><p className="mt-1 text-[10px] text-slate-500">Latest SMS, email and WhatsApp delivery attempts.</p></div>
      <div className="overflow-x-auto"><table className="w-full min-w-[980px] border-collapse text-left"><thead><tr className="border-b border-slate-100 bg-[#F8FAFD]">{['Student','Channel','Recipient','Template','Status','Attempts','Created'].map((label) => <th key={label} className="px-4 py-3 text-[9px] font-extrabold uppercase tracking-[.04em] text-slate-400">{label}</th>)}</tr></thead><tbody className="divide-y divide-slate-100">{data.rows.map((row) => <tr key={row.id} className="hover:bg-blue-50/20"><td className="px-4 py-3"><p className="text-xs font-bold text-slate-800">{row.student}</p><p className="mt-0.5 text-[9px] text-slate-400">{row.reg_no}</p></td><td className="px-4 py-3 text-xs text-slate-600">{row.channel}</td><td className="px-4 py-3 text-xs text-slate-600">{row.recipient || '—'}</td><td className="px-4 py-3 text-xs text-slate-600">{row.template}</td><td className="px-4 py-3"><span className={`rounded-full border px-2 py-1 text-[9px] font-bold ${statusTone(row.status)}`}>{row.status}</span></td><td className="px-4 py-3 text-xs text-slate-600">{row.attempts}</td><td className="px-4 py-3 text-[10px] text-slate-500">{new Date(row.created).toLocaleString()}</td></tr>)}</tbody></table></div>
      {!data.rows.length && <div className="px-5 py-12 text-center text-xs text-slate-400">No outbound notifications have been attempted yet.</div>}
    </section>
  </section>;
}
