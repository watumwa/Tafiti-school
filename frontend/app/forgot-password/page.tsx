import type { Metadata } from 'next';

import { AuthPageShell } from '@/components/auth/AuthPageShell';
import { ForgotPasswordForm } from '@/components/auth/ForgotPasswordForm';

export const metadata: Metadata = { title: 'Reset password' };

export default function ForgotPasswordPage() {
  return (
    <AuthPageShell title="Reset your password" description="Enter the email address linked to your Tafiti account and we’ll send you a secure reset link.">
      <ForgotPasswordForm />
    </AuthPageShell>
  );
}
