import type { Message } from "@/types";

/**
 * The reporting session survives a page refresh (sessionStorage = this tab only, erased when the tab closes), so a reporter
 * who accidentally reloads does not lose a half-finished conversation.
 *
 * What is NEVER stored here: the Secret Key. It lives only in memory and can be re-fetched from the server until the
 * reporter confirms they saved it.
 */
const KEY = "beacon.report.v1";

export interface StoredSession {
    reportId: string;
    accessToken: string;
    messages: Message[];
    completed: boolean;
    acknowledged: boolean;
    caseId: string | null;
    mode: "ai" | "basic";
}

function isStoredSession(value: unknown): value is StoredSession {
    if (!value || typeof value !== "object") return false;
    const v = value as Partial<StoredSession>;
    return typeof v.reportId === "string" && typeof v.accessToken === "string" && Array.isArray(v.messages);
}

export function loadSession(): StoredSession | null {
    try {
        const raw = window.sessionStorage.getItem(KEY);
        const parsed: unknown = raw ? JSON.parse(raw) : null;
        return isStoredSession(parsed) ? parsed : null;
    } catch {
        return null; // storage blocked or corrupt - behave as a fresh session
    }
}

export function saveSession(session: StoredSession): void {
    try {
        // Strip transient UI state (blob preview URLs die with the page; unsent messages are not worth restoring).
        const messages = session.messages
            .filter((m) => m.status !== "sending" && m.status !== "failed")
            .map(({ attachments, ...rest }) => ({
                ...rest,
                attachments: attachments?.map((meta) => ({ type: meta.type, name: meta.name, size: meta.size })),
            }));
        window.sessionStorage.setItem(KEY, JSON.stringify({ ...session, messages }));
    } catch {
        /* storage full or blocked - persistence is a convenience, never a requirement */
    }
}

export function clearSession(): void {
    try {
        window.sessionStorage.removeItem(KEY);
    } catch {
        /* ignore */
    }
}
