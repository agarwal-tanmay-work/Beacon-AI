"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Shield, Clock, AlertTriangle, CheckCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface ReportItem {
    id: string;
    status: string;
    priority: string;
    credibility_score: number | null;
    created_at: string;
}

export default function DashboardPage() {
    const [reports, setReports] = useState<ReportItem[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchReports();
    }, []);

    const fetchReports = async () => {
        try {
            const res = await api.get("/admin/reports/");
            setReports(res.data);
        } catch (err) {
            console.error("Fetch failed", err);
        } finally {
            setLoading(false);
        }
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'NEW': return 'text-blue-400 bg-blue-400/10 border-blue-400/20';
            case 'VERIFIED': return 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20';
            case 'CRITICAL': return 'text-red-400 bg-red-400/10 border-red-400/20';
            default: return 'text-white/50 bg-white/5 border-white/10';
        }
    };

    return (
        <div className="flex-1 p-8 space-y-8 max-w-7xl mx-auto w-full">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-white mb-2">Case Dashboard</h1>
                    <p className="text-white/50">Overview of incoming anonymous reports</p>
                </div>
                <div className="flex items-center gap-4">
                    <div className="glass-panel px-4 py-2 rounded-full flex items-center gap-2 text-sm text-white/60">
                        <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                        Live System
                    </div>
                </div>
            </div>

            {/* Metrics Row (Static for Demo) */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {[
                    { label: "Total Reports", val: reports.length, icon: Shield },
                    { label: "High Priority", val: reports.filter(r => r.priority === 'HIGH' || r.priority === 'CRITICAL').length, icon: AlertTriangle },
                    { label: "Avg Credibility", val: "72%", icon: CheckCircle },
                    { label: "Pending Review", val: reports.filter(r => r.status === 'NEW').length, icon: Clock },
                ].map((m, i) => (
                    <div key={i} className="glass-panel p-6 rounded-2xl flex items-center justify-between">
                        <div>
                            <p className="text-sm text-white/40 mb-1">{m.label}</p>
                            <p className="text-2xl font-bold text-white">{m.val}</p>
                        </div>
                        <m.icon className="w-8 h-8 text-white/10" />
                    </div>
                ))}
            </div>

            {/* List */}
            <div className="glass-panel rounded-2xl overflow-hidden">
                <table className="w-full text-left">
                    <thead className="bg-white/5 text-xs uppercase text-white/40 font-mono tracking-wider">
                        <tr>
                            <th className="p-4">Case ID</th>
                            <th className="p-4">Date</th>
                            <th className="p-4">Status</th>
                            <th className="p-4">Priority</th>
                            <th className="p-4">Score</th>
                            <th className="p-4">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                        {reports.map((r) => (
                            <tr key={r.id} className="hover:bg-white/5 transition-colors">
                                <td className="p-4 font-mono text-sm text-white/70">{r.id.slice(0, 8)}...</td>
                                <td className="p-4 text-sm text-white/70">{new Date(r.created_at).toLocaleDateString()}</td>
                                <td className="p-4">
                                    <span className={cn("px-2 py-1 rounded-full text-xs font-medium border", getStatusColor(r.status))}>
                                        {r.status}
                                    </span>
                                </td>
                                <td className="p-4">
                                    <span className={cn("px-2 py-1 rounded-full text-xs font-medium border",
                                        r.priority === 'CRITICAL' ? 'text-red-400 bg-red-400/10 border-red-400/20' : 'text-white/50 border-white/10'
                                    )}>
                                        {r.priority}
                                    </span>
                                </td>
                                <td className="p-4">
                                    {r.credibility_score ? (
                                        <div className="flex items-center gap-2">
                                            <div className="w-16 h-1 bg-white/10 rounded-full overflow-hidden">
                                                <div className="h-full bg-emerald-400" style={{ width: `${r.credibility_score}%` }} />
                                            </div>
                                            <span className="text-xs text-white/50">{r.credibility_score}</span>
                                        </div>
                                    ) : <span className="text-white/20">-</span>}
                                </td>
                                <td className="p-4">
                                    <Link href={`/dashboard/${r.id}`}>
                                        <button className="px-3 py-1.5 glass-button rounded-lg text-xs hover:bg-white/20">View</button>
                                    </Link>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
