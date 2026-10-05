import type { Metadata } from 'next';

import { AuthPageShell } from '@/components/auth/AuthPageShell';
import { PasswordForm } from '@/components/auth/PasswordForm';

export const metadata: Metadata = { title: 'Set your password' };

export default function ChangePasswordPage() {
  return (
    <AuthPageShell title="Set your private password" description="Before continuing, replace your temporary password with one only you know." backToLogin={false}>
      <PasswordForm mode="change" />
    </AuthPageShell>
  );
}
