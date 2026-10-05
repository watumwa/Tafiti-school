'use client';

import { FormEvent, useState } from 'react';
import { AlertCircle, CheckCircle2, LoaderCircle, Mail } from 'lucide-react';

export function ForgotPasswordForm() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim()) {
      setError('Enter the email address linked to your account.');
      return;
    }

    setSubmitting(true);
    setError('');
    try {
      const response = await fetch('/api/auth/password-reset/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim() }),
      });
      if (!response.ok) {
        setError(response.status === 503 ? "We couldn't connect to Tafiti. Try again shortly." : 'Check the email address and try again.');
        return;
      }
      setSent(true);
    } catch {
      setError("We couldn't connect to Tafiti. Check your connection and try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (sent) {
    return (
      <div className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm leading-6 text-emerald-900" role="status">
        <div className="flex gap-3">
          <CheckCircle2 className="mt-0.5 shrink-0 text-[#087F5B]" size={19} aria-hidden="true" />
          <p>If an active account matches <strong>{email}</strong>, reset instructions are on the way. Check your inbox and spam folder.</p>
        </div>
      </div>
    );
  }

  return (
    <form className="mt-7" onSubmit={handleSubmit} noValidate>
      <label htmlFor="recovery-email" className="mb-2 block text-sm font-semibold text-[#303533]">Email address</label>
      <div className="group relative">
        <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#89918F] group-focus-within:text-[#087F5B]" size={18} aria-hidden="true" />
        <input
          id="recovery-email"
          type="email"
          value={email}
          onChange={(event) => {
            setEmail(event.target.value);
            setError('');
          }}
          autoComplete="email"
          disabled={submitting}
          placeholder="you@school.com"
          aria-invalid={Boolean(error)}
          className={`h-12 w-full rounded-xl border bg-[#F7F8F8] pl-11 pr-4 text-[15px] outline-none transition-all focus:bg-white focus:ring-4 ${error ? 'border-red-500 focus:ring-red-100' : 'border-[#DFE3E1] focus:border-[#087F5B] focus:ring-emerald-100/60'}`}
        />
      </div>
      <div aria-live="polite">
        {error && <p className="error-enter mt-2 flex items-center gap-1.5 text-xs text-red-700"><AlertCircle size={13} aria-hidden="true" />{error}</p>}
      </div>
      <button
        type="submit"
        disabled={submitting}
        className="mt-6 flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#087F5B] text-sm font-semibold text-white transition-all hover:bg-[#07543F] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-emerald-200 active:scale-[0.99] disabled:opacity-65"
      >
        {submitting && <LoaderCircle className="animate-spin" size={18} aria-hidden="true" />}
        {submitting ? 'Sending instructions…' : 'Send reset instructions'}
      </button>
    </form>
  );
}
