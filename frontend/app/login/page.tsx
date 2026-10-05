import type { Metadata } from 'next';

import { LoginPage } from '@/components/auth/LoginPage';

export const metadata: Metadata = {
  title: 'Sign in',
  description: 'Sign in securely to your Tafiti school portal.',
};

export default async function LoginRoute({
  searchParams,
}: {
  searchParams: Promise<{ notice?: string }>;
}) {
  const params = await searchParams;
  return <LoginPage notice={params.notice} />;
}
