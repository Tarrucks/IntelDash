import type { Metadata } from "next";
import type { ReactNode } from "react";

import { themeInitScript } from "@/lib/theme";

import "./globals.css";

export const metadata: Metadata = {
  title: "Aperture — OSINT Fusion",
  description:
    "Analyst-grade open-source intelligence platform. Cyber, maritime, aviation, and open-web on a single geospatial map.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  // The default ``dark`` class is set here so SSR markup is consistent;
  // the blocking init script below mutates it before first paint to
  // match the user's stored preference. This avoids a flash of the
  // wrong theme without needing useEffect-based hydration tricks.
  return (
    <html lang="en" className="dark h-full" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="h-full">{children}</body>
    </html>
  );
}
