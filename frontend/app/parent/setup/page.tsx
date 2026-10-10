import type { Metadata } from 'next';

import { AuthPageShell } from '@/components/auth/AuthPageShell';
import { PasswordForm } from '@/components/auth/PasswordForm';

export const metadata: Metadata = { title: 'Set up parent access' };

type ParentSetupPageProps = {
  searchParams: Promise<{ uid?: string; token?: string }>;
};

export default async function ParentSetupPage({ searchParams }: ParentSetupPageProps) {
  const params = await searchParams;
  return (
    <AuthPageShell
      title="Set up your parent account"
      description="Choose your private Tafiti password. This one-time setup link expires and stops working immediately after the password is created."
    >
      <PasswordForm mode="parent-setup" uid={params.uid} token={params.token} />
    </AuthPageShell>
  );
}
