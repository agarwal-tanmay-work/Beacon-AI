import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import ClientLayout from "@/components/layout/ClientLayout";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Beacon NGO Portal",
  description: "Secure Anti-Corruption Case Management",
  icons: {
    icon: [
      { url: "/favicon-final.png", type: "image/png", sizes: "any" },
    ],
    shortcut: ["/favicon-final.png"],
    apple: ["/favicon-final.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className={`${inter.className} bg-background min-h-screen`} suppressHydrationWarning>
        <ClientLayout>
          {children}
        </ClientLayout>
      </body>
    </html>
  );
}
