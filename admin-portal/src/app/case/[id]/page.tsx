"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AlertTriangle, ArrowLeft, CheckCircle2, ChevronDown, Clock, FileText, Loader2, Paperclip, RefreshCw, Send, Shield, User, X } from "lucide-react";

import { SafeMarkdown } from "@/components/ui/safe-markdown";
import { api, errorCode, errorMessage, resolveFileUrl } from "@/lib/api";
import type { CaseDetail, CaseMessage, CaseStatus } from "@/lib/types";
import { cn, formatSize, formatToIST } from "@/lib/utils";

type Notice = { kind: "error" | "success"; text: string } | null;

const STATUSES: CaseStatus[] = ["Pending", "Ongoing", "Completed"];
const STATUS_PILL: Record<CaseStatus, string> = {
    Pending: "bg-red-500 text-white",
    Ongoing: "bg-yellow-500 text-black",
    Completed: "bg-green-500 text-white",
};
const DETAIL_LABELS: [string, string][] = [
    ["what", "What happened"],
    ["where", "Where"],
    ["when", "When"],
    ["who", "Who was involved"],
    ["evidence", "Evidence"],
    ["other_details", "Additional details"],
];

function Card({ title, icon, children }: { title: string; icon?: React.ReactNode; children: React.ReactNode }) {
    return (
        <section className="bg-card border border-border rounded-xl p-6">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                {icon} {title}
            </h2>
            {children}
        </section>
    );
}

function Banner({ notice, onClose }: { notice: Notice; onClose: () => void }) {
    if (!notice) return null;
    const isError = notice.kind === "error";
    return (
        <div
            role={isError ? "alert" : "status"}
            className={cn("flex items-start gap-2 rounded-lg border px-3 py-2 text-sm", isError ? "border-red-500/30 bg-red-500/10 text-red-300" : "border-green-500/30 bg-green-500/10 text-green-300")}
        >
            {isError ? <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> : <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />}
            <span className="flex-1">{notice.text}</span>
            <button type="button" aria-label="Dismiss" onClick={onClose} className="opacity-70 hover:opacity-100">
                <X className="h-4 w-4" />
            </button>
        </div>
    );
}

export default function CaseDetailPage() {
    const params = useParams<{ id: string }>();
    const router = useRouter();
    const caseUuid = params.id;

    const [data, setData] = useState<CaseDetail | null>(null);
    const [messages, setMessages] = useState<CaseMessage[]>([]);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [notice, setNotice] = useState<Notice>(null);

    const [editingStatus, setEditingStatus] = useState(false);
    const [statusBusy, setStatusBusy] = useState(false);
    const statusMenuRef = useRef<HTMLDivElement>(null);

    const [messageInput, setMessageInput] = useState("");
    const [file, setFile] = useState<File | null>(null);
    const [sending, setSending] = useState(false);
    const [messageNotice, setMessageNotice] = useState<Notice>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const [updateText, setUpdateText] = useState("");
    const [publishing, setPublishing] = useState(false);
    const [updateNotice, setUpdateNotice] = useState<Notice>(null);
    const [offerRaw, setOfferRaw] = useState(false);
    const [analysisBusy, setAnalysisBusy] = useState(false);

    const load = useCallback(async () => {
        try {
            const [detail, thread] = await Promise.all([
                api.get<CaseDetail>(`/admin/reports/${caseUuid}`),
                api.get<CaseMessage[]>(`/admin/reports/${caseUuid}/messages`),
            ]);
            setData(detail.data);
            setMessages(thread.data);
            setLoadError(null);
        } catch (err) {
            setLoadError(errorMessage(err, "Failed to load this case."));
        }
    }, [caseUuid]);

    useEffect(() => {
        const first = window.setTimeout(() => void load(), 0);
        const timer = window.setInterval(() => {
            if (document.visibilityState === "visible") void load();
        }, 30_000);
        return () => {
            window.clearTimeout(first);
            window.clearInterval(timer);
        };
    }, [load]);

    useEffect(() => {
        if (!editingStatus) return;
        const close = (e: MouseEvent) => {
            if (statusMenuRef.current && !statusMenuRef.current.contains(e.target as Node)) setEditingStatus(false);
        };
        document.addEventListener("mousedown", close);
        return () => document.removeEventListener("mousedown", close);
    }, [editingStatus]);

    const messageCount = messages.length;
    useEffect(() => {
        if (messageCount > 0) messagesEndRef.current?.scrollIntoView({ block: "nearest" });
    }, [messageCount]);

    // ---- actions -------------------------------------------------------------------------------------------------
    const changeStatus = async (status: CaseStatus) => {
        setStatusBusy(true);
        try {
            await api.put(`/admin/reports/${caseUuid}/status`, { status });
            setData((prev) => (prev ? { ...prev, status } : prev));
            setEditingStatus(false);
        } catch (err) {
            setNotice({ kind: "error", text: errorMessage(err, "Failed to update the status.") });
        } finally {
            setStatusBusy(false);
        }
    };

    const recalculate = async () => {
        setAnalysisBusy(true);
        try {
            await api.post(`/admin/reports/${caseUuid}/analyze`);
            setNotice({ kind: "success", text: "Analysis queued. The score will appear here when it finishes." });
            window.setTimeout(() => void load(), 4000);
        } catch (err) {
            setNotice({ kind: "error", text: errorMessage(err, "Could not start the analysis.") });
        } finally {
            setAnalysisBusy(false);
        }
    };

    const sendMessage = async () => {
        if (sending || (!messageInput.trim() && !file)) return;
        setSending(true);
        setMessageNotice(null);
        try {
            const attachments = [];
            if (file) {
                const form = new FormData();
                form.append("file", file);
                const upload = await api.post(`/admin/reports/${caseUuid}/upload`, form, { headers: { "Content-Type": "multipart/form-data" } });
                attachments.push({ file_name: upload.data.file_name, file_path: upload.data.file_path, mime_type: upload.data.mime_type });
            }
            const { data: sent } = await api.post<CaseMessage>(`/admin/reports/${caseUuid}/message`, { content: messageInput.trim() || null, attachments });
            setMessages((prev) => [...prev, sent]);
            setMessageInput("");
            setFile(null);
        } catch (err) {
            setMessageNotice({ kind: "error", text: errorMessage(err, "Failed to send the message.") });
        } finally {
            setSending(false);
        }
    };

    const publishUpdate = async (publishRaw: boolean) => {
        if (!updateText.trim() || publishing) return;
        setPublishing(true);
        setUpdateNotice(null);
        try {
            await api.post(`/admin/reports/${caseUuid}/update`, { raw_update: updateText.trim(), updated_by: "ADMIN", publish_raw: publishRaw });
            setUpdateText("");
            setOfferRaw(false);
            setUpdateNotice({ kind: "success", text: publishRaw ? "Update published exactly as written." : "Update rewritten and published." });
            await load();
        } catch (err) {
            // The AI rewrite is the safety net that keeps internal wording off the reporter's screen, so when it is
            // unavailable the investigator has to choose explicitly whether to publish the text as typed.
            setOfferRaw(errorCode(err) === "ai_unavailable");
            setUpdateNotice({ kind: "error", text: errorMessage(err, "Failed to publish the update.") });
        } finally {
            setPublishing(false);
        }
    };

    if (loadError && !data) return <div className="p-12 text-center text-destructive" role="alert">{loadError}</div>;
    if (!data) return <div className="p-12 text-center text-muted-foreground">Loading sensitive case data...</div>;

    const analysing = data.analysis_status === "pending" || data.analysis_status === "processing";
    const details = data.reporter_details ?? {};
    const summary = data.ai_summary || data.incident_summary;

    return (
        <div className="space-y-6 max-w-6xl mx-auto pb-12">
            <button type="button" onClick={() => router.back()} className="flex items-center gap-2 text-muted-foreground hover:text-white mb-4">
                <ArrowLeft className="w-4 h-4" /> Back to Dashboard
            </button>

            <Banner notice={notice} onClose={() => setNotice(null)} />
            {loadError && <Banner notice={{ kind: "error", text: `${loadError} (showing the last loaded data)` }} onClose={() => setLoadError(null)} />}

            {/* Top stat bar */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="p-4 bg-card border border-border rounded-xl">
                    <span className="text-muted-foreground text-xs uppercase tracking-wider">Case ID</span>
                    <div className="text-2xl font-mono text-white mt-1 break-all">{data.case_id}</div>
                </div>

                <div className="p-4 bg-card border border-border rounded-xl relative" ref={statusMenuRef}>
                    <span className="text-muted-foreground text-xs uppercase tracking-wider">Status</span>
                    <div className="mt-1">
                        <button
                            type="button"
                            aria-haspopup="listbox"
                            aria-expanded={editingStatus}
                            onClick={() => setEditingStatus((v) => !v)}
                            className={cn("flex items-center gap-2 px-3 py-1 rounded-full text-sm font-bold transition-all hover:ring-2 ring-white/20", STATUS_PILL[data.status])}
                        >
                            {data.status}
                            <ChevronDown className="w-4 h-4 opacity-70" />
                        </button>
                        {editingStatus && (
                            <ul role="listbox" className="absolute left-2 right-2 top-full z-10 mt-1 flex flex-col gap-1 rounded-lg border border-zinc-700 bg-zinc-900 p-2 shadow-xl">
                                {STATUSES.map((s) => (
                                    <li key={s}>
                                        <button
                                            type="button"
                                            role="option"
                                            aria-selected={data.status === s}
                                            disabled={statusBusy}
                                            onClick={() => void changeStatus(s)}
                                            className={cn("w-full text-left px-3 py-2 rounded hover:bg-white/10 text-sm flex items-center justify-between", data.status === s ? "text-primary font-bold" : "text-gray-300", statusBusy && "opacity-50")}
                                        >
                                            {s}
                                            {statusBusy && s === data.status && <Clock className="w-3 h-3 animate-spin" />}
                                        </button>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>
                </div>

                <div className="p-4 bg-card border border-border rounded-xl flex flex-col justify-between gap-2">
                    <div>
                        <span className="text-muted-foreground text-xs uppercase tracking-wider">Credibility Score</span>
                        {data.credibility_score !== null ? (
                            <div className={cn("text-2xl font-bold mt-1", data.confidence === "High" ? "text-green-500" : data.confidence === "Medium" ? "text-yellow-500" : "text-red-400")}>
                                {data.credibility_score}% <span className="text-sm font-medium opacity-80">{data.confidence}</span>
                            </div>
                        ) : (
                            <div className="mt-1 flex items-center gap-2 text-lg font-semibold text-muted-foreground">
                                {analysing && <Loader2 className="h-4 w-4 animate-spin" />}
                                {analysing ? "Analysis in progress" : data.analysis_status === "failed" ? "Analysis failed" : "Not analysed yet"}
                            </div>
                        )}
                    </div>
                    {data.credibility_score === null && data.analysis_status !== "processing" && (
                        <button
                            type="button"
                            disabled={analysisBusy}
                            onClick={() => void recalculate()}
                            className="inline-flex items-center justify-center gap-1 text-[11px] bg-primary/20 hover:bg-primary/30 text-primary border border-primary/30 px-2 py-1 rounded transition-colors disabled:opacity-60"
                        >
                            <RefreshCw className={cn("h-3 w-3", analysisBusy && "animate-spin")} />
                            {analysisBusy ? "Queuing..." : "Recalculate analysis"}
                        </button>
                    )}
                </div>

                <div className="p-4 bg-card border border-border rounded-xl">
                    <span className="text-muted-foreground text-xs uppercase tracking-wider">Reported On</span>
                    <div className="text-sm text-white mt-1">{formatToIST(data.created_at)}</div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div className="lg:col-span-2 space-y-6">
                    <Card title="Incident Summary" icon={<FileText className="w-5 h-5 text-primary" />}>
                        <div className="prose prose-invert max-w-none text-sm leading-relaxed text-gray-300">
                            {summary ? <SafeMarkdown>{summary}</SafeMarkdown> : <span className="italic text-muted-foreground">Summary unavailable.</span>}
                        </div>
                    </Card>

                    {Object.keys(details).length > 0 && (
                        <Card title="Details provided by the reporter" icon={<User className="w-5 h-5 text-sky-400" />}>
                            <dl className="grid grid-cols-1 sm:grid-cols-[10rem_1fr] gap-x-6 gap-y-3 text-sm">
                                {DETAIL_LABELS.filter(([key]) => details[key]).map(([key, label]) => (
                                    <div key={key} className="contents">
                                        <dt className="text-muted-foreground">{label}</dt>
                                        <dd className="text-gray-200 whitespace-pre-wrap break-words">{details[key]}</dd>
                                    </div>
                                ))}
                                {details.contact_info && (
                                    <div className="contents">
                                        <dt className="text-amber-400">Contact details</dt>
                                        <dd className="text-gray-200 whitespace-pre-wrap break-words">
                                            {details.contact_info}
                                            <span className="mt-1 block text-xs text-amber-300/80">Volunteered by the reporter for follow-up. Handle with care: this is the only identifying information on the case.</span>
                                        </dd>
                                    </div>
                                )}
                            </dl>
                        </Card>
                    )}

                    <Card title="Credibility Score Explanation" icon={<Shield className="w-5 h-5 text-purple-500" />}>
                        {data.ai_explanation && (
                            <div className="space-y-6 mb-6">
                                <div>
                                    <div className="text-sm font-bold text-white mb-2">Analysis Rationale</div>
                                    <ul className="list-disc pl-5 space-y-1 text-sm text-gray-300">
                                        {data.ai_explanation.rationale.map((r, i) => (
                                            <li key={i}>{r}</li>
                                        ))}
                                    </ul>
                                </div>
                                {data.ai_explanation.limitations.length > 0 && (
                                    <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
                                        <div className="text-sm font-bold text-yellow-500 mb-1 flex items-center gap-2">
                                            <AlertTriangle className="w-4 h-4" /> Verifiability Constraints
                                        </div>
                                        <ul className="list-disc pl-5 space-y-1 text-xs text-yellow-200/80">
                                            {data.ai_explanation.limitations.map((l, i) => (
                                                <li key={i}>{l}</li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                            </div>
                        )}
                        <div className="text-sm text-gray-300 bg-white/5 p-4 rounded-lg border border-white/10">
                            {data.app_score_explanation ?? (analysing ? "The AI analysis is still running." : "No explanation available.")}
                        </div>
                        {data.ai_explanation?.safety && <p className="mt-3 text-xs text-muted-foreground">{data.ai_explanation.safety}</p>}
                    </Card>

                    <Card title="Communication Channel" icon={<Send className="w-5 h-5 text-primary" />}>
                        <div className="space-y-4 mb-6 max-h-[400px] overflow-y-auto pr-2" aria-live="polite">
                            {messages.length === 0 ? (
                                <div className="text-center py-8 text-muted-foreground text-sm italic">No communication history yet.</div>
                            ) : (
                                messages.map((msg) => (
                                    <div key={msg.id} className={cn("flex flex-col max-w-[85%]", msg.sender_role === "admin" ? "ml-auto items-end" : "mr-auto items-start")}>
                                        <div
                                            className={cn(
                                                "px-4 py-2 rounded-2xl text-sm prose prose-invert prose-sm max-w-none",
                                                msg.sender_role === "admin" ? "bg-primary/20 border border-primary/30 text-white rounded-tr-none" : "bg-white/5 border border-white/10 text-gray-300 rounded-tl-none",
                                            )}
                                        >
                                            {msg.content && <SafeMarkdown>{msg.content}</SafeMarkdown>}
                                            {msg.attachments.length > 0 && (
                                                <div className="mt-2 space-y-1 not-prose">
                                                    {msg.attachments.map((att, idx) => (
                                                        <a
                                                            key={idx}
                                                            href={resolveFileUrl(att.file_path) ?? "#"}
                                                            target="_blank"
                                                            rel="noopener noreferrer"
                                                            className="flex items-center gap-2 text-xs bg-black/20 p-2 rounded hover:bg-black/40 transition-colors"
                                                        >
                                                            <FileText className="w-3 h-3 text-primary" />
                                                            <span className="truncate max-w-[150px]">{att.file_name}</span>
                                                        </a>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                        <span className="text-[10px] text-muted-foreground mt-1">
                                            {msg.sender_role === "admin" ? "You" : "Reporter"} • {formatToIST(msg.timestamp)}
                                        </span>
                                    </div>
                                ))
                            )}
                            <div ref={messagesEndRef} />
                        </div>

                        <div className="space-y-3 pt-4 border-t border-border">
                            <Banner notice={messageNotice} onClose={() => setMessageNotice(null)} />
                            {file && (
                                <div className="flex items-center justify-between rounded-lg border border-primary/30 bg-primary/10 px-3 py-2 text-xs text-gray-200">
                                    <span className="truncate">
                                        {file.name} <span className="opacity-60">({formatSize(file.size)})</span>
                                    </span>
                                    <button type="button" aria-label="Remove attachment" onClick={() => setFile(null)}>
                                        <X className="h-4 w-4" />
                                    </button>
                                </div>
                            )}
                            <div className="flex gap-2">
                                <textarea
                                    value={messageInput}
                                    onChange={(e) => setMessageInput(e.target.value)}
                                    aria-label="Message to the reporter"
                                    maxLength={4000}
                                    placeholder="Type a message to the reporter..."
                                    rows={2}
                                    className="flex-1 bg-background border border-border rounded-lg p-3 text-sm text-white placeholder:text-muted-foreground focus:border-primary focus:ring-1 focus:ring-primary outline-none resize-none"
                                />
                                <div className="flex flex-col gap-2">
                                    <label className={cn("p-3 rounded-lg border border-border hover:bg-white/5 transition-colors cursor-pointer", file ? "text-primary border-primary/50" : "text-muted-foreground")} title="Attach file">
                                        <input
                                            type="file"
                                            className="hidden"
                                            onChange={(e) => {
                                                setFile(e.target.files?.[0] ?? null);
                                                e.target.value = "";
                                            }}
                                        />
                                        <Paperclip className="w-5 h-5" />
                                    </label>
                                    <button
                                        type="button"
                                        onClick={() => void sendMessage()}
                                        disabled={sending || (!messageInput.trim() && !file)}
                                        aria-label="Send message"
                                        className="p-3 bg-primary text-white rounded-lg hover:bg-primary/90 disabled:opacity-50 transition-colors"
                                    >
                                        {sending ? <Clock className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                                    </button>
                                </div>
                            </div>
                        </div>
                    </Card>
                </div>

                <div className="space-y-6">
                    <Card title="Evidence" icon={<FileText className="w-5 h-5 text-blue-500" />}>
                        {data.evidence_files.length > 0 ? (
                            <ul className="space-y-3">
                                {data.evidence_files.map((evidence, idx) => {
                                    const href = resolveFileUrl(evidence.full_url);
                                    return (
                                        <li key={idx}>
                                            <a
                                                href={href ?? undefined}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                aria-disabled={!href}
                                                className="block p-3 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 transition-colors"
                                            >
                                                <div className="flex items-center gap-3 overflow-hidden">
                                                    <div className="w-8 h-8 rounded bg-blue-500/20 flex items-center justify-center flex-shrink-0">
                                                        <FileText className="w-4 h-4 text-blue-500" />
                                                    </div>
                                                    <div className="min-w-0">
                                                        <div className="text-sm font-medium text-white truncate">{evidence.file_name}</div>
                                                        <div className="text-xs text-muted-foreground">{formatSize(evidence.size_bytes)}</div>
                                                    </div>
                                                </div>
                                                {evidence.summary && <p className="mt-2 text-xs text-gray-400 line-clamp-4">{evidence.summary}</p>}
                                                <div className="mt-2 flex flex-wrap gap-1">
                                                    <span className={cn("rounded px-1.5 py-0.5 text-[10px]", evidence.analyzed ? "bg-green-500/15 text-green-400" : "bg-yellow-500/15 text-yellow-400")}>
                                                        {evidence.analyzed ? "AI analysed" : "Not analysed"}
                                                    </span>
                                                    {evidence.quality_notes.map((note) => (
                                                        <span key={note} className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] text-gray-300">
                                                            {note.replaceAll("_", " ")}
                                                        </span>
                                                    ))}
                                                </div>
                                            </a>
                                        </li>
                                    );
                                })}
                            </ul>
                        ) : (
                            <div className="text-sm text-muted-foreground italic">No evidence files provided.</div>
                        )}
                    </Card>

                    <Card title="Publish Update">
                        <div className="space-y-3">
                            <textarea
                                value={updateText}
                                onChange={(e) => setUpdateText(e.target.value)}
                                aria-label="Status update"
                                maxLength={4000}
                                placeholder="Status update (an AI rewrites it for the reporter)..."
                                rows={3}
                                className="w-full bg-background border border-border rounded-lg p-3 text-sm text-white placeholder:text-muted-foreground focus:border-primary focus:ring-1 focus:ring-primary outline-none resize-none"
                            />
                            <Banner notice={updateNotice} onClose={() => setUpdateNotice(null)} />
                            <button
                                type="button"
                                onClick={() => void publishUpdate(false)}
                                disabled={publishing || !updateText.trim()}
                                className="w-full flex items-center justify-center gap-2 py-2 bg-primary text-white rounded-lg text-sm font-semibold hover:bg-primary/90 disabled:opacity-50"
                            >
                                {publishing ? <Clock className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                                {publishing ? "Processing..." : "Publish"}
                            </button>
                            {offerRaw && (
                                <button
                                    type="button"
                                    onClick={() => void publishUpdate(true)}
                                    disabled={publishing || !updateText.trim()}
                                    className="w-full rounded-lg border border-yellow-500/40 py-2 text-xs text-yellow-300 hover:bg-yellow-500/10 disabled:opacity-50"
                                >
                                    Publish exactly as written (no AI rewrite) - the reporter will see this text
                                </button>
                            )}
                        </div>
                    </Card>

                    {data.updates.length > 0 ? (
                        <Card title="Update History">
                            <div className="space-y-4">
                                {[...data.updates].reverse().map((update) => (
                                    <div key={update.id} className="relative pl-4 border-l border-white/10 pb-1">
                                        <div className="absolute -left-[5px] top-1 w-2.5 h-2.5 rounded-full bg-primary ring-4 ring-background" />
                                        <div className="text-sm text-white prose prose-invert prose-sm max-w-none">
                                            <SafeMarkdown>{update.public_update}</SafeMarkdown>
                                        </div>
                                        <p className="text-xs text-muted-foreground mt-1">{formatToIST(update.created_at)}</p>
                                    </div>
                                ))}
                            </div>
                        </Card>
                    ) : (
                        <div className="bg-card border border-border rounded-xl p-6 text-center text-muted-foreground text-sm italic">No updates posted. Case Status: {data.status}</div>
                    )}
                </div>
            </div>
        </div>
    );
}
