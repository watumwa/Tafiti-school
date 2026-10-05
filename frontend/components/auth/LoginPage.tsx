'use client';

import { FormEvent, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  AlertCircle,
  ArrowRight,
  BookOpenText,
  ChartNoAxesColumnIncreasing,
  Eye,
  EyeOff,
  GraduationCap,
  LoaderCircle,
  LockKeyhole,
  ShieldCheck,
  UsersRound,
  UserRound,
} from 'lucide-react';

import { Logo } from '@/components/brand/Logo';
import type { AuthFailure, AuthSuccess, LoginContext } from '@/lib/auth';
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

const features = [
  { label: 'Secure access', detail: 'Your data is safe', Icon: ShieldCheck },
  { label: 'Attendance', detail: 'Track with ease', Icon: UsersRound },
  { label: 'Finance', detail: 'Manage smarter', Icon: ChartNoAxesColumnIncreasing },
  { label: 'Results', detail: 'Insights for progress', Icon: BookOpenText },
];

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

  const activeRole = roleOptions.find((role) => role.value === loginContext) ?? roleOptions[0];

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
    <main className="relative grid min-h-dvh place-items-center overflow-hidden bg-[#EEF6FF] px-4 py-8 text-[#142747] sm:px-6">
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_38%,rgba(255,255,255,0.98)_0%,rgba(234,244,255,0.8)_45%,rgba(218,235,255,0.9)_100%)]" />
        <div className="absolute -left-28 top-[30%] h-[420px] w-[420px] rounded-full border-[44px] border-blue-200/25" />
        <div className="absolute -right-20 bottom-[-190px] h-[490px] w-[600px] -rotate-12 rounded-[48%] border-[38px] border-white/45" />
        <div className="absolute left-4 top-[14%] grid grid-cols-4 gap-3 opacity-40 sm:left-8">
          {Array.from({ length: 12 }).map((_, index) => <span key={index} className="h-1.5 w-1.5 rounded-full bg-blue-300" />)}
        </div>
        <div className="absolute right-[8%] top-[41%] grid grid-cols-4 gap-3 opacity-35">
          {Array.from({ length: 12 }).map((_, index) => <span key={index} className="h-1.5 w-1.5 rounded-full bg-blue-300" />)}
        </div>
        <GraduationCap className="absolute right-[2%] top-[10%] h-28 w-28 text-blue-300/[0.2] sm:h-40 sm:w-40" strokeWidth={1} />
        <BookOpenText className="absolute -right-5 bottom-[6%] h-48 w-48 text-blue-300/[0.18] sm:right-[2%] sm:h-64 sm:w-64" strokeWidth={1} />
      </div>

      <section className="relative z-10 w-full max-w-[462px]">
        <div className="rounded-[22px] border border-white/90 bg-white/90 p-6 shadow-[0_22px_65px_rgba(43,91,151,0.14)] backdrop-blur-xl sm:p-7">
          <div className="flex justify-center">
            <Logo accent="blue" />
          </div>

          <header className="mt-5 text-center">
            <h1 className="text-[1.8rem] font-bold leading-tight tracking-[-0.035em] text-[#102344] sm:text-[2rem]">Sign in to Tafiti</h1>
            <p className="mx-auto mt-2 max-w-[330px] text-sm leading-5 text-[#64748B]">
              Access your school workspace and manage everything in one place.
            </p>
          </header>

          <form className="mt-5" onSubmit={handleSubmit} noValidate>
            <div className="space-y-3">
              <div>
                <label htmlFor="identifier" className="mb-1.5 block text-xs font-semibold text-[#394B66]">
                  School email or username
                </label>
                <div className="group relative">
                  <UserRound
                    size={17}
                    aria-hidden="true"
                    className={`pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 transition-colors ${
                      fieldErrors.identifier ? 'text-[#DC2626]' : 'text-[#52647D] group-focus-within:text-[#1769EF]'
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
                    className={`h-[43px] w-full rounded-xl border bg-white pl-11 pr-4 text-xs text-[#1A1D20] outline-none transition-all duration-200 placeholder:text-[#8A99AE] disabled:cursor-not-allowed disabled:opacity-60 ${
                      fieldErrors.identifier
                        ? 'border-[#DC2626] focus:border-[#DC2626] focus:ring-4 focus:ring-red-100/60'
                        : 'border-[#D9E0EA] hover:border-[#C7D2E1] focus:border-[#377FF5] focus:ring-4 focus:ring-blue-100/65'
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

              <RoleSelector value={loginContext} onChange={setLoginContext} disabled={submitting} />

              <div>
                <div className="mb-1.5 flex items-center justify-between gap-4">
                  <label htmlFor="password" className="block text-xs font-semibold text-[#394B66]">
                    Password
                  </label>
                  <Link
                    href="/forgot-password"
                    className="rounded text-[11px] font-semibold text-[#1769EF] underline-offset-4 transition-colors hover:text-[#0D4FB8] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#377FF5] focus-visible:ring-offset-2"
                  >
                    Forgot password?
                  </Link>
                </div>
                <div className="group relative">
                  <LockKeyhole
                    size={17}
                    aria-hidden="true"
                    className={`pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 transition-colors ${
                      fieldErrors.password ? 'text-[#DC2626]' : 'text-[#52647D] group-focus-within:text-[#1769EF]'
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
                    className={`h-[43px] w-full rounded-xl border bg-white pl-11 pr-12 text-xs text-[#1A1D20] outline-none transition-all duration-200 placeholder:text-[#8A99AE] disabled:cursor-not-allowed disabled:opacity-60 ${
                      fieldErrors.password
                        ? 'border-[#DC2626] focus:border-[#DC2626] focus:ring-4 focus:ring-red-100/60'
                        : 'border-[#D9E0EA] hover:border-[#C7D2E1] focus:border-[#377FF5] focus:ring-4 focus:ring-blue-100/65'
                    }`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((visible) => !visible)}
                    disabled={submitting}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    className="absolute right-2.5 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-lg text-[#52647D] transition-colors hover:bg-blue-50 hover:text-[#1769EF] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#377FF5] disabled:opacity-50"
                  >
                    {showPassword ? <EyeOff size={17} aria-hidden="true" /> : <Eye size={17} aria-hidden="true" />}
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

            <div className="mt-2 flex items-center justify-between gap-3">
              <label className="inline-flex cursor-pointer items-center gap-2 text-[11px] font-medium text-[#52647D]">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(event) => setRememberMe(event.target.checked)}
                  disabled={submitting}
                  className="h-4 w-4 rounded border-[#C9D4E2] text-[#1769EF] accent-[#1769EF] focus:ring-[#377FF5]"
                />
                Remember me
              </label>
              <button
                type="button"
                onClick={() => document.getElementById('login-context')?.focus()}
                className="rounded text-[10px] font-semibold text-[#1769EF] hover:text-[#0D4FB8] hover:underline"
              >
                My account has multiple roles
              </button>
            </div>

            <div aria-live="polite" aria-atomic="true" className="min-h-[1px]">
              {formError && (
                <div className="error-enter mt-4 flex gap-2.5 rounded-xl border border-red-200 bg-red-50 px-3.5 py-3 text-sm leading-5 text-[#991B1B]" role="alert">
                  <AlertCircle className="mt-0.5 shrink-0" size={17} aria-hidden="true" />
                  <span>{formError}</span>
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="mt-3 flex h-[43px] w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#45A0FA] to-[#1265EE] px-4 text-sm font-semibold text-white shadow-[0_9px_19px_rgba(31,115,239,0.26)] transition-all duration-200 hover:brightness-105 hover:shadow-[0_11px_24px_rgba(31,115,239,0.32)] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-blue-200 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-65"
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

          <div className="mt-4 flex items-center gap-3 text-[10px] font-medium text-[#718096]">
            <span className="h-px flex-1 bg-[#DCE5F0]" />
            <span>or</span>
            <span className="h-px flex-1 bg-[#DCE5F0]" />
          </div>
          <div className="mt-3 flex items-center justify-center gap-2 text-[10px] font-medium text-[#52647D]">
            <ShieldCheck size={15} className="text-[#1769EF]" aria-hidden="true" />
            Secure access to your school data
          </div>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-y-4 sm:grid-cols-4 sm:gap-0">
          {features.map(({ label, detail, Icon }, index) => (
            <div key={label} className={`flex items-center justify-center gap-2.5 ${index > 0 ? 'sm:border-l sm:border-[#C9DAEE]' : ''}`}>
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-blue-100/80 text-[#1769EF]">
                <Icon size={19} strokeWidth={2.2} aria-hidden="true" />
              </span>
              <span>
                <span className="block text-[10px] font-bold text-[#1B355B]">{label}</span>
                <span className="mt-0.5 block text-[9px] text-[#718096]">{detail}</span>
              </span>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
