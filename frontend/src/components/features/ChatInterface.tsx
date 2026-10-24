"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, FileText, Info, Loader2, Music, Paperclip, RefreshCw, Send, X } from "lucide-react";

import { CredentialsCard } from "@/components/features/CredentialsCard";
import { SafeMarkdown } from "@/components/ui/safe-markdown";
import { api, toApiProblem, type ApiProblem } from "@/lib/api";
import { ACCEPT, attachmentKind, formatSize, newId, validateFile } from "@/lib/files";
import { clearSession, loadSession, saveSession } from "@/lib/reportSession";
import { cn } from "@/lib/utils";
import type { AttachmentMeta, Message, MessageResponse } from "@/types";

const MAX_CHARS = 4000;

const GREETING: Message = {
    id: "initial-greeting",
    sender: "SYSTEM",
    content:
        "Hello. I am Beacon AI, your compassionate and anonymous assistant. I'm here to help you report corruption safely. Please know that your identity is fully protected, and I will guide you through this process one step at a time.\n\nHow can I assist you today?",
    timestamp: "",
};

interface PendingFile {
    id: string;
    file: File;
    previewUrl?: string;
    /** Set once the upload succeeded, so retrying a failed message does not upload the same file again. */
    uploaded: boolean;
}

interface Outgoing {
    text: string;
    files: PendingFile[];
}

function formatTime(iso: string): string {
    const date = new Date(iso);
    return Number.isNaN(date.getTime()) ? "" : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: true });
}

export function ChatInterface() {
    // The page loads this component with ssr:false, so reading sessionStorage during the first render is safe.
    const [initial] = useState(() => loadSession());

    const [messages, setMessages] = useState<Message[]>(() => (initial && initial.messages.length > 0 ? initial.messages : [GREETING]));
    const [input, setInput] = useState("");
    const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([]);
    const [fileNotice, setFileNotice] = useState<string | null>(null);
    const [sending, setSending] = useState(false);
    const [slow, setSlow] = useState(false);
    const [problem, setProblem] = useState<ApiProblem | null>(null);

    const [mode, setMode] = useState<"ai" | "basic">(initial?.mode ?? "ai");
    const [completed, setCompleted] = useState(initial?.completed ?? false);
    const [caseId, setCaseId] = useState<string | null>(initial?.caseId ?? null);
    const [secretKey, setSecretKey] = useState<string | null>(null);
    const [acknowledged, setAcknowledged] = useState(initial?.acknowledged ?? false);
    const [finalMessageId, setFinalMessageId] = useState<string | null>(null);

    const sessionRef = useRef<{ reportId: string; accessToken: string } | null>(
        initial ? { reportId: initial.reportId, accessToken: initial.accessToken } : null,
    );
    const outgoingRef = useRef(new Map<string, Outgoing>());
    const previewUrlsRef = useRef<string[]>([]);
    const bottomRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const sessionExpired = problem?.code === "invalid_session";
    const locked = completed || sessionExpired;

    // ---- persistence (never writes the Secret Key) -------------------------------------------------------------
    useEffect(() => {
        const session = sessionRef.current;
        if (!session || sessionExpired) return;
        saveSession({
            ...session,
            messages: secretKey ? messages.map((m) => ({ ...m, content: m.content.replaceAll(secretKey, "[hidden]") })) : messages,
            completed,
            acknowledged,
            caseId,
            mode,
        });
    }, [messages, completed, acknowledged, caseId, mode, secretKey, sessionExpired]);

    // A reporter who refreshed after submitting but before confirming gets their credentials back from the server.
    useEffect(() => {
        const session = sessionRef.current;
        if (!initial?.completed || initial.acknowledged || !session) return;
        let cancelled = false;
        (async () => {
            try {
                const { data } = await api.post<{ case_id: string; secret_key: string }>("/public/reports/credentials", {
                    report_id: session.reportId,
                    access_token: session.accessToken,
                });
                if (!cancelled) {
                    setCaseId(data.case_id);
                    setSecretKey(data.secret_key);
                }
            } catch {
                if (!cancelled) setAcknowledged(true); // no longer available (confirmed elsewhere or expired)
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [initial]);

    // ---- layout niceties ---------------------------------------------------------------------------------------
    useEffect(() => {
        const area = textareaRef.current;
        if (area) {
            area.style.height = "inherit";
            area.style.height = `${area.scrollHeight}px`;
        }
    }, [input]);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }, [messages, sending, pendingFiles.length, completed]);

    useEffect(() => {
        const urls = previewUrlsRef.current;
        return () => urls.forEach((url) => URL.revokeObjectURL(url));
    }, []);

    // ---- files -------------------------------------------------------------------------------------------------
    const addFiles = (list: FileList | null) => {
        if (!list || list.length === 0) return;
        const accepted: PendingFile[] = [];
        let notice: string | null = null;
        for (const file of Array.from(list)) {
            const reason = validateFile(file, pendingFiles.length + accepted.length);
            if (reason) {
                notice = reason;
                continue;
            }
            const previewUrl = file.type.startsWith("image/") ? URL.createObjectURL(file) : undefined;
            if (previewUrl) previewUrlsRef.current.push(previewUrl);
            accepted.push({ id: newId(), file, previewUrl, uploaded: false });
        }
        setFileNotice(notice);
        if (accepted.length > 0) setPendingFiles((prev) => [...prev, ...accepted]);
    };

    const removeFile = (id: string) => {
        setPendingFiles((prev) => prev.filter((f) => f.id !== id));
        setFileNotice(null);
    };

    // ---- delivery ----------------------------------------------------------------------------------------------
    const deliver = useCallback(async (messageId: string) => {
        const outgoing = outgoingRef.current.get(messageId);
        if (!outgoing) return;

        setSending(true);
        setProblem(null);
        setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, status: "sending" } : m)));
        const slowTimer = window.setTimeout(() => setSlow(true), 8000); // Render free plan cold start

        try {
            if (!sessionRef.current) {
                const { data } = await api.post<{ report_id: string; access_token: string }>("/public/reports/create", {});
                sessionRef.current = { reportId: data.report_id, accessToken: data.access_token };
            }
            const session = sessionRef.current;

            for (const pending of outgoing.files) {
                if (pending.uploaded) continue;
                const form = new FormData();
                form.append("report_id", session.reportId);
                form.append("access_token", session.accessToken);
                form.append("file", pending.file);
                await api.post("/public/evidence/upload", form, { headers: { "Content-Type": "multipart/form-data" } });
                pending.uploaded = true;
            }

            const fileNames = outgoing.files.map((f) => f.file.name).join(", ");
            const content = outgoing.text || `[User uploaded ${outgoing.files.length} file(s): ${fileNames}]`;
            const { data } = await api.post<MessageResponse>("/public/reports/message", {
                report_id: session.reportId,
                access_token: session.accessToken,
                content,
            });

            const reply: Message = { id: newId(), sender: data.sender, content: data.content, timestamp: data.timestamp };
            setMessages((prev) => [...prev.map((m) => (m.id === messageId ? { ...m, status: undefined } : m)), reply]);
            outgoingRef.current.delete(messageId);
            setMode(data.mode);

            if (data.next_step === "COMPLETED") {
                setCompleted(true);
                setCaseId(data.case_id);
                setSecretKey(data.secret_key);
                setAcknowledged(!data.secret_key);
                setFinalMessageId(reply.id);
            }
        } catch (error) {
            const found = toApiProblem(error);
            setProblem(found);
            setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, status: "failed" } : m)));
        } finally {
            window.clearTimeout(slowTimer);
            setSlow(false);
            setSending(false);
        }
    }, []);

    const send = () => {
        const text = input.trim();
        if (sending || locked || (!text && pendingFiles.length === 0)) return;

        const id = newId();
        const attachments: AttachmentMeta[] = pendingFiles.map((p) => ({
            type: attachmentKind(p.file),
            name: p.file.name,
            size: p.file.size,
            previewUrl: p.previewUrl,
        }));
        outgoingRef.current.set(id, { text, files: pendingFiles });
        setMessages((prev) => [
            ...prev,
            { id, sender: "USER", content: text, timestamp: new Date().toISOString(), attachments: attachments.length ? attachments : undefined, status: "sending" },
        ]);
        setInput("");
        setPendingFiles([]);
        setFileNotice(null);
        void deliver(id);
    };

    const retry = (id: string) => {
        if (!sending) void deliver(id);
    };

    const editFailed = (id: string) => {
        const outgoing = outgoingRef.current.get(id);
        if (!outgoing || sending) return;
        setInput(outgoing.text);
        setPendingFiles(outgoing.files);
        outgoingRef.current.delete(id);
        setMessages((prev) => prev.filter((m) => m.id !== id));
        setProblem(null);
        textareaRef.current?.focus();
    };

    // ---- completion --------------------------------------------------------------------------------------------
    const acknowledge = async () => {
        const session = sessionRef.current;
        if (session) {
            try {
                await api.post("/public/reports/credentials/ack", { report_id: session.reportId, access_token: session.accessToken });
            } catch {
                /* the server-side copy expires by itself after 24 hours */
            }
        }
        setMessages((prev) =>
            prev.map((m) =>
                m.id === finalMessageId
                    ? { ...m, content: `Your report was submitted as Case ID ${caseId}. Your Secret Key was shown once. Keep it safe to follow your case.` }
                    : m,
            ),
        );
        setSecretKey(null);
        setAcknowledged(true);
    };

    const startOver = () => {
        clearSession();
        sessionRef.current = null;
        outgoingRef.current.clear();
        setMessages([GREETING]);
        setInput("");
        setPendingFiles([]);
        setProblem(null);
        setCompleted(false);
        setCaseId(null);
        setSecretKey(null);
        setAcknowledged(false);
        setFinalMessageId(null);
        setMode("ai");
    };

    const canSend = !sending && !locked && (input.trim().length > 0 || pendingFiles.length > 0);

    return (
        <div className="w-full max-w-6xl mx-auto flex flex-col h-full md:h-full pt-4 md:pt-0 pb-4 md:pb-0">
            <div className="w-full bg-black/40 backdrop-blur-3xl border border-white/10 rounded-t-[2rem] rounded-b-xl overflow-hidden flex flex-col h-full md:min-h-[500px] shadow-2xl relative">
                {/* Header */}
                <div className="flex items-center gap-3 px-4 md:px-6 py-4 border-b border-white/5 bg-white/5 backdrop-blur-md">
                    <span className="text-white font-semibold text-lg tracking-wide">Beacon AI</span>
                </div>

                {mode === "basic" && !completed && (
                    <div role="status" className="flex items-start gap-2 border-b border-amber-400/20 bg-amber-400/10 px-4 py-2.5 text-xs text-amber-100/90 md:px-6">
                        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                        Our AI assistant is temporarily unavailable, so I&apos;ll ask a few standard questions instead. Your report is still being recorded.
                    </div>
                )}

                {/* Messages */}
                <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-8 scrollbar-hide relative" aria-live="polite" aria-label="Conversation">
                    <AnimatePresence initial={false}>
                        {messages.map((msg) => (
                            <motion.div
                                key={msg.id}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                className={cn("flex w-full", msg.sender === "USER" ? "justify-end" : "justify-start")}
                            >
                                <div className={cn("flex flex-col gap-1.5 max-w-[85%]", msg.sender === "USER" ? "items-end" : "items-start")}>
                                    <div
                                        className={cn(
                                            "relative p-5 rounded-[1.25rem] text-[15px] leading-relaxed flex flex-col gap-3 transition-opacity",
                                            msg.sender === "USER"
                                                ? "bg-blue-600/90 text-white rounded-tr-none shadow-[0_4px_20px_rgba(37,99,235,0.2)]"
                                                : "bg-white/5 border border-white/10 text-gray-200 rounded-tl-none backdrop-blur-md shadow-lg",
                                            msg.status === "sending" && "opacity-60",
                                            msg.status === "failed" && "bg-red-600/30 border border-red-400/40",
                                        )}
                                    >
                                        {msg.attachments && msg.attachments.length > 0 && (
                                            <div className="flex flex-wrap gap-2 mb-1">
                                                {msg.attachments.map((att, idx) =>
                                                    att.type === "image" && att.previewUrl ? (
                                                        <div key={idx} className="relative rounded-lg overflow-hidden border border-white/10 max-w-[200px]">
                                                            {/* eslint-disable-next-line @next/next/no-img-element -- local blob preview */}
                                                            <img src={att.previewUrl} alt={att.name} className="w-full h-auto object-cover max-h-[200px]" />
                                                        </div>
                                                    ) : (
                                                        <div key={idx} className="flex items-center gap-3 bg-white/10 p-3 rounded-lg border border-white/10 min-w-[150px]">
                                                            <div className="p-2 bg-white/10 rounded-lg">
                                                                {att.type === "audio" ? <Music className="w-6 h-6 text-white" /> : <FileText className="w-6 h-6 text-white" />}
                                                            </div>
                                                            <div className="flex-1 min-w-0">
                                                                <p className="text-sm font-medium text-white truncate max-w-[120px]">{att.name}</p>
                                                                <p className="text-xs text-white/50">{formatSize(att.size)}</p>
                                                            </div>
                                                        </div>
                                                    ),
                                                )}
                                            </div>
                                        )}

                                        {msg.content.trim() !== "" &&
                                            (msg.sender === "USER" ? (
                                                <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                                            ) : (
                                                <div className="markdown-content whitespace-pre-wrap">
                                                    <SafeMarkdown>{msg.content}</SafeMarkdown>
                                                </div>
                                            ))}

                                        {msg.timestamp && (
                                            <div className={cn("mt-1 flex items-center gap-1.5 text-[10px] opacity-50 font-mono", msg.sender === "USER" ? "text-blue-200" : "text-gray-400")}>
                                                <div className="w-1 h-1 rounded-full bg-current" />
                                                <time suppressHydrationWarning dateTime={msg.timestamp}>
                                                    {formatTime(msg.timestamp)}
                                                </time>
                                            </div>
                                        )}
                                    </div>

                                    {msg.status === "failed" && (
                                        <div className="flex items-center gap-3 text-xs text-red-300" role="group" aria-label="This message was not sent">
                                            <span className="inline-flex items-center gap-1">
                                                <AlertTriangle className="h-3 w-3" /> Not sent
                                            </span>
                                            <button type="button" onClick={() => retry(msg.id)} disabled={sending} className="inline-flex items-center gap-1 underline underline-offset-2 hover:text-white disabled:opacity-50">
                                                <RefreshCw className="h-3 w-3" /> Retry
                                            </button>
                                            <button type="button" onClick={() => editFailed(msg.id)} disabled={sending} className="underline underline-offset-2 hover:text-white disabled:opacity-50">
                                                Edit
                                            </button>
                                        </div>
                                    )}
                                </div>
                            </motion.div>
                        ))}
                    </AnimatePresence>

                    {sending && (
                        <div className="flex flex-col gap-2" role="status" aria-label="Beacon AI is typing">
                            <div className="flex gap-4">
                                <div className="bg-white/5 border border-white/10 px-4 py-3 rounded-[1.25rem] rounded-tl-none ml-0">
                                    <div className="flex gap-1">
                                        {[0, 150, 300].map((delay) => (
                                            <span key={delay} className="w-1.5 h-1.5 bg-white/40 rounded-full animate-bounce" style={{ animationDelay: `${delay}ms` }} />
                                        ))}
                                    </div>
                                </div>
                            </div>
                            {slow && <p className="text-xs text-white/40 ml-1 animate-pulse">The server is starting up. This can take up to a minute the first time...</p>}
                        </div>
                    )}
                    <div ref={bottomRef} className="h-1" />
                </div>

                {/* Footer: errors, credentials or composer */}
                <div className="p-3 md:p-4 bg-white/[0.02] border-t border-white/5 relative shrink-0 space-y-3">
                    {problem && (
                        <div role="alert" className="flex items-start gap-2 rounded-xl border border-red-400/30 bg-red-500/10 px-3 py-2.5 text-sm text-red-200">
                            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                            <p className="flex-1">{problem.message}</p>
                            {sessionExpired ? (
                                <button type="button" onClick={startOver} className="shrink-0 rounded-full bg-white/10 px-3 py-1 text-xs text-white hover:bg-white/20">
                                    Start a new report
                                </button>
                            ) : (
                                <button type="button" aria-label="Dismiss" onClick={() => setProblem(null)} className="shrink-0 text-red-200/70 hover:text-white">
                                    <X className="h-4 w-4" />
                                </button>
                            )}
                        </div>
                    )}

                    {completed && caseId ? (
                        <CredentialsCard caseId={caseId} secretKey={acknowledged ? null : secretKey} onAcknowledge={acknowledge} onNewReport={startOver} />
                    ) : (
                        !sessionExpired && (
                            <>
                                <AnimatePresence>
                                    {pendingFiles.length > 0 && (
                                        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 10 }} className="flex gap-2 overflow-x-auto pb-1 pt-2 scrollbar-hide">
                                            {pendingFiles.map((pending) => (
                                                <div key={pending.id} className="relative group shrink-0">
                                                    <div
                                                        className={cn(
                                                            "w-16 h-16 rounded-xl border border-white/10 overflow-hidden flex items-center justify-center shadow-lg",
                                                            pending.previewUrl ? "bg-black" : "bg-white/5",
                                                        )}
                                                        title={`${pending.file.name} (${formatSize(pending.file.size)})`}
                                                    >
                                                        {pending.previewUrl ? (
                                                            // eslint-disable-next-line @next/next/no-img-element -- local blob preview
                                                            <img src={pending.previewUrl} alt={pending.file.name} className="w-full h-full object-cover" />
                                                        ) : attachmentKind(pending.file) === "audio" ? (
                                                            <Music className="w-6 h-6 text-white/50" />
                                                        ) : (
                                                            <FileText className="w-6 h-6 text-white/50" />
                                                        )}
                                                    </div>
                                                    <button
                                                        type="button"
                                                        aria-label={`Remove ${pending.file.name}`}
                                                        onClick={() => removeFile(pending.id)}
                                                        className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center text-white shadow-md hover:bg-red-600 transition-colors z-20"
                                                    >
                                                        <X className="w-3 h-3" />
                                                    </button>
                                                </div>
                                            ))}
                                        </motion.div>
                                    )}
                                </AnimatePresence>
                                {fileNotice && (
                                    <p role="alert" className="px-2 text-xs text-amber-300">
                                        {fileNotice}
                                    </p>
                                )}

                                <form
                                    onSubmit={(e) => {
                                        e.preventDefault();
                                        send();
                                    }}
                                    className="w-full flex items-center gap-3 bg-white/5 border border-white/10 rounded-full pl-4 pr-1.5 py-1.5 focus-within:bg-white/[0.07] focus-within:border-white/20 transition-all duration-300 shadow-inner"
                                >
                                    <input
                                        type="file"
                                        ref={fileInputRef}
                                        className="hidden"
                                        multiple
                                        accept={ACCEPT}
                                        onChange={(e) => {
                                            addFiles(e.target.files);
                                            e.target.value = "";
                                        }}
                                    />
                                    <button
                                        type="button"
                                        aria-label="Attach files"
                                        onClick={() => fileInputRef.current?.click()}
                                        disabled={sending}
                                        className={cn("transition-colors p-1", pendingFiles.length > 0 ? "text-blue-400" : "text-white/30 hover:text-white")}
                                    >
                                        <Paperclip className="w-5 h-5" />
                                    </button>

                                    <textarea
                                        ref={textareaRef}
                                        value={input}
                                        maxLength={MAX_CHARS}
                                        onChange={(e) => setInput(e.target.value)}
                                        onKeyDown={(e) => {
                                            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                                                e.preventDefault();
                                                send();
                                            }
                                        }}
                                        aria-label="Your message"
                                        placeholder="Describe the incident..."
                                        className="flex-1 bg-transparent border-none text-white placeholder-white/20 focus:outline-none focus:ring-0 text-[16px] md:text-sm px-2 font-light resize-none py-2 max-h-32 min-h-[44px] md:min-h-0 scrollbar-hide"
                                        disabled={sending}
                                        rows={1}
                                    />

                                    {input.length > MAX_CHARS - 500 && <span className="hidden text-[10px] text-white/40 sm:block">{MAX_CHARS - input.length}</span>}

                                    <button
                                        type="submit"
                                        disabled={!canSend}
                                        className="bg-[#1A5CFF] hover:bg-blue-600 text-white px-5 py-2.5 rounded-full flex items-center gap-2 text-sm font-medium transition-all duration-300 shadow-[0_0_15px_rgba(37,99,235,0.3)] hover:shadow-[0_0_25px_rgba(37,99,235,0.5)] disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4 ml-0.5" />}
                                        Send
                                    </button>
                                </form>
                            </>
                        )
                    )}
                </div>
            </div>
        </div>
    );
}
