import { LoadingEmblem } from '@/components/brand/LoadingEmblem';

export default function ContextualWorkspaceLoading() {
  return (
    <div className="grid min-h-[420px] place-items-center rounded-2xl border border-slate-200 bg-white">
      <div className="text-center text-sm font-medium text-slate-500">
        <LoadingEmblem size={76} className="mx-auto mb-3" />
        Opening contextual workspace…
      </div>
    </div>
  );
}
