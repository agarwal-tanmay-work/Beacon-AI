"use client";

import { useCallback, useEffect, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import type { ReportListItem } from "@/lib/types";

/** Loads the case list and keeps it fresh (a new submission shows up without a manual reload). */
export function useReports(refreshMs = 30_000) {
    const [reports, setReports] = useState<ReportListItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const reload = useCallback(async () => {
        try {
            const { data } = await api.get<ReportListItem[]>("/admin/reports/");
            setReports(data);
            setError(null);
        } catch (err) {
            setError(errorMessage(err, "Failed to load reports."));
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        const first = window.setTimeout(() => void reload(), 0);
        const timer = window.setInterval(() => {
            if (document.visibilityState === "visible") void reload();
        }, refreshMs);
        return () => {
            window.clearTimeout(first);
            window.clearInterval(timer);
        };
    }, [reload, refreshMs]);

    return { reports, loading, error, reload };
}
