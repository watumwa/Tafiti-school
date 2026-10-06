import type { Metadata } from 'next';

import { ReferenceDashboardShellV3 } from '@/components/reference/ReferenceDashboardShellV3';

export const metadata: Metadata = {
  title: 'School workspace',
};

export default function DashboardPage() {
  return <ReferenceDashboardShellV3 />;
}
