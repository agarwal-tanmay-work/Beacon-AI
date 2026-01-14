"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";

export default function AuthGuard({ children }: { children: React.ReactNode }) {
    const router = useRouter();
    const pathname = usePathname();
    const [authorized, setAuthorized] = useState(false);

    useEffect(() => {
        // Allow login page access without check
        if (pathname === "/login") {
            setAuthorized(true);
            return;
        }

        // Check strict session storage
        const token = sessionStorage.getItem("ngo_token");

        if (!token) {
            router.replace("/login");
        } else {
            setAuthorized(true);
        }
    }, [pathname, router]);

    // Show nothing while checking (prevents flash of content)
    // Or a loading spinner if preferred, but requirements say "inaccessible"
    if (!authorized && pathname !== "/login") {
        return null;
    }

    return <>{children}</>;
}
