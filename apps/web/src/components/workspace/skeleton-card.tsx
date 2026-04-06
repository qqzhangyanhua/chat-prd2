interface SkeletonCardProps {
  className?: string;
}

export function SkeletonCard({ className = "" }: SkeletonCardProps) {
  return (
    <div
      className={`rounded-2xl border border-stone-200/80 bg-white animate-pulse shadow-[0_2px_12px_rgba(0,0,0,0.04)] ${className}`}
    />
  );
}
