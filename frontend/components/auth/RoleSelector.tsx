import type { LoginContext } from '@/lib/auth';

type RoleOption = {
  value: LoginContext;
  label: string;
  fieldLabel: string;
  placeholder: string;
};

export const roleOptions: readonly RoleOption[] = [
  { value: 'admin', label: 'Admin', fieldLabel: 'Username or email', placeholder: 'Enter your username or email' },
  {
    value: 'teacher',
    label: 'Teacher',
    fieldLabel: 'Username, email or phone',
    placeholder: 'Enter your username, email or phone',
  },
  {
    value: 'bursar',
    label: 'Bursar',
    fieldLabel: 'Username, email or phone',
    placeholder: 'Enter your username, email or phone',
  },
  {
    value: 'parent',
    label: 'Parent',
    fieldLabel: 'Parent email or phone number',
    placeholder: 'Enter your email or phone number',
  },
] as const;

type RoleSelectorProps = {
  value: LoginContext;
  onChange: (value: LoginContext) => void;
  disabled?: boolean;
};

export function RoleSelector({ value, onChange, disabled = false }: RoleSelectorProps) {
  return (
    <fieldset disabled={disabled}>
      <legend className="sr-only">Choose your portal context</legend>
      <div className="grid grid-cols-4 gap-1 rounded-xl bg-[#F1F3F2] p-1" role="radiogroup" aria-label="Portal context">
        {roleOptions.map((option) => {
          const selected = option.value === value;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={selected}
              disabled={disabled}
              onClick={() => onChange(option.value)}
              className={`min-h-10 rounded-[9px] px-1.5 text-xs font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#087F5B] focus-visible:ring-offset-2 sm:text-sm ${
                selected
                  ? 'bg-[#087F5B] text-white shadow-[0_2px_7px_rgba(8,127,91,0.25)]'
                  : 'text-[#56605F] hover:bg-white hover:text-[#1A1D20]'
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
      <p className="mt-2 text-[11px] leading-4 text-[#7A8583]">
        This helps tailor sign-in. Your access is always set by your school account.
      </p>
    </fieldset>
  );
}
