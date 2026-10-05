import { Check, ChevronDown, ShieldCheck } from 'lucide-react';

import { Logo } from '@/components/brand/Logo';

const capabilities = ['Academics', 'Finance', 'Administration', 'Parent communication'];
const inputs = ['Students', 'Academics', 'Fees', 'Staff', 'Parents'];

export function BrandPanel() {
  return (
    <aside className="brand-panel relative hidden min-h-dvh w-[45%] overflow-hidden bg-[#07543F] px-10 py-9 text-white xl:flex xl:flex-col 2xl:px-16 2xl:py-12">
      <div className="brand-grid absolute inset-0 opacity-35" aria-hidden="true" />
      <div className="brand-orb absolute -right-40 -top-32 h-[420px] w-[420px] rounded-full border border-white/[0.08]" aria-hidden="true" />
      <div className="brand-orb brand-orb-delay absolute -bottom-52 -left-36 h-[430px] w-[430px] rounded-full border border-white/[0.08]" aria-hidden="true" />

      <div className="relative z-10">
        <Logo inverted />
      </div>

      <div className="relative z-10 my-auto max-w-[580px] py-10">
        <span className="mb-5 block h-0.5 w-10 bg-[#D79B35]" />
        <h1 className="max-w-[540px] text-[clamp(2.25rem,3.2vw,4rem)] font-semibold leading-[1.08] tracking-[-0.035em]">
          Everything your school needs.
          <span className="mt-2 block text-emerald-50/85">One secure platform.</span>
        </h1>
        <p className="mt-6 max-w-[510px] text-[15px] leading-7 text-emerald-50/72 2xl:text-base">
          Manage academics, fees, students, staff and parent communication from one connected workspace.
        </p>

        <div className="mt-9 rounded-2xl border border-white/10 bg-[#064A38]/80 p-5 shadow-[0_18px_50px_rgba(0,27,20,0.18)] 2xl:p-6">
          <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4">
            <div className="space-y-2">
              {inputs.map((item) => (
                <div key={item} className="flex items-center gap-2 text-xs font-medium text-emerald-50/70">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#D79B35]" />
                  {item}
                </div>
              ))}
            </div>
            <div className="flex items-center gap-2 text-emerald-100/45" aria-hidden="true">
              <span className="h-px w-6 bg-current" />
              <span>→</span>
            </div>
            <div className="flex flex-col items-center">
              <div className="grid h-20 w-20 place-items-center rounded-full border border-[#D79B35]/40 bg-[#083D30] shadow-[0_0_0_7px_rgba(255,255,255,0.025)]">
                <span className="text-xs font-bold tracking-[0.16em] text-white">TAFITI</span>
              </div>
              <ChevronDown className="my-1 text-[#D79B35]" size={17} aria-hidden="true" />
              <span className="text-center text-[11px] font-medium leading-4 text-emerald-50/65">
                School insights
                <br />
                &amp; management
              </span>
            </div>
          </div>
        </div>

        <ul className="mt-7 grid grid-cols-2 gap-x-5 gap-y-3">
          {capabilities.map((capability) => (
            <li key={capability} className="flex items-center gap-2.5 text-sm text-emerald-50/80">
              <span className="grid h-5 w-5 place-items-center rounded-full bg-white/10 text-[#E8B65F]">
                <Check size={12} strokeWidth={2.8} aria-hidden="true" />
              </span>
              {capability}
            </li>
          ))}
        </ul>
      </div>

      <div className="relative z-10 flex items-center gap-2 text-xs font-medium tracking-wide text-emerald-50/60">
        <ShieldCheck size={16} aria-hidden="true" />
        Secure school management platform
      </div>
    </aside>
  );
}
