'use client';

import { FormEvent, useMemo, useState } from 'react';
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
import type { AuthFailure, AuthSuccess, LoginContext } from '@/lib/auth';
import { BrandPanel } from './BrandPanel';
import { RoleSelector, roleOptions } from './RoleSelector';

type FieldErrors = {
  identifier?: string;
  password?: string;
};

const errorMessages: Record<string, string> = {
  invalid_credentials: "We couldn't sign you in. Check your username and password and try again.",
  inactive_account: 'Your account is currently inactive. Please contact your school administrator.',
  portal_access_denied: 'This account does not have active portal access. Please contact your school administrator.',
  role_context_denied: 'This account is not assigned to the selected workspace. Choose the role you use at this school.',
  network_error: "We couldn't connect to Tafiti. Check your connection and try again.",
};

export function LoginPage({ notice }: { notice?: string }) {
  const router = useRouter();
  const [loginContext, setLoginContext] = useState<LoginContext>('admin');
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState(
    notice ? 'Your session has ended. Sign in again to continue.' : '',
  );

  const activeRole = useMemo(
    () => roleOptions.find((role) => role.value === loginContext) ?? roleOptions[0],
    [loginContext],
  );

  function validate(): boolean {
    const nextErrors: FieldErrors = {};
    if (!identifier.trim()) nextErrors.identifier = 'Enter your username or email.';
    if (!password) nextErrors.password = 'Enter your password.';
    setFieldErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting || !validate()) return;

    setSubmitting(true);
    setFormError('');

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          identifier: identifier.trim(),
          password,
          login_context: loginContext,
          remember_me: rememberMe,
        }),
      });
      const result = (await response.json()) as AuthSuccess | AuthFailure;

      if (!response.ok || !('user' in result)) {
        const code = 'code' in result ? result.code : undefined;
        setFormError((code && errorMessages[code]) || 'Something went wrong. Please try again.');
        return;
      }

      router.replace(result.user.dashboard_path);
      router.refresh();
    } catch {
      setFormError(errorMessages.network_error);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-dvh bg-[#F8F9FA] text-[#1A1D20]">
      <BrandPanel />

      <section className="relative flex min-h-dvh w-full items-center justify-center overflow-hidden px-4 py-7 sm:px-6 sm:py-10 xl:w-[55%] xl:px-10">
        <div className="auth-soft-grid absolute inset-0 opacity-50 xl:opacity-70" aria-hidden="true" />
        <div className="relative z-10 w-full max-w-[470px]">
          <div className="mb-9 flex justify-center xl:hidden">
            <Logo />
          </div>

          <div className="bg-transparent sm:rounded-[22px] sm:border sm:border-[#E9ECEF] sm:bg-white sm:p-8 sm:shadow-[0_18px_55px_rgba(26,29,32,0.07)] md:p-10">
            <header>
              <div className="mb-5 hidden h-10 w-10 place-items-center rounded-xl bg-[#E9F5F1] text-[#087F5B] sm:grid xl:grid">
                <ShieldCheck size={21} strokeWidth={1.9} aria-hidden="true" />
              </div>
              <h2 className="text-[2rem] font-semibold leading-tight tracking-[-0.035em] sm:text-[2.15rem]">Welcome back</h2>
              <p className="mt-2 text-sm leading-6 text-[#667085] sm:text-[15px]">
                Sign in to continue to your school portal.
              </p>
            </header>

            <form className="mt-7" onSubmit={handleSubmit} noValidate>
              <RoleSelector value={loginContext} onChange={setLoginContext} disabled={submitting} />

              <div className="mt-6 space-y-5">
                <div>
                  <label htmlFor="identifier" className="mb-2 block text-sm font-semibold text-[#303533]">
                    {activeRole.fieldLabel}
                  </label>
                  <div className="group relative">
                    <UserRound
                      size={18}
                      aria-hidden="true"
                      className={`pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 transition-colors ${
                        fieldErrors.identifier ? 'text-[#DC2626]' : 'text-[#89918F] group-focus-within:text-[#087F5B]'
                      }`}
                    />
                    <input
                      id="identifier"
                      name="identifier"
                      type="text"
                      value={identifier}
                      onChange={(event) => {
                        setIdentifier(event.target.value);
                        if (fieldErrors.identifier) setFieldErrors((current) => ({ ...current, identifier: undefined }));
                      }}
                      disabled={submitting}
                      autoComplete="username"
                      autoCapitalize="none"
                      spellCheck={false}
                      aria-invalid={Boolean(fieldErrors.identifier)}
                      aria-describedby={fieldErrors.identifier ? 'identifier-error' : undefined}
                      placeholder={activeRole.placeholder}
                      className={`h-12 w-full rounded-xl border bg-[#F7F8F8] pl-11 pr-4 text-[15px] text-[#1A1D20] outline-none transition-all duration-200 placeholder:text-[#99A19F] disabled:cursor-not-allowed disabled:opacity-60 ${
                        fieldErrors.identifier
                          ? 'border-[#DC2626] focus:border-[#DC2626] focus:ring-4 focus:ring-red-100/60'
                          : 'border-[#DFE3E1] hover:border-[#C9CFCC] focus:border-[#087F5B] focus:bg-white focus:ring-4 focus:ring-emerald-100/60'
                      }`}
                    />
                  </div>
                  {fieldErrors.identifier && (
                    <p id="identifier-error" className="error-enter mt-1.5 flex items-center gap-1.5 text-xs text-[#B91C1C]">
                      <AlertCircle size={13} aria-hidden="true" />
                      {fieldErrors.identifier}
                    </p>
                  )}
                </div>

                <div>
                  <div className="mb-2 flex items-center justify-between gap-4">
                    <label htmlFor="password" className="block text-sm font-semibold text-[#303533]">
                      Password
                    </label>
                    <Link
                      href="/forgot-password"
                      className="rounded text-xs font-semibold text-[#087F5B] underline-offset-4 transition-colors hover:text-[#07543F] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#087F5B] focus-visible:ring-offset-2"
                    >
                      Forgot password?
                    </Link>
                  </div>
                  <div className="group relative">
                    <LockKeyhole
                      size={18}
                      aria-hidden="true"
                      className={`pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 transition-colors ${
                        fieldErrors.password ? 'text-[#DC2626]' : 'text-[#89918F] group-focus-within:text-[#087F5B]'
                      }`}
                    />
                    <input
                      id="password"
                      name="password"
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(event) => {
                        setPassword(event.target.value);
                        if (fieldErrors.password) setFieldErrors((current) => ({ ...current, password: undefined }));
                      }}
                      disabled={submitting}
                      autoComplete="current-password"
                      aria-invalid={Boolean(fieldErrors.password)}
                      aria-describedby={fieldErrors.password ? 'password-error' : undefined}
                      placeholder="Enter your password"
                      className={`h-12 w-full rounded-xl border bg-[#F7F8F8] pl-11 pr-12 text-[15px] text-[#1A1D20] outline-none transition-all duration-200 placeholder:text-[#99A19F] disabled:cursor-not-allowed disabled:opacity-60 ${
                        fieldErrors.password
                          ? 'border-[#DC2626] focus:border-[#DC2626] focus:ring-4 focus:ring-red-100/60'
                          : 'border-[#DFE3E1] hover:border-[#C9CFCC] focus:border-[#087F5B] focus:bg-white focus:ring-4 focus:ring-emerald-100/60'
                      }`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((visible) => !visible)}
                      disabled={submitting}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      className="absolute right-2.5 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-lg text-[#7B8582] transition-colors hover:bg-[#E9F5F1] hover:text-[#087F5B] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#087F5B] disabled:opacity-50"
                    >
                      {showPassword ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
                    </button>
                  </div>
                  {fieldErrors.password && (
                    <p id="password-error" className="error-enter mt-1.5 flex items-center gap-1.5 text-xs text-[#B91C1C]">
                      <AlertCircle size={13} aria-hidden="true" />
                      {fieldErrors.password}
                    </p>
                  )}
                </div>
              </div>

              <label className="mt-5 inline-flex cursor-pointer items-center gap-2.5 text-sm text-[#56605F]">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(event) => setRememberMe(event.target.checked)}
                  disabled={submitting}
                  className="h-4 w-4 rounded border-[#C9CFCC] text-[#087F5B] accent-[#087F5B] focus:ring-[#087F5B]"
                />
                Remember me
              </label>

              <div aria-live="polite" aria-atomic="true" className="min-h-[1px]">
                {formError && (
                  <div className="error-enter mt-5 flex gap-2.5 rounded-xl border border-red-200 bg-red-50 px-3.5 py-3 text-sm leading-5 text-[#991B1B]" role="alert">
                    <AlertCircle className="mt-0.5 shrink-0" size={17} aria-hidden="true" />
                    <span>{formError}</span>
                  </div>
                )}
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="mt-6 flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#087F5B] px-4 text-sm font-semibold text-white shadow-[0_8px_20px_rgba(8,127,91,0.18)] transition-all duration-200 hover:bg-[#07543F] hover:shadow-[0_10px_24px_rgba(7,84,63,0.22)] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-emerald-200 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-65 disabled:hover:bg-[#087F5B]"
              >
                {submitting ? (
                  <>
                    <LoaderCircle className="animate-spin" size={18} aria-hidden="true" />
                    Signing you in...
                  </>
                ) : (
                  <>
                    Sign in
                    <ArrowRight size={17} aria-hidden="true" />
                  </>
                )}
              </button>
            </form>

            <div className="mt-6 flex items-center justify-center gap-2 text-[11px] font-medium tracking-wide text-[#7A8583]">
              <ShieldCheck size={14} aria-hidden="true" />
              Secure access
            </div>
          </div>

          <p className="mt-6 text-center text-[11px] leading-5 text-[#8A9391]">
            Access is limited to authorised members of your school community.
          </p>
        </div>
      </section>
    </main>
  );
}
