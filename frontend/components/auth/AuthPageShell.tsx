import type { ReactNode } from 'react';
import Link from 'next/link';
import { ArrowLeft, ShieldCheck } from 'lucide-react';

import { Logo } from '@/components/brand/Logo';

type AuthPageShellProps = {
  title: string;
  description: string;
  children: ReactNode;
  backToLogin?: boolean;
};

export function AuthPageShell({ title, description, children, backToLogin = true }: AuthPageShellProps) {
  return (
    <main className="relative grid min-h-dvh place-items-center overflow-hidden bg-[#F8F9FA] px-4 py-8 sm:px-6">
      <div className="auth-soft-grid absolute inset-0" aria-hidden="true" />
      <div className="relative z-10 w-full max-w-[470px]">
        <div className="mb-8 flex justify-center">
          <Logo />
        </div>
        <section className="rounded-[22px] border border-[#E9ECEF] bg-white p-6 shadow-[0_18px_55px_rgba(26,29,32,0.07)] sm:p-9">
          <div className="grid h-11 w-11 place-items-center rounded-xl bg-[#E9F5F1] text-[#087F5B]">
            <ShieldCheck size={22} strokeWidth={1.9} aria-hidden="true" />
          </div>
          <h1 className="mt-5 text-2xl font-semibold tracking-[-0.03em] text-[#1A1D20] sm:text-[1.75rem]">{title}</h1>
          <p className="mt-2 text-sm leading-6 text-[#667085]">{description}</p>
          {children}
        </section>
        {backToLogin && (
          <div className="mt-6 text-center">
            <Link href="/login" className="inline-flex items-center gap-2 text-sm font-semibold text-[#087F5B] hover:text-[#07543F]">
              <ArrowLeft size={16} aria-hidden="true" />
              Back to sign in
            </Link>
          </div>
        )}
      </div>
    </main>
  );
}
