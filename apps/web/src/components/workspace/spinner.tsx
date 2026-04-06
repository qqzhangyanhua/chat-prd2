interface SpinnerProps {
  /** "sm" = h-3.5/w-3.5, "md" = h-4/w-4 */
  size?: "sm" | "md";
  /** Color scheme: "dark" = stone-900 border, "light" = white border */
  variant?: "dark" | "light";
  className?: string;
}

const sizes = {
  sm: "h-3.5 w-3.5",
  md: "h-4 w-4",
};

const variants = {
  dark: "border-stone-300 border-t-stone-900",
  light: "border-white/30 border-t-white",
};

export function Spinner({ size = "md", variant = "dark", className = "" }: SpinnerProps) {
  return (
    <div
      className={`rounded-full border-2 animate-spin ${sizes[size]} ${variants[variant]} ${className}`}
    />
  );
}
