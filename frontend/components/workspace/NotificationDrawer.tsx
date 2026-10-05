'use client';

import { Bell, CheckCircle2, X } from 'lucide-react';

import type { WorkspaceNotification } from '@/lib/workspace';

function formatWhen(value: string) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export function NotificationDrawer({
  open,
  onClose,
  notifications,
}: {
  open: boolean;
  onClose: () => void;
  notifications: WorkspaceNotification[];
}) {
  return (
    <>
      <button
        type="button"
        aria-label="Close notifications"
        onClick={onClose}
        className={`fixed inset-0 z-50 bg-slate-950/25 backdrop-blur-[1px] transition-opacity ${open ? 'opacity-100' : 'pointer-events-none opacity-0'}`}
      />
      <aside
        aria-label="Notifications"
        className={`fixed inset-y-0 right-0 z-[60] flex w-full max-w-[410px] flex-col border-l border-slate-200 bg-white shadow-[-20px_0_60px_rgba(15,23,42,0.12)] transition-transform duration-300 ${open ? 'translate-x-0' : 'translate-x-full'}`}
      >
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <div>
            <p className="text-base font-semibold text-slate-950">Notifications</p>
            <p className="mt-0.5 text-xs text-slate-500">Recent school activity that needs your attention.</p>
          </div>
          <button type="button" onClick={onClose} className="grid h-9 w-9 place-items-center rounded-xl text-slate-500 hover:bg-slate-100" aria-label="Close notifications">
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {!notifications.length ? (
            <div className="grid min-h-[340px] place-items-center text-center">
              <div>
                <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-emerald-50 text-emerald-700"><CheckCircle2 size={22} /></span>
                <p className="mt-4 text-sm font-semibold text-slate-900">You’re all caught up</p>
                <p className="mt-1 max-w-[260px] text-xs leading-5 text-slate-500">There are no recent notifications for this workspace.</p>
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              {notifications.map((notification) => (
                <article key={notification.id} className={`rounded-2xl border p-4 ${notification.read ? 'border-slate-200 bg-white' : 'border-emerald-200 bg-emerald-50/45'}`}>
                  <div className="flex gap-3">
                    <span className={`mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-xl ${notification.read ? 'bg-slate-100 text-slate-500' : 'bg-emerald-100 text-emerald-800'}`}>
                      <Bell size={16} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-3">
                        <p className="text-sm font-semibold text-slate-900">{notification.title}</p>
                        {!notification.read && <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-emerald-600" aria-label="Unread" />}
                      </div>
                      {notification.message && <p className="mt-1.5 text-xs leading-5 text-slate-600">{notification.message}</p>}
                      <p className="mt-2 text-[11px] font-medium text-slate-400">{formatWhen(notification.created_at)}</p>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
