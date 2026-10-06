import type { Metadata } from 'next';

import { ReferenceDashboardShellV3 } from '@/components/reference/ReferenceDashboardShellV3';

export const metadata: Metadata = {
  title: 'Contextual workspace',
};

export default function ContextualWorkspacePage() {
  return <ReferenceDashboardShellV3 />;
}
