"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";
import { AlertCircle, RefreshCw, Filter } from "lucide-react";
import { clsx } from "clsx";
import { format } from "date-fns";

type ReportStatus = 'Pending' | 'Ongoing' | 'Completed';
type ReportPriority = 'Low' | 'Medium' | 'High';

interface Report {
    id: string;
    case_id?: string;
    status: ReportStatus;
    priority: ReportPriority;
    credibility_score?: number;
    created_at: string;
}

export default function PendingReports() {
    const [reports, setReports] = useState<Report[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const router = useRouter();

    const fetchReports = async () => {
        try {
            const res = await api.get("/admin/reports/");
            // Filter for Pending
            const allReports: Report[] = res.data;
            setReports(allReports.filter(r => r.status === 'Pending'));
            setError(null);
        } catch (err: any) {
            console.error(err);
            if (err.response?.status !== 401) {
                setError("Failed to load reports.");
            }
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchReports();
    }, [router]);

    const getStatusColor = (status: ReportStatus) => {
        switch (status) {
            case 'Pending': return "bg-red-500/10 text-red-500 border-red-500/20";
            case 'Ongoing': return "bg-yellow-500/10 text-yellow-500 border-yellow-500/20";
            case 'Completed': return "bg-green-500/10 text-green-500 border-green-500/20";
            default: return "bg-gray-500/10 text-gray-500";
        }
    }

    const getPriorityColor = (priority: ReportPriority) => {
        switch (priority) {
            case 'High': return "text-red-500 font-bold";
            case 'Medium': return "text-yellow-500 font-semibold";
            case 'Low': return "text-blue-500";
            default: return "text-gray-500";
        }
    }

    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-white">Pending Reports</h1>
                    <p className="text-muted-foreground mt-1">Cases awaiting initial review.</p>
                </div>
                <div className="flex items-center gap-3">
                    <button
                        onClick={() => fetchReports()}
                        className="p-2 rounded-md bg-secondary text-muted-foreground hover:text-white hover:bg-white/5 transition-colors"
                        title="Refresh"
                    >
                        <RefreshCw className={clsx("h-5 w-5", loading && "animate-spin")} />
                    </button>
                </div>
            </div>

            {/* Reports Table */}
            <div className="rounded-xl border border-border bg-card overflow-hidden">
                <div className="p-6 border-b border-border">
                    <h3 className="font-semibold text-white">Pending Cases</h3>
                </div>

                {loading ? (
                    <div className="p-12 text-center text-muted-foreground">Loading secure data...</div>
                ) : error ? (
                    <div className="p-12 text-center text-destructive flex flex-col items-center gap-2">
                        <AlertCircle className="h-8 w-8" />
                        {error}
                    </div>
                ) : reports.length === 0 ? (
                    <div className="p-12 text-center text-muted-foreground">No pending reports found.</div>
                ) : (
                    <div className="overflow-x-auto">
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
                                    <tr
                                        key={report.id}
                                        className="hover:bg-white/5 transition-colors cursor-pointer"
                                        onClick={() => router.push(`/case/${report.id}`)}
                                    >
                                        <td className="px-6 py-4 font-mono text-white">
                                            {report.case_id || report.id.substring(0, 8).toUpperCase() + "..."}
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className={clsx("text-xs font-medium uppercase", getPriorityColor(report.priority))}>
                                                {report.priority}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-2">
                                                <div className="h-2 w-16 bg-secondary rounded-full overflow-hidden">
                                                    <div
                                                        className={clsx("h-full", report.credibility_score && report.credibility_score > 70 ? "bg-green-500" : "bg-yellow-500")}
                                                        style={{ width: `${report.credibility_score || 0}%` }}
                                                    />
                                                </div>
                                                <span className="text-muted-foreground">{report.credibility_score || 0}%</span>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 text-muted-foreground">
                                            {format(new Date(report.created_at), 'MMM d, yyyy HH:mm')}
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className={clsx("inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ring-1 ring-inset", getStatusColor(report.status))}>
                                                {report.status}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}
