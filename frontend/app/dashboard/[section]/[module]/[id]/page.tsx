import type { Metadata } from 'next';

import { DashboardShell } from '@/components/dashboard/DashboardShell';

export const metadata: Metadata = {
  title: 'Contextual workspace',
};

export default function ContextualWorkspacePage() {
  return <DashboardShell />;
}
