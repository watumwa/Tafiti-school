import type { AuthUser } from '@/lib/auth';

export type WorkspaceNavItem = {
  slug: string;
  label: string;
  icon: string;
  resource: string | null;
};

export type WorkspaceNavGroup = {
  key: string;
  label: string;
  items: WorkspaceNavItem[];
};

export type WorkspaceNotification = {
  id: string;
  title: string;
  message: string;
  created_at: string;
  read: boolean;
  kind: string;
};

export type WorkspaceBootstrap = {
  user: AuthUser;
  school: {
    name: string;
    motto: string;
    logo: string;
    primary_color: string;
    secondary_color: string;
    accent_color: string;
  };
  academic_context: {
    year: string;
    term: string;
    year_id: number | null;
    term_id: number | null;
  };
  navigation: WorkspaceNavGroup[];
  notification_count: number;
  notifications: WorkspaceNotification[];
};

export type WorkspaceStat = {
  label: string;
  value: number | string;
  hint: string;
  tone: 'green' | 'blue' | 'gold' | 'violet';
  currency?: boolean;
};

export type WorkspaceDashboard = {
  role: string;
  school: WorkspaceBootstrap['school'];
  academic_context: WorkspaceBootstrap['academic_context'];
  stats: WorkspaceStat[];
  analytics?: {
    attendance_trend?: { label: string; value: number; detail: string }[];
    collection_trend?: { label: string; value: number }[];
  };
  attention: { title: string; resource: string; severity: 'info' | 'warning' | 'danger' }[];
  notifications: WorkspaceNotification[];
  parent_portal?: {
    children: {
      id: number;
      name: string;
      student_id: string;
      photo: string;
      class: string;
      stream: string;
      attendance_percent: number | null;
      academic_average: number | null;
      outstanding_balance: string | null;
    }[];
    recent_results: {
      id: number;
      student: string;
      student_id: number;
      subject: string;
      assessment: string;
      score: string;
      out_of: number;
      percentage: number;
      grade: string;
      date: string;
    }[];
    upcoming_events: {
      id: number;
      title: string;
      starts_at: string;
      location: string;
    }[];
    announcements: {
      id: number;
      title: string;
      body: string;
      starts_at: string;
      priority: string;
    }[];
  };
};

export type WorkspaceColumn = {
  key: string;
  label: string;
};

export type WorkspaceActions = {
  view: boolean;
  create: boolean;
  edit: boolean;
  delete: boolean;
  create_label: string;
  edit_label: string;
  delete_label: string;
  delete_mode?: 'delete' | 'toggle-active' | 'toggle-status';
};

export type WorkspaceResource = {
  resource: string;
  title: string;
  description: string;
  columns: WorkspaceColumn[];
  rows: Record<string, unknown>[];
  actions: WorkspaceActions;
  pagination: {
    page: number;
    page_size: number;
    total: number;
    pages: number;
  };
  metrics?: WorkspaceStat[];
  view?: string;
  active_filter?: string;
  filters?: { value: string; label: string; count: number }[];
};

export type WorkspaceEntityMetric = {
  label: string;
  value: number | string;
  hint: string;
  tone: 'green' | 'blue' | 'gold' | 'violet';
};

export type WorkspaceEntityAction = {
  label: string;
  href?: string;
  action?: 'edit';
  icon: string;
  primary?: boolean;
};

export type WorkspaceEntityTab = {
  key: string;
  label: string;
  count: number;
  description: string;
  columns: WorkspaceColumn[];
  rows: Record<string, unknown>[];
  empty_title: string;
};

export type ResultVerificationWorkflow = {
  kind: 'result_verification';
  can_finalize: boolean;
  blocked_reason: string;
  out_of: number;
  samples: {
    sample_id: number;
    student: string;
    student_id: string;
    value: string;
    checked: boolean;
  }[];
  next_href: string;
};

export type AttendanceCaptureWorkflow = {
  kind: 'attendance_capture';
  locked: boolean;
  can_edit: boolean;
  can_unlock: boolean;
  allow_teacher_edit_locked: boolean;
  blocked_reason: string;
  statuses: { value: string; label: string }[];
  students: {
    student_id: number;
    student_name: string;
    display_id: string;
    status: string;
    remarks: string;
  }[];
};

export type WorkspaceEntity = {
  resource: string;
  id: number;
  eyebrow: string;
  title: string;
  subtitle: string;
  photo: string;
  status: string;
  metadata: { label: string; value: string; href?: string }[];
  metrics: WorkspaceEntityMetric[];
  tabs: WorkspaceEntityTab[];
  actions: WorkspaceEntityAction[];
  workflow?: ResultVerificationWorkflow | AttendanceCaptureWorkflow;
};

export type WorkspaceFormOption = {
  value: string;
  label: string;
};

export type WorkspaceFormField = {
  name: string;
  label: string;
  type: 'text' | 'email' | 'number' | 'date' | 'datetime-local' | 'textarea' | 'select' | 'multiselect' | 'checkbox' | 'file' | 'image';
  required: boolean;
  disabled: boolean;
  help_text: string;
  options: WorkspaceFormOption[];
  initial: unknown;
  min_value?: number | null;
  max_value?: number | null;
  current_file_url?: string;
};

export type WorkspaceFormSchema = {
  resource: string;
  mode: 'create' | 'edit';
  title: string;
  submit_label: string;
  fields: WorkspaceFormField[];
  actions: WorkspaceActions;
};
