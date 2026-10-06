'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  Archive,
  BellRing,
  CalendarDays,
  LoaderCircle,
  MessageCircle,
  MessagesSquare,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Send,
  X,
} from 'lucide-react';

import type { WorkspaceFormSchema } from '@/lib/workspace';
import { useToast } from '@/components/ui/ToastProvider';
import { ResourceFormDialog } from '@/components/workspace/ResourceFormDialog';

type ConsolePayload = {
  rows: Record<string, unknown>[];
  form: WorkspaceFormSchema;
  archived?: boolean;
};

type ThreadPayload = {
  thread: Record<string, unknown>;
  messages: {
    id: number;
    sender: string;
    sender_id: number | null;
    mine: boolean;
    body: string;
    created: string;
  }[];
  form: WorkspaceFormSchema;
};

function dateLabel(value: unknown) {
  const text = String(value ?? '');
  if (!text) return '—';
  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) return text;
  return new Intl.DateTimeFormat(undefined, { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }).format(parsed);
}

function withBodyField(schema: WorkspaceFormSchema): WorkspaceFormSchema {
  if (schema.fields.some((field) => field.name === 'body')) return schema;
  return {
    ...schema,
    fields: [
      ...schema.fields,
      {
        name: 'body',
        label: 'Message',
        type: 'textarea',
        required: false,
        disabled: false,
        help_text: 'Optional opening message. You can also open the conversation and reply afterwards.',
        options: [],
        initial: '',
      },
    ],
  };
}

export function ReferenceCommunicationConsoleView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  const requestedTab = searchParams.get('tab') || 'messages';
  const tab = ['messages', 'announcements', 'events', 'archived'].includes(requestedTab) ? requestedTab : 'messages';
  const [data, setData] = useState<ConsolePayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [reloadKey, setReloadKey] = useState(0);
  const [formOpen, setFormOpen] = useState(false);
  const [formSchema, setFormSchema] = useState<WorkspaceFormSchema | null>(null);
  const [formLoading, setFormLoading] = useState(false);
  const [formErrors, setFormErrors] = useState<Record<string, string[]>>({});
  const [formAction, setFormAction] = useState<{ screen: string; id?: number } | null>(null);
  const [thread, setThread] = useState<ThreadPayload | null>(null);
  const [threadLoading, setThreadLoading] = useState(false);
  const [reply, setReply] = useState('');

  const screen = tab === 'archived' ? 'messages' : tab;
  const archived = tab === 'archived';

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    const suffix = screen === 'messages' && archived ? '?archived=1' : '';
    fetch(`/api/workspace/communication-console/${screen}${suffix}`, { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Communication could not be loaded.');
        return payload as ConsolePayload;
      })
      .then((payload) => {
        if (screen === 'messages') payload.form = withBodyField(payload.form);
        setData(payload);
        setQuery('');
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Communication could not be loaded.');
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [archived, reloadKey, screen]);

  const rows = useMemo(() => {
    const text = query.trim().toLowerCase();
    if (!text) return data?.rows ?? [];
    return (data?.rows ?? []).filter((row) => Object.values(row).some((value) => String(value ?? '').toLowerCase().includes(text)));
  }, [data, query]);

  function selectTab(next: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set('tab', next);
    router.replace(`?${params.toString()}`, { scroll: false });
    setThread(null);
  }

  async function openForm(screenName: string, id?: number, fallback?: WorkspaceFormSchema) {
    setFormAction({ screen: screenName, id });
    setFormOpen(true);
    setFormErrors({});
    if (!id && fallback) {
      setFormSchema(screenName === 'messages' ? withBodyField(fallback) : fallback);
      return;
    }
    setFormSchema(null);
    setFormLoading(true);
    try {
      const path = id ? `/api/workspace/communication-console/${screenName}/${id}` : `/api/workspace/communication-console/${screenName}`;
      const response = await fetch(path, { cache: 'no-store' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'The form could not be opened.');
      const schema = (payload.form ?? payload) as WorkspaceFormSchema;
      setFormSchema(screenName === 'messages' ? withBodyField(schema) : schema);
    } catch (reason: unknown) {
      toast.error('Could not open communication form', reason instanceof Error ? reason.message : 'Please try again.');
      setFormOpen(false);
    } finally { setFormLoading(false); }
  }

  async function saveForm(values: Record<string, unknown>) {
    if (!formAction) return;
    setFormLoading(true);
    setFormErrors({});
    try {
      const path = formAction.id
        ? `/api/workspace/communication-console/${formAction.screen}/${formAction.id}`
        : `/api/workspace/communication-console/${formAction.screen}`;
      const response = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values) });
      const payload = await response.json();
      if (!response.ok) {
        setFormErrors((payload.errors as Record<string, string[]>) ?? {});
        throw new Error(payload.detail || 'The communication action could not be completed.');
      }
      toast.success('Communication updated', payload.detail || 'Saved successfully.');
      setFormOpen(false);
      setReloadKey((value) => value + 1);
      if (formAction.screen === 'messages' && typeof payload.id === 'number') void openThread(payload.id);
    } catch (reason: unknown) {
      toast.error('Communication action failed', reason instanceof Error ? reason.message : 'Please try again.');
    } finally { setFormLoading(false); }
  }

  async function openThread(id: number) {
    setThreadLoading(true);
    try {
      const response = await fetch(`/api/workspace/communication-console/thread/${id}`, { cache: 'no-store' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Conversation could not be opened.');
      setThread(payload as ThreadPayload);
      setReply('');
    } catch (reason: unknown) {
      toast.error('Could not open conversation', reason instanceof Error ? reason.message : 'Please try again.');
    } finally { setThreadLoading(false); }
  }

  async function threadAction(action: 'reply' | 'archive' | 'unarchive') {
    if (!thread || typeof thread.thread.id !== 'number') return;
    if (action === 'reply' && !reply.trim()) return;
    setThreadLoading(true);
    try {
      const response = await fetch(`/api/workspace/communication-console/thread/${thread.thread.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(action === 'reply' ? { action: 'reply', body: reply.trim() } : { action }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Conversation could not be updated.');
      toast.success('Conversation updated', payload.detail || 'Saved.');
      if (action === 'reply') {
        setReply('');
        await openThread(thread.thread.id as number);
      } else {
        setThread(null);
        setReloadKey((value) => value + 1);
      }
    } catch (reason: unknown) {
      toast.error('Conversation action failed', reason instanceof Error ? reason.message : 'Please try again.');
    } finally { setThreadLoading(false); }
  }

  const pageTitle = tab === 'messages' ? 'Inbox' : tab === 'archived' ? 'Archived conversations' : tab === 'announcements' ? 'Announcements' : 'Events';
  const createLabel = tab === 'messages' ? 'New conversation' : tab === 'announcements' ? 'New announcement' : tab === 'events' ? 'New event' : '';

  return (
    <section>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex items-start gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-600"><MessagesSquare size={21} /></span><div><h1 className="text-[1.65rem] font-extrabold tracking-[-0.035em] text-[#10224A]">Communication</h1><p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">Messages, announcements and events stay in one connected school communication workspace.</p></div></div>
        <div className="flex flex-wrap gap-2"><button type="button" onClick={() => setReloadKey((value) => value + 1)} className="clay-button-secondary"><RefreshCw size={14} />Refresh</button>{createLabel && data?.form && <button type="button" onClick={() => void openForm(screen, undefined, data.form)} className="clay-button-primary"><Plus size={14} />{createLabel}</button>}</div>
      </div>

      <div className="mb-4 overflow-x-auto rounded-xl border border-slate-200 bg-white p-1.5 shadow-[0_5px_16px_rgba(28,55,97,.035)]"><div className="flex min-w-max gap-1">{[
        ['messages','Inbox',MessageCircle],['announcements','Announcements',BellRing],['events','Events',CalendarDays],['archived','Archived',Archive],
      ].map(([key,label,Icon]) => { const TabIcon = Icon as typeof MessageCircle; const active = tab === key; return <button key={String(key)} type="button" onClick={() => selectTab(String(key))} className={`inline-flex h-9 items-center gap-1.5 rounded-lg px-3 text-[10px] font-extrabold ${active ? 'bg-blue-600 text-white shadow-[0_5px_12px_rgba(37,99,235,.18)]' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'}`}><TabIcon size={13} />{String(label)}</button>; })}</div></div>

      <section className="tafiti-card overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-slate-100 px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between sm:px-5"><div><h2 className="text-sm font-extrabold text-[#10224A]">{pageTitle}</h2><p className="mt-1 text-[10px] text-slate-500">{rows.length} item{rows.length === 1 ? '' : 's'} in this view.</p></div><div className="relative w-full sm:max-w-[330px]"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={`Search ${pageTitle.toLowerCase()}…`} className="tafiti-input h-9 w-full pl-9 pr-3 text-xs" /></div></div>

        {loading && !data ? <div className="grid min-h-[340px] place-items-center"><LoaderCircle className="animate-spin text-blue-600" size={24} /></div>
          : error ? <div className="px-5 py-12 text-center"><p className="text-sm font-bold text-slate-800">Communication unavailable</p><p className="mt-2 text-xs text-slate-500">{error}</p></div>
          : screen === 'messages' ? <div className="divide-y divide-slate-100">{rows.map((row, index) => <button key={String(row.id ?? index)} type="button" onClick={() => typeof row.id === 'number' && void openThread(row.id)} className="flex w-full items-start gap-3 px-4 py-4 text-left transition hover:bg-blue-50/30 sm:px-5"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-blue-50 text-blue-600"><MessageCircle size={16} /></span><div className="min-w-0 flex-1"><div className="flex items-center justify-between gap-3"><p className="truncate text-xs font-extrabold text-slate-800">{String(row.subject ?? 'Conversation')}</p><span className="shrink-0 text-[9px] font-semibold text-slate-400">{dateLabel(row.updated)}</span></div><p className="mt-1 truncate text-[10px] font-semibold text-slate-500">{String(row.participants ?? '')}</p><p className="mt-1 line-clamp-2 text-[10px] leading-4 text-slate-400">{String(row.preview ?? '')}</p></div></button>)}</div>
          : screen === 'announcements' ? <div className="divide-y divide-slate-100">{rows.map((row, index) => <div key={String(row.id ?? index)} className="flex items-start gap-3 px-4 py-4 sm:px-5"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-amber-50 text-amber-600"><BellRing size={16} /></span><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><p className="text-xs font-extrabold text-slate-800">{String(row.title ?? '—')}</p><span className="rounded-full bg-slate-100 px-2 py-0.5 text-[8px] font-bold text-slate-500">{String(row.audience ?? '')}</span><span className="rounded-full bg-blue-50 px-2 py-0.5 text-[8px] font-bold text-blue-600">{String(row.priority ?? '')}</span></div><p className="mt-1 line-clamp-2 text-[10px] leading-4 text-slate-500">{String(row.body ?? '')}</p><p className="mt-1.5 text-[9px] text-slate-400">Starts {dateLabel(row.starts)} · {String(row.status ?? '')}</p></div>{typeof row.id === 'number' && <button type="button" onClick={() => void openForm('announcements', row.id)} className="clay-row-action"><Pencil size={13} /></button>}</div>)}</div>
          : <div className="divide-y divide-slate-100">{rows.map((row, index) => <div key={String(row.id ?? index)} className="flex items-start gap-3 px-4 py-4 sm:px-5"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-violet-50 text-violet-600"><CalendarDays size={16} /></span><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><p className="text-xs font-extrabold text-slate-800">{String(row.title ?? '—')}</p><span className="rounded-full bg-slate-100 px-2 py-0.5 text-[8px] font-bold text-slate-500">{String(row.audience ?? '')}</span></div><p className="mt-1 line-clamp-2 text-[10px] text-slate-500">{String(row.description ?? '')}</p><p className="mt-1.5 text-[9px] text-slate-400">{dateLabel(row.starts)} · {String(row.location ?? 'School')}</p></div>{typeof row.id === 'number' && <button type="button" onClick={() => void openForm('events', row.id)} className="clay-row-action"><Pencil size={13} /></button>}</div>)}</div>}
        {!loading && !rows.length && <div className="px-5 py-12 text-center text-xs text-slate-400">Nothing to show in {pageTitle.toLowerCase()}.</div>}
      </section>

      {thread && <><button type="button" onClick={() => setThread(null)} className="fixed inset-0 z-40 bg-slate-950/30 backdrop-blur-[1px]" aria-label="Close conversation" /><aside className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[500px] flex-col border-l border-slate-200 bg-[#F7FAFD] shadow-[-20px_0_50px_rgba(15,39,71,.13)]"><div className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-4"><div className="min-w-0"><p className="truncate text-sm font-extrabold text-[#10224A]">{String(thread.thread.subject ?? 'Conversation')}</p><p className="mt-1 truncate text-[10px] text-slate-400">{String(thread.thread.participants ?? '')}</p></div><button type="button" onClick={() => setThread(null)} className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-slate-200 text-slate-500"><X size={16} /></button></div><div className="flex-1 space-y-3 overflow-y-auto p-5">{thread.messages.map((message) => <div key={message.id} className={`flex ${message.mine ? 'justify-end' : 'justify-start'}`}><div className={`max-w-[82%] rounded-2xl px-3.5 py-3 ${message.mine ? 'rounded-br-md bg-blue-600 text-white' : 'rounded-bl-md border border-slate-100 bg-white text-slate-700 shadow-sm'}`}><p className={`text-[9px] font-bold ${message.mine ? 'text-blue-100' : 'text-slate-400'}`}>{message.sender}</p><p className="mt-1 whitespace-pre-wrap text-xs leading-5">{message.body}</p><p className={`mt-1.5 text-[8px] ${message.mine ? 'text-blue-100/75' : 'text-slate-400'}`}>{dateLabel(message.created)}</p></div></div>)}{!thread.messages.length && <div className="py-12 text-center text-xs text-slate-400">No messages yet.</div>}</div><div className="border-t border-slate-200 bg-white p-4"><textarea value={reply} onChange={(event) => setReply(event.target.value)} placeholder="Write a reply…" rows={3} className="tafiti-input min-h-[76px] w-full resize-none px-3 py-2.5 text-xs" /><div className="mt-2 flex items-center justify-between gap-2"><button type="button" disabled={threadLoading} onClick={() => void threadAction(archived ? 'unarchive' : 'archive')} className="clay-button-secondary"><Archive size={14} />{archived ? 'Unarchive' : 'Archive'}</button><button type="button" disabled={threadLoading || !reply.trim()} onClick={() => void threadAction('reply')} className="clay-button-primary">{threadLoading ? <LoaderCircle className="animate-spin" size={14} /> : <Send size={14} />}Send</button></div></div></aside></>}

      <ResourceFormDialog open={formOpen} schema={formSchema} loading={formLoading} errors={formErrors} onClose={() => { setFormOpen(false); setFormAction(null); setFormErrors({}); }} onSubmit={saveForm} />
    </section>
  );
}
