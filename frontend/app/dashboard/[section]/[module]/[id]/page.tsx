import type { Metadata } from 'next';

import { ReferenceDashboardShellV4 } from '@/components/reference/ReferenceDashboardShellV4';

export const metadata: Metadata = {
  title: 'Contextual workspace',
};

export default function ContextualWorkspacePage() {
  return <ReferenceDashboardShellV4 />;
}