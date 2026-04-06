interface BrandIconProps {
  /** "sm" = 14×14 inside h-7/w-7 container (nav), "md" = 18×18 inside h-10/w-10 (hero / empty state) */
  size?: "sm" | "md";
  className?: string;
}

const sizes = {
  sm: { container: "h-7 w-7 rounded-lg shadow-sm", svg: 14 },
  md: { container: "h-10 w-10 rounded-xl shadow-lg", svg: 18 },
};

export function BrandIcon({ size = "md", className = "" }: BrandIconProps) {
  const { container, svg } = sizes[size];
  return (
    <div
      className={`flex shrink-0 items-center justify-center bg-gradient-to-br from-brand-primary to-brand-accent text-white ${container} ${className}`}
    >
      <svg
        width={svg}
        height={svg}
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z"
          fill="currentColor"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}
