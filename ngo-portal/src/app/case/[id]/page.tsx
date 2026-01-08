"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { ArrowLeft, Send, Clock, CheckCircle2 } from "lucide-react";
import { format } from "date-fns";

interface CaseDetail {
    id: string;
    case_id: string;
    status: string;
    credibility_score: number | null;
    incident_summary: string | null;
    created_at: string;
    last_updated_at: string;
}

interface CaseUpdate {
    id: string;
    public_update: string;
    updated_by: string;
    created_at: string;
}

export default function CaseDetailPage() {
    const params = useParams();
    const router = useRouter();
    const caseId = params.id as string;

    const [caseData, setCaseData] = useState<CaseDetail | null>(null);
    const [updates, setUpdates] = useState<CaseUpdate[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Update form
    const [updateText, setUpdateText] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [submitSuccess, setSubmitSuccess] = useState(false);

    const fetchCaseData = async () => {
        try {
            // Fetch case details - this endpoint may need to be created on backend if not existing
            // For now, we'll use the reports list endpoint and filter
            const res = await api.get(`/admin/reports/`);
            const found = res.data.find((r: any) => r.id === caseId);
            if (found) {
                setCaseData(found);
            } else {
                setError("Case not found");
            }
        } catch (err) {
            console.error(err);
            setError("Failed to load case details");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchCaseData();
    }, [caseId]);

    const handlePublishUpdate = async () => {
        if (!updateText.trim()) return;

        setSubmitting(true);
        setSubmitSuccess(false);

        try {
            const res = await api.post(`/admin/reports/${caseId}/update`, {
                raw_update: updateText.trim(),
                updated_by: "NGO_ADMIN" // Hardcoded for now
            });

            setUpdates(prev => [{
                id: crypto.randomUUID(),
                public_update: res.data.public_update,
                updated_by: "NGO_ADMIN",
                created_at: new Date().toISOString()
            }, ...prev]);

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

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[50vh]">
                <div className="text-muted-foreground">Loading case data...</div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4">
                <div className="text-destructive">{error}</div>
                <button onClick={() => router.back()} className="text-primary">Go Back</button>
            </div>
        );
    }

    return (
        <div className="space-y-8 max-w-4xl mx-auto">
            {/* Back Button */}
            <button
                onClick={() => router.push("/")}
                className="flex items-center gap-2 text-muted-foreground hover:text-white transition-colors"
            >
                <ArrowLeft className="w-4 h-4" />
                Back to Dashboard
            </button>

            {/* Case Header */}
            <div className="rounded-xl border border-border bg-card p-6">
                <div className="flex items-center justify-between mb-4">
                    <h1 className="text-2xl font-bold text-white">Case Details</h1>
                    <span className="px-3 py-1 text-xs rounded-full bg-primary/10 text-primary border border-primary/20">
                        {caseData?.status}
                    </span>
                </div>
                <div className="grid grid-cols-2 gap-6 text-sm">
                    <div>
                        <p className="text-muted-foreground">Case ID</p>
                        <p className="font-mono text-white">{caseData?.case_id || caseData?.id.slice(0, 8)}</p>
                    </div>
                    <div>
                        <p className="text-muted-foreground">Credibility</p>
                        <p className="text-white">{caseData?.credibility_score || "Pending"}%</p>
                    </div>
                    <div>
                        <p className="text-muted-foreground">Submitted</p>
                        <p className="text-white">{caseData?.created_at ? format(new Date(caseData.created_at), 'PPpp') : "-"}</p>
                    </div>
                    <div>
                        <p className="text-muted-foreground">Last Updated</p>
                        <p className="text-white">{caseData?.last_updated_at ? format(new Date(caseData.last_updated_at), 'PPpp') : "-"}</p>
                    </div>
                </div>
            </div>

            {/* Publish Update Section */}
            <div className="rounded-xl border border-border bg-card p-6">
                <h2 className="text-xl font-semibold text-white mb-4">Publish Status Update</h2>
                <p className="text-muted-foreground text-sm mb-4">
                    Write an internal update. It will be automatically rewritten by AI for safe public display.
                </p>

                <div className="space-y-4">
                    <textarea
                        value={updateText}
                        onChange={(e) => setUpdateText(e.target.value)}
                        placeholder="e.g., Police verified the complaint. Investigation is ongoing."
                        rows={4}
                        className="w-full bg-background border border-border rounded-lg p-4 text-white placeholder:text-muted-foreground focus:border-primary focus:ring-1 focus:ring-primary outline-none resize-none"
                    />

                    <div className="flex items-center justify-between">
                        <div className="text-xs text-muted-foreground">
                            The update will be processed for PII removal and neutral language.
                        </div>
                        <button
                            onClick={handlePublishUpdate}
                            disabled={submitting || !updateText.trim()}
                            className="flex items-center gap-2 px-5 py-2.5 bg-primary text-white rounded-lg font-semibold disabled:opacity-50 disabled:cursor-not-allowed hover:bg-primary/90 transition-colors"
                        >
                            {submitting ? (
                                <>
                                    <Clock className="w-4 h-4 animate-spin" />
                                    Processing...
                                </>
                            ) : submitSuccess ? (
                                <>
                                    <CheckCircle2 className="w-4 h-4" />
                                    Published!
                                </>
                            ) : (
                                <>
                                    <Send className="w-4 h-4" />
                                    Publish Update
                                </>
                            )}
                        </button>
                    </div>
                </div>
            </div>

            {/* Update History */}
            {updates.length > 0 && (
                <div className="rounded-xl border border-border bg-card p-6">
                    <h2 className="text-xl font-semibold text-white mb-4">Recent Updates</h2>
                    <div className="space-y-4">
                        {updates.map((update) => (
                            <div key={update.id} className="border-l-2 border-primary/30 pl-4 py-2">
                                <p className="text-white">{update.public_update}</p>
                                <p className="text-xs text-muted-foreground mt-1">
                                    {format(new Date(update.created_at), 'PPpp')} by {update.updated_by}
                                </p>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
