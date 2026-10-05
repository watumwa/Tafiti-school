import { Inbox } from 'lucide-react';

export function EmptyState({ title = 'Nothing here yet', description = 'No records match the current view.' }: { title?: string; description?: string }) {
  return (
    <div className="grid min-h-64 place-items-center px-6 py-12 text-center">
      <div>
        <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-slate-100 text-slate-500">
          <Inbox size={21} aria-hidden="true" />
        </span>
        <h3 className="mt-4 text-sm font-semibold text-slate-900">{title}</h3>
        <p className="mt-1 max-w-sm text-xs leading-5 text-slate-500">{description}</p>
      </div>
    </div>
  );
}
