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
  attention: { title: string; resource: string; severity: 'info' | 'warning' | 'danger' }[];
  notifications: WorkspaceNotification[];
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
