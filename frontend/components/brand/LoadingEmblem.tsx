import Image from 'next/image';

export function LoadingEmblem({ size = 104, className = '' }: { size?: number; className?: string }) {
  return (
    <Image
      src="/brand/tafiti-loading-emblem.png"
      alt=""
      aria-hidden="true"
      width={1254}
      height={1254}
      sizes={`${size}px`}
      priority
      draggable={false}
      style={{ width: size, height: size }}
      className={`select-none object-contain drop-shadow-[0_12px_28px_rgba(37,99,235,.18)] motion-safe:animate-pulse ${className}`}
    />
  );
}
