'use client';

import { FormEvent, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  AlertCircle,
  ArrowRight,
  Eye,
  EyeOff,
  GraduationCap,
  LoaderCircle,
  LockKeyhole,
  School,
  ShieldCheck,
  UserRound,
} from 'lucide-react';

import { Logo } from '@/components/brand/Logo';
import type { AuthFailure, AuthSuccess, LoginContext } from '@/lib/auth';

const workspaceOptions: { value: LoginContext; label: string; description: string }[] = [
  { value: 'admin', label: 'School management', description: 'Admin, head teacher, admissions, library and support roles' },
  { value: 'teacher', label: 'Teaching', description: 'Teacher and class-teacher workspaces' },
  { value: 'bursar', label: 'Finance', description: 'Bursar and school finance workspace' },
  { value: 'parent', label: 'Parent portal', description: 'Parent and guardian access' },
];

const errorMessages: Record<string, string> = {
  invalid_credentials: "We couldn't sign you in. Check your username and password and try again.",
  inactive_account: 'Your account is inactive. Please contact your school administrator.',
  portal_access_denied: 'This account does not have active portal access.',
  role_context_denied: 'This account is not assigned to the selected workspace.',
  network_error: "We couldn't connect to Tafiti. Check your connection and try again.",
};

export function ReferenceLoginPage({ notice }: { notice?: string }) {
  const router = useRouter();
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [workspace, setWorkspace] = useState<LoginContext>('admin');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(notice ? 'Your session has ended. Sign in again to continue.' : '');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!identifier.trim() || !password || submitting) return;
    setSubmitting(true); setFormError('');
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier: identifier.trim(), password, login_context: workspace, remember_me: rememberMe }),
      });
      const result = await response.json() as AuthSuccess | AuthFailure;
      if (!response.ok || !('user' in result)) {
        const code = 'code' in result ? result.code : undefined;
        setFormError((code && errorMessages[code]) || result.detail || 'Sign in failed. Please try again.');
        return;
      }
      router.replace(result.user.dashboard_path); router.refresh();
    } catch {
      setFormError(errorMessages.network_error);
    } finally { setSubmitting(false); }
  }

  const selected = workspaceOptions.find((item) => item.value === workspace) ?? workspaceOptions[0];

  return (
    <main className="relative min-h-dvh overflow-hidden bg-[#EFF5FD] text-[#10224A]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_18%_18%,rgba(70,143,255,.12),transparent_32rem),radial-gradient(circle_at_88%_82%,rgba(37,99,235,.08),transparent_28rem)]" aria-hidden="true" />
      <div className="relative mx-auto grid min-h-dvh max-w-[1500px] lg:grid-cols-[1.05fr_.95fr]">
        <section className="relative hidden overflow-hidden bg-[#081F49] px-12 py-12 text-white lg:flex lg:flex-col lg:justify-between xl:px-16">
          <div className="absolute -left-28 bottom-[-120px] h-[430px] w-[430px] rounded-full border-[52px] border-blue-400/[.08]" aria-hidden="true" />
          <div className="absolute -right-32 top-[-130px] h-[390px] w-[390px] rounded-full border border-white/[.08]" aria-hidden="true" />
          <div className="relative"><Logo inverted /></div>
          <div className="relative max-w-xl">
            <span className="inline-flex items-center gap-2 rounded-full border border-blue-300/20 bg-blue-400/10 px-3 py-1.5 text-[10px] font-bold uppercase tracking-[.12em] text-blue-100"><ShieldCheck size={13} /> Secure school workspace</span>
            <h1 className="mt-6 text-5xl font-extrabold leading-[1.04] tracking-[-.045em] xl:text-6xl">One place to run your school with clarity.</h1>
            <p className="mt-5 max-w-lg text-sm leading-7 text-blue-100/70">Students, academics, attendance, results, finance, staff, library and parent communication stay connected to the same Django business rules.</p>
            <div className="mt-8 grid max-w-lg grid-cols-2 gap-3"><div className="rounded-2xl border border-white/[.09] bg-white/[.06] p-4"><GraduationCap size={20} className="text-blue-300" /><p className="mt-3 text-sm font-bold">Academics</p><p className="mt-1 text-[10px] text-blue-100/55">Classes, results and attendance</p></div><div className="rounded-2xl border border-white/[.09] bg-white/[.06] p-4"><School size={20} className="text-blue-300" /><p className="mt-3 text-sm font-bold">Administration</p><p className="mt-1 text-[10px] text-blue-100/55">People, finance and operations</p></div></div>
          </div>
          <p className="relative text-[10px] font-semibold text-blue-100/45">Tafiti School Management System</p>
        </section>

        <section className="grid place-items-center px-4 py-8 sm:px-8 lg:px-12">
          <div className="w-full max-w-[470px]">
            <div className="mb-6 flex justify-center lg:hidden"><Logo accent="blue" /></div>
            <div className="rounded-[24px] border border-white bg-white/95 p-6 shadow-[0_28px_80px_rgba(31,76,139,.14)] backdrop-blur-xl sm:p-8">
              <div className="flex items-start gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-600"><ShieldCheck size={20} /></span><div><h2 className="text-[1.85rem] font-extrabold tracking-[-.04em] text-[#10224A]">Welcome back</h2><p className="mt-1 text-xs text-slate-500">Sign in to continue to your school portal.</p></div></div>

              <form onSubmit={submit} className="mt-6 space-y-4">
                <label className="block"><span className="mb-1.5 block text-[11px] font-extrabold text-slate-700">Username or email</span><span className="relative block"><UserRound className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" size={16} /><input value={identifier} onChange={(event) => setIdentifier(event.target.value)} disabled={submitting} autoComplete="username" placeholder="Enter your username or email" className="tafiti-input h-11 w-full pl-10 pr-3 text-sm" required /></span></label>

                <label className="block"><div className="mb-1.5 flex items-center justify-between"><span className="text-[11px] font-extrabold text-slate-700">Password</span><Link href="/forgot-password" className="text-[10px] font-bold text-blue-600 hover:underline">Forgot password?</Link></div><span className="relative block"><LockKeyhole className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" size={16} /><input value={password} onChange={(event) => setPassword(event.target.value)} disabled={submitting} type={showPassword ? 'text' : 'password'} autoComplete="current-password" placeholder="Enter your password" className="tafiti-input h-11 w-full pl-10 pr-11 text-sm" required /><button type="button" onClick={() => setShowPassword((value) => !value)} className="absolute right-2.5 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-lg text-slate-400 hover:bg-blue-50 hover:text-blue-600">{showPassword ? <EyeOff size={16} /> : <Eye size={16} />}</button></span></label>

                <label className="block"><div className="mb-1.5 flex items-center justify-between"><span className="text-[11px] font-extrabold text-slate-700">Workspace</span><span className="text-[9px] font-semibold text-slate-400">Your permissions are still enforced by Django</span></div><select value={workspace} onChange={(event) => setWorkspace(event.target.value as LoginContext)} disabled={submitting} className="tafiti-input h-11 w-full px-3 text-sm font-semibold"><option value="admin">School management</option><option value="teacher">Teaching</option><option value="bursar">Finance</option><option value="parent">Parent portal</option></select><p className="mt-1.5 text-[10px] leading-4 text-slate-400">{selected.description}. This avoids listing every assigned role on the login card.</p></label>

                <div className="flex items-center justify-between"><label className="inline-flex items-center gap-2 text-[10px] font-semibold text-slate-500"><input type="checkbox" checked={rememberMe} onChange={(event) => setRememberMe(event.target.checked)} className="h-4 w-4 accent-blue-600" />Remember me</label><span className="text-[9px] text-slate-400">Secure access</span></div>

                {formError && <div className="error-enter flex items-start gap-2 rounded-xl border border-red-100 bg-red-50 px-3.5 py-3 text-xs leading-5 text-red-700"><AlertCircle size={16} className="mt-0.5 shrink-0" />{formError}</div>}

                <button type="submit" disabled={submitting} className="flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#2F7DF4] to-[#1E64F0] text-sm font-extrabold text-white shadow-[0_10px_24px_rgba(37,99,235,.24)] transition hover:brightness-105 disabled:opacity-60">{submitting ? <><LoaderCircle className="animate-spin" size={17} />Signing in…</> : <>Sign in <ArrowRight size={16} /></>}</button>
              </form>
            </div>
            <p className="mt-5 text-center text-[9px] font-semibold text-slate-400">Access is limited to authorised members of your school community.</p>
          </div>
        </section>
      </div>
    </main>
  );
}
