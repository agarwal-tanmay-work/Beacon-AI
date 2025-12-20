"use client";

import { AdminProvider, useAdminAuth } from "@/lib/auth-context";
import { useRouter, usePathname } from "next/navigation";
import { useEffect } from "react";

function AuthGuard({ children }: { children: React.ReactNode }) {
    useAdminAuth();
    const router = useRouter();
    const pathname = usePathname();

    useEffect(() => {
        // If not authenticated and not on login page, redirect
        // Simple check: if localstorage empty
        const stored = localStorage.getItem("admin_token");
        if (!stored && pathname !== "/login") {
            router.push("/login");
        }
        else if (stored && pathname === "/login") {
            router.push("/dashboard");
        }
    }, [pathname, router]);

    return <>{children}</>;
}

export default function AdminLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <AdminProvider>
            <AuthGuard>
                <div className="w-full min-h-screen flex flex-col">
                    {children}
                </div>
            </AuthGuard>
        </AdminProvider>
    );
}
