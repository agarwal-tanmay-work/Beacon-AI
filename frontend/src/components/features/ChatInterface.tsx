"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ShieldCheck, Lock, Upload, User, Bot, AlertTriangle, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Message } from "@/types";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChatInput } from "@/components/ui/chat-input";
import { Button } from "@/components/ui/button";
import { Paperclip, Mic, CornerDownLeft } from "lucide-react";

// PII Redaction Helper
function sanitizeContent(content: string) {
    const emailRegex = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g;
    const phoneRegex = /\b(\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b/g;

    return content
        .replace(emailRegex, "[EMAIL REDACTED]")
        .replace(phoneRegex, "[PHONE REDACTED]");
}

export function ChatInterface() {
    const [messages, setMessages] = useState<Message[]>([
        {
            id: "initial-greeting",
            sender: "SYSTEM",
            content: "Hello. I am Beacon AI, your compassionate and anonymous assistant. I'm here to help you report corruption safely. Please know that your identity is fully protected, and I will guide you through this process one step at a time. How can I assist you today?",
            timestamp: new Date().toISOString()
        }
    ]);
    const [inputValue, setInputValue] = useState("");
    const [loading, setLoading] = useState(false);
    const [reportId, setReportId] = useState<string | null>(null);
    const [accessToken, setAccessToken] = useState<string | null>(null);
    const [currentStep, setCurrentStep] = useState<string>("GREETING");
    const bottomRef = useRef<HTMLDivElement>(null);

    const [totalUploadSize, setTotalUploadSize] = useState(0);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const [secretKey, setSecretKey] = useState<string | null>(null);
    const [finalCaseId, setFinalCaseId] = useState<string | null>(null);

    const isLocked = currentStep === "SUBMITTED";

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, loading]);

    const handleFileUploadRequest = () => {
        if (isLocked) return;
        fileInputRef.current?.click();
    };

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files || !e.target.files[0]) return;
        const file = e.target.files[0];
        const MAX_SIZE = 5 * 1024 * 1024; // 5MB

        if (totalUploadSize + file.size > MAX_SIZE) {
            setMessages(prev => [...prev, {
                id: crypto.randomUUID(),
                sender: "SYSTEM",
                content: `⚠️ Upload Rejected: Total file size limit (5MB) exceeded.`,
                timestamp: new Date().toISOString()
            }]);
            return;
        }

        let currentReportId = reportId;
        let currentAccessToken = accessToken;

        if (!currentReportId || !currentAccessToken) {
            try {
                const seed = Math.random().toString(36).substring(7);
                const initRes = await api.post("/public/reports/create", { client_seed: seed });
                currentReportId = initRes.data.report_id;
                currentAccessToken = initRes.data.access_token;
                setReportId(currentReportId);
                setAccessToken(currentAccessToken);
            } catch (err) {
                console.error("Session init failed", err);
                return;
            }
        }

        if (!currentReportId || !currentAccessToken) return;

        const formData = new FormData();
        formData.append("report_id", currentReportId);
        formData.append("access_token", currentAccessToken);
        formData.append("file", file);

        try {
            setLoading(true);
            await api.post("/public/evidence/upload", formData, {
                headers: { "Content-Type": "multipart/form-data" }
            });
            setTotalUploadSize(prev => prev + file.size);
            setMessages(prev => [...prev, {
                id: crypto.randomUUID(),
                sender: "SYSTEM",
                content: `✅ Evidence Uploaded: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`,
                timestamp: new Date().toISOString()
            }]);
        } catch (err) {
            console.error("Upload failed", err);
        } finally {
            setLoading(false);
            if (fileInputRef.current) fileInputRef.current.value = "";
        }
    };

    const handleSendMessage = async (e?: React.FormEvent) => {
        e?.preventDefault();
        if (isLocked || !inputValue.trim()) return;

        const content = inputValue.trim();
        setInputValue("");

        const userMsg: Message = {
            id: crypto.randomUUID(),
            sender: "USER",
            content: content,
            timestamp: new Date().toISOString(),
        };

        setMessages((prev) => [...prev, userMsg]);
        setLoading(true);

        try {
            let currentReportId = reportId;
            let currentAccessToken = accessToken;

            if (!currentReportId || !currentAccessToken) {
                const seed = Math.random().toString(36).substring(7);
                const initRes = await api.post("/public/reports/create", { client_seed: seed });
                currentReportId = initRes.data.report_id;
                currentAccessToken = initRes.data.access_token;
                setReportId(currentReportId);
                setAccessToken(currentAccessToken);
            }

            const res = await api.post("/public/reports/message", {
                report_id: currentReportId,
                access_token: currentAccessToken,
                content: userMsg.content,
            });

            const sysMsg: Message = {
                id: crypto.randomUUID(),
                sender: res.data.sender,
                content: res.data.content,
                timestamp: res.data.timestamp,
                next_step: res.data.next_step
            };

            setMessages((prev) => [...prev, sysMsg]);

            if (res.data.next_step === "SUBMITTED") {
                setCurrentStep("SUBMITTED");
                if (res.data.case_id) setFinalCaseId(res.data.case_id);
                if (res.data.secret_key) setSecretKey(res.data.secret_key);
            } else if (res.data.next_step) {
                setCurrentStep(res.data.next_step);
            }

        } catch (err) {
            console.error("Send Failed", err);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="w-full max-w-5xl flex flex-col h-[85vh] relative overflow-hidden bg-white/[0.01] rounded-[2.5rem] border border-white/5 backdrop-blur-3xl shadow-[0_0_100px_rgba(0,0,0,0.5)]">
            {/* SCANNING LINE EFFECT */}
            <div className="absolute inset-0 pointer-events-none z-10 overflow-hidden rounded-[2.5rem]">
                <motion.div
                    animate={{ y: ["0%", "100%", "0%"] }}
                    transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
                    className="w-full h-[2px] bg-gradient-to-r from-transparent via-emerald-500/20 to-transparent opacity-30 shadow-[0_0_15px_rgba(16,185,129,0.2)]"
                />
            </div>

            {/* INVISIBLE FILE INPUT */}
            <input type="file" ref={fileInputRef} className="hidden" onChange={handleFileUpload} accept="image/*,application/pdf,video/*" />

            {/* SUCCESS OVERLAY */}
            <AnimatePresence>
                {isLocked && secretKey && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="absolute inset-0 z-[60] flex items-center justify-center p-6 bg-black/90 backdrop-blur-2xl"
                    >
                        <motion.div
                            initial={{ scale: 0.9, y: 20 }}
                            animate={{ scale: 1, y: 0 }}
                            className="w-full max-w-lg bg-black/40 backdrop-blur-3xl border border-emerald-500/30 rounded-[3rem] p-10 shadow-[0_0_100px_rgba(16,185,129,0.15)] relative overflow-hidden"
                        >
                            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-emerald-500 to-transparent" />

                            <div className="text-center mb-10">
                                <div className="w-24 h-24 bg-emerald-500/10 rounded-full flex items-center justify-center mx-auto mb-6 border border-emerald-500/20 shadow-[0_0_50px_rgba(16,185,129,0.2)]">
                                    <CheckCircle2 className="w-12 h-12 text-emerald-400" />
                                </div>
                                <h2 className="text-4xl font-bold text-white mb-2 tracking-tight">Transmission Secured</h2>
                                <p className="text-white/40 text-xs font-mono uppercase tracking-[0.3em] font-medium">Uplink Status: TERMINATED</p>
                            </div>

                            <div className="space-y-8">
                                <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-3xl p-8 group cursor-pointer active:scale-[0.98] transition-all hover:bg-emerald-500/10"
                                    onClick={() => {
                                        navigator.clipboard.writeText(`Case ID: ${finalCaseId}\nSecret Key: ${secretKey}`);
                                    }}>
                                    <div className="flex justify-between items-center mb-4">
                                        <p className="text-[10px] text-emerald-400 font-mono uppercase tracking-[0.3em] font-bold">Secret Access Key</p>
                                        <div className="flex items-center gap-1">
                                            <span className="text-[9px] text-emerald-500/60 font-mono">ENCRYPTED</span>
                                            <Lock className="w-3 h-3 text-emerald-500/50" />
                                        </div>
                                    </div>
                                    <div className="font-mono text-4xl text-white font-bold tracking-[0.3em] break-words text-center py-4 drop-shadow-[0_0_10px_rgba(255,255,255,0.3)]">
                                        {secretKey}
                                    </div>
                                    <div className="w-full h-px bg-emerald-500/10 my-4" />
                                    <p className="text-center text-[10px] text-emerald-500/40 font-mono uppercase tracking-widest group-hover:text-emerald-500 transition-colors">Click to copy vital records</p>
                                </div>

                                <div className="flex bg-orange-500/5 border border-orange-500/20 p-6 rounded-3xl items-start gap-5">
                                    <div className="p-2 bg-orange-500/10 rounded-xl">
                                        <AlertTriangle className="w-6 h-6 text-orange-400 shrink-0" />
                                    </div>
                                    <div className="space-y-1">
                                        <p className="text-[13px] text-orange-200/80 leading-relaxed font-semibold">One-Time Revelation</p>
                                        <p className="text-xs text-orange-200/40 leading-relaxed">
                                            This key is never shown again. Without it, your report remains inaccessible. Secure it immediately.
                                        </p>
                                    </div>
                                </div>
                            </div>

                            <div className="mt-10 text-center text-[10px] text-white/10 font-mono tracking-[0.3em] uppercase">
                                Log purging initiated • Security Level 4
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* MESSAGES AREA */}
            <div className="flex-1 overflow-y-auto px-6 py-10 space-y-8 scrollbar-hide">
                <AnimatePresence initial={false}>
                    {messages.map((msg, i) => (
                        <motion.div
                            key={msg.id}
                            initial={{ opacity: 0, y: 20, scale: 0.98 }}
                            animate={{ opacity: 1, y: 0, scale: 1 }}
                            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                            className={cn(
                                "flex w-full group",
                                msg.sender === "USER" ? "justify-end" : "justify-start"
                            )}
                        >
                            <div className={cn(
                                "flex items-end gap-4 max-w-[85%] md:max-w-[70%]",
                                msg.sender === "USER" ? "flex-row-reverse" : "flex-row"
                            )}>
                                {/* Avatar */}
                                <div className={cn(
                                    "w-10 h-10 rounded-full flex items-center justify-center border shrink-0 transition-all duration-500",
                                    msg.sender === "USER"
                                        ? "bg-indigo-500/10 border-indigo-500/20 text-indigo-400 group-hover:border-indigo-500/40"
                                        : "bg-emerald-500/10 border-emerald-500/20 text-emerald-400 group-hover:border-emerald-500/40"
                                )}>
                                    {msg.sender === "USER" ? <User size={18} /> : <ShieldCheck size={18} />}
                                </div>

                                {/* Bubble */}
                                <div className={cn(
                                    "relative p-6 rounded-[2rem] border transition-all duration-500",
                                    msg.sender === "USER"
                                        ? "bg-indigo-500/5 border-indigo-500/20 text-white rounded-br-none hover:bg-indigo-500/10 group-hover:border-indigo-500/30"
                                        : "bg-white/5 border-white/10 text-white/90 rounded-bl-none hover:bg-white/[0.08] group-hover:border-white/20"
                                )}>
                                    {/* Glass inner glow */}
                                    <div className="absolute inset-x-4 top-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent opacity-50" />

                                    <div className="markdown-content text-[15px] leading-relaxed tracking-tight font-medium">
                                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                            {sanitizeContent(msg.content)}
                                        </ReactMarkdown>
                                    </div>

                                    <div className={cn(
                                        "mt-3 text-[10px] font-mono tracking-widest uppercase opacity-20 group-hover:opacity-40 transition-opacity flex items-center gap-2",
                                        msg.sender === "USER" ? "justify-end" : "justify-start"
                                    )}>
                                        {msg.sender !== "USER" && <span className="w-1 h-1 rounded-full bg-emerald-500" />}
                                        {new Date(msg.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })}
                                        {msg.sender === "USER" && <span className="w-1 h-1 rounded-full bg-indigo-500" />}
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    ))}

                    {loading && (
                        <motion.div
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            className="flex justify-start"
                        >
                            <div className="bg-white/5 border border-white/10 px-6 py-4 rounded-[1.5rem] rounded-bl-none flex items-center gap-2">
                                <motion.div animate={{ scale: [1, 1.2, 1] }} transition={{ repeat: Infinity, duration: 1 }} className="w-2 h-2 bg-emerald-500/50 rounded-full" />
                                <motion.div animate={{ scale: [1, 1.2, 1] }} transition={{ repeat: Infinity, duration: 1, delay: 0.2 }} className="w-2 h-2 bg-blue-500/50 rounded-full" />
                                <motion.div animate={{ scale: [1, 1.2, 1] }} transition={{ repeat: Infinity, duration: 1, delay: 0.4 }} className="w-2 h-2 bg-purple-500/50 rounded-full" />
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
                <div ref={bottomRef} className="h-4" />
            </div>

            {/* INPUT AREA */}
            <div className="p-6 bg-gradient-to-t from-black via-black/80 to-transparent backdrop-blur-sm z-20">
                <form
                    className="relative rounded-[2rem] border border-white/10 bg-white/5 focus-within:border-emerald-500/40 focus-within:ring-1 focus-within:ring-emerald-500/20 transition-all duration-300 p-2 overflow-hidden shadow-2xl"
                    onSubmit={handleSendMessage}
                >
                    <ChatInput
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === "Enter" && !e.shiftKey) {
                                e.preventDefault();
                                handleSendMessage();
                            }
                        }}
                        placeholder={isLocked ? "Session Terminated" : "Type your message securely..."}
                        disabled={isLocked || loading}
                        className="min-h-12 resize-none rounded-2xl bg-transparent border-0 p-4 shadow-none focus-visible:ring-0 text-white placeholder:text-white/20"
                    />
                    <div className="flex items-center p-2 pt-0 gap-2">
                        <Button
                            variant="ghost"
                            size="icon"
                            type="button"
                            onClick={handleFileUploadRequest}
                            disabled={isLocked || loading}
                            className="rounded-xl text-white/40 hover:text-white hover:bg-white/5 transition-colors"
                        >
                            <Paperclip className="size-5" />
                            <span className="sr-only">Attach file</span>
                        </Button>

                        <Button
                            variant="ghost"
                            size="icon"
                            type="button"
                            className="rounded-xl text-white/40 hover:text-white hover:bg-white/5 transition-colors"
                        >
                            <Mic className="size-5" />
                            <span className="sr-only">Use Microphone</span>
                        </Button>

                        <div className="ml-auto flex items-center gap-3">
                            <div className="hidden md:flex items-center gap-2 text-[10px] text-white/20 font-mono tracking-widest mr-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                                ENCRYPTED TUNNEL
                            </div>
                            <Button
                                type="submit"
                                size="sm"
                                disabled={isLocked || loading || !inputValue.trim()}
                                className="gap-1.5 bg-emerald-500 text-black hover:bg-emerald-400 rounded-xl px-5 font-bold shadow-[0_0_20px_rgba(16,185,129,0.2)] transition-all active:scale-95"
                            >
                                Send
                                <CornerDownLeft className="size-4" />
                            </Button>
                        </div>
                    </div>
                </form>
            </div>
        </div>
    );
}
