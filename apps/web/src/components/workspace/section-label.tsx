import type { ReactNode } from "react";

interface SectionLabelProps {
  children: ReactNode;
  className?: string;
}

export function SectionLabel({ children, className = "" }: SectionLabelProps) {
  return (
    <p
      className={`text-[10px] font-semibold uppercase tracking-[0.28em] text-stone-400 ${className}`}
    >
      {children}
    </p>
  );
}
