"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Upload, ShieldCheck, Lock } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Message } from "@/types";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function ChatInterface() {
    const [messages, setMessages] = useState<Message[]>([
        {
            id: "initial-greeting",
            sender: "SYSTEM",
            content: "Hello. I am Beacon AI, your compassionate and anonymous assistant. I'm here to help you report corruption safely. Please know that your identity is fully protected, and I will guide you through this process one step at a time. How can I assist you today?",
            timestamp: new Date().toISOString()
        }
    ]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [reportId, setReportId] = useState<string | null>(null);
    const [accessToken, setAccessToken] = useState<string | null>(null);
    const [currentStep, setCurrentStep] = useState<string>("GREETING");
    const bottomRef = useRef<HTMLDivElement>(null);

    // No auto-init on mount to prevent premature errors

    const [totalUploadSize, setTotalUploadSize] = useState(0);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Derived state for locking
    const isLocked = currentStep === "SUBMITTED";

    // Auto-scroll
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files || !e.target.files[0]) return;
        const file = e.target.files[0];
        const MAX_SIZE = 5 * 1024 * 1024; // 5MB

        // Client-side validation
        if (totalUploadSize + file.size > MAX_SIZE) {
            setMessages(prev => [...prev, {
                id: crypto.randomUUID(),
                sender: "SYSTEM",
                content: `⚠️ Upload Rejected: Total file size limit (5MB) exceeded. Please upload a smaller file.`,
                timestamp: new Date().toISOString()
            }]);
            return;
        }

        let currentReportId = reportId;
        let currentAccessToken = accessToken;

        // Auto-initialize session if needed
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
                setMessages(prev => [...prev, {
                    id: crypto.randomUUID(),
                    sender: "SYSTEM",
                    content: `❌ Connection Error: Could not establish secure session.`,
                    timestamp: new Date().toISOString()
                }]);
                return;
            }
        }

        if (!currentReportId || !currentAccessToken) {
            console.error("Missing credentials after init attempt");
            return;
        }

        const formData = new FormData();
        formData.append("report_id", currentReportId);
        formData.append("access_token", currentAccessToken);

        formData.append("file", file);

        try {
            setLoading(true);
            const res = await api.post("/public/evidence/upload", formData, {
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
            setMessages(prev => [...prev, {
                id: crypto.randomUUID(),
                sender: "SYSTEM",
                content: `❌ Upload Failed: ${(err as any).response?.data?.detail || "Server Error"}`,
                timestamp: new Date().toISOString()
            }]);
        } finally {
            setLoading(false);
            if (fileInputRef.current) fileInputRef.current.value = ""; // Reset input
        }
    };

    const sendMessage = async () => {
        if (!input.trim() || isLocked) return;

        const userMsg: Message = {
            id: crypto.randomUUID(),
            sender: "USER",
            content: input.trim(),
            timestamp: new Date().toISOString(),
        };

        setMessages((prev) => [...prev, userMsg]);
        setInput("");
        setLoading(true);

        try {
            let currentReportId = reportId;
            let currentAccessToken = accessToken;

            // Initialize session if it doesn't exist (first message)
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
            if (res.data.next_step) setCurrentStep(res.data.next_step);

        } catch (err: unknown) {
            console.error("Send Failed", err);
            const errorMessage = err instanceof Error ? err.message : "Server Unreachable";
            setMessages((prev) => [...prev, {
                id: crypto.randomUUID(),
                sender: "SYSTEM",
                content: `Connection Error: ${errorMessage}. Please check your connection and try again.`,
                timestamp: new Date().toISOString()
            }]);
        } finally {
            setLoading(false);
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    return (
        <div className="w-full max-w-4xl h-[85vh] flex flex-col glass-panel rounded-3xl overflow-hidden relative shadow-2xl border border-white/5">
            {/* Header */}
            <div className="px-6 py-4 border-b border-white/5 flex items-center justify-between bg-black/40 backdrop-blur-md">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-emerald-500/10 rounded-xl border border-emerald-500/20">
                        <ShieldCheck className="text-emerald-400 w-5 h-5" />
                    </div>
                    <div>
                        <h2 className="text-white font-semibold tracking-wide text-sm">SECURE CONNECTION</h2>
                        <div className="flex items-center gap-1.5">
                            <span className={`w-1.5 h-1.5 rounded-full ${isLocked ? "bg-red-500" : "bg-emerald-500 animate-pulse"}`} />
                            <span className={`text-[10px] font-mono tracking-wider ${isLocked ? "text-red-500/80" : "text-emerald-500/80"}`}>
                                {isLocked ? "SESSION LOCKED" : "ENCRYPTED"}
                            </span>
                        </div>
                    </div>
                </div>
                <div className="hidden sm:block">
                    <div className="px-3 py-1 bg-white/5 rounded-lg border border-white/5 text-[10px] text-white/40 font-mono">
                        {reportId ? `SESSION: ${reportId.slice(0, 8)}...` : "ESTABLISHING UPLINK..."}
                    </div>
                </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-hide bg-gradient-to-b from-transparent to-black/20">
                <AnimatePresence mode="sync">
                    {messages.map((msg) => (
                        <motion.div
                            key={msg.id}
                            initial={{ opacity: 0, y: 10, scale: 0.98 }}
                            animate={{ opacity: 1, y: 0, scale: 1 }}
                            transition={{ duration: 0.3 }}
                            className={cn(
                                "flex w-full",
                                msg.sender === "USER" ? "justify-end" : "justify-start"
                            )}
                        >
                            <div
                                className={cn(
                                    "max-w-[85%] sm:max-w-[70%] p-5 rounded-3xl text-sm leading-relaxed backdrop-blur-sm shadow-sm",
                                    msg.sender === "USER"
                                        ? "bg-blue-600/10 border border-blue-500/20 text-blue-50 rounded-tr-sm"
                                        : "bg-white/5 border border-white/10 text-gray-200 rounded-tl-sm"
                                )}
                            >
                                <div className="markdown-content">
                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                        {msg.content}
                                    </ReactMarkdown>
                                </div>
                                <div className="mt-2 text-[10px] opacity-30 flex justify-end gap-1 items-center">
                                    {msg.sender === "SYSTEM" && <ShieldCheck className="w-3 h-3" />}
                                    {new Date(msg.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })}
                                </div>
                            </div>
                        </motion.div>
                    ))}
                    {loading && (
                        <motion.div
                            key="loading-indicator"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="flex justify-start"
                        >
                            <div className="bg-white/5 border border-white/10 px-4 py-3 rounded-2xl rounded-tl-none flex items-center gap-2">
                                <div className="w-1.5 h-1.5 bg-blue-400/50 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                                <div className="w-1.5 h-1.5 bg-purple-400/50 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                                <div className="w-1.5 h-1.5 bg-emerald-400/50 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
                <div ref={bottomRef} />
            </div>

            {/* Input Area */}
            <div className="p-5 bg-black/40 border-t border-white/5 backdrop-blur-xl">
                <div className="relative flex items-end gap-3">
                    {/* Evidence Upload Trigger */}
                    <input
                        type="file"
                        ref={fileInputRef}
                        className="hidden"
                        onChange={handleFileUpload}
                        accept="image/*,application/pdf,video/*"
                    />

                    <AnimatePresence>
                        {/* Always show upload option unless locked */}
                        {!isLocked && (
                            <motion.button
                                initial={{ width: 0, opacity: 0 }}
                                animate={{ width: "auto", opacity: 1 }}
                                exit={{ width: 0, opacity: 0 }}
                                onClick={() => fileInputRef.current?.click()}
                                disabled={isLocked || loading}
                                className="p-3.5 mb-1 glass-button rounded-2xl text-purple-400 hover:text-purple-300 hover:bg-purple-500/10 hover:border-purple-500/20 disabled:opacity-50"
                                title="Upload Evidence (Max 5MB)"
                            >
                                <Upload className="w-5 h-5" />
                            </motion.button>
                        )}
                    </AnimatePresence>

                    <textarea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyPress}
                        disabled={isLocked}
                        placeholder={isLocked ? "Case Report Submitted. Session Locked." : "Type your message securely... (Shift+Enter for new line)"}
                        className="flex-1 bg-white/5 hover:bg-white/10 focus:bg-white/10 border border-white/5 focus:border-white/10 rounded-2xl p-4 pr-14 text-white placeholder:text-white/20 transition-all outline-none resize-none min-h-[56px] max-h-[150px] scrollbar-hide"
                        rows={1}
                        style={{ height: "auto" }} // Simplistic auto-grow can be improved if needed
                    />

                    <button
                        onClick={sendMessage}
                        disabled={loading || !input.trim() || isLocked}
                        className="absolute right-2 bottom-2 p-2.5 bg-white/10 hover:bg-white/20 text-white rounded-xl transition-all disabled:opacity-0 disabled:scale-90"
                    >
                        <Send className="w-4 h-4" />
                    </button>
                </div>

                <div className="mt-4 flex justify-center">
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/5">
                        <Lock className="w-3 h-3 text-emerald-500/50" />
                        <span className="text-[10px] text-white/30 tracking-widest uppercase font-medium">End-to-End Encrypted & Anonymous</span>
                    </div>
                </div>
            </div>
        </div>
    );
}
