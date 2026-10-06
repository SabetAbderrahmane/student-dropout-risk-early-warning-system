import type { Metadata } from "next";
import { Geist } from "next/font/google";
import type { ReactNode } from "react";
import { ThemeProvider } from "@/components/theme/theme-provider";
import { THEME_INITIALIZATION } from "@/lib/theme";

import "./theme.css";
import "./globals.css";
const geist = Geist({ subsets: ["latin"], variable: "--font-geist" });

export const metadata: Metadata = {
  title: "Student Dropout Early Warning System",
  description:
    "Secure foundation for student dropout risk early warning workflows.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          id="initialize-theme"
          dangerouslySetInnerHTML={{ __html: THEME_INITIALIZATION }}
        />
      </head>
      <body className={geist.variable}>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
