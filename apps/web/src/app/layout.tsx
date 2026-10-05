import type { Metadata, Viewport } from "next";
import { Inter, Oswald } from "next/font/google";

import { BottomNav } from "@/components/bottom-nav";
import { Providers } from "@/components/providers";
import { TopBar } from "@/components/top-bar";
import { THEME_INIT_SCRIPT } from "@/lib/theme-script";

import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const oswald = Oswald({ variable: "--font-oswald", subsets: ["latin"], weight: ["500", "600", "700"] });

export const metadata: Metadata = {
  title: "SundayRush — every NFL game that matters to you",
  description: "Connect your fantasy teams and see every NFL game that matters to you in one place.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f5ef" },
    { media: "(prefers-color-scheme: dark)", color: "#0f1726" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // suppressHydrationWarning: THEME_INIT_SCRIPT may add the .dark class before React hydrates.
    <html lang="en" className={`${inter.variable} ${oswald.variable} h-full antialiased`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="min-h-full">
        <Providers>
          <main className="mx-auto w-full max-w-3xl px-4 pt-4 pb-28">
            <TopBar />
            {children}
          </main>
          <BottomNav />
        </Providers>
      </body>
    </html>
  );
}
