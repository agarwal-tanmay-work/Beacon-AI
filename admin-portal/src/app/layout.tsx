import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import ClientLayout from "@/components/layout/ClientLayout";

const inter = Inter({ subsets: ["latin"] });

// The favicon comes from src/app/icon.png (Next.js file convention). The admin portal must never be indexed.
export const metadata: Metadata = {
  title: "Beacon Admin Portal",
  description: "Secure case management for investigators",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = { colorScheme: "dark" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className={`${inter.className} bg-background min-h-screen`} suppressHydrationWarning>
        <ClientLayout>{children}</ClientLayout>
      </body>
    </html>
  );
}
