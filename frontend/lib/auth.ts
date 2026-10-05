export type LoginContext = 'admin' | 'teacher' | 'bursar' | 'parent';

export type AuthRole = {
  code: string;
  label: string;
};

export type AuthUser = {
  id: number;
  username: string;
  email: string;
  name: string;
  role: AuthRole;
  roles: AuthRole[];
  permissions: string[];
  dashboard_path: string;
  must_change_password: boolean;
};

export type AuthSuccess = {
  user: AuthUser;
};

export type AuthFailure = {
  code?: string;
  detail?: string;
  identifier?: string[];
  password?: string[];
};
