'use client';

import { FormEvent, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { AlertCircle, CheckCircle2, Eye, EyeOff, LoaderCircle, LockKeyhole } from 'lucide-react';

import type { AuthSuccess } from '@/lib/auth';

type PasswordFormProps =
  | { mode: 'reset'; uid?: string; token?: string }
  | { mode: 'parent-setup'; uid?: string; token?: string }
  | { mode: 'change'; uid?: never; token?: never };

type ErrorPayload = {
  code?: string;
  detail?: string;
  password?: string[];
  confirm_password?: string[];
};

export function PasswordForm(props: PasswordFormProps) {
  const router = useRouter();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [checkingSession, setCheckingSession] = useState(props.mode === 'change');
  const [error, setError] = useState('');
  const [complete, setComplete] = useState(false);

  useEffect(() => {
    if (props.mode !== 'change') return;
    fetch('/api/auth/session', { cache: 'no-store' })
      .then((response) => {
        if (!response.ok) router.replace('/login?notice=session-expired');
      })
      .catch(() => router.replace('/login?notice=session-expired'))
      .finally(() => setCheckingSession(false));
  }, [props.mode, router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password.length < 8) {
      setError('Use at least 8 characters for your new password.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    if (props.mode !== 'change' && (!props.uid || !props.token)) {
      setError(props.mode === 'parent-setup' ? 'This parent setup link is incomplete. Ask the school for a new one.' : 'This password reset link is incomplete. Request a new one.');
      return;
    }

    setSubmitting(true);
    setError('');
    try {
      const endpoint = props.mode === 'change'
        ? '/api/auth/password-change'
        : props.mode === 'parent-setup'
          ? '/api/auth/parent-setup/confirm'
          : '/api/auth/password-reset/confirm';
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...(props.mode !== 'change' ? { uid: props.uid, token: props.token } : {}),
          password,
          confirm_password: confirmPassword,
        }),
      });
      const result = (await response.json()) as ErrorPayload | AuthSuccess;
      if (!response.ok) {
        const details = 'password' in result ? result.password?.[0] : undefined;
        setError(details || ('detail' in result ? result.detail : undefined) || 'We could not update your password. Try again.');
        if (response.status === 401) router.replace('/login?notice=session-expired');
        return;
      }

      if (props.mode === 'change' && 'user' in result) {
        router.replace(result.user.dashboard_path);
        router.refresh();
        return;
      }
      setComplete(true);
    } catch {
      setError("We couldn't connect to Tafiti. Check your connection and try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (checkingSession) {
    return <div className="mt-8 flex items-center justify-center gap-2 text-sm text-[#667085]"><LoaderCircle className="animate-spin" size={18} aria-hidden="true" />Checking your session…</div>;
  }

  if (complete) {
    return (
      <div className="mt-6">
        <div className="flex gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm leading-6 text-emerald-900" role="status">
          <CheckCircle2 className="mt-0.5 shrink-0 text-[#087F5B]" size={19} aria-hidden="true" />
          {props.mode === 'parent-setup' ? 'Your parent account is ready. Your setup link can no longer be reused.' : 'Your password has been reset successfully.'}
        </div>
        <Link href="/login" className="mt-5 flex h-12 items-center justify-center rounded-xl bg-[#087F5B] text-sm font-semibold text-white hover:bg-[#07543F]">Continue to sign in</Link>
      </div>
    );
  }

  return (
    <form className="mt-7 space-y-5" onSubmit={handleSubmit} noValidate>
      <div>
        <label htmlFor="new-password" className="mb-2 block text-sm font-semibold text-[#303533]">New password</label>
        <div className="group relative">
          <LockKeyhole className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#89918F] group-focus-within:text-[#087F5B]" size={18} aria-hidden="true" />
          <input id="new-password" type={showPassword ? 'text' : 'password'} value={password} onChange={(event) => { setPassword(event.target.value); setError(''); }} autoComplete="new-password" disabled={submitting} className="h-12 w-full rounded-xl border border-[#DFE3E1] bg-[#F7F8F8] pl-11 pr-12 text-[15px] outline-none transition-all focus:border-[#087F5B] focus:bg-white focus:ring-4 focus:ring-emerald-100/60" />
          <button type="button" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? 'Hide password' : 'Show password'} className="absolute right-2.5 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-lg text-[#7B8582] hover:bg-[#E9F5F1] hover:text-[#087F5B]">
            {showPassword ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
          </button>
        </div>
      </div>
      <div>
        <label htmlFor="confirm-password" className="mb-2 block text-sm font-semibold text-[#303533]">Confirm new password</label>
        <div className="group relative">
          <LockKeyhole className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#89918F] group-focus-within:text-[#087F5B]" size={18} aria-hidden="true" />
          <input id="confirm-password" type={showPassword ? 'text' : 'password'} value={confirmPassword} onChange={(event) => { setConfirmPassword(event.target.value); setError(''); }} autoComplete="new-password" disabled={submitting} className="h-12 w-full rounded-xl border border-[#DFE3E1] bg-[#F7F8F8] pl-11 pr-4 text-[15px] outline-none transition-all focus:border-[#087F5B] focus:bg-white focus:ring-4 focus:ring-emerald-100/60" />
        </div>
      </div>
      <p className="text-xs leading-5 text-[#7B8582]">Use at least 8 characters. Avoid common words and passwords you use elsewhere.</p>
      <div aria-live="polite">
        {error && <p className="error-enter flex items-start gap-1.5 rounded-xl border border-red-200 bg-red-50 p-3 text-xs leading-5 text-red-700"><AlertCircle className="mt-0.5 shrink-0" size={14} aria-hidden="true" />{error}</p>}
      </div>
      <button type="submit" disabled={submitting} className="flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#087F5B] text-sm font-semibold text-white transition-all hover:bg-[#07543F] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-emerald-200 active:scale-[0.99] disabled:opacity-65">
        {submitting && <LoaderCircle className="animate-spin" size={18} aria-hidden="true" />}
        {submitting ? 'Updating password…' : props.mode === 'parent-setup' ? 'Create my password' : 'Update password'}
      </button>
    </form>
  );
}
