"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import AuthGuard from "@/components/auth/AuthGuard";

export default function ClientLayout({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();
    const isLoginPage = pathname === "/login";

    return (
        <AuthGuard>
            <div className="flex min-h-screen">
                {!isLoginPage && <Sidebar />}
                <main className={!isLoginPage ? "flex-1 ml-64 p-8 overflow-y-auto h-screen" : "w-full"}>
                    {children}
                </main>
            </div>
        </AuthGuard>
    );
}
