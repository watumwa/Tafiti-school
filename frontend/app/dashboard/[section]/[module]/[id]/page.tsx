import type { Metadata } from 'next';

import { ReferenceDashboardShell } from '@/components/reference/ReferenceDashboardShell';

export const metadata: Metadata = {
  title: 'Contextual workspace',
};

export default function ContextualWorkspacePage() {
  return <ReferenceDashboardShell />;
}
