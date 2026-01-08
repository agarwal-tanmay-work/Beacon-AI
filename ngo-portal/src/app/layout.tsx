import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/layout/Sidebar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Beacon NGO Portal",
  description: "Secure Anti-Corruption Case Management",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-background min-h-screen flex`}>
        <Sidebar />
        <main className="flex-1 ml-64 p-8 overflow-y-auto h-screen">
          {children}
        </main>
      </body>
    </html>
  );
}
