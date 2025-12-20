export interface ReportResponse {
    report_id: string;
    access_token: string;
    message: string;
}

export interface MessageResponse {
    report_id: string;
    sender: "USER" | "SYSTEM" | "AI";
    content: string;
    timestamp: string;
    next_step: string | null;
}

export interface Message {
    id: string;
    sender: "USER" | "SYSTEM" | "AI";
    content: string;
    timestamp: string;
    next_step?: string;
}

export interface EvidenceParam {
    report_id: string;
    access_token: string;
    file: File;
}
