'use client';

import { FormEvent, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  AlertCircle,
  ArrowRight,
  Eye,
  EyeOff,
  LoaderCircle,
  LockKeyhole,
  ShieldCheck,
  UserRound,
} from 'lucide-react';

import { Logo } from '@/components/brand/Logo';
import type { AuthFailure, AuthSuccess } from '@/lib/auth';

const errorMessages: Record<string, string> = {
  invalid_credentials: "We couldn't sign you in. Check your username and password and try again.",
  inactive_account: 'Your account is inactive. Please contact your school administrator.',
  portal_access_denied: 'This account does not have active portal access.',
  temporary_password_expired: 'Your temporary password has expired. Please contact your school administrator.',
  network_error: "We couldn't connect to Tafiti. Check your connection and try again.",
};

export function ReferenceLoginPage({ notice }: { notice?: string }) {
  const router = useRouter();
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(notice ? 'Your session has ended. Sign in again to continue.' : '');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!identifier.trim() || !password || submitting) return;
    setSubmitting(true);
    setFormError('');

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier: identifier.trim(), password, remember_me: rememberMe }),
      });
      const result = await response.json() as AuthSuccess | AuthFailure;
      if (!response.ok || !('user' in result)) {
        const code = 'code' in result ? result.code : undefined;
        setFormError((code && errorMessages[code]) || result.detail || 'Sign in failed. Please try again.');
        return;
      }

      if (result.user.must_change_password) {
        router.replace('/account/change-password');
      } else if (result.user.roles.length > 1) {
        router.replace('/choose-role');
      } else {
        router.replace(result.user.dashboard_path);
      }
      router.refresh();
    } catch {
      setFormError(errorMessages.network_error);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="relative grid min-h-dvh place-items-center overflow-hidden bg-[#dcecff] px-4 py-7 text-[#102754] sm:px-6 sm:py-10">
      <Image
        src="/images/tafiti-campus-login.png"
        alt=""
        fill
        priority
        sizes="100vw"
        className="object-cover object-center"
      />
      <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(230,243,255,.14),rgba(224,238,255,.24))]" aria-hidden="true" />
      <div className="absolute inset-0 bg-white/[.08] backdrop-blur-[1px]" aria-hidden="true" />

      <section className="relative isolate w-full max-w-[610px] overflow-hidden rounded-[28px] border border-white/80 bg-[linear-gradient(142deg,rgba(255,255,255,.93),rgba(247,250,255,.89))] px-6 py-9 shadow-[0_28px_80px_rgba(28,65,116,.24),0_2px_6px_rgba(39,70,114,.12)] backdrop-blur-[18px] sm:px-10 sm:py-12">
        <div className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full border-[48px] border-blue-100/55" aria-hidden="true" />
        <div className="pointer-events-none absolute -bottom-36 -left-28 h-60 w-60 rounded-full bg-blue-100/25 blur-2xl" aria-hidden="true" />

        <div className="relative mx-auto w-full max-w-[486px]">
          <div className="flex justify-center">
            <Logo accent="blue" />
          </div>

          <header className="mt-9 text-center sm:mt-10">
            <h1 className="text-[2.2rem] font-extrabold leading-none tracking-[-.055em] text-[#102754] sm:text-[2.65rem]">Welcome back</h1>
            <p className="mt-3 text-base font-medium tracking-[-.02em] text-[#6e82a6] sm:text-[1.05rem]">Sign in to your account</p>
          </header>

          <form onSubmit={submit} className="mt-9 space-y-4 sm:mt-10 sm:space-y-[18px]">
            <label className="block">
              <span className="sr-only">Username or email</span>
              <span className="relative block">
                <UserRound className="pointer-events-none absolute left-5 top-1/2 -translate-y-1/2 text-[#7990b7]" size={21} strokeWidth={1.85} aria-hidden="true" />
                <input
                  value={identifier}
                  onChange={(event) => setIdentifier(event.target.value)}
                  disabled={submitting}
                  autoComplete="username"
                  placeholder="Username or email"
                  className="h-[65px] w-full rounded-2xl border border-[#d7e1f0] bg-white/72 pl-[66px] pr-5 text-[1.02rem] font-medium text-[#142957] outline-none transition placeholder:text-[#8ba0c1] hover:border-[#aec5e7] focus:border-[#4d8dff] focus:bg-white focus:ring-4 focus:ring-blue-500/10 disabled:cursor-not-allowed disabled:opacity-70"
                  required
                />
              </span>
            </label>

            <label className="block">
              <span className="sr-only">Password</span>
              <span className="relative block">
                <LockKeyhole className="pointer-events-none absolute left-5 top-1/2 -translate-y-1/2 text-[#7990b7]" size={21} strokeWidth={1.85} aria-hidden="true" />
                <input
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  disabled={submitting}
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="Password"
                  className="h-[65px] w-full rounded-2xl border border-[#d7e1f0] bg-white/72 pl-[66px] pr-16 text-[1.02rem] font-medium text-[#142957] outline-none transition placeholder:text-[#8ba0c1] hover:border-[#aec5e7] focus:border-[#4d8dff] focus:bg-white focus:ring-4 focus:ring-blue-500/10 disabled:cursor-not-allowed disabled:opacity-70"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((value) => !value)}
                  className="absolute right-3 top-1/2 grid h-10 w-10 -translate-y-1/2 place-items-center rounded-xl text-[#7990b7] transition hover:bg-blue-50 hover:text-[#276dea] focus:outline-none focus:ring-4 focus:ring-blue-500/10"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={21} strokeWidth={1.8} /> : <Eye size={21} strokeWidth={1.8} />}
                </button>
              </span>
            </label>

            <div className="flex items-center justify-between gap-4 pt-1">
              <label className="inline-flex cursor-pointer items-center gap-2.5 text-sm font-semibold text-[#5d7298]">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(event) => setRememberMe(event.target.checked)}
                  className="h-5 w-5 cursor-pointer rounded-[5px] border-[#aebfd8] accent-[#2472ef]"
                />
                Remember me
              </label>
              <Link href="/forgot-password" className="text-sm font-bold text-[#1265ed] transition hover:text-[#0b4bb8] hover:underline">
                Forgot password?
              </Link>
            </div>

            {formError && (
              <div className="error-enter flex items-start gap-2.5 rounded-2xl border border-red-200 bg-red-50/95 px-4 py-3.5 text-sm leading-5 text-red-700" role="alert">
                <AlertCircle size={18} className="mt-0.5 shrink-0" aria-hidden="true" />
                <span>{formError}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="flex h-[65px] w-full items-center justify-center gap-3 rounded-2xl bg-[linear-gradient(110deg,#2d7af3,#1459ee)] text-lg font-extrabold tracking-[-.025em] text-white shadow-[0_16px_28px_rgba(30,99,234,.27)] transition hover:-translate-y-0.5 hover:shadow-[0_20px_32px_rgba(30,99,234,.35)] focus:outline-none focus:ring-4 focus:ring-blue-500/25 disabled:cursor-not-allowed disabled:translate-y-0 disabled:opacity-60"
            >
              {submitting ? <><LoaderCircle className="animate-spin" size={21} aria-hidden="true" />Signing in…</> : <>Sign in <ArrowRight size={21} strokeWidth={2.2} aria-hidden="true" /></>}
            </button>
          </form>

          <div className="mt-9 flex items-center gap-4 text-[#8195b6] sm:mt-10">
            <span className="h-px flex-1 bg-[#dbe4f1]" />
            <span className="inline-flex items-center gap-2 whitespace-nowrap text-[.82rem] font-medium">
              <ShieldCheck size={18} strokeWidth={1.9} aria-hidden="true" />
              Secure access
            </span>
            <span className="h-px flex-1 bg-[#dbe4f1]" />
          </div>
        </div>
      </section>
    </main>
  );
}
