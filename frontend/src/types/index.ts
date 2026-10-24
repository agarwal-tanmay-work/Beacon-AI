export type Sender = "USER" | "SYSTEM" | "AI";

/** Response of POST /public/reports/message */
export interface MessageResponse {
    report_id: string;
    sender: Sender;
    content: string;
    timestamp: string;
    next_step: "ACTIVE" | "COMPLETED";
    case_id: string | null;
    secret_key: string | null;
    /** "basic" = the AI assistant was unavailable and fixed questions were used. */
    mode: "ai" | "basic";
    notice: string | null;
}

export interface AttachmentMeta {
    type: "image" | "audio" | "file";
    name: string;
    size: number;
    previewUrl?: string;
}

export interface Message {
    id: string;
    sender: Sender;
    content: string;
    timestamp: string;
    attachments?: AttachmentMeta[];
    /** Local-only delivery state for the user's own messages. */
    status?: "sending" | "failed";
}

export interface Credentials {
    caseId: string;
    secretKey: string;
}
