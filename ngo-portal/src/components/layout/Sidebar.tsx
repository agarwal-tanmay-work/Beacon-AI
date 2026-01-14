"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Inbox, CheckCircle, Clock, Shield, LogOut } from "lucide-react";
import { clsx } from "clsx";

const navigation = [
    { name: "Dashboard", href: "/", icon: LayoutDashboard },
    { name: "Pending", href: "/pending", icon: Inbox },
    { name: "Ongoing", href: "/ongoing", icon: Clock },
    { name: "Completed", href: "/completed", icon: CheckCircle },
];

export function Sidebar() {
    const pathname = usePathname();

    return (
        <div className="flex h-screen w-64 flex-col fixed inset-y-0 z-50 bg-card border-r border-border">
            <div className="flex h-16 shrink-0 items-center px-6 border-b border-border">
                <Shield className="h-8 w-8 text-primary mr-2" />
                <span className="text-lg font-bold tracking-tight text-white">Beacon NGO</span>
            </div>
            <nav className="flex flex-1 flex-col px-4 py-6 gap-1">
                {navigation.map((item) => {
                    const isActive = pathname === item.href;
                    return (
                        <Link
                            key={item.name}
                            href={item.href}
                            className={clsx(
                                isActive
                                    ? "bg-primary/10 text-primary"
                                    : "text-muted-foreground hover:bg-white/5 hover:text-white",
                                "group flex gap-x-3 rounded-md p-2 text-sm font-semibold leading-6 transition-colors"
                            )}
                        >
                            <item.icon
                                className={clsx(
                                    isActive ? "text-primary" : "text-muted-foreground group-hover:text-white",
                                    "h-5 w-5 shrink-0"
                                )}
                                aria-hidden="true"
                            />
                            {item.name}
                        </Link>
                    );
                })}
            </nav>
            <div className="p-4 border-t border-border">
                <div className="flex items-center gap-3 mb-4">
                    <div className="h-8 w-8 rounded-full bg-accent/20 flex items-center justify-center">
                        <span className="text-xs font-bold text-accent">AD</span>
                    </div>
                    <div className="flex flex-col">
                        <span className="text-sm font-medium text-white">Admin User</span>
                        <span className="text-xs text-muted-foreground">Secure Access</span>
                    </div>
                </div>

                <button
                    onClick={() => {
                        sessionStorage.removeItem("ngo_token");
                        sessionStorage.removeItem("ngo_user");
                        window.location.href = "/login";
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
