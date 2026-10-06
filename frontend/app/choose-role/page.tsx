import type { Metadata } from 'next';

import { ReferenceRoleChooser } from '@/components/reference/ReferenceRoleChooser';

export const metadata: Metadata = {
  title: 'Choose workspace',
  description: 'Choose one of the Tafiti workspaces assigned to your account.',
};

export default function ChooseRolePage() {
  return <ReferenceRoleChooser />;
}
