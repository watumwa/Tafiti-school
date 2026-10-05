import type { Metadata } from 'next';

import { DashboardShell } from '@/components/dashboard/DashboardShell';

export const metadata: Metadata = {
  title: 'School workspace',
};

export default function DashboardPage() {
  return <DashboardShell />;
}
