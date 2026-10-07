import { BookOpen, Sparkles } from 'lucide-react';

type LogoProps = {
  inverted?: boolean;
  compact?: boolean;
  accent?: 'green' | 'blue';
  sidebar?: boolean;
};

export function Logo({ inverted = false, compact = false, accent = 'blue', sidebar = false }: LogoProps) {
  const blue = accent === 'blue';

  return (
    <div className={`flex items-center ${sidebar ? 'gap-3.5' : 'gap-3'}`} aria-label="Tafiti School Management System">
      <span
        className={`relative grid shrink-0 place-items-center border ${sidebar ? 'h-12 w-12 rounded-2xl' : 'h-10 w-10 rounded-xl'} ${
          inverted
            ? 'border-white/20 bg-white/10 text-white shadow-[inset_0_1px_0_rgba(255,255,255,.14)]'
            : blue
              ? 'border-blue-500/10 bg-gradient-to-br from-[#4B9CFF] via-[#2675F4] to-[#1758D1] text-white shadow-[0_7px_18px_rgba(37,99,235,.24)]'
              : 'border-emerald-900/10 bg-[#07543F] text-white shadow-sm'
        }`}
      >
        <BookOpen aria-hidden="true" size={sidebar ? 26 : 21} strokeWidth={1.9} />
        <Sparkles
          aria-hidden="true"
          size={sidebar ? 12 : 10}
          strokeWidth={2.4}
          className={`absolute right-1 top-1 ${inverted ? 'text-[#FFCB55]' : blue ? 'text-[#FFCB55]' : 'text-[#F1BE62]'}`}
        />
      </span>
      <span className={inverted ? 'text-white' : 'text-[#10224A]'}>
        <span className={`block font-extrabold leading-none tracking-[0.16em] ${sidebar ? 'text-[18px]' : 'text-[16px]'}`}>TAFITI</span>
        {!compact && (
          <span
            className={`mt-1.5 block font-semibold tracking-[0.17em] ${sidebar ? 'whitespace-nowrap text-[7px]' : 'text-[8px]'} ${
              inverted ? 'text-blue-100/70' : 'text-[#71809A]'
            }`}
          >
            SCHOOL MANAGEMENT SYSTEM
          </span>
        )}
      </span>
    </div>
  );
}
