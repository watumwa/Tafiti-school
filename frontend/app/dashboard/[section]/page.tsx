import type { Metadata } from 'next';

import { ReferenceDashboardShell } from '@/components/reference/ReferenceDashboardShell';

export const metadata: Metadata = {
  title: 'School workspace',
};

export default function DashboardPage() {
  return <ReferenceDashboardShell />;
}
