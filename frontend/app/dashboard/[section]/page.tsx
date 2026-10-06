import type { Metadata } from 'next';

import { ReferenceDashboardShellV2 } from '@/components/reference/ReferenceDashboardShellV2';

export const metadata: Metadata = {
  title: 'School workspace',
};

export default function DashboardPage() {
  return <ReferenceDashboardShellV2 />;
}
