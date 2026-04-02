import type { ReactNode } from "react";


export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-stone-100 text-neutral-950">{children}</body>
    </html>
  );
}
