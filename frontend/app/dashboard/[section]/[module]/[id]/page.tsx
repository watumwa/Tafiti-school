import type { Metadata } from 'next';

import { ReferenceDashboardShellV2 } from '@/components/reference/ReferenceDashboardShellV2';

export const metadata: Metadata = {
  title: 'Contextual workspace',
};

export default function ContextualWorkspacePage() {
  return <ReferenceDashboardShellV2 />;
}
