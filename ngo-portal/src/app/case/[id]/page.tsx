"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { ArrowLeft, Send, Clock, CheckCircle2, AlertTriangle, FileText, Shield, User, MapPin, Calendar } from "lucide-react";
import { format } from "date-fns";
import { clsx } from "clsx";

interface EvidenceFile {
    file_name: string;
    mime_type: string;
    size_bytes: number;
}

interface CredibilityBreakdown {
    narrative: { score: number; reason: string; };
    evidence: { score: number; reason: string; };
    behavioral: { score: number; reason: string; };
}

interface CaseDetail {
    id: string;
    case_id: string;
    status: string;
    priority: string;
    credibility_score: number | null;
    credibility_breakdown: CredibilityBreakdown | null;
    incident_summary: string | null;
    score_explanation: string | null;
    evidence_files: EvidenceFile[];
    created_at: string;
    last_updated_at: string;
    authority_summary: string | null;
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
            // In a real app we'd have a direct endpoint /admin/reports/{id}
            // For now using list and filter as per current backend capability or mock it
            // Assuming the list endpoint returns full details for now or we update backend to support detail get
            const res = await api.get(`/admin/reports/`);
            const found = res.data.find((r: any) => r.id === caseId);
            if (found) {
                // Transform or validate data if needed
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
                updated_by: "NGO_ADMIN"
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
                <div className="p-4 bg-card border border-border rounded-xl">
                    <span className="text-muted-foreground text-xs uppercase tracking-wider">Case ID</span>
                    <div className="text-2xl font-mono text-white mt-1">{caseData.case_id}</div>
                </div>
                <div className="p-4 bg-card border border-border rounded-xl">
                    <span className="text-muted-foreground text-xs uppercase tracking-wider">Status</span>
                    <div className="flex items-center gap-2 mt-1">
                        <span className={clsx("w-2 h-2 rounded-full", caseData.status === 'NEW' ? 'bg-red-500' : 'bg-green-500')}></span>
                        <span className="text-xl font-semibold text-white">{caseData.status}</span>
                    </div>
                </div>
                <div className="p-4 bg-card border border-border rounded-xl">
                    <span className="text-muted-foreground text-xs uppercase tracking-wider">Credibility Score</span>
                    <div className={clsx("text-2xl font-bold mt-1", (caseData.credibility_score || 0) > 70 ? "text-green-500" : "text-yellow-500")}>
                        {caseData.credibility_score ? `${caseData.credibility_score}%` : "Pending"}
                    </div>
                </div>
                <div className="p-4 bg-card border border-border rounded-xl">
                    <span className="text-muted-foreground text-xs uppercase tracking-wider">Reported On</span>
                    <div className="text-lg text-white mt-1">{format(new Date(caseData.created_at), 'PPP')}</div>
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

                    {/* AI Analysis & Breakdown */}
                    <div className="bg-card border border-border rounded-xl p-6">
                        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <Shield className="w-5 h-5 text-purple-500" /> AI Credibility Analysis
                        </h2>

                        {caseData.credibility_breakdown ? (
                            <div className="space-y-6">
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                    <div className="p-3 bg-white/5 rounded-lg">
                                        <div className="text-xs text-muted-foreground mb-1">Narrative Consistency</div>
                                        <div className="text-lg font-semibold text-white">{caseData.credibility_breakdown.narrative.score}/100</div>
                                        <div className="text-xs text-gray-400 mt-1 line-clamp-2">{caseData.credibility_breakdown.narrative.reason}</div>
                                    </div>
                                    <div className="p-3 bg-white/5 rounded-lg">
                                        <div className="text-xs text-muted-foreground mb-1">Evidence Strength</div>
                                        <div className="text-lg font-semibold text-white">{caseData.credibility_breakdown.evidence.score}/100</div>
                                        <div className="text-xs text-gray-400 mt-1 line-clamp-2">{caseData.credibility_breakdown.evidence.reason}</div>
                                    </div>
                                    <div className="p-3 bg-white/5 rounded-lg">
                                        <div className="text-xs text-muted-foreground mb-1">Behavioral Reliability</div>
                                        <div className="text-lg font-semibold text-white">{caseData.credibility_breakdown.behavioral.score}/100</div>
                                        <div className="text-xs text-gray-400 mt-1 line-clamp-2">{caseData.credibility_breakdown.behavioral.reason}</div>
                                    </div>
                                </div>

                                <div>
                                    <div className="text-sm font-medium text-white mb-2">Overall Assessment</div>
                                    <p className="text-sm text-gray-300 bg-white/5 p-3 rounded-lg border border-white/10">
                                        {caseData.score_explanation || "No explanation provided."}
                                    </p>
                                </div>

                                {caseData.authority_summary && (
                                    <div>
                                        <div className="text-sm font-medium text-white mb-2">Internal Note (Authority Summary)</div>
                                        <p className="text-sm text-amber-500/80 bg-amber-500/10 p-3 rounded-lg border border-amber-500/20">
                                            {caseData.authority_summary}
                                        </p>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="text-center py-8 text-muted-foreground text-sm">
                                Full analysis not yet generated.
                            </div>
                        )}
                    </div>
                </div>

                {/* Sidebar (Right 1/3) */}
                <div className="space-y-6">

                    {/* Evidence Files */}
                    <div className="bg-card border border-border rounded-xl p-6">
                        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <FileText className="w-5 h-5 text-blue-500" /> Evidence
                        </h2>
                        {caseData.evidence_files && caseData.evidence_files.length > 0 ? (
                            <ul className="space-y-3">
                                {caseData.evidence_files.map((file, idx) => (
                                    <li key={idx} className="flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 transition-colors cursor-pointer group">
                                        <div className="flex items-center gap-3 overflow-hidden">
                                            <div className="w-8 h-8 rounded bg-blue-500/20 flex items-center justify-center flex-shrink-0">
                                                <FileText className="w-4 h-4 text-blue-500" />
                                            </div>
                                            <div className="min-w-0">
                                                <div className="text-sm font-medium text-white truncate max-w-[150px]">{file.file_name}</div>
                                                <div className="text-xs text-muted-foreground">{(file.size_bytes / 1024).toFixed(1)} KB</div>
                                            </div>
                                        </div>
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
                        <p className="text-muted-foreground text-xs mb-4">
                            Updates are rewritten by AI for safety before public release.
                        </p>
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
                    {updates.length > 0 && (
                        <div className="bg-card border border-border rounded-xl p-6">
                            <h2 className="text-lg font-semibold text-white mb-4">Update History</h2>
                            <div className="space-y-4">
                                {updates.map((update) => (
                                    <div key={update.id} className="relative pl-4 border-l border-white/10 pb-1">
                                        <div className="absolute -left-[5px] top-1 w-2.5 h-2.5 rounded-full bg-primary ring-4 ring-background"></div>
                                        <p className="text-sm text-white">{update.public_update}</p>
                                        <p className="text-xs text-muted-foreground mt-1">{format(new Date(update.created_at), 'MMM d, h:mm a')}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                </div>
            </div>
        </div>
    );
}
