"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CheckCircle, Clock, Inbox, LayoutDashboard, LogOut, Shield } from "lucide-react";
import { clsx } from "clsx";
import { clearSession } from "@/lib/auth";

const navigation = [
    { name: "Dashboard", href: "/", icon: LayoutDashboard },
    { name: "Pending", href: "/pending", icon: Inbox },
    { name: "Ongoing", href: "/ongoing", icon: Clock },
    { name: "Completed", href: "/completed", icon: CheckCircle },
];

export function Sidebar() {
    const pathname = usePathname();

    return (
        <div className="flex w-full h-auto relative flex-col md:w-64 md:h-screen md:fixed md:inset-y-0 z-50 bg-card border-b md:border-b-0 md:border-r border-border">
            <div className="flex h-16 shrink-0 items-center px-6 border-b border-border">
                <Shield className="h-8 w-8 text-primary mr-2" />
                <span className="text-lg font-bold tracking-tight text-white">Beacon Admin</span>
            </div>
            <nav className="flex flex-1 flex-col px-4 py-6 gap-1" aria-label="Main">
                {navigation.map((item) => {
                    const isActive = pathname === item.href;
                    return (
                        <Link
                            key={item.name}
                            href={item.href}
                            aria-current={isActive ? "page" : undefined}
                            className={clsx(
                                isActive ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-white/5 hover:text-white",
                                "group flex gap-x-3 rounded-md p-2 text-sm font-semibold leading-6 transition-colors",
                            )}
                        >
                            <item.icon className={clsx(isActive ? "text-primary" : "text-muted-foreground group-hover:text-white", "h-5 w-5 shrink-0")} aria-hidden="true" />
                            {item.name}
                        </Link>
                    );
                })}
            </nav>
            <div className="p-4 border-t border-border">
                <button
                    type="button"
                    onClick={() => {
                        clearSession();
                        window.location.replace("/login");
                    }}
                    className="flex w-full items-center gap-x-3 rounded-md p-2 text-sm font-semibold leading-6 text-red-400 hover:bg-red-500/10 hover:text-red-300 transition-colors"
                >
                    <LogOut className="h-5 w-5 shrink-0" />
                    Sign Out
                </button>
            </div>
        </div>
    );
}
