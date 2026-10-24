import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuroraBackground } from "@/components/glass/AuroraBackground";
import { AppNavBar } from "@/components/ui/app-navbar";
import { PixelCursorTrail } from "@/components/ui/pixel-trail";

const inter = Inter({ subsets: ["latin"] });

// The favicon comes from src/app/icon.png (Next.js file convention).
export const metadata: Metadata = {
  title: { default: "Beacon AI", template: "%s | Beacon AI" },
  description: "Report corruption or misconduct safely and anonymously, guided by an AI assistant. Track your case with a private Case ID and Secret Key.",
};

export const viewport: Viewport = {
  themeColor: "#000000",
  colorScheme: "dark",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className} suppressHydrationWarning={true}>
        {/* Watermark: top-left on desktop only */}
        <div className="hidden md:block fixed md:top-6 md:left-8 z-[100] pointer-events-none select-none">
          <div className="bg-black/50 border border-white/10 backdrop-blur-lg py-2 px-4 md:py-3 md:px-6 rounded-full shadow-lg flex items-center justify-center">
            <span className="text-lg md:text-xl font-bold text-white tracking-[0.1em] drop-shadow-[0_0_15px_rgba(0,255,255,0.8)] opacity-90">Beacon AI</span>
          </div>
        </div>
        <PixelCursorTrail />
        <AppNavBar />
        <AuroraBackground />
        <main className="min-h-screen flex flex-col items-center p-0 overflow-x-hidden pt-24 md:pt-0">{children}</main>
      </body>
    </html>
  );
}
