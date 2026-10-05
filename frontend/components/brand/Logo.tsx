import { BookOpen, Sprout } from 'lucide-react';

type LogoProps = {
  inverted?: boolean;
  compact?: boolean;
  accent?: 'green' | 'blue';
};

export function Logo({ inverted = false, compact = false, accent = 'green' }: LogoProps) {
  const blue = accent === 'blue';
  return (
    <div className="flex items-center gap-3" aria-label="Tafiti School Management System">
      <span
        className={`relative grid h-11 w-11 shrink-0 place-items-center rounded-xl border ${
          inverted
            ? 'border-white/25 bg-white/10 text-white'
            : blue
              ? 'border-blue-500/15 bg-gradient-to-br from-[#48A4FF] to-[#1265EE] text-white shadow-[0_5px_12px_rgba(18,101,238,0.22)]'
              : 'border-emerald-900/10 bg-[#07543F] text-white shadow-sm'
        }`}
      >
        <BookOpen aria-hidden="true" size={22} strokeWidth={1.8} />
        <Sprout
          aria-hidden="true"
          size={12}
          strokeWidth={2.2}
          className={`absolute right-1.5 top-1.5 ${inverted ? 'text-[#E8B65F]' : blue ? 'text-white' : 'text-[#F1BE62]'}`}
        />
      </span>
      <span className={inverted ? 'text-white' : 'text-[#1A1D20]'}>
        <span className="block text-[17px] font-bold leading-none tracking-[0.16em]">TAFITI</span>
        {!compact && (
          <span
            className={`mt-1.5 block text-[9px] font-semibold tracking-[0.14em] ${
              inverted ? 'text-emerald-50/75' : 'text-[#667085]'
            }`}
          >
            SCHOOL MANAGEMENT SYSTEM
          </span>
        )}
      </span>
    </div>
  );
}
