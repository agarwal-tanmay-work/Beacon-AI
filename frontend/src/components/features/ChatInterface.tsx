"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Bot, Paperclip, Send, User, ChevronRight, X, FileText, Download, Image as ImageIcon, Loader2, Music } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Message } from "@/types";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// PII Redaction Helper
function sanitizeContent(content: string) {
    const emailRegex = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g;
    const phoneRegex = /\b(\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b/g;

    return content
        .replace(emailRegex, "[EMAIL REDACTED]")
        .replace(phoneRegex, "[PHONE REDACTED]");
}

interface Attachment {
    type: 'image' | 'file' | 'audio';
    url?: string;
    name: string;
    size: number;
    mimeType?: string;
}

interface ExtendedMessage extends Message {
    attachments?: Attachment[];
}

export function ChatInterface() {
    const [mounted, setMounted] = useState(false);
    const [messages, setMessages] = useState<ExtendedMessage[]>([]);

    useEffect(() => {
        setMounted(true);
        setMessages([
            {
                id: "initial-greeting",
                sender: "SYSTEM",
                content: "Hello. I am Beacon AI, your compassionate and anonymous assistant. I'm here to help you report corruption safely. Please know that your identity is fully protected, and I will guide you through this process one step at a time.\n\nHow can I assist you today?",
                timestamp: new Date().toISOString()
            }
        ]);
    }, []);
    const [inputValue, setInputValue] = useState("");
    const [loading, setLoading] = useState(false);
    const [reportId, setReportId] = useState<string | null>(null);
    const [accessToken, setAccessToken] = useState<string | null>(null);
    const [currentStep, setCurrentStep] = useState<string>("GREETING");
    const bottomRef = useRef<HTMLDivElement>(null);

    const [totalUploadSize, setTotalUploadSize] = useState(0);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // File Upload State (Multi-file)
    const [pendingFiles, setPendingFiles] = useState<File[]>([]);
    const [previewUrls, setPreviewUrls] = useState<Map<string, string>>(new Map());

    const [secretKey, setSecretKey] = useState<string | null>(null);
    const [finalCaseId, setFinalCaseId] = useState<string | null>(null);

    const isLocked = currentStep === "SUBMITTED";

    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = "inherit";
            textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
        }
    }, [inputValue]);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({
            behavior: "smooth",
            block: "nearest",
            inline: "nearest"
        });
    }, [messages, loading, pendingFiles]);

    // Clean up preview URLs
    useEffect(() => {
        return () => {
            previewUrls.forEach(url => URL.revokeObjectURL(url));
        };
    }, []);

    const handleFileUploadRequest = () => {
        if (isLocked) return;
        fileInputRef.current?.click();
    };

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files || e.target.files.length === 0) return;

        const newFiles = Array.from(e.target.files);
        const MAX_SIZE = 5 * 1024 * 1024; // 5MB per file check (or total?)

        // Filter and add valid files
        const validFiles: File[] = [];
        let addedSize = 0;

        newFiles.forEach(file => {
            // Simple individual check for now, can be cumulative
            if (file.size > MAX_SIZE) {
                // Maybe show toast? For now just skip
                console.warn(`File ${file.name} too large`);
                return;
            }
            validFiles.push(file);
            addedSize += file.size;

            if (file.type.startsWith('image/')) {
                const url = URL.createObjectURL(file);
                setPreviewUrls(prev => new Map(prev).set(file.name, url));
            }
        });

        if (totalUploadSize + addedSize > 50 * 1024 * 1024) { // Global safety cap
            alert("Total upload size limit exceeded.");
            return;
        }

        setPendingFiles(prev => [...prev, ...validFiles]);
        setTotalUploadSize(prev => prev + addedSize);

        // Reset input
        e.target.value = "";
    };

    const removeFile = (index: number) => {
        const fileToRemove = pendingFiles[index];
        setPendingFiles(prev => prev.filter((_, i) => i !== index));
        setTotalUploadSize(prev => prev - fileToRemove.size);

        if (previewUrls.has(fileToRemove.name)) {
            const url = previewUrls.get(fileToRemove.name);
            if (url) URL.revokeObjectURL(url);
            setPreviewUrls(prev => {
                const newMap = new Map(prev);
                newMap.delete(fileToRemove.name);
                return newMap;
            });
        }
    };

    const handleSendMessage = async (e?: React.FormEvent) => {
        e?.preventDefault();

        // Allow send if there is text OR files
        if (isLocked || (!inputValue.trim() && pendingFiles.length === 0)) return;

        const content = inputValue.trim();
        const filesToSend = [...pendingFiles];
        const currentPreviews = new Map(previewUrls);

        // Prepare Attachments for UI
        const attachments: Attachment[] = filesToSend.map(file => ({
            type: file.type.startsWith('image/') ? 'image' :
                file.type.startsWith('audio/') ? 'audio' : 'file',
            url: currentPreviews.get(file.name),
            name: file.name,
            size: file.size,
            mimeType: file.type
        }));

        // Immediate UI Update
        const userMsg: ExtendedMessage = {
            id: crypto.randomUUID(),
            sender: "USER",
            content: content,
            timestamp: new Date().toISOString(),
            attachments: attachments.length > 0 ? attachments : undefined
        };

        setMessages((prev) => [...prev, userMsg]);

        // Clear inputs immediately
        setInputValue("");
        setPendingFiles([]);
        // We DON'T revoke URLs yet because they are used in the message bubble.
        // In a real app we'd upload -> get remote URL -> replace. 
        // For here we keep local ObjectURL alive or let it leak until refresh.
        setLoading(true);

        try {
            let currentReportId = reportId;
            let currentAccessToken = accessToken;

            // Initialize session if needed
            if (!currentReportId || !currentAccessToken) {
                const seed = Math.random().toString(36).substring(7);
                const initRes = await api.post("/public/reports/create", { client_seed: seed });
                currentReportId = initRes.data.report_id;
                currentAccessToken = initRes.data.access_token;
                setReportId(currentReportId);
                setAccessToken(currentAccessToken);
            }

            if (!currentReportId || !currentAccessToken) throw new Error("Session init failed");

            // 1. Upload ALL Files sequentially (to keep simple)
            for (const file of filesToSend) {
                const formData = new FormData();
                formData.append("report_id", currentReportId);
                formData.append("access_token", currentAccessToken);
                formData.append("file", file);

                await api.post("/public/evidence/upload", formData, {
                    headers: { "Content-Type": "multipart/form-data" }
                });
            }

            // 2. Send Message
            const fileNames = filesToSend.map(f => f.name).join(", ");
            // If empty content but has files, add context for LLM
            const messageContent = content || (filesToSend.length > 0 ? `[User uploaded ${filesToSend.length} files: ${fileNames}]` : " ");

            const res = await api.post("/public/reports/message", {
                report_id: currentReportId,
                access_token: currentAccessToken,
                content: messageContent,
            });

            const sysMsg: ExtendedMessage = {
                id: crypto.randomUUID(),
                sender: res.data.sender,
                content: res.data.content,
                timestamp: res.data.timestamp,
                // next_step logic
            };

            // Check for next_step / case_id logic
            if (res.data.next_step === "SUBMITTED") {
                setCurrentStep("SUBMITTED");
                if (res.data.case_id) setFinalCaseId(res.data.case_id);
                if (res.data.secret_key) setSecretKey(res.data.secret_key);
                sysMsg.next_step = "SUBMITTED";
            } else if (res.data.next_step) {
                setCurrentStep(res.data.next_step);
                sysMsg.next_step = res.data.next_step;
            }

            setMessages((prev) => [...prev, sysMsg]);

        } catch (err) {
            console.error("Send Failed", err);
            // Error handling UI could be added here
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="w-full max-w-6xl mx-auto flex flex-col gap-6 h-full">
            {/* Main Chat Card */}
            <div className="w-full bg-black/40 backdrop-blur-3xl border border-white/10 rounded-t-[2rem] rounded-b-xl overflow-hidden flex flex-col h-full min-h-[500px] shadow-2xl relative">

                {/* Header */}
                <div className="flex items-center gap-3 px-6 py-4 border-b border-white/5 bg-white/5 backdrop-blur-md">
                    <span className="text-white font-semibold text-lg tracking-wide">Beacon AI</span>
                </div>

                {/* Messages Area */}
                <div className="flex-1 overflow-y-auto p-6 space-y-8 scrollbar-hide relative">

                    <AnimatePresence initial={false}>
                        {messages.map((msg) => (
                            <motion.div
                                key={msg.id}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                className={cn(
                                    "flex w-full",
                                    msg.sender === "USER" ? "justify-end" : "justify-start"
                                )}
                            >
                                <div className={cn(
                                    "flex gap-4 max-w-[85%]",
                                    msg.sender === "USER" ? "flex-row-reverse" : "flex-row"
                                )}>

                                    {/* Bubble */}
                                    <div className={cn(
                                        "relative p-5 rounded-[1.25rem] text-[15px] leading-relaxed flex flex-col gap-3",
                                        msg.sender === "USER"
                                            ? "bg-blue-600/90 text-white rounded-tr-none shadow-[0_4px_20px_rgba(37,99,235,0.2)]"
                                            : "bg-white/5 border border-white/10 text-gray-200 rounded-tl-none backdrop-blur-md shadow-lg"
                                    )}>
                                        {/* Attachments Grid */}
                                        {msg.attachments && msg.attachments.length > 0 && (
                                            <div className="flex flex-wrap gap-2 mb-1">
                                                {msg.attachments.map((att, idx) => (
                                                    att.type === 'image' ? (
                                                        <div key={idx} className="relative rounded-lg overflow-hidden border border-white/10 max-w-[200px]">
                                                            <img
                                                                src={att.url}
                                                                alt={att.name}
                                                                className="w-full h-auto object-cover max-h-[200px]"
                                                            />
                                                        </div>
                                                    ) : (
                                                        <div key={idx} className="flex items-center gap-3 bg-white/10 p-3 rounded-lg border border-white/10 min-w-[150px]">
                                                            <div className="p-2 bg-white/10 rounded-lg">
                                                                {att.type === 'audio' ? (
                                                                    <Music className="w-6 h-6 text-white" />
                                                                ) : (
                                                                    <FileText className="w-6 h-6 text-white" />
                                                                )}
                                                            </div>
                                                            <div className="flex-1 min-w-0">
                                                                <p className="text-sm font-medium text-white truncate max-w-[120px]">{att.name}</p>
                                                                <p className="text-xs text-white/50">{(att.size / 1024).toFixed(1)} KB</p>
                                                            </div>
                                                        </div>
                                                    )
                                                ))}
                                            </div>
                                        )}

                                        {/* Text Content */}
                                        {msg.content && msg.content.trim() !== "" && (
                                            <div className="markdown-content whitespace-pre-wrap">
                                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                    {sanitizeContent(msg.content)}
                                                </ReactMarkdown>
                                            </div>
                                        )}

                                        {/* Timestamp in Bubble */}
                                        <div className={cn(
                                            "mt-1 flex items-center gap-1.5 text-[10px] opacity-50 font-mono",
                                            msg.sender === "USER" ? "text-blue-200" : "text-gray-400"
                                        )}>
                                            <div className="w-1 h-1 rounded-full bg-current" />
                                            {mounted ? new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true }) : "--:-- --"}
                                        </div>
                                    </div>
                                </div>
                            </motion.div>
                        ))}
                    </AnimatePresence>

                    {loading && (
                        <div className="flex gap-4">
                            <div className="bg-white/5 border border-white/10 px-4 py-3 rounded-[1.25rem] rounded-tl-none ml-0">
                                <div className="flex gap-1">
                                    <span className="w-1.5 h-1.5 bg-white/40 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                                    <span className="w-1.5 h-1.5 bg-white/40 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                                    <span className="w-1.5 h-1.5 bg-white/40 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                                </div>
                            </div>
                        </div>
                    )}
                    <div ref={bottomRef} className="h-1" />
                </div>

                {/* Input Area */}
                <div className="p-4 bg-white/[0.02] border-t border-white/5 relative">

                    {/* Pre-upload Preview (Thumbnails Only) */}
                    <AnimatePresence>
                        {pendingFiles.length > 0 && (
                            <motion.div
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: 10 }}
                                className="absolute bottom-full left-4 mb-2 z-10 w-[calc(100%-2rem)]"
                            >
                                <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
                                    {pendingFiles.map((file, idx) => (
                                        <div key={`${file.name}-${idx}`} className="relative group shrink-0">
                                            {/* Thumbnail Container */}
                                            <div className={cn(
                                                "w-16 h-16 rounded-xl border border-white/10 overflow-hidden flex items-center justify-center shadow-lg transition-transform hover:scale-105",
                                                file.type.startsWith('image/') ? "bg-black" : "bg-white/5"
                                            )}>
                                                {file.type.startsWith('image/') && previewUrls.get(file.name) ? (
                                                    <img
                                                        src={previewUrls.get(file.name)}
                                                        alt="preview"
                                                        className="w-full h-full object-cover"
                                                    />
                                                ) : file.type.startsWith('audio/') ? (
                                                    <Music className="w-6 h-6 text-white/50" />
                                                ) : (
                                                    <FileText className="w-6 h-6 text-white/50" />
                                                )}

                                                {/* NO Text Details as per requirement */}
                                            </div>

                                            {/* X Button (Top Right corner of thumbnail) */}
                                            <button
                                                onClick={() => removeFile(idx)}
                                                className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center text-white shadow-md hover:bg-red-600 transition-colors z-20"
                                            >
                                                <X className="w-3 h-3" />
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    <form
                        onSubmit={handleSendMessage}
                        className="w-full flex items-center gap-3 bg-white/5 border border-white/10 rounded-full pl-4 pr-1.5 py-1.5 focus-within:bg-white/[0.07] focus-within:border-white/20 transition-all duration-300 shadow-inner"
                    >
                        <input
                            type="file"
                            ref={fileInputRef}
                            className="hidden"
                            onChange={handleFileSelect}
                            multiple // Enable multiple files
                            accept="image/*,audio/*,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        />

                        <button
                            type="button"
                            onClick={handleFileUploadRequest}
                            className={cn(
                                "transition-colors p-1",
                                pendingFiles.length > 0 ? "text-blue-400" : "text-white/30 hover:text-white"
                            )}
                        >
                            <Paperclip className="w-5 h-5" />
                        </button>

                        <textarea
                            ref={textareaRef}
                            value={inputValue}
                            onChange={(e) => setInputValue(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === "Enter" && !e.shiftKey) {
                                    e.preventDefault();
                                    handleSendMessage();
                                }
                            }}
                            placeholder="Type your message..."
                            className="flex-1 bg-transparent border-none text-white placeholder-white/20 focus:outline-none focus:ring-0 text-sm px-2 font-light resize-none py-2 max-h-32 scrollbar-hide"
                            disabled={isLocked || loading}
                            rows={1}
                        />

                        <button
                            type="submit"
                            disabled={(!inputValue.trim() && pendingFiles.length === 0) || loading || isLocked}
                            className="bg-[#1A5CFF] hover:bg-blue-600 text-white px-5 py-2.5 rounded-full flex items-center gap-2 text-sm font-medium transition-all duration-300 shadow-[0_0_15px_rgba(37,99,235,0.3)] hover:shadow-[0_0_25px_rgba(37,99,235,0.5)] disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4 ml-0.5" />}
                            Send
                        </button>
                    </form>
                </div>
            </div>
        </div>
    );
}
