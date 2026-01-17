"use client";
// Force Refresh for Timezone Fix

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { ArrowLeft, Send, Clock, AlertTriangle, FileText, ChevronDown, Shield, Paperclip } from "lucide-react";
import { clsx } from "clsx";
import { formatToIST } from "@/lib/utils";

interface EvidenceFile {
    file_name: string;
    mime_type: string;
    size_bytes: number;
    full_url?: string;
    file_path?: string;
    error?: string;
}

interface CaseDetail {
    id: string;
    case_id: string;
    status: 'Pending' | 'Ongoing' | 'Completed';
    priority: 'Low' | 'Medium' | 'High';
    credibility_score: number | null;
    incident_summary: string | null;
    app_score_explanation: string | null; // Renamed from score_explanation to match backend
    evidence_files: EvidenceFile[];
    updates: CaseUpdate[];
    created_at: string;
}

interface CaseUpdate {
    id: string;
    public_update: string;
    updated_by: string;
    created_at: string;
}

interface TrackMessage {
    id: string;
    sender_role: 'user' | 'ngo';
    content?: string;
    attachments: MessageAttachment[];
    timestamp: string;
}

interface MessageAttachment {
    file_name: string;
    file_path: string;
    mime_type: string;
}

export default function CaseDetailPage() {
    const params = useParams();
    const router = useRouter();
    const caseId = params.id as string;

    const [caseData, setCaseData] = useState<CaseDetail | null>(null);
    const [messages, setMessages] = useState<TrackMessage[]>([]);
    // updates removed, using caseData.updates
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Status Edit State
    const [isEditingStatus, setIsEditingStatus] = useState(false);
    const [statusLoading, setStatusLoading] = useState(false);

    // Communication State
    const [messageInput, setMessageInput] = useState("");
    const [sending, setSending] = useState(false);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);

    // Update form
    const [updateText, setUpdateText] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [submitSuccess, setSubmitSuccess] = useState(false);

    const fetchCaseData = useCallback(async () => {
        try {
            // Parallelize fetches for better performance
            const [reportRes, msgRes] = await Promise.all([
                api.get(`/admin/reports/${caseId}`),
                api.get(`/admin/reports/${caseId}/messages`)
            ]);

            setCaseData(reportRes.data);
            setMessages(msgRes.data);
        } catch (err) {
            console.error(err);
            setError("Failed to load case details or messages");
        } finally {
            setLoading(false);
        }
    }, [caseId]);

    useEffect(() => {
        fetchCaseData();
        const interval = setInterval(fetchCaseData, 30000);
        return () => clearInterval(interval);
    }, [caseId, fetchCaseData]);

    const handleStatusChange = async (newStatus: string) => {
        if (!caseData) return;
        setStatusLoading(true);
        try {
            const res = await api.put(`/admin/reports/${caseId}/status`, { status: newStatus });
            setCaseData(prev => prev ? { ...prev, status: res.data.status } : null);
            setIsEditingStatus(false);
        } catch (err) {
            console.error("Failed to update status", err);
            alert("Failed to update status");
        } finally {
            setStatusLoading(false);
        }
    };

    const handleSendMessage = async () => {
        if (!messageInput.trim() && !selectedFile) return;
        setSending(true);

        try {
            const attachments: MessageAttachment[] = [];

            if (selectedFile) {
                const formData = new FormData();
                formData.append("file", selectedFile);
                const uploadRes = await api.post(`/admin/reports/${caseId}/upload`, formData, {
                    headers: { "Content-Type": "multipart/form-data" }
                });
                attachments.push({
                    file_name: uploadRes.data.file_name,
                    file_path: uploadRes.data.file_path,
                    mime_type: uploadRes.data.mime_type
                });
            }

            await api.post(`/admin/reports/${caseId}/message`, {
                case_id: caseData?.case_id,
                secret_key: "NGO_BYPASS",
                content: messageInput.trim(),
                attachments
            });

            setMessageInput("");
            setSelectedFile(null);
            fetchCaseData();
        } catch (err) {
            console.error("Failed to send message", err);
            alert("Failed to send message");
        } finally {
            setSending(false);
        }
    };

    const handlePublishUpdate = async () => {
        if (!updateText.trim()) return;

        setSubmitting(true);
        setSubmitSuccess(false);

        try {
            const res = await api.post(`/admin/reports/${caseId}/update`, {
                raw_update: updateText.trim(),
                updated_by: "NGO_ADMIN"
            });

            // Optimistically update caseData
            if (caseData) {
                const newUpdate: CaseUpdate = {
                    id: crypto.randomUUID(),
                    public_update: res.data.public_update,
                    updated_by: "NGO_ADMIN",
                    created_at: new Date().toISOString()
                };
                setCaseData({
                    ...caseData,
                    updates: [newUpdate, ...(caseData.updates || [])]
                });
            }

            setUpdateText("");
            setSubmitSuccess(true);
            setTimeout(() => setSubmitSuccess(false), 3000);

        } catch (err) {
            console.error("Failed to publish update", err);
            alert("Failed to publish update. Please try again.");
        } finally {
            setSubmitting(false);
        }
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'Pending': return "bg-red-500 text-white";
            case 'Ongoing': return "bg-yellow-500 text-black";
            case 'Completed': return "bg-green-500 text-white";
            default: return "bg-gray-500 text-white";
        }
    }

    if (loading) return <div className="p-12 text-center text-muted-foreground">Loading sensitive case data...</div>;
    if (error) return <div className="p-12 text-center text-destructive">{error}</div>;
    if (!caseData) return null;

    return (
        <div className="space-y-6 max-w-6xl mx-auto pb-12">
            {/* Header / Nav */}
            <button onClick={() => router.back()} className="flex items-center gap-2 text-muted-foreground hover:text-white mb-4">
                <ArrowLeft className="w-4 h-4" /> Back to Dashboard
            </button>

            {/* Top Stat Bar */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {/* Case ID */}
                <div className="p-4 bg-card border border-border rounded-xl">
                    <span className="text-muted-foreground text-xs uppercase tracking-wider">Case ID</span>
                    <div className="text-2xl font-mono text-white mt-1">{caseData.case_id}</div>
                </div>

                {/* Status - Editable */}
                <div className="p-4 bg-card border border-border rounded-xl relative group">
                    <span className="text-muted-foreground text-xs uppercase tracking-wider">Status</span>
                    <div className="mt-1">
                        {isEditingStatus ? (
                            <div className="flex flex-col gap-1 absolute top-2 left-2 right-2 bg-zinc-900 border border-zinc-700 p-2 rounded-lg shadow-xl z-10">
                                {['Pending', 'Ongoing', 'Completed'].map(s => (
                                    <button
                                        key={s}
                                        disabled={statusLoading}
                                        onClick={() => handleStatusChange(s)}
                                        className={clsx(
                                            "text-left px-3 py-2 rounded hover:bg-white/10 text-sm flex items-center justify-between",
                                            caseData.status === s ? "text-primary font-bold" : "text-gray-300",
                                            statusLoading && "opacity-50 cursor-not-allowed"
                                        )}
                                    >
                                        {s}
                                        {statusLoading && s === caseData.status && <Clock className="w-3 h-3 animate-spin" />}
                                    </button>
                                ))}
                            </div>
                        ) : (
                            <button
                                onClick={() => setIsEditingStatus(true)}
                                className={clsx("flex items-center gap-2 px-3 py-1 rounded-full text-sm font-bold transition-all hover:ring-2 ring-white/20", getStatusColor(caseData.status))}
                            >
                                {caseData.status}
                                <ChevronDown className="w-4 h-4 opacity-70" />
                            </button>
                        )}
                    </div>
                </div>

                {/* Credibility Score */}
                <div className="p-4 bg-card border border-border rounded-xl flex flex-col justify-between">
                    <div>
                        <span className="text-muted-foreground text-xs uppercase tracking-wider">Credibility Score</span>
                        <div className={clsx(
                            "text-2xl font-bold mt-1",
                            caseData.credibility_score === null ? "text-muted-foreground" :
                                caseData.credibility_score > 70 ? "text-green-500" : "text-yellow-500"
                        )}>
                            {caseData.credibility_score !== null && caseData.credibility_score !== undefined
                                ? `${caseData.credibility_score}%`
                                : "Pending Analysis"}
                        </div>
                    </div>
                    {caseData.credibility_score === null && (
                        <button
                            disabled={submitting}
                            onClick={async () => {
                                setSubmitting(true);
                                try {
                                    await api.post(`/admin/reports/${caseId}/analyze`);
                                    alert("AI Analysis re-queued. Please refresh in a few moments.");
                                    fetchCaseData();
                                } catch (err) {
                                    console.error(err);
                                    alert("Failed to trigger analysis.");
                                } finally {
                                    setSubmitting(false);
                                }
                            }}
                            className="mt-2 text-[10px] bg-primary/20 hover:bg-primary/30 text-primary border border-primary/30 px-2 py-1 rounded transition-colors"
                        >
                            {submitting ? "Queuing..." : "Recalculate Analysis"}
                        </button>
                    )}
                </div>

                {/* Reported On */}
                <div className="p-4 bg-card border border-border rounded-xl">
                    <span className="text-muted-foreground text-xs uppercase tracking-wider">Reported On</span>
                    <div className="text-sm text-white mt-1">{formatToIST(caseData.created_at)}</div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Main Content (Left 2/3) */}
                <div className="lg:col-span-2 space-y-6">

                    {/* Incident Summary */}
                    <div className="bg-card border border-border rounded-xl p-6">
                        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <FileText className="w-5 h-5 text-primary" /> Incident Summary
                        </h2>
                        <div className="prose prose-invert max-w-none text-sm leading-relaxed text-gray-300">
                            {caseData.incident_summary || <span className="italic text-muted-foreground">Analysis pending or summary unavailable.</span>}
                        </div>
                    </div>

                    {/* Credibility Explanation - Simplified based on requirements */}
                    <div className="bg-card border border-border rounded-xl p-6">
                        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <Shield className="w-5 h-5 text-purple-500" /> Credibility Score Explanation
                        </h2>
                        <div className="text-sm text-gray-300 bg-white/5 p-4 rounded-lg border border-white/10">
                            {caseData.app_score_explanation || "No explanation provided."}
                        </div>
                    </div>

                    {/* Communication Channel */}
                    <div className="bg-card border border-border rounded-xl p-6">
                        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <Send className="w-5 h-5 text-primary" /> Communication Channel
                        </h2>

                        <div className="space-y-4 mb-6 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
                            {messages.length === 0 ? (
                                <div className="text-center py-8 text-muted-foreground text-sm italic">
                                    No communication history yet.
                                </div>
                            ) : (
                                messages.map((msg) => (
                                    <div
                                        key={msg.id}
                                        className={clsx(
                                            "flex flex-col max-w-[85%]",
                                            msg.sender_role === 'ngo' ? "ml-auto items-end" : "mr-auto items-start"
                                        )}
                                    >
                                        <div className={clsx(
                                            "px-4 py-2 rounded-2xl text-sm",
                                            msg.sender_role === 'ngo'
                                                ? "bg-primary/20 border border-primary/30 text-white rounded-tr-none"
                                                : "bg-white/5 border border-white/10 text-gray-300 rounded-tl-none"
                                        )}>
                                            {msg.content}
                                            {msg.attachments && msg.attachments.length > 0 && (
                                                <div className="mt-2 space-y-1">
                                                    {msg.attachments.map((att, idx) => {
                                                        const backendRoot = process.env.NEXT_PUBLIC_API_URL?.replace(/\/api\/v1\/?$/, "") || "http://127.0.0.1:8000";
                                                        const fileUrl = att.file_path.startsWith("http") ? att.file_path : `${backendRoot}/${att.file_path}`;
                                                        return (
                                                            <a
                                                                key={idx}
                                                                href={fileUrl}
                                                                target="_blank"
                                                                rel="noopener noreferrer" // ...
                                                                className="flex items-center gap-2 text-xs bg-black/20 p-2 rounded hover:bg-black/40 transition-colors"
                                                            >
                                                                <FileText className="w-3 h-3 text-primary" />
                                                                <span className="truncate max-w-[150px]">{att.file_name}</span>
                                                            </a>
                                                        );
                                                    })}
                                                </div>
                                            )}
                                        </div>
                                        <span className="text-[10px] text-muted-foreground mt-1">
                                            {msg.sender_role === 'ngo' ? "You" : "USER"} • {formatToIST(msg.timestamp, { hour: undefined, minute: undefined, day: '2-digit', month: 'short', year: 'numeric' })}
                                        </span>
                                    </div>
                                ))
                            )}
                        </div>

                        {/* Reply Input */}
                        <div className="space-y-3 pt-4 border-t border-border">
                            <div className="flex gap-2">
                                <textarea
                                    value={messageInput}
                                    onChange={(e) => setMessageInput(e.target.value)}
                                    placeholder="Type a message to the user..."
                                    rows={2}
                                    className="flex-1 bg-background border border-border rounded-lg p-3 text-sm text-white placeholder:text-muted-foreground focus:border-primary focus:ring-1 focus:ring-primary outline-none resize-none"
                                />
                                <div className="flex flex-col gap-2">
                                    <input
                                        type="file"
                                        id="ngo-chat-file"
                                        className="hidden"
                                        onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                                    />
                                    <button
                                        onClick={() => document.getElementById('ngo-chat-file')?.click()}
                                        className={clsx(
                                            "p-3 rounded-lg border border-border hover:bg-white/5 transition-colors",
                                            selectedFile ? "text-primary border-primary/50" : "text-muted-foreground"
                                        )}
                                        title="Attach file"
                                    >
                                        <Paperclip className="w-5 h-5" />
                                    </button>
                                    <button
                                        onClick={handleSendMessage}
                                        disabled={sending || (!messageInput.trim() && !selectedFile)}
                                        className="p-3 bg-primary text-white rounded-lg hover:bg-primary/90 disabled:opacity-50 transition-colors"
                                    >
                                        {sending ? <Clock className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Sidebar (Right 1/3) */}
                <div className="space-y-6">

                    {/* Evidence Files - Clickable */}
                    <div className="bg-card border border-border rounded-xl p-6">
                        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <FileText className="w-5 h-5 text-blue-500" /> Evidence
                        </h2>
                        {caseData.evidence_files && caseData.evidence_files.length > 0 ? (
                            <ul className="space-y-3">
                                {caseData.evidence_files.map((file, idx) => (
                                    <li key={idx}>
                                        {file.error ? (
                                            <div className="flex items-center justify-between p-3 rounded-lg bg-red-500/10 border border-red-500/20 cursor-not-allowed group">
                                                <div className="flex items-center gap-3 overflow-hidden">
                                                    <div className="w-8 h-8 rounded bg-red-500/20 flex items-center justify-center flex-shrink-0">
                                                        <AlertTriangle className="w-4 h-4 text-red-500" />
                                                    </div>
                                                    <div className="min-w-0">
                                                        <div className="text-sm font-medium text-white truncate max-w-[150px]">{file.file_name}</div>
                                                        <div className="text-xs text-red-400">Upload Failed</div>
                                                    </div>
                                                </div>
                                            </div>
                                        ) : (
                                            <a
                                                href={file.full_url || "#"}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                onClick={(e) => {
                                                    if (!file.full_url) {
                                                        e.preventDefault();
                                                        alert(`File not accessible. Path: ${file.file_path || 'Unknown'}`);
                                                    }
                                                }}
                                                className="flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 transition-colors cursor-pointer group"
                                            >
                                                <div className="flex items-center gap-3 overflow-hidden">
                                                    <div className="w-8 h-8 rounded bg-blue-500/20 flex items-center justify-center flex-shrink-0">
                                                        <FileText className="w-4 h-4 text-blue-500" />
                                                    </div>
                                                    <div className="min-w-0">
                                                        <div className="text-sm font-medium text-white truncate max-w-[150px]">{file.file_name}</div>
                                                        <div className="text-xs text-muted-foreground">{(file.size_bytes / 1024).toFixed(1)} KB</div>
                                                    </div>
                                                </div>
                                            </a>
                                        )}
                                    </li>
                                ))}
                            </ul>
                        ) : (
                            <div className="text-sm text-muted-foreground italic">No evidence files provided.</div>
                        )}
                    </div>

                    {/* Publish Update */}
                    <div className="bg-card border border-border rounded-xl p-6">
                        <h2 className="text-lg font-semibold text-white mb-4">Publish Update</h2>
                        <div className="space-y-3">
                            <textarea
                                value={updateText}
                                onChange={(e) => setUpdateText(e.target.value)}
                                placeholder="Status update..."
                                rows={3}
                                className="w-full bg-background border border-border rounded-lg p-3 text-sm text-white placeholder:text-muted-foreground focus:border-primary focus:ring-1 focus:ring-primary outline-none resize-none"
                            />
                            <button
                                onClick={handlePublishUpdate}
                                disabled={submitting || !updateText.trim()}
                                className="w-full flex items-center justify-center gap-2 py-2 bg-primary text-white rounded-lg text-sm font-semibold hover:bg-primary/90 disabled:opacity-50"
                            >
                                {submitting ? <Clock className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                                {submitting ? "Processing..." : "Publish"}
                            </button>
                            {submitSuccess && <div className="text-xs text-green-500 text-center font-medium">Update published successfully!</div>}
                        </div>
                    </div>

                    {/* Recent Updates Feed */}
                    {caseData.updates && caseData.updates.length > 0 ? (
                        <div className="bg-card border border-border rounded-xl p-6">
                            <h2 className="text-lg font-semibold text-white mb-4">Update History</h2>
                            <div className="space-y-4">
                                {caseData.updates.map((update) => (
                                    <div key={update.id} className="relative pl-4 border-l border-white/10 pb-1">
                                        <div className="absolute -left-[5px] top-1 w-2.5 h-2.5 rounded-full bg-primary ring-4 ring-background"></div>
                                        <p className="text-sm text-white">{update.public_update}</p>
                                        <p className="text-xs text-muted-foreground mt-1">{formatToIST(update.created_at, { hour: undefined, minute: undefined })}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ) : (
                        <div className="bg-card border border-border rounded-xl p-6 text-center text-muted-foreground text-sm italic">
                            No updates posted. Case Status: {caseData.status}
                        </div>
                    )}

                </div>
            </div>
        </div>
    );
}
