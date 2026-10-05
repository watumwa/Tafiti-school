'use client';

import { useEffect, useMemo, useState } from 'react';

import { workspaceMediaSrc } from '@/lib/media';

function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return '?';
  return parts.slice(0, 2).map((part) => part[0]?.toUpperCase() ?? '').join('');
}

export function ProfileAvatar({
  src,
  name,
  size = 'md',
  className = '',
}: {
  src: unknown;
  name: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}) {
  const resolved = useMemo(() => workspaceMediaSrc(src), [src]);
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [resolved]);

  const sizes = {
    sm: 'h-8 w-8 text-[10px]',
    md: 'h-10 w-10 text-xs',
    lg: 'h-16 w-16 text-base',
    xl: 'h-24 w-24 text-xl',
  };

  return (
    <span className={`relative inline-grid shrink-0 place-items-center overflow-hidden rounded-full border-2 border-white bg-[#DDE8F3] font-bold text-[#173F6B] shadow-[0_5px_14px_rgba(15,39,71,.16)] ${sizes[size]} ${className}`}>
      {resolved && !failed ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={resolved} alt={`${name} profile`} className="h-full w-full object-cover" onError={() => setFailed(true)} />
      ) : (
        <span aria-label={`${name} has no profile photo`}>{initials(name)}</span>
      )}
    </span>
  );
}
