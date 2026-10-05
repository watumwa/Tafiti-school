'use client';

import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react';
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react';

type ToastTone = 'success' | 'error' | 'warning' | 'info';

type ToastInput = {
  title: string;
  message?: string;
  tone?: ToastTone;
  duration?: number;
};

type Toast = Required<Pick<ToastInput, 'title' | 'tone'>> &
  Pick<ToastInput, 'message'> & {
    id: number;
  };

type ToastContextValue = {
  notify: (toast: ToastInput) => void;
  success: (title: string, message?: string) => void;
  error: (title: string, message?: string) => void;
  warning: (title: string, message?: string) => void;
  info: (title: string, message?: string) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

const styles: Record<ToastTone, { wrapper: string; icon: string; Icon: typeof CheckCircle2 }> = {
  success: {
    wrapper: 'border-emerald-200/80 bg-white',
    icon: 'bg-emerald-50 text-emerald-700',
    Icon: CheckCircle2,
  },
  error: {
    wrapper: 'border-red-200/80 bg-white',
    icon: 'bg-red-50 text-red-700',
    Icon: XCircle,
  },
  warning: {
    wrapper: 'border-amber-200/80 bg-white',
    icon: 'bg-amber-50 text-amber-700',
    Icon: AlertTriangle,
  },
  info: {
    wrapper: 'border-sky-200/80 bg-white',
    icon: 'bg-sky-50 text-sky-700',
    Icon: Info,
  },
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const notify = useCallback(
    ({ title, message, tone = 'info', duration = 4200 }: ToastInput) => {
      const id = nextId.current++;
      setToasts((current) => [...current.slice(-3), { id, title, message, tone }]);
      window.setTimeout(() => dismiss(id), duration);
    },
    [dismiss],
  );

  const value = useMemo<ToastContextValue>(
    () => ({
      notify,
      success: (title, message) => notify({ title, message, tone: 'success' }),
      error: (title, message) => notify({ title, message, tone: 'error', duration: 6500 }),
      warning: (title, message) => notify({ title, message, tone: 'warning' }),
      info: (title, message) => notify({ title, message, tone: 'info' }),
    }),
    [notify],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        aria-atomic="false"
        className="pointer-events-none fixed inset-x-3 top-3 z-[100] flex flex-col items-end gap-2 sm:inset-x-auto sm:right-5 sm:top-5 sm:w-[390px]"
      >
        {toasts.map((toast) => {
          const tone = styles[toast.tone];
          const Icon = tone.Icon;
          return (
            <div
              key={toast.id}
              role={toast.tone === 'error' ? 'alert' : 'status'}
              className={`toast-enter pointer-events-auto flex w-full gap-3 rounded-2xl border p-3.5 shadow-[0_18px_50px_rgba(15,23,42,0.12)] ${tone.wrapper}`}
            >
              <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl ${tone.icon}`}>
                <Icon size={18} aria-hidden="true" />
              </span>
              <div className="min-w-0 flex-1 pt-0.5">
                <p className="text-sm font-semibold text-slate-900">{toast.title}</p>
                {toast.message && <p className="mt-1 text-xs leading-5 text-slate-600">{toast.message}</p>}
              </div>
              <button
                type="button"
                onClick={() => dismiss(toast.id)}
                className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                aria-label="Dismiss notification"
              >
                <X size={16} aria-hidden="true" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error('useToast must be used inside ToastProvider');
  return context;
}
