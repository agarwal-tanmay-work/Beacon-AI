"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Inbox, CheckCircle, FileText, Settings, Shield } from "lucide-react";
import { clsx } from "clsx";

const navigation = [
    { name: "Dashboard", href: "/", icon: LayoutDashboard },
    { name: "Incoming Reports", href: "/reports/incoming", icon: Inbox },
    { name: "Verified Cases", href: "/reports/verified", icon: CheckCircle },
    { name: "Evidence Vault", href: "/evidence", icon: FileText },
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
                <div className="flex items-center gap-3">
                    <div className="h-8 w-8 rounded-full bg-accent/20 flex items-center justify-center">
                        <span className="text-xs font-bold text-accent">AD</span>
                    </div>
                    <div className="flex flex-col">
                        <span className="text-sm font-medium text-white">Admin User</span>
                        <span className="text-xs text-muted-foreground">Secure Access</span>
                    </div>
                </div>
            </div>
        </div>
    );
}
