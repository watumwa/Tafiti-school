import { LoaderCircle } from 'lucide-react';

export default function ContextualWorkspaceLoading() {
  return (
    <div className="grid min-h-[420px] place-items-center rounded-2xl border border-slate-200 bg-white">
      <div className="text-center text-sm font-medium text-slate-500">
        <LoaderCircle className="mx-auto mb-3 animate-spin text-[#3157D5]" size={24} />
        Opening contextual workspace…
      </div>
    </div>
  );
}
