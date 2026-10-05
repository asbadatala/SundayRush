import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { BottomNav } from "@/components/bottom-nav";
import { Providers } from "@/components/providers";

import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "SundayRush — every NFL game that matters to you",
  description: "Connect your fantasy teams and see every NFL game that matters to you in one place.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, viewportFit: "cover" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full bg-muted/30">
        <Providers>
          <main className="mx-auto w-full max-w-3xl px-4 pt-6 pb-28">{children}</main>
          <BottomNav />
        </Providers>
      </body>
    </html>
  );
}
