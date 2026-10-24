"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, Loader2 } from "lucide-react";
import { cn, formatToIST } from "@/lib/utils";
import type { CaseStatus, Priority, ReportListItem } from "@/lib/types";

const STATUS_STYLE: Record<CaseStatus, string> = {
    Pending: "bg-red-500/10 text-red-500 border-red-500/20",
    Ongoing: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20",
    Completed: "bg-green-500/10 text-green-500 border-green-500/20",
};

const PRIORITY_STYLE: Record<Priority, string> = {
    High: "text-red-500 font-bold",
    Medium: "text-yellow-500 font-semibold",
    Low: "text-blue-500",
    Pending: "text-muted-foreground italic",
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
    return (
        <span className={cn("inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ring-1 ring-inset", STATUS_STYLE[status as CaseStatus] ?? "bg-gray-500/10 text-gray-500", className)}>
            {status}
        </span>
    );
}

function scoreColor(report: ReportListItem): string {
    if (report.confidence === "High") return "bg-green-500";
    if (report.confidence === "Medium") return "bg-yellow-500";
    return "bg-red-500";
}

/** The credibility score, or what is happening instead of one (analysis running / failed). */
export function ScoreCell({ report }: { report: ReportListItem }) {
    if (report.credibility_score !== null) {
        return (
            <div className="flex items-center gap-2">
                <div className="h-2 w-16 bg-secondary rounded-full overflow-hidden" role="presentation">
                    <div className={cn("h-full", scoreColor(report))} style={{ width: `${report.credibility_score}%` }} />
                </div>
                <span className="text-muted-foreground">{report.credibility_score}%</span>
            </div>
        );
    }
    if (report.analysis_status === "failed") {
        return (
            <span className="inline-flex items-center gap-1 text-xs text-red-400">
                <AlertCircle className="h-3 w-3" /> Analysis failed
            </span>
        );
    }
    return (
        <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" /> Analysing
        </span>
    );
}

interface ReportsTableProps {
    reports: ReportListItem[];
    loading: boolean;
    error: string | null;
    emptyText: string;
}

export function ReportsTable({ reports, loading, error, emptyText }: ReportsTableProps) {
    const router = useRouter();

    if (loading) return <div className="p-12 text-center text-muted-foreground">Loading secure data...</div>;
    if (error) {
        return (
            <div className="p-12 text-center text-destructive flex flex-col items-center gap-2" role="alert">
                <AlertCircle className="h-8 w-8" />
                {error}
            </div>
        );
    }
    if (reports.length === 0) return <div className="p-12 text-center text-muted-foreground">{emptyText}</div>;

    return (
        <>
            {/* Desktop table */}
            <div className="hidden md:block overflow-x-auto">
                <table className="w-full text-left text-sm">
                    <thead className="bg-white/5 text-muted-foreground">
                        <tr>
                            <th className="px-6 py-3 font-medium">Case ID</th>
                            <th className="px-6 py-3 font-medium">Priority</th>
                            <th className="px-6 py-3 font-medium">Credibility Score</th>
                            <th className="px-6 py-3 font-medium">Submitted On</th>
                            <th className="px-6 py-3 font-medium">Status</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                        {reports.map((report) => (
                            <tr key={report.id} className="hover:bg-white/5 transition-colors cursor-pointer" onClick={() => router.push(`/case/${report.id}`)}>
                                <td className="px-6 py-4 font-mono text-white">
                                    <Link href={`/case/${report.id}`} onClick={(e) => e.stopPropagation()} className="hover:underline focus-visible:underline">
                                        {report.case_id}
                                    </Link>
                                </td>
                                <td className="px-6 py-4">
                                    <span className={cn("text-xs font-medium uppercase", PRIORITY_STYLE[report.priority])}>{report.priority}</span>
                                </td>
                                <td className="px-6 py-4">
                                    <ScoreCell report={report} />
                                </td>
                                <td className="px-6 py-4 text-muted-foreground">{formatToIST(report.created_at)}</td>
                                <td className="px-6 py-4">
                                    <StatusBadge status={report.status} />
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Mobile cards */}
            <div className="md:hidden divide-y divide-border">
                {reports.map((report) => (
                    <Link key={report.id} href={`/case/${report.id}`} className="block p-4 space-y-3 active:bg-white/5 transition-colors">
                        <div className="flex justify-between items-start">
                            <div className="font-mono text-white text-sm">{report.case_id}</div>
                            <StatusBadge status={report.status} className="px-2 py-0.5 text-[10px] font-bold uppercase" />
                        </div>
                        <div className="flex items-center justify-between text-xs">
                            <div className="flex items-center gap-2">
                                <span className="text-muted-foreground">Priority:</span>
                                <span className={cn("font-bold uppercase", PRIORITY_STYLE[report.priority])}>{report.priority}</span>
                            </div>
                            <div className="text-muted-foreground">{formatToIST(report.created_at)}</div>
                        </div>
                        <div className="flex items-center gap-2 pt-1">
                            <span className="text-[10px] text-muted-foreground uppercase tracking-widest">Score:</span>
                            <ScoreCell report={report} />
                        </div>
                    </Link>
                ))}
            </div>
        </>
    );
}
