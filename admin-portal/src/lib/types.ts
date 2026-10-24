export type CaseStatus = "Pending" | "Ongoing" | "Completed";
export type Priority = "Pending" | "Low" | "Medium" | "High";

/** One row of GET /admin/reports/ */
export interface ReportListItem {
    id: string;
    case_id: string;
    status: CaseStatus;
    priority: Priority;
    credibility_score: number | null;
    confidence: "Low" | "Medium" | "High" | null;
    analysis_status: "pending" | "processing" | "completed" | "failed" | null;
    created_at: string;
}

export interface EvidenceFile {
    file_name: string;
    mime_type: string | null;
    size_bytes: number;
    /** Short-lived signed link (relative to the API). */
    full_url: string | null;
    kind: string | null;
    /** What the AI found in the file: scene description, transcript or extracted text. */
    summary: string | null;
    analyzed: boolean;
    quality_notes: string[];
}

export interface CaseUpdate {
    id: string;
    public_update: string;
    updated_by: string;
    created_at: string;
}

export interface CaseDetail extends ReportListItem {
    incident_summary: string | null;
    ai_summary: string | null;
    ai_explanation: {
        rationale: string[];
        confidence: string;
        limitations: string[];
        safety: string;
    } | null;
    app_score_explanation: string | null;
    /** What the reporter told the assistant: what / where / when / who / evidence / contact_info / other_details. */
    reporter_details: Record<string, string> | null;
    evidence_files: EvidenceFile[];
    updates: CaseUpdate[];
}

export interface MessageAttachment {
    file_name: string;
    file_path: string;
    mime_type: string;
}

export interface CaseMessage {
    id: string;
    sender_role: "user" | "admin";
    content: string | null;
    attachments: MessageAttachment[];
    timestamp: string;
}

export interface SystemStatus {
    environment: string;
    database: "connected" | "disconnected";
    storage: "supabase" | "local";
    ai: { state: "ok" | "unknown" | "degraded" | "key_invalid" | "unconfigured"; key_error: string | null };
    analysis_queue: Record<string, number>;
    warnings: string[];
}
