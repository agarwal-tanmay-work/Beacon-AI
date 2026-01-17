"use client";
// Force Refresh for Timezone Fix

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Shield, Calendar, AlignLeft, RefreshCcw, AlertCircle, ArrowRight, Loader2, Activity } from "lucide-react";
import { SparklesCore } from "@/components/ui/sparkles";
import { FireSphere } from "@/components/ui/fire-sphere";
import { api } from "@/lib/api";
import { cn, formatToIST } from "@/lib/utils";

interface PublicUpdate {
    message: string;
    timestamp: string;
}

interface TrackResult {
    status: string;
    reported_at: string;
    incident_summary: string;
    last_updated: string;
    updates: PublicUpdate[];
    messages: TrackMessage[];
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

export default function TrackPage() {
    React.useEffect(() => {
        // Force resize for Three.js initialization
        window.dispatchEvent(new Event('resize'));
    }, []);

    const [caseId, setCaseId] = useState("");
    const [secretKey, setSecretKey] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<TrackResult | null>(null);

    // Chat State
    const [messageInput, setMessageInput] = useState("");
    const [sending, setSending] = useState(false);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [fileUploading, setFileUploading] = useState(false);

    const handleTrack = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!caseId || !secretKey) return;

        setLoading(true);
        setError(null);
        setResult(null);

        try {
            const res = await api.post("/public/track", {
                case_id: caseId,
                secret_key: secretKey,
            });
            setResult(res.data);
        } catch (err: any) {
            console.error("Tracking Failed", err);
            setError("No case found with the provided credentials. Please ensure both values are correct.");
        } finally {
            setLoading(false);
        }
    };

    const handleSendMessage = async () => {
        if ((!messageInput.trim() && !selectedFile) || !result) return;
        setSending(true);

        try {
            let attachments: MessageAttachment[] = [];

            // 1. Upload File if selected
            if (selectedFile) {
                setFileUploading(true);
                const formData = new FormData();
                formData.append("case_id", caseId);
                formData.append("secret_key", secretKey);
                formData.append("file", selectedFile);

                const uploadRes = await api.post("/public/track/upload", formData, {
                    headers: { "Content-Type": "multipart/form-data" },
                });

                attachments.push({
                    file_name: uploadRes.data.file_name,
                    file_path: uploadRes.data.file_path,
                    mime_type: uploadRes.data.mime_type
                });
                setFileUploading(false);
            }

            // 2. Send Message
            const msgRes = await api.post("/public/track/message", {
                case_id: caseId,
                secret_key: secretKey,
                content: messageInput,
                attachments: attachments
            });

            // 3. Update UI
            setResult(prev => prev ? {
                ...prev,
                messages: [...prev.messages, msgRes.data]
            } : null);

            setMessageInput("");
            setSelectedFile(null);

        } catch (err) {
            console.error("Failed to send message", err);
            // Optionally show error toast
        } finally {
            setSending(false);
            setFileUploading(false);
        }
    };

    return (
        <div className={cn(
            "w-full min-h-screen bg-black text-white relative flex flex-col items-center overflow-x-hidden font-sans selection:bg-blue-500/30",
            !result && "justify-center"
        )}>
            {/* Background Sparkles */}
            <div className="absolute inset-0 z-0">
                <SparklesCore
                    id="track-sparkles"
                    background="transparent"
                    minSize={0.6}
                    maxSize={1.4}
                    particleDensity={60}
                    className="w-full h-full"
                    particleColor="#FFFFFF"
                />
            </div>

            {/* Fire Sphere Effect - Grounded at the bottom */}
            <div className="absolute bottom-[-110px] left-0 w-full h-[400px] z-0 opacity-25 pointer-events-none">
                <FireSphere
                    color1={[201, 158, 72]}
                    color0={[74, 30, 0]}
                    bloomStrength={0.3}
                    bloomRadius={0.8}
                />
            </div>

            <div className="relative z-10 w-full max-w-4xl mx-auto px-6 pt-6 pb-20 flex flex-col items-center gap-8 md:gap-12">
                {/* Header */}
                <div className="text-center space-y-4">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="flex items-center justify-center gap-3 mb-2"
                    >
                        <Activity className="w-8 h-8 text-blue-500" />
                        <h1 className="text-4xl md:text-5xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60 drop-shadow-2xl">
                            Track Status
                        </h1>
                    </motion.div>
                    <motion.div
                        initial={{ opacity: 0, width: 0 }}
                        animate={{ opacity: 1, width: 128 }}
                        className="h-[2px] bg-gradient-to-r from-transparent via-blue-600 to-transparent mx-auto shadow-[0_0_15px_rgba(37,99,235,0.6)]"
                    />
                    <motion.p
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.2 }}
                        className="text-blue-100/60 text-lg font-light tracking-wide max-w-3xl mx-auto"
                    >
                        Enter your secure credentials to check the progress of your submitted report.
                    </motion.p>
                </div>

                {/* Track Form Card */}
                <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="w-full max-w-2xl bg-white/[0.03] border border-white/10 backdrop-blur-2xl rounded-3xl p-6 md:p-10 shadow-2xl relative overflow-hidden group"
                >
                    <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

                    <form onSubmit={handleTrack} className="space-y-8 relative z-10 text-left">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div className="space-y-2">
                                <label className="text-sm font-medium text-white/40 ml-1 uppercase tracking-widest">Case ID</label>
                                <div className="relative">
                                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/20" />
                                    <input
                                        type="text"
                                        value={caseId}
                                        onChange={(e) => setCaseId(e.target.value)}
                                        placeholder="BCNXXXXXXXXXXXX"
                                        className="w-full bg-white/5 border border-white/10 rounded-2xl py-4 pl-12 pr-4 text-white placeholder:text-white/10 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all text-lg font-mono"
                                        required
                                    />
                                </div>
                            </div>

                            <div className="space-y-2">
                                <label className="text-sm font-medium text-white/40 ml-1 uppercase tracking-widest">Secret Access Key</label>
                                <div className="relative">
                                    <Shield className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/20" />
                                    <input
                                        type="password"
                                        value={secretKey}
                                        onChange={(e) => setSecretKey(e.target.value)}
                                        placeholder="XXXX-XXXX"
                                        className="w-full bg-white/5 border border-white/10 rounded-2xl py-4 pl-12 pr-4 text-white placeholder:text-white/10 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all text-lg font-mono"
                                        required
                                    />
                                </div>
                            </div>
                        </div>

                        <AnimatePresence>
                            {error && (
                                <motion.div
                                    initial={{ opacity: 0, height: 0 }}
                                    animate={{ opacity: 1, height: "auto" }}
                                    exit={{ opacity: 0, height: 0 }}
                                    className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm"
                                >
                                    <AlertCircle className="w-5 h-5 shrink-0" />
                                    <p>{error}</p>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        <button
                            type="submit"
                            disabled={loading}
                            className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-bold py-4 rounded-2xl flex items-center justify-center gap-3 transition-all duration-300 shadow-[0_0_20px_rgba(37,99,235,0.3)] hover:shadow-[0_0_30px_rgba(37,99,235,0.5)] active:scale-95 text-lg"
                        >
                            {loading ? (
                                <Loader2 className="w-6 h-6 animate-spin" />
                            ) : (
                                <>
                                    Track Status
                                    <ArrowRight className="w-5 h-5" />
                                </>
                            )}
                        </button>
                    </form>
                </motion.div>

                {/* Results Area */}
                <AnimatePresence>
                    {result && (
                        <motion.div
                            initial={{ opacity: 0, y: 40 }}
                            animate={{ opacity: 1, y: 0 }}
                            style={{ willChange: 'transform' }}
                            className="w-full max-w-5xl space-y-24 mt-8 pb-32"
                        >
                            {/* Detailed Results Section */}
                            <div className="grid grid-cols-1 md:grid-cols-1 gap-20 text-left">
                                {/* 1. Submission & Status Info */}
                                <div className="space-y-8">
                                    <div className="space-y-4">
                                        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                                            <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-white">
                                                Report Submitted
                                            </h2>

                                            {/* Status Badge */}
                                            <div className={cn(
                                                "px-6 py-2 rounded-full border flex items-center gap-3 w-fit",
                                                (() => {
                                                    const s = (result.status || "Received").toUpperCase();
                                                    if (["NEW", "RECEIVED", "PENDING", "ANALYZING"].includes(s)) return "bg-yellow-500/10 border-yellow-500/20 text-yellow-500";
                                                    if (["ONGOING", "IN_REVIEW", "VERIFIED", "ESCALATED"].includes(s)) return "bg-blue-500/10 border-blue-500/20 text-blue-400";
                                                    if (["CLOSED", "COMPLETED", "RESOLVED"].includes(s)) return "bg-green-500/10 border-green-500/20 text-green-400";
                                                    if (["DISMISSED", "REJECTED"].includes(s)) return "bg-red-500/10 border-red-500/20 text-red-400";
                                                    return "bg-white/5 border-white/10 text-white/60"; // Default
                                                })()
                                            )}>
                                                <div className={cn(
                                                    "w-2.5 h-2.5 rounded-full animate-pulse",
                                                    (() => {
                                                        const s = (result.status || "Received").toUpperCase();
                                                        if (["NEW", "RECEIVED", "PENDING", "ANALYZING"].includes(s)) return "bg-yellow-500";
                                                        if (["ONGOING", "IN_REVIEW", "VERIFIED", "ESCALATED"].includes(s)) return "bg-blue-400";
                                                        if (["CLOSED", "COMPLETED", "RESOLVED"].includes(s)) return "bg-green-400";
                                                        if (["DISMISSED", "REJECTED"].includes(s)) return "bg-red-400";
                                                        return "bg-white/40";
                                                    })()
                                                )} />
                                                <span className="text-sm font-bold tracking-widest uppercase">
                                                    {result.status || "Received"}
                                                </span>
                                            </div>
                                        </div>

                                        <div className="flex flex-col md:flex-row gap-12 md:gap-24">
                                            <div className="space-y-2">
                                                <p className="text-white/30 text-xs font-bold uppercase tracking-widest flex items-center gap-2">
                                                    <Calendar className="w-3 h-3" />
                                                    Submitted On
                                                </p>
                                                <p className="text-white/90 text-2xl font-light tracking-wide">
                                                    {formatToIST(result.reported_at)}
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {/* 2. Incident Summary (Only show if available) */}
                                {result.incident_summary && (
                                    <div className="space-y-6">
                                        <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-white mb-6">
                                            Incident Summary
                                        </h2>
                                        <div className="w-full">
                                            <p className="text-white/60 leading-relaxed font-light text-xl md:text-2xl max-w-4xl">
                                                {result.incident_summary}
                                            </p>
                                        </div>
                                    </div>
                                )}

                                {/* 3. NGO Updates Timeline (Only show if updates exist) */}
                                {result.updates.length > 0 && (
                                    <div className="space-y-12">
                                        <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-white mb-6">
                                            Case Updates
                                        </h2>
                                        <div className="space-y-16">
                                            {result.updates.map((update, idx) => (
                                                <motion.div
                                                    key={idx}
                                                    initial={{ opacity: 0, x: -20 }}
                                                    whileInView={{ opacity: 1, x: 0 }}
                                                    viewport={{ once: true }}
                                                    transition={{ delay: 0.1 * idx }}
                                                    className="relative space-y-4"
                                                >
                                                    <div className="flex items-center gap-4 mb-2">
                                                        <div className="h-[1px] w-8 bg-blue-500/50" />
                                                        <p className="text-white/30 text-xs font-mono uppercase tracking-widest">
                                                            Update {idx + 1} • {formatToIST(update.timestamp, { hour: undefined, minute: undefined })}
                                                        </p>
                                                    </div>
                                                    <p className="text-white/80 leading-relaxed font-light text-xl md:text-2xl max-w-4xl border-l-2 border-blue-500/20 pl-8">
                                                        {update.message}
                                                    </p>
                                                </motion.div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* 4. Secure Communication Channel */}
                                <div className="space-y-12">
                                    <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-white mb-6 flex items-center gap-4">
                                        Communication Channel
                                        <span className="text-xs font-mono font-normal text-white/40 tracking-widest uppercase border border-white/10 px-3 py-1 rounded-full">Secure</span>
                                    </h2>

                                    <div className="w-full bg-white/[0.02] border border-white/10 rounded-3xl overflow-hidden backdrop-blur-sm">
                                        {/* Message List */}
                                        <div className="p-8 space-y-8 max-h-[600px] overflow-y-auto custom-scrollbar">
                                            {result.messages.length === 0 ? (
                                                <p className="text-center text-white/20 italic py-12">No messages yet. Start a secure conversation below.</p>
                                            ) : (
                                                result.messages.map((msg) => (
                                                    <div key={msg.id} className={cn(
                                                        "flex flex-col max-w-[80%]",
                                                        msg.sender_role === 'user' ? "ml-auto items-end" : "mr-auto items-start"
                                                    )}>
                                                        <div className={cn(
                                                            "p-6 rounded-2xl text-lg font-light leading-relaxed",
                                                            msg.sender_role === 'user'
                                                                ? "bg-blue-600/10 border border-blue-500/20 text-blue-50 rounded-tr-sm"
                                                                : "bg-white/5 border border-white/10 text-white/90 rounded-tl-sm"
                                                        )}>
                                                            {msg.content && <p>{msg.content}</p>}
                                                            {msg.attachments.length > 0 && (
                                                                <div className="mt-4 space-y-2">
                                                                    {msg.attachments.map((att, i) => {
                                                                        const backendRoot = process.env.NEXT_PUBLIC_API_URL?.replace(/\/api\/v1\/?$/, "") || "http://127.0.0.1:8000";
                                                                        const fileUrl = att.file_path.startsWith("http") ? att.file_path : `${backendRoot}/${att.file_path}`;
                                                                        return (
                                                                            <a
                                                                                key={i}
                                                                                href={fileUrl}
                                                                                target="_blank"
                                                                                rel="noopener noreferrer" // ...
                                                                                className="flex items-center gap-3 bg-black/20 p-3 rounded-lg border border-white/5 hover:bg-black/40 transition-colors group/file"
                                                                            >
                                                                                <div className="w-8 h-8 flex items-center justify-center bg-white/10 rounded-md group-hover/file:bg-blue-500/20 transition-colors">
                                                                                    <Search className="w-4 h-4 text-white/40 group-hover/file:text-blue-400" />
                                                                                </div>
                                                                                <span className="text-sm font-mono opacity-70 truncate max-w-[200px] group-hover/file:opacity-100">{att.file_name}</span>
                                                                            </a>
                                                                        );
                                                                    })}
                                                                </div>
                                                            )}
                                                        </div>
                                                        <span className="text-xs text-white/20 mt-2 font-mono uppercase tracking-widest px-1">
                                                            {msg.sender_role === 'user' ? 'You' : 'NGO'} • {formatToIST(msg.timestamp, { hour: undefined, minute: undefined })}
                                                        </span>
                                                    </div>
                                                ))
                                            )}
                                        </div>

                                        {/* Input Area */}
                                        <div className="p-6 border-t border-white/10 bg-white/[0.02]">
                                            <div className="space-y-4">
                                                {selectedFile && (
                                                    <div className="flex items-center justify-between bg-blue-500/10 border border-blue-500/20 p-3 rounded-xl">
                                                        <span className="text-sm text-blue-200 flex items-center gap-2">
                                                            <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
                                                            {selectedFile.name}
                                                        </span>
                                                        <button
                                                            onClick={() => setSelectedFile(null)}
                                                            className="text-white/40 hover:text-white p-1"
                                                        >
                                                            &times;
                                                        </button>
                                                    </div>
                                                )}
                                                <div className="flex gap-4">
                                                    <label className="flex-shrink-0">
                                                        <input
                                                            type="file"
                                                            className="hidden"
                                                            onChange={(e) => e.target.files && setSelectedFile(e.target.files[0])}
                                                        />
                                                        <div className="w-14 h-14 flex items-center justify-center rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 cursor-pointer transition-colors">
                                                            <div className="w-6 h-6 border-2 border-white/30 rounded-full flex items-center justify-center">
                                                                <span className="text-lg text-white/30 leading-none pb-1">+</span>
                                                            </div>
                                                        </div>
                                                    </label>
                                                    <textarea
                                                        value={messageInput}
                                                        onChange={(e) => setMessageInput(e.target.value)}
                                                        placeholder="Type a secure message..."
                                                        className="flex-1 bg-white/5 border border-white/10 rounded-xl p-4 text-white placeholder:text-white/20 focus:outline-none focus:ring-1 focus:ring-blue-500/50 resize-none h-14 min-h-[56px] "
                                                        style={{ scrollbarWidth: 'none' }}
                                                    />
                                                    <button
                                                        onClick={handleSendMessage}
                                                        disabled={sending || (!messageInput.trim() && !selectedFile)}
                                                        className="w-14 h-14 flex items-center justify-center rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:bg-white/5 transition-all text-white shadow-lg"
                                                    >
                                                        {sending ? (
                                                            <Loader2 className="w-6 h-6 animate-spin" />
                                                        ) : (
                                                            <ArrowRight className="w-6 h-6" />
                                                        )}
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Info Text */}
                <motion.p
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 0.4 }}
                    className="text-center text-sm text-white max-w-md leading-relaxed font-light"
                >
                    Beacon AI ensures that status tracking is as secure as the reporting itself. Your credentials are never stored in your browser session.
                </motion.p>
            </div>
        </div>
    );
}
