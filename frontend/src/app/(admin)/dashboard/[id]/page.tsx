"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { ArrowLeft, Download, Shield, User, Bot, AlertTriangle, FileText, CheckCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { useAdminAuth } from "@/lib/auth-context";

interface Conversation {
    id: string;
    sender: "USER" | "SYSTEM" | "AI";
    content_redacted: string;
    created_at: string;
}

interface Evidence {
    id: string;
    file_name: string;
    mime_type: string;
    file_hash: string;
    is_pii_cleansed: boolean;
}

interface ReportDetail {
    id: string;
    status: string;
    priority: string;
    credibility_score: number | null;
    score_explanation: string | null;
    categories: string[];
    location_meta: Record<string, unknown> | null;
    created_at: string;
    conversations: Conversation[];
    evidence: Evidence[];
}

export default function CaseDetailPage() {
    const params = useParams();
    const { token } = useAdminAuth();
    const [report, setReport] = useState<ReportDetail | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (params.id) fetchReport(params.id as string);
    }, [params.id]);

    const fetchReport = async (id: string) => {
        try {
            const res = await api.get(`/admin/reports/${id}`);
            setReport(res.data);
        } catch (err) {
            console.error("Fetch failed", err);
        } finally {
            setLoading(false);
        }
    };

    const updateStatus = async (newStatus: string) => {
        if (!report) return;
        try {
            await api.put(`/admin/reports/${report.id}/status`, null, { params: { status: newStatus } });
            fetchReport(report.id);
        } catch (err) {
            console.error("Update failed", err);
        }
    };

    const downloadEvidence = async (evidenceId: string, filename: string) => {
        try {
            const res = await api.get(`/admin/evidence/${evidenceId}/download`, { responseType: 'blob' });
            const url = window.URL.createObjectURL(new Blob([res.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', filename);
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (err) {
            console.error("Download failed", err);
        }
    };

    if (loading) return <div className="p-8 text-white/50">Loading Case Data...</div>;
    if (!report) return <div className="p-8 text-white/50">Case Not Found</div>;

    return (
        <div className="flex-1 p-8 space-y-8 max-w-7xl mx-auto w-full">
            {/* Header */}
            <div className="flex items-center gap-4 mb-8">
                <Link href="/dashboard">
                    <button className="p-2 glass-button rounded-full text-white/50 hover:text-white">
                        <ArrowLeft className="w-5 h-5" />
                    </button>
                </Link>
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        Case #{report.id.slice(0, 8)}
                        <span className="text-xs px-2 py-1 rounded-full border border-white/10 bg-white/5 text-white/50 font-mono">
                            {report.status}
                        </span>
                    </h1>
                    <p className="text-sm text-white/40">Created {new Date(report.created_at).toLocaleString()}</p>
                </div>
                <div className="ml-auto flex gap-2">
                    {['VERIFIED', 'IN_REVIEW', 'CLOSED', 'DISMISSED'].map(s => (
                        <button
                            key={s}
                            onClick={() => updateStatus(s)}
                            className={cn(
                                "px-3 py-1.5 rounded-lg text-xs font-medium transition-all border",
                                report.status === s
                                    ? "bg-white text-black border-white"
                                    : "bg-transparent text-white/50 border-white/10 hover:border-white/30"
                            )}
                        >
                            {s}
                        </button>
                    ))}
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Main Chat View */}
                <div className="lg:col-span-2 space-y-6">
                    <div className="glass-panel p-6 rounded-2xl min-h-[500px]">
                        <h2 className="text-sm font-semibold text-white/70 mb-4 flex items-center gap-2">
                            <Shield className="w-4 h-4 text-emerald-400" />
                            Secure Transcript (Redacted)
                        </h2>
                        <div className="space-y-4">
                            {report.conversations.map(msg => (
                                <div key={msg.id} className={cn("flex gap-4 p-4 rounded-xl", msg.sender === 'USER' ? "bg-white/5 border border-white/5" : "bg-transparent")}>
                                    <div className="mt-1">
                                        {msg.sender === 'USER' ? <User className="w-5 h-5 text-blue-400" /> : <Bot className="w-5 h-5 text-purple-400" />}
                                    </div>
                                    <div className="space-y-1">
                                        <div className="flex items-center gap-2">
                                            <span className="text-xs font-bold text-white/60">{msg.sender}</span>
                                            <span className="text-[10px] text-white/20">{new Date(msg.created_at).toLocaleTimeString()}</span>
                                        </div>
                                        <p className="text-sm text-white/80 leading-relaxed font-mono whitespace-pre-wrap">
                                            {msg.content_redacted}
                                        </p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Sidebar */}
                <div className="space-y-6">
                    {/* Credibility Score */}
                    <div className="glass-panel p-6 rounded-2xl">
                        <h3 className="text-sm font-semibold text-white/70 mb-4 flex items-center gap-2">
                            <CheckCircle className="w-4 h-4 text-blue-400" />
                            AI Analysis
                        </h3>
                        <div className="flex items-center gap-4 mb-4">
                            <div className="text-4xl font-bold text-white">{report.credibility_score || 0}%</div>
                            <div className="text-xs text-white/40 leading-tight">Credibility<br />Score</div>
                        </div>
                        <div className="p-3 bg-white/5 rounded-lg border border-white/10">
                            <p className="text-xs text-white/60 leading-relaxed">
                                {report.score_explanation || "No analysis available."}
                            </p>
                        </div>
                    </div>

                    {/* Meta Data */}
                    <div className="glass-panel p-6 rounded-2xl">
                        <h3 className="text-sm font-semibold text-white/70 mb-4 flex items-center gap-2">
                            <FileText className="w-4 h-4 text-yellow-400" />
                            Metadata
                        </h3>
                        <div className="space-y-3 text-sm">
                            <div className="flex justify-between">
                                <span className="text-white/40">Priority</span>
                                <span className={cn("text-white", report.priority === 'CRITICAL' && "text-red-400 font-bold")}>{report.priority}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-white/40">Categories</span>
                                <span className="text-white text-right">{report.categories.join(", ") || "None"}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-white/40">Location</span>
                                <span className="text-white text-right">{String(report.location_meta?.location || "Unknown")}</span>
                            </div>
                        </div>
                    </div>

                    {/* Evidence */}
                    <div className="glass-panel p-6 rounded-2xl">
                        <h3 className="text-sm font-semibold text-white/70 mb-4 flex items-center gap-2">
                            <AlertTriangle className="w-4 h-4 text-orange-400" />
                            Evidence Files
                        </h3>
                        {report.evidence.length === 0 ? (
                            <div className="text-center py-8 text-white/20 text-xs">No files uploaded.</div>
                        ) : (
                            <div className="space-y-2">
                                {report.evidence.map(f => (
                                    <button
                                        key={f.id}
                                        onClick={() => downloadEvidence(f.id, f.file_name)}
                                        className="w-full p-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl flex items-center justify-between group transition-all"
                                    >
                                        <div className="flex items-center gap-3 overflow-hidden">
                                            <FileText className="w-4 h-4 text-white/40" />
                                            <div className="text-left overflow-hidden">
                                                <p className="text-xs text-white truncate">{f.file_name}</p>
                                                <p className="text-[10px] text-white/30 uppercase">{f.is_pii_cleansed ? "Scrubbed" : "Raw"}</p>
                                            </div>
                                        </div>
                                        <Download className="w-4 h-4 text-white/20 group-hover:text-white transition-colors" />
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
