import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "Aperture — OSINT Fusion",
  description:
    "Analyst-grade open-source intelligence platform. Cyber, maritime, aviation, and open-web on a single geospatial map.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  // `dark` class is on <html> by default — light mode toggle lands in Phase 8.
  return (
    <html lang="en" className="dark h-full">
      <body className="h-full">{children}</body>
    </html>
  );
}
