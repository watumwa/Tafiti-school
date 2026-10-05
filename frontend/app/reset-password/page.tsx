import type { Metadata } from 'next';

import { AuthPageShell } from '@/components/auth/AuthPageShell';
import { PasswordForm } from '@/components/auth/PasswordForm';

export const metadata: Metadata = { title: 'Choose a new password' };

type ResetPasswordPageProps = {
  searchParams: Promise<{ uid?: string; token?: string }>;
};

export default async function ResetPasswordPage({ searchParams }: ResetPasswordPageProps) {
  const params = await searchParams;
  return (
    <AuthPageShell title="Choose a new password" description="Create a strong password for your Tafiti school account.">
      <PasswordForm mode="reset" uid={params.uid} token={params.token} />
    </AuthPageShell>
  );
}
