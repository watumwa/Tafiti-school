import { Suspense } from 'react';
import type { Metadata } from 'next';

import { ReferenceRoleChooser } from '@/components/reference/ReferenceRoleChooser';
import { LoadingEmblem } from '@/components/brand/LoadingEmblem';

export const metadata: Metadata = {
  title: 'Choose workspace',
  description: 'Choose one of the Tafiti workspaces assigned to your account.',
};

function RoleChooserFallback() {
  return <main className="grid min-h-dvh place-items-center bg-[#F2F6FC] text-xs font-bold text-slate-500"><div className="text-center"><LoadingEmblem className="mx-auto mb-4" />Loading your workspaces…</div></main>;
}

export default function ChooseRolePage() {
  return (
    <Suspense fallback={<RoleChooserFallback />}>
      <ReferenceRoleChooser />
    </Suspense>
  );
}
