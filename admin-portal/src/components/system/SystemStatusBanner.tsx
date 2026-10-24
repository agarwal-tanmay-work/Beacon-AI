"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";
import type { SystemStatus } from "@/lib/types";

const AI_LABEL: Record<SystemStatus["ai"]["state"], string> = {
    ok: "AI assistant online",
    unknown: "AI assistant ready",
    degraded: "AI assistant degraded (basic mode)",
    key_invalid: "AI key rejected",
    unconfigured: "AI not configured",
};

/** Tells the administrator when something that affects reporters needs attention (AI down, bad key, ephemeral storage ...). */
export function SystemStatusBanner() {
    const [status, setStatus] = useState<SystemStatus | null>(null);

    useEffect(() => {
        let cancelled = false;
        const load = async () => {
            try {
                const { data } = await api.get<SystemStatus>("/admin/system/status");
                if (!cancelled) setStatus(data);
            } catch {
                /* the banner is optional - never block the dashboard on it */
            }
        };
        void load();
        const timer = window.setInterval(load, 60_000);
        return () => {
            cancelled = true;
            window.clearInterval(timer);
        };
    }, []);

    if (!status) return null;
    const healthy = status.warnings.length === 0 && status.database === "connected";
    return (
        <div
            role={healthy ? "status" : "alert"}
            className={healthy ? "flex items-center gap-2 rounded-xl border border-green-500/20 bg-green-500/5 px-4 py-3 text-sm text-green-300" : "space-y-1 rounded-xl border border-yellow-500/30 bg-yellow-500/10 px-4 py-3 text-sm text-yellow-100"}
        >
            {healthy ? (
                <>
                    <CheckCircle2 className="h-4 w-4 shrink-0" /> All systems operational. {AI_LABEL[status.ai.state]}.
                </>
            ) : (
                <>
                    <p className="flex items-center gap-2 font-semibold">
                        <AlertTriangle className="h-4 w-4 shrink-0" /> {AI_LABEL[status.ai.state]}
                        {status.database !== "connected" && " · database disconnected"}
                    </p>
                    <ul className="list-disc space-y-0.5 pl-6 text-yellow-100/80">
                        {status.warnings.map((warning) => (
                            <li key={warning}>{warning}</li>
                        ))}
                    </ul>
                </>
            )}
        </div>
    );
}
