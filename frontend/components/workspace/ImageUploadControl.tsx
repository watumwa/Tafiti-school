'use client';

import { Camera, ImagePlus } from 'lucide-react';
import { useEffect, useMemo } from 'react';

import { workspaceMediaSrc } from '@/lib/media';
import { ProfileAvatar } from './ProfileAvatar';

export function ImageUploadControl({
  name,
  currentUrl,
  value,
  required,
  disabled,
  onChange,
}: {
  name: string;
  currentUrl?: string;
  value: unknown;
  required: boolean;
  disabled: boolean;
  onChange: (file: File | null) => void;
}) {
  const selectedFile = value instanceof File ? value : null;
  const selectedUrl = useMemo(() => selectedFile ? URL.createObjectURL(selectedFile) : '', [selectedFile]);
  useEffect(() => () => { if (selectedUrl) URL.revokeObjectURL(selectedUrl); }, [selectedUrl]);
  const source = selectedUrl || workspaceMediaSrc(currentUrl);

  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white/75 p-4 shadow-[inset_1px_1px_0_rgba(255,255,255,.95),0_8px_22px_rgba(15,39,71,.05)]">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="relative">
          <ProfileAvatar src={source} name={name.replaceAll('_', ' ')} size="xl" />
          <span className="absolute -bottom-1 -right-1 grid h-8 w-8 place-items-center rounded-full border-2 border-white bg-[#173F6B] text-white shadow-lg"><Camera size={14} /></span>
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-slate-800">{selectedFile ? selectedFile.name : currentUrl ? 'Current profile photo' : 'No profile photo yet'}</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">Use a clear portrait photo. JPG, PNG and WebP work best.</p>
          <label className="clay-button-secondary mt-3 inline-flex cursor-pointer">
            <ImagePlus size={15} /> {currentUrl ? 'Replace photo' : 'Choose photo'}
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="sr-only"
              required={required && !currentUrl}
              disabled={disabled}
              onChange={(event) => onChange(event.target.files?.[0] ?? null)}
            />
          </label>
        </div>
      </div>
    </div>
  );
}
