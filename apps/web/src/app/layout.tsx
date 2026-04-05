import type { ReactNode } from "react";
import "./globals.css";


export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen font-[family-name:var(--font-sans)] antialiased">
        {children}
      </body>
    </html>
  );
}
