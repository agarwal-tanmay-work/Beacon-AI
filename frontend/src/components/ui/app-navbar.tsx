"use client";

import { AnimeNavBar } from "@/components/ui/anime-navbar";
import { Home, ShieldCheck, Activity, Info } from "lucide-react";

import { usePathname } from "next/navigation";

export function AppNavBar() {
    const pathname = usePathname();

    const navItems = [
        { name: "Home", url: "/", icon: Home },
        { name: "Submit Report", url: "/report", icon: ShieldCheck },
        { name: "Track Status", url: "/track", icon: Activity },
    ];

    // Align center on Home, Right on other pages
    const alignment = pathname === "/" ? "center" : "right";

    return <AnimeNavBar items={navItems} alignment={alignment} />;
}
