"use client";

import { useEffect, useSyncExternalStore } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getToken, isExpired } from "@/lib/auth";

function subscribe(onChange: () => void) {
    window.addEventListener("storage", onChange); // sign-in / sign-out in another tab
    return () => window.removeEventListener("storage", onChange);
}

/** True when this tab holds a valid, unexpired admin token. Server render: false (nothing is shown until the client checks). */
function useSignedIn(): boolean {
    return useSyncExternalStore(
        subscribe,
        () => !isExpired(getToken()),
        () => false,
    );
}

export default function AuthGuard({ children }: { children: React.ReactNode }) {
    const router = useRouter();
    const pathname = usePathname();
    const signedIn = useSignedIn();
    const onLoginPage = pathname === "/login";

    useEffect(() => {
        if (!signedIn && !onLoginPage) router.replace("/login");
    }, [signedIn, onLoginPage, router]);

    // Never flash protected content to a signed-out visitor.
    if (!signedIn && !onLoginPage) return null;
    return <>{children}</>;
}
