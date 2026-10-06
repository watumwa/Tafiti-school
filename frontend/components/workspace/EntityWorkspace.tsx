'use client';

import { ReferenceAttendanceWorkspace } from '@/components/reference/ReferenceAttendanceWorkspace';
import { ReferenceEntityWorkspace } from '@/components/reference/ReferenceEntityWorkspace';
import { ReferenceResultVerificationWorkspace } from '@/components/reference/ReferenceResultVerificationWorkspace';

export function EntityWorkspace({
  resource,
  id,
  dashboardPath,
  onTitleChange,
}: {
  resource: string;
  id: number;
  dashboardPath: string;
  onTitleChange?: (title: string) => void;
}) {
  if (resource === 'attendance') {
    return <ReferenceAttendanceWorkspace id={id} dashboardPath={dashboardPath} onTitleChange={onTitleChange} />;
  }

  if (resource === 'results') {
    return <ReferenceResultVerificationWorkspace id={id} dashboardPath={dashboardPath} onTitleChange={onTitleChange} />;
  }

  return <ReferenceEntityWorkspace resource={resource} id={id} dashboardPath={dashboardPath} onTitleChange={onTitleChange} />;
}
