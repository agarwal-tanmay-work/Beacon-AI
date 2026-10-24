"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Activity, AlertCircle, ArrowRight, Calendar, Eye, EyeOff, FileText, Loader2, Lock, Paperclip, RefreshCw, Search, Shield, X } from "lucide-react";

import { SparklesCore } from "@/components/ui/sparkles";
import { SafeMarkdown } from "@/components/ui/safe-markdown";
import { FireSphere } from "@/components/ui/fire-sphere";
import { api, resolveApiUrl, toApiProblem, type ApiProblem } from "@/lib/api";
import { ACCEPT, formatSize, validateFile } from "@/lib/files";
import { cn, formatToIST } from "@/lib/utils";

interface MessageAttachment {
    file_name: string;
    file_path: string;
    mime_type: string;
}

interface TrackMessage {
    id: string;
    sender_role: "user" | "admin";
    content?: string | null;
    attachments: MessageAttachment[];
    timestamp: string;
}

interface TrackResult {
    status: string;
    reported_at: string;
    incident_summary?: string | null;
    last_updated: string;
    updates: { message: string; timestamp: string }[];
    messages: TrackMessage[];
}

const REFRESH_MS = 30_000;

function statusTone(status: string): { badge: string; dot: string } {
    const s = (status || "Received").toUpperCase();
    if (["NEW", "RECEIVED", "PENDING", "ANALYZING"].includes(s)) return { badge: "bg-yellow-500/10 border-yellow-500/20 text-yellow-500", dot: "bg-yellow-500" };
    if (["ONGOING", "IN_REVIEW", "VERIFIED", "ESCALATED"].includes(s)) return { badge: "bg-blue-500/10 border-blue-500/20 text-blue-400", dot: "bg-blue-400" };
    if (["CLOSED", "COMPLETED", "RESOLVED"].includes(s)) return { badge: "bg-green-500/10 border-green-500/20 text-green-400", dot: "bg-green-400" };
    if (["DISMISSED", "REJECTED"].includes(s)) return { badge: "bg-red-500/10 border-red-500/20 text-red-400", dot: "bg-red-400" };
    return { badge: "bg-white/5 border-white/10 text-white/60", dot: "bg-white/40" };
}

export default function TrackPage() {
    const [caseId, setCaseId] = useState("");
    const [secretKey, setSecretKey] = useState("");
    const [showKey, setShowKey] = useState(false);
    const [loading, setLoading] = useState(false);
    const [problem, setProblem] = useState<ApiProblem | null>(null);
    const [result, setResult] = useState<TrackResult | null>(null);
    const [refreshing, setRefreshing] = useState(false);

    const [messageInput, setMessageInput] = useState("");
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [sending, setSending] = useState(false);
    const [sendProblem, setSendProblem] = useState<string | null>(null);

    // The credentials stay in memory only (never in storage, cookies or the URL) and are re-sent with every request.
    const credentials = useRef<{ caseId: string; secretKey: string } | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        // Three.js sizes its canvas from window resize events.
        window.dispatchEvent(new Event("resize"));
    }, []);

    const fetchCase = useCallback(async (): Promise<TrackResult> => {
        const creds = credentials.current;
        if (!creds) throw new Error("no credentials");
        const { data } = await api.post<TrackResult>("/public/track", { case_id: creds.caseId, secret_key: creds.secretKey });
        return data;
    }, []);

    const handleTrack = async (e: React.FormEvent) => {
        e.preventDefault();
        const id = caseId.trim().toUpperCase();
        const key = secretKey.trim();
        if (!id || !key || loading) return;

        setLoading(true);
        setProblem(null);
        setResult(null);
        credentials.current = { caseId: id, secretKey: key };
        try {
            setResult(await fetchCase());
        } catch (error) {
            credentials.current = null;
            setProblem(toApiProblem(error));
        } finally {
            setLoading(false);
        }
    };

    const refresh = useCallback(async () => {
        if (!credentials.current) return;
        setRefreshing(true);
        try {
            setResult(await fetchCase());
        } catch {
            /* a background refresh failing is not worth interrupting the reader for */
        } finally {
            setRefreshing(false);
        }
    }, [fetchCase]);

    // New investigator messages show up without the reporter having to look them up again.
    const signedIn = result !== null;
    useEffect(() => {
        if (!signedIn) return;
        const timer = window.setInterval(() => {
            if (document.visibilityState === "visible") void refresh();
        }, REFRESH_MS);
        return () => window.clearInterval(timer);
    }, [signedIn, refresh]);

    const messageCount = result?.messages.length ?? 0;
    useEffect(() => {
        if (messageCount > 0) messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }, [messageCount]);

    const signOut = () => {
        credentials.current = null;
        setResult(null);
        setCaseId("");
        setSecretKey("");
        setMessageInput("");
        setSelectedFile(null);
        setProblem(null);
    };

    const pickFile = (file: File | undefined) => {
        if (!file) return;
        const reason = validateFile(file, 0);
        setSendProblem(reason);
        setSelectedFile(reason ? null : file);
    };

    const handleSendMessage = async () => {
        const creds = credentials.current;
        if (!creds || sending || (!messageInput.trim() && !selectedFile)) return;
        setSending(true);
        setSendProblem(null);
        try {
            const attachments: MessageAttachment[] = [];
            if (selectedFile) {
                const form = new FormData();
                form.append("case_id", creds.caseId);
                form.append("secret_key", creds.secretKey);
                form.append("file", selectedFile);
                const upload = await api.post<{ file_name: string; file_path: string; mime_type: string }>("/public/track/upload", form, {
                    headers: { "Content-Type": "multipart/form-data" },
                });
                attachments.push({ file_name: upload.data.file_name, file_path: upload.data.file_path, mime_type: upload.data.mime_type });
            }
            const { data } = await api.post<TrackMessage>("/public/track/message", {
                case_id: creds.caseId,
                secret_key: creds.secretKey,
                content: messageInput.trim() || null,
                attachments,
            });
            setResult((prev) => (prev ? { ...prev, messages: [...prev.messages, data] } : prev));
            setMessageInput("");
            setSelectedFile(null);
        } catch (error) {
            setSendProblem(toApiProblem(error).message);
        } finally {
            setSending(false);
        }
    };

    const tone = statusTone(result?.status ?? "");

    return (
        <div className={cn("w-full min-h-screen bg-black text-white relative flex flex-col items-center overflow-x-hidden font-sans selection:bg-blue-500/30", !result && "justify-center")}>
            <div className="absolute inset-0 z-0">
                <SparklesCore id="track-sparkles" background="transparent" minSize={0.6} maxSize={1.4} particleDensity={60} className="w-full h-full" particleColor="#FFFFFF" />
            </div>
            <div className="absolute bottom-[-110px] left-0 w-full h-[400px] z-0 opacity-25 pointer-events-none">
                <FireSphere color1={[201, 158, 72]} color0={[74, 30, 0]} bloomStrength={0.3} bloomRadius={0.8} />
            </div>

            <div className="relative z-10 w-full max-w-4xl mx-auto px-6 pt-20 md:pt-6 pb-20 flex flex-col items-center gap-8 md:gap-12">
                {/* Header */}
                <div className="text-center space-y-4">
                    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-center gap-3 mb-2">
                        <Activity className="w-8 h-8 text-blue-500" />
                        <h1 className="text-4xl md:text-5xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60 drop-shadow-2xl">Track Status</h1>
                    </motion.div>
                    <motion.div initial={{ opacity: 0, width: 0 }} animate={{ opacity: 1, width: 128 }} className="h-[2px] bg-gradient-to-r from-transparent via-blue-600 to-transparent mx-auto shadow-[0_0_15px_rgba(37,99,235,0.6)]" />
                    <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }} className="text-blue-100/60 text-lg font-light tracking-wide max-w-3xl mx-auto">
                        Enter your secure credentials to check the progress of your submitted report.
                    </motion.p>
                </div>

                {/* Form */}
                {!result && (
                    <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="w-full max-w-2xl bg-white/[0.03] border border-white/10 backdrop-blur-2xl rounded-3xl p-6 md:p-10 shadow-2xl relative overflow-hidden group">
                        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                        <form onSubmit={handleTrack} className="space-y-8 relative z-10 text-left" autoComplete="off">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div className="space-y-2">
                                    <label htmlFor="case-id" className="text-sm font-medium text-white/40 ml-1 uppercase tracking-widest">Case ID</label>
                                    <div className="relative">
                                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/20" />
                                        <input
                                            id="case-id"
                                            type="text"
                                            value={caseId}
                                            onChange={(e) => setCaseId(e.target.value)}
                                            placeholder="BCNXXXXXXXXXXXX"
                                            autoCapitalize="characters"
                                            spellCheck={false}
                                            className="w-full bg-white/5 border border-white/10 rounded-2xl py-4 pl-12 pr-4 text-white placeholder:text-white/10 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all text-lg font-mono"
                                            required
                                        />
                                    </div>
                                </div>
                                <div className="space-y-2">
                                    <label htmlFor="secret-key" className="text-sm font-medium text-white/40 ml-1 uppercase tracking-widest">Secret Access Key</label>
                                    <div className="relative">
                                        <Shield className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/20" />
                                        <input
                                            id="secret-key"
                                            type={showKey ? "text" : "password"}
                                            value={secretKey}
                                            onChange={(e) => setSecretKey(e.target.value)}
                                            placeholder="XXXX-XXXX-XXXX-XXXX"
                                            autoCapitalize="characters"
                                            spellCheck={false}
                                            className="w-full bg-white/5 border border-white/10 rounded-2xl py-4 pl-12 pr-12 text-white placeholder:text-white/10 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all text-lg font-mono"
                                            required
                                        />
                                        <button
                                            type="button"
                                            aria-label={showKey ? "Hide secret key" : "Show secret key"}
                                            onClick={() => setShowKey((v) => !v)}
                                            className="absolute right-4 top-1/2 -translate-y-1/2 text-white/30 hover:text-white"
                                        >
                                            {showKey ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                                        </button>
                                    </div>
                                </div>
                            </div>

                            <AnimatePresence>
                                {problem && (
                                    <motion.div
                                        role="alert"
                                        initial={{ opacity: 0, height: 0 }}
                                        animate={{ opacity: 1, height: "auto" }}
                                        exit={{ opacity: 0, height: 0 }}
                                        className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm"
                                    >
                                        <AlertCircle className="w-5 h-5 shrink-0" />
                                        <p>{problem.message}</p>
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
                )}

                {/* Results */}
                <AnimatePresence>
                    {result && (
                        <motion.div initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-5xl space-y-24 mt-8 pb-32">
                            <div className="grid grid-cols-1 gap-20 text-left">
                                <div className="space-y-8">
                                    <div className="space-y-4">
                                        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                                            <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-white">Report Submitted</h2>
                                            <div className="flex items-center gap-3">
                                                <div className={cn("px-6 py-2 rounded-full border flex items-center gap-3 w-fit", tone.badge)}>
                                                    <div className={cn("w-2.5 h-2.5 rounded-full animate-pulse", tone.dot)} />
                                                    <span className="text-sm font-bold tracking-widest uppercase">{result.status || "Received"}</span>
                                                </div>
                                                <button
                                                    type="button"
                                                    onClick={() => void refresh()}
                                                    aria-label="Refresh"
                                                    title="Refresh"
                                                    className="rounded-full border border-white/10 p-2.5 text-white/50 transition-colors hover:bg-white/5 hover:text-white"
                                                >
                                                    <RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} />
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={signOut}
                                                    className="inline-flex items-center gap-1.5 rounded-full border border-white/10 px-4 py-2.5 text-xs text-white/50 transition-colors hover:bg-white/5 hover:text-white"
                                                >
                                                    <Lock className="h-3.5 w-3.5" /> Lock
                                                </button>
                                            </div>
                                        </div>

                                        <div className="flex flex-col md:flex-row gap-12 md:gap-24">
                                            <div className="space-y-2">
                                                <p className="text-white/30 text-xs font-bold uppercase tracking-widest flex items-center gap-2">
                                                    <Calendar className="w-3 h-3" /> Submitted On
                                                </p>
                                                <p className="text-white/90 text-2xl font-light tracking-wide">{formatToIST(result.reported_at)}</p>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {result.incident_summary && (
                                    <div className="space-y-6">
                                        <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-white mb-6">Incident Summary</h2>
                                        <div className="text-white/60 leading-relaxed font-light text-xl md:text-2xl max-w-4xl prose prose-invert prose-blue">
                                            <SafeMarkdown>{result.incident_summary}</SafeMarkdown>
                                        </div>
                                    </div>
                                )}

                                {result.updates.length > 0 && (
                                    <div className="space-y-12">
                                        <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-white mb-6">Case Updates</h2>
                                        <div className="space-y-16">
                                            {result.updates.map((update, idx) => (
                                                <motion.div
                                                    key={`${update.timestamp}-${idx}`}
                                                    initial={{ opacity: 0, x: -20 }}
                                                    whileInView={{ opacity: 1, x: 0 }}
                                                    viewport={{ once: true }}
                                                    transition={{ delay: 0.1 * Math.min(idx, 5) }}
                                                    className="relative space-y-4"
                                                >
                                                    <div className="flex items-center gap-4 mb-2">
                                                        <div className="h-[1px] w-8 bg-blue-500/50" />
                                                        <p className="text-white/30 text-xs font-mono uppercase tracking-widest">
                                                            Update {idx + 1} • {formatToIST(update.timestamp, { hour: undefined, minute: undefined })}
                                                        </p>
                                                    </div>
                                                    <div className="text-white/80 leading-relaxed font-light text-xl md:text-2xl max-w-4xl border-l-2 border-blue-500/20 pl-8 prose prose-invert prose-blue">
                                                        <SafeMarkdown>{update.message}</SafeMarkdown>
                                                    </div>
                                                </motion.div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Secure communication channel */}
                                <div className="space-y-12">
                                    <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-white mb-6 flex items-center gap-4">
                                        Communication Channel
                                        <span className="text-xs font-mono font-normal text-white/40 tracking-widest uppercase border border-white/10 px-3 py-1 rounded-full">Secure</span>
                                    </h2>

                                    <div className="w-full bg-white/[0.02] border border-white/10 rounded-3xl overflow-hidden backdrop-blur-sm">
                                        <div className="p-8 space-y-8 max-h-[600px] overflow-y-auto custom-scrollbar" aria-live="polite">
                                            {result.messages.length === 0 ? (
                                                <p className="text-center text-white/20 italic py-12">No messages yet. Start a secure conversation below.</p>
                                            ) : (
                                                result.messages.map((msg) => (
                                                    <div key={msg.id} className={cn("flex flex-col max-w-[80%]", msg.sender_role === "user" ? "ml-auto items-end" : "mr-auto items-start")}>
                                                        <div
                                                            className={cn(
                                                                "p-6 rounded-2xl text-lg font-light leading-relaxed prose prose-invert prose-blue max-w-none",
                                                                msg.sender_role === "user" ? "bg-blue-600/10 border border-blue-500/20 text-blue-50 rounded-tr-sm" : "bg-white/5 border border-white/10 text-white/90 rounded-tl-sm",
                                                            )}
                                                        >
                                                            {msg.content && <SafeMarkdown>{msg.content}</SafeMarkdown>}
                                                            {msg.attachments.length > 0 && (
                                                                <div className="mt-4 space-y-2 not-prose">
                                                                    {msg.attachments.map((att, i) => (
                                                                        <a
                                                                            key={i}
                                                                            href={resolveApiUrl(att.file_path)}
                                                                            target="_blank"
                                                                            rel="noopener noreferrer"
                                                                            className="flex items-center gap-3 bg-black/20 p-3 rounded-lg border border-white/5 hover:bg-black/40 transition-colors group/file"
                                                                        >
                                                                            <div className="w-8 h-8 flex items-center justify-center bg-white/10 rounded-md group-hover/file:bg-blue-500/20 transition-colors">
                                                                                <FileText className="w-4 h-4 text-white/40 group-hover/file:text-blue-400" />
                                                                            </div>
                                                                            <span className="text-sm font-mono opacity-70 truncate max-w-[200px] group-hover/file:opacity-100">{att.file_name}</span>
                                                                        </a>
                                                                    ))}
                                                                </div>
                                                            )}
                                                        </div>
                                                        <span className="text-xs text-white/20 mt-2 font-mono uppercase tracking-widest px-1">
                                                            {msg.sender_role === "user" ? "You" : "Investigator"} • {formatToIST(msg.timestamp)}
                                                        </span>
                                                    </div>
                                                ))
                                            )}
                                            <div ref={messagesEndRef} />
                                        </div>

                                        <div className="p-6 border-t border-white/10 bg-white/[0.02]">
                                            <div className="space-y-4">
                                                {selectedFile && (
                                                    <div className="flex items-center justify-between bg-blue-500/10 border border-blue-500/20 p-3 rounded-xl">
                                                        <span className="text-sm text-blue-200 flex items-center gap-2 min-w-0">
                                                            <Paperclip className="w-4 h-4 shrink-0" />
                                                            <span className="truncate">{selectedFile.name}</span>
                                                            <span className="text-blue-200/50 shrink-0">{formatSize(selectedFile.size)}</span>
                                                        </span>
                                                        <button type="button" aria-label="Remove attachment" onClick={() => setSelectedFile(null)} className="text-white/40 hover:text-white p-1">
                                                            <X className="w-4 h-4" />
                                                        </button>
                                                    </div>
                                                )}
                                                {sendProblem && (
                                                    <p role="alert" className="flex items-center gap-2 text-sm text-red-300">
                                                        <AlertCircle className="h-4 w-4 shrink-0" /> {sendProblem}
                                                    </p>
                                                )}
                                                <div className="flex gap-4">
                                                    <label className="flex-shrink-0 cursor-pointer" aria-label="Attach a file">
                                                        <input
                                                            type="file"
                                                            className="hidden"
                                                            accept={ACCEPT}
                                                            onChange={(e) => {
                                                                pickFile(e.target.files?.[0]);
                                                                e.target.value = "";
                                                            }}
                                                        />
                                                        <div className="w-14 h-14 flex items-center justify-center rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 transition-colors">
                                                            <Paperclip className="w-5 h-5 text-white/40" />
                                                        </div>
                                                    </label>
                                                    <textarea
                                                        value={messageInput}
                                                        maxLength={4000}
                                                        onChange={(e) => setMessageInput(e.target.value)}
                                                        aria-label="Message to the investigators"
                                                        placeholder="Type a secure message..."
                                                        className="flex-1 bg-white/5 border border-white/10 rounded-xl p-4 text-white placeholder:text-white/20 focus:outline-none focus:ring-1 focus:ring-blue-500/50 resize-none h-14 min-h-[56px]"
                                                        style={{ scrollbarWidth: "none" }}
                                                    />
                                                    <button
                                                        type="button"
                                                        onClick={() => void handleSendMessage()}
                                                        disabled={sending || (!messageInput.trim() && !selectedFile)}
                                                        aria-label="Send message"
                                                        className="w-14 h-14 flex items-center justify-center rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:bg-white/5 transition-all text-white shadow-lg"
                                                    >
                                                        {sending ? <Loader2 className="w-6 h-6 animate-spin" /> : <ArrowRight className="w-6 h-6" />}
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

                <motion.p initial={{ opacity: 0 }} animate={{ opacity: 0.4 }} className="text-center text-sm text-white max-w-md leading-relaxed font-light">
                    Your Case ID and Secret Key are never stored in your browser. They are kept in memory only while this page is open.
                </motion.p>
            </div>
        </div>
    );
}
