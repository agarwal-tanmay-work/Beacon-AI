"use client";

import { useState } from "react";
import Link from "next/link";
import { Check, Copy, Download, Loader2, ShieldCheck, TriangleAlert } from "lucide-react";
import { cn } from "@/lib/utils";

interface CredentialsCardProps {
    caseId: string;
    /** null once the reporter has confirmed they saved it (the server copy is deleted at that point). */
    secretKey: string | null;
    onAcknowledge: () => Promise<void>;
    onNewReport: () => void;
}

async function copyToClipboard(text: string): Promise<boolean> {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch {
        // Older browsers / insecure contexts: fall back to a temporary textarea.
        const area = document.createElement("textarea");
        area.value = text;
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        const ok = document.execCommand("copy");
        document.body.removeChild(area);
        return ok;
    }
}

function CopyButton({ value, label }: { value: string; label: string }) {
    const [copied, setCopied] = useState(false);
    return (
        <button
            type="button"
            aria-label={`Copy ${label}`}
            onClick={async () => {
                if (await copyToClipboard(value)) {
                    setCopied(true);
                    window.setTimeout(() => setCopied(false), 2000);
                }
            }}
            className="shrink-0 inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white/70 transition-colors hover:bg-white/10 hover:text-white"
        >
            {copied ? <Check className="h-3.5 w-3.5 text-green-400" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? "Copied" : "Copy"}
        </button>
    );
}

function Field({ label, value, mono = true }: { label: string; value: string; mono?: boolean }) {
    return (
        <div className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-black/30 px-4 py-3">
            <div className="min-w-0">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-white/40">{label}</p>
                <p className={cn("mt-0.5 break-all text-lg text-white", mono && "font-mono tracking-wider")}>{value}</p>
            </div>
            <CopyButton value={value} label={label} />
        </div>
    );
}

function downloadCredentials(caseId: string, secretKey: string) {
    const body = [
        "Beacon AI - case credentials",
        "",
        `Case ID:    ${caseId}`,
        `Secret Key: ${secretKey}`,
        "",
        `Track your case at: ${window.location.origin}/track`,
        "Both values are required. The Secret Key cannot be recovered if it is lost.",
        "Keep this file somewhere private - anyone who has both can read your case messages.",
        "",
    ].join("\n");
    const url = URL.createObjectURL(new Blob([body], { type: "text/plain" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `beacon-${caseId}.txt`;
    link.click();
    URL.revokeObjectURL(url);
}

export function CredentialsCard({ caseId, secretKey, onAcknowledge, onNewReport }: CredentialsCardProps) {
    const [busy, setBusy] = useState(false);

    if (!secretKey) {
        return (
            <div className="space-y-4 rounded-2xl border border-green-500/20 bg-green-500/5 p-5 text-center" role="status">
                <ShieldCheck className="mx-auto h-8 w-8 text-green-400" />
                <div>
                    <p className="font-semibold text-white">Your report is submitted</p>
                    <p className="mt-1 text-sm text-white/60">
                        Case ID <span className="font-mono text-white">{caseId}</span>. Use it together with your Secret Key to check progress or message the investigators.
                    </p>
                </div>
                <div className="flex flex-col justify-center gap-2 sm:flex-row">
                    <Link href="/track" className="rounded-full bg-[#1A5CFF] px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-600">
                        Track my case
                    </Link>
                    <button type="button" onClick={onNewReport} className="rounded-full border border-white/15 px-5 py-2.5 text-sm text-white/70 transition-colors hover:bg-white/5 hover:text-white">
                        Start a new report
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-4 rounded-2xl border border-amber-400/30 bg-amber-400/5 p-4 md:p-5" role="region" aria-label="Your case credentials">
            <div className="flex items-start gap-3">
                <TriangleAlert className="mt-0.5 h-5 w-5 shrink-0 text-amber-300" />
                <div>
                    <p className="font-semibold text-white">Save these now - they are shown only once</p>
                    <p className="mt-1 text-sm text-white/60">
                        You need <strong className="text-white/80">both</strong> to follow your case. We do not store your Secret Key in readable form, so it cannot be recovered or reset.
                    </p>
                </div>
            </div>
            <div className="space-y-2">
                <Field label="Case ID" value={caseId} />
                <Field label="Secret Key" value={secretKey} />
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
                <button
                    type="button"
                    onClick={() => downloadCredentials(caseId, secretKey)}
                    className="inline-flex items-center justify-center gap-2 rounded-full border border-white/15 px-4 py-2.5 text-sm text-white/80 transition-colors hover:bg-white/10"
                >
                    <Download className="h-4 w-4" /> Download as a file
                </button>
                <button
                    type="button"
                    disabled={busy}
                    onClick={async () => {
                        setBusy(true);
                        await onAcknowledge();
                        setBusy(false);
                    }}
                    className="inline-flex flex-1 items-center justify-center gap-2 rounded-full bg-[#1A5CFF] px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-600 disabled:opacity-60"
                >
                    {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                    I have saved my Case ID and Secret Key
                </button>
            </div>
        </div>
    );
}
