import { Suspense } from 'react';
import type { Metadata } from 'next';

import { ReferenceRoleChooser } from '@/components/reference/ReferenceRoleChooser';

export const metadata: Metadata = {
  title: 'Choose workspace',
  description: 'Choose one of the Tafiti workspaces assigned to your account.',
};

function RoleChooserFallback() {
  return <main className="grid min-h-dvh place-items-center bg-[#F2F6FC] text-xs font-bold text-slate-500">Loading your workspaces…</main>;
}

export default function ChooseRolePage() {
  return (
    <Suspense fallback={<RoleChooserFallback />}>
      <ReferenceRoleChooser />
    </Suspense>
  );
}
