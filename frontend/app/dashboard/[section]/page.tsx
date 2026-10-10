import type { Metadata } from 'next';

import { ReferenceDashboardShellV4 } from '@/components/reference/ReferenceDashboardShellV4';

export const metadata: Metadata = {
  title: 'School workspace',
};

export default function DashboardPage() {
  return <ReferenceDashboardShellV4 />;
}