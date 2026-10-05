import { ChevronDown, School } from 'lucide-react';

import type { LoginContext } from '@/lib/auth';

type RoleOption = {
  value: LoginContext;
  label: string;
  fieldLabel: string;
  placeholder: string;
};

export const roleOptions: readonly RoleOption[] = [
  {
    value: 'admin',
    label: 'School administrator',
    fieldLabel: 'School email or username',
    placeholder: 'Enter your school email or username',
  },
  {
    value: 'teacher',
    label: 'Teacher workspace',
    fieldLabel: 'School email or username',
    placeholder: 'Enter your school email or username',
  },
  {
    value: 'bursar',
    label: 'Finance workspace',
    fieldLabel: 'School email or username',
    placeholder: 'Enter your school email or username',
  },
  {
    value: 'parent',
    label: 'Parent portal',
    fieldLabel: 'School email or username',
    placeholder: 'Enter your school email or username',
  },
] as const;

type RoleSelectorProps = {
  value: LoginContext;
  onChange: (value: LoginContext) => void;
  disabled?: boolean;
};

export function RoleSelector({ value, onChange, disabled = false }: RoleSelectorProps) {
  return (
    <div>
      <label htmlFor="login-context" className="mb-2 block text-xs font-semibold text-[#394B66]">
        School / Workspace
      </label>
      <div className="group relative">
        <School
          size={17}
          aria-hidden="true"
          className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[#41536D] transition-colors group-focus-within:text-[#1769EF]"
        />
        <select
          id="login-context"
          value={value}
          onChange={(event) => onChange(event.target.value as LoginContext)}
          disabled={disabled}
          className="h-[43px] w-full appearance-none rounded-xl border border-[#D9E0EA] bg-white pl-11 pr-10 text-xs font-medium text-[#354966] outline-none transition hover:border-[#C7D2E1] focus:border-[#377FF5] focus:ring-4 focus:ring-blue-100/65 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {roleOptions.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
        <ChevronDown
          size={16}
          aria-hidden="true"
          className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-[#52647D]"
        />
      </div>
    </div>
  );
}
