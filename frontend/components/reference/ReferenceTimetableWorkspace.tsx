'use client';

import { useEffect, useMemo, useState } from 'react';
import { CalendarDays, CheckCircle2, LoaderCircle, Lock, Plus, Trash2, Unlock } from 'lucide-react';
import { useToast } from '@/components/ui/ToastProvider';

type Entry = { id:number; weekday:string; weekday_label:string; time_slot_id:number; time:string; subject:string; subject_id:number; teacher:string; teacher_id:number|null; classroom:string; classroom_id:number|null };
type Hub = {
  title:string; description:string; role:string; period:{year:string;term:string};
  streams:{id:number;label:string;locked:boolean;students:number}[]; selected_stream_id:number|null; selected_locked:boolean;
  weekdays:{value:string;label:string}[]; time_slots:{id:number;label:string;start:string;end:string}[];
  breaks:{weekday:string;time_slot_id:number;name:string}[]; entries:Entry[];
  allocations:{id:number;subject_id:number;subject:string;teacher_id:number|null;teacher:string}[];
  classrooms:{id:number;label:string;capacity:number}[];
  metrics:{label:string;value:number|string;hint:string;tone:string}[];
  permissions:{edit:boolean;lock:boolean};
};

export function ReferenceTimetableWorkspace() {
  const toast = useToast();
  const [data,setData] = useState<Hub|null>(null);
  const [stream,setStream] = useState('');
  const [loading,setLoading] = useState(true);
  const [saving,setSaving] = useState(false);
  const [draft,setDraft] = useState({weekday:'MON',time_slot_id:'',allocation_id:'',classroom_id:''});
  const [reload,setReload] = useState(0);

  useEffect(()=>{
    const controller=new AbortController(); setLoading(true);
    const query=stream?`?class_stream=${stream}`:'';
    fetch(`/api/workspace/timetable-console/hub${query}`,{cache:'no-store',signal:controller.signal})
      .then(async r=>{const p=await r.json(); if(!r.ok) throw new Error(p.detail||'Timetable could not be loaded.'); return p as Hub;})
      .then(p=>{setData(p); if(!stream&&p.selected_stream_id) setStream(String(p.selected_stream_id));})
      .catch((e:unknown)=>{if(!controller.signal.aborted) toast.error('Timetable unavailable',e instanceof Error?e.message:'Please try again.');})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return ()=>controller.abort();
  },[stream,reload,toast]);

  const entryMap=useMemo(()=>new Map((data?.entries??[]).map(e=>[`${e.weekday}:${e.time_slot_id}`,e])),[data]);
  const breakMap=useMemo(()=>new Map((data?.breaks??[]).map(b=>[`${b.weekday}:${b.time_slot_id}`,b.name])),[data]);

  async function post(payload:Record<string,unknown>){
    setSaving(true);
    try{
      const r=await fetch('/api/workspace/timetable-console/hub',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...payload,class_stream_id:Number(stream)})});
      const p=await r.json();
      if(!r.ok) throw new Error(p.detail||Object.values(p.errors??{}).flat().join(' ')||'Timetable could not be updated.');
      toast.success('Timetable updated',p.detail||'Saved successfully.'); setReload(v=>v+1); return true;
    }catch(e:unknown){toast.error('Timetable not updated',e instanceof Error?e.message:'Please try again.'); return false;}
    finally{setSaving(false);}
  }

  async function addEntry(){
    if(!draft.time_slot_id||!draft.allocation_id){toast.error('Missing details','Choose a period and subject allocation.');return;}
    const ok=await post({action:'save_entry',weekday:draft.weekday,time_slot_id:Number(draft.time_slot_id),allocation_id:Number(draft.allocation_id),classroom_id:draft.classroom_id?Number(draft.classroom_id):null});
    if(ok)setDraft(v=>({...v,time_slot_id:'',allocation_id:'',classroom_id:''}));
  }

  if(loading&&!data)return <div className="tafiti-card grid min-h-[440px] place-items-center"><div className="text-center text-xs font-semibold text-slate-500"><LoaderCircle className="mx-auto mb-3 animate-spin text-blue-600" size={24}/>Loading timetable…</div></div>;
  if(!data)return null;

  return <section>
    <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
      <div className="flex items-start gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-600"><CalendarDays size={21}/></span><div><h1 className="text-[1.65rem] font-extrabold tracking-[-.035em] text-[#10224A]">Timetable</h1><p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">{data.description}</p><p className="mt-1 text-[10px] font-bold text-blue-700">{data.period.year} · {data.period.term}</p></div></div>
      <div className="flex flex-wrap gap-2"><select value={stream} onChange={e=>setStream(e.target.value)} className="tafiti-input h-10 min-w-[240px] px-3 text-xs font-bold">{data.streams.map(s=><option key={s.id} value={s.id}>{s.label}</option>)}</select>{data.permissions.lock&&stream&&<button disabled={saving} onClick={()=>void post({action:'toggle_lock',locked:!data.selected_locked})} className="clay-button-secondary">{data.selected_locked?<Unlock size={14}/>:<Lock size={14}/>} {data.selected_locked?'Unlock':'Lock'}</button>}</div>
    </div>

    <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{data.metrics.map(m=><article key={m.label} className="tafiti-kpi"><p className="text-[9px] font-bold uppercase tracking-[.06em] text-slate-400">{m.label}</p><p className="mt-1 text-xl font-extrabold text-[#10224A]">{m.value}</p><p className="mt-1 text-[9px] text-slate-400">{m.hint}</p></article>)}</div>

    {data.selected_locked&&<div className="mb-4 flex items-center gap-2 rounded-xl border border-amber-100 bg-amber-50 p-3 text-xs font-semibold text-amber-800"><Lock size={15}/>This class timetable is locked. Unlock it before changing lessons.</div>}

    {data.permissions.edit&&!data.selected_locked&&<section className="tafiti-card mb-4 p-4"><div className="mb-3 flex items-center gap-2"><Plus size={16} className="text-blue-600"/><h2 className="text-sm font-extrabold text-[#10224A]">Add lesson</h2></div><div className="grid gap-2 md:grid-cols-5"><select value={draft.weekday} onChange={e=>setDraft(v=>({...v,weekday:e.target.value}))} className="tafiti-input h-10 px-3 text-xs">{data.weekdays.map(d=><option key={d.value} value={d.value}>{d.label}</option>)}</select><select value={draft.time_slot_id} onChange={e=>setDraft(v=>({...v,time_slot_id:e.target.value}))} className="tafiti-input h-10 px-3 text-xs"><option value="">Choose period</option>{data.time_slots.map(s=><option key={s.id} value={s.id}>{s.label}</option>)}</select><select value={draft.allocation_id} onChange={e=>setDraft(v=>({...v,allocation_id:e.target.value}))} className="tafiti-input h-10 px-3 text-xs"><option value="">Choose subject</option>{data.allocations.map(a=><option key={a.id} value={a.id}>{a.subject} · {a.teacher}</option>)}</select><select value={draft.classroom_id} onChange={e=>setDraft(v=>({...v,classroom_id:e.target.value}))} className="tafiti-input h-10 px-3 text-xs"><option value="">No room</option>{data.classrooms.map(r=><option key={r.id} value={r.id}>{r.label}</option>)}</select><button disabled={saving} onClick={()=>void addEntry()} className="clay-button-primary justify-center"><Plus size={14}/>Add lesson</button></div></section>}

    <section className="tafiti-card overflow-hidden"><div className="border-b border-slate-100 px-4 py-3.5"><h2 className="text-sm font-extrabold text-[#10224A]">Weekly teaching grid</h2><p className="mt-1 text-[10px] text-slate-500">Conflicting teacher, classroom, break and class periods are rejected by Django validation.</p></div><div className="overflow-x-auto"><table className="w-full min-w-[950px] border-collapse text-left"><thead><tr className="bg-[#F8FAFD] border-b border-slate-100"><th className="px-4 py-3 text-[9px] font-extrabold text-slate-400">PERIOD</th>{data.weekdays.map(d=><th key={d.value} className="px-3 py-3 text-[9px] font-extrabold text-slate-400">{d.label.toUpperCase()}</th>)}</tr></thead><tbody className="divide-y divide-slate-100">{data.time_slots.map(slot=><tr key={slot.id}><td className="px-4 py-3 text-[10px] font-extrabold text-slate-600">{slot.label}</td>{data.weekdays.map(day=>{const key=`${day.value}:${slot.id}`; const entry=entryMap.get(key); const br=breakMap.get(key); return <td key={key} className="min-w-[155px] px-2 py-2 align-top">{br?<div className="rounded-lg border border-amber-100 bg-amber-50 p-3 text-center text-[10px] font-extrabold text-amber-700">{br}</div>:entry?<div className="group rounded-lg border border-blue-100 bg-blue-50/60 p-2.5"><div className="flex items-start gap-2"><div className="min-w-0 flex-1"><p className="truncate text-[10px] font-extrabold text-blue-900">{entry.subject}</p><p className="mt-1 truncate text-[9px] text-slate-500">{entry.teacher}</p><p className="mt-0.5 truncate text-[9px] text-slate-400">{entry.classroom}</p></div>{data.permissions.edit&&!data.selected_locked&&<button title="Remove lesson" onClick={()=>void post({action:'delete_entry',entry_id:entry.id})} className="grid h-7 w-7 shrink-0 place-items-center rounded-md text-slate-400 opacity-0 transition hover:bg-red-50 hover:text-red-600 group-hover:opacity-100"><Trash2 size={12}/></button>}</div></div>:<div className="grid min-h-[58px] place-items-center rounded-lg border border-dashed border-slate-200 text-[9px] text-slate-300">Open</div>}</td>})}</tr>)}</tbody></table></div></section>

    <div className="mt-4 flex items-center gap-2 text-[10px] font-semibold text-slate-400"><CheckCircle2 size={13} className="text-emerald-500"/>Teacher and room conflicts are validated across the same academic year and term.</div>
  </section>;
}
