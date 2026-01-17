import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuroraBackground } from "@/components/glass/AuroraBackground";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Beacon AI",
  description: "Secure Anti-Corruption Reporting",
  icons: {
    icon: [
      { url: "/favicon-final.png", type: "image/png", sizes: "any" },
    ],
    shortcut: ["/favicon-final.png"],
    apple: ["/favicon-final.png"],
  },
};

import { AppNavBar } from "@/components/ui/app-navbar";
import { PixelCursorTrail } from "@/components/ui/pixel-trail";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className} suppressHydrationWarning={true}>
        <div className="fixed top-4 left-4 md:top-6 md:left-8 z-[100] pointer-events-none select-none">
          <div className="bg-black/50 border border-white/10 backdrop-blur-lg py-2 px-4 md:py-3 md:px-6 rounded-full shadow-lg flex items-center justify-center">
            <span className="text-lg md:text-xl font-bold text-white tracking-[0.1em] drop-shadow-[0_0_15px_rgba(0,255,255,0.8)] opacity-90">
              Beacon AI
            </span>
          </div>
        </div>
        <PixelCursorTrail />
        <AppNavBar />
        <AuroraBackground />
        <main className="min-h-screen flex flex-col items-center p-0 overflow-x-hidden">
          {children}
        </main>
      </body>
    </html>
  );
}
