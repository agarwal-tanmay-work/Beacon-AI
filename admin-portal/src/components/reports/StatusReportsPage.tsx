"use client";

import { RefreshCw } from "lucide-react";
import { clsx } from "clsx";
import { ReportsTable } from "@/components/reports/ReportsTable";
import { useReports } from "@/components/reports/useReports";
import type { CaseStatus } from "@/lib/types";

interface StatusReportsPageProps {
    status: CaseStatus;
    title: string;
    subtitle: string;
    emptyText: string;
}

/** The Pending / Ongoing / Completed lists - one component instead of three near-identical pages. */
export function StatusReportsPage({ status, title, subtitle, emptyText }: StatusReportsPageProps) {
    const { reports, loading, error, reload } = useReports();
    const filtered = reports.filter((r) => r.status === status);

    return (
        <div className="space-y-8">
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-white">{title}</h1>
                    <p className="text-muted-foreground mt-1">{subtitle}</p>
                </div>
                <button
                    type="button"
                    onClick={() => void reload()}
                    className="p-2 rounded-md bg-secondary text-muted-foreground hover:text-white hover:bg-white/5 transition-colors"
                    title="Refresh"
                    aria-label="Refresh"
                >
                    <RefreshCw className={clsx("h-5 w-5", loading && "animate-spin")} />
                </button>
            </div>

            <div className="rounded-xl border border-border bg-card overflow-hidden">
                <div className="p-6 border-b border-border">
                    <h2 className="font-semibold text-white">
                        {title} <span className="ml-2 text-sm font-normal text-muted-foreground">{loading ? "" : `(${filtered.length})`}</span>
                    </h2>
                </div>
                <ReportsTable reports={filtered} loading={loading} error={error} emptyText={emptyText} />
            </div>
        </div>
    );
}
