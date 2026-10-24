import axios, { type AxiosError } from "axios";

// All requests are same-origin by default: the browser talks to the Next.js server, whose rewrite (next.config.ts)
// forwards /api/v1/* to the backend. That removes CORS entirely and keeps the backend URL out of the bundle.
// Setting NEXT_PUBLIC_API_URL switches to direct calls (then the backend must allow this origin via CORS_ORIGINS).
function resolveBaseUrl(): string {
    const explicit = process.env.NEXT_PUBLIC_API_URL?.trim();
    if (explicit) {
        const url = explicit.replace(/\/$/, "");
        return url.endsWith("/api/v1") ? url : `${url}/api/v1`;
    }
    return "/api/v1";
}

export const API_BASE = resolveBaseUrl();

export const api = axios.create({
    baseURL: API_BASE,
    headers: { "Content-Type": "application/json" },
    // Survives a Render free-plan cold start (30-60 s) plus a slow AI turn. (Vercel itself cuts proxied requests at 120 s.)
    timeout: 130_000,
});

/** Links returned by the API (signed file URLs) are relative to the API origin. */
export function resolveApiUrl(path: string): string {
    if (/^https?:\/\//i.test(path)) return path;
    return API_BASE.startsWith("http") ? new URL(path, API_BASE).toString() : path;
}

// ---------------------------------------------------------------------------------------------------------------
// Errors: turn whatever went wrong into something the UI can act on.
// ---------------------------------------------------------------------------------------------------------------
export interface ApiProblem {
    kind: "network" | "timeout" | "http";
    status: number | null;
    /** Machine-readable code from the backend, e.g. "rate_limited", "invalid_session", "ai_unavailable". */
    code: string | null;
    /** Human-readable text that is safe to show to the user. */
    message: string;
    /** Seconds to wait before retrying, if the server said so. */
    retryAfter: number | null;
}

const FRIENDLY: Record<string, (retryAfter: number | null) => string> = {
    rate_limited: (s) => `You're going a little fast. Please wait ${s ? `${s} seconds` : "a moment"} and try again.`,
    busy: () => "I'm still working on your previous message. One moment, please.",
    invalid_session: () => "This reporting session is no longer valid. Nothing you sent was lost on your device, but you'll need to start a new report.",
    message_blocked: () => "I couldn't process that message automatically. Could you try rephrasing it?",
    file_too_large: () => "That file is too large. The limit is 10 MB per file.",
    payload_too_large: () => "That is too large to send. Files are limited to 10 MB.",
    storage_unavailable: () => "File storage is temporarily unavailable. Please try again in a moment.",
    invalid_credentials: () => "That Case ID and Secret Key don't match. Please check both and try again.",
};

interface ErrorBody {
    detail?: unknown;
    code?: string;
    retry_after?: number;
}

export function toApiProblem(error: unknown): ApiProblem {
    if (axios.isAxiosError(error)) {
        const axiosError = error as AxiosError<ErrorBody>;
        if (axiosError.code === "ECONNABORTED" || axiosError.code === "ETIMEDOUT") {
            return {
                kind: "timeout",
                status: null,
                code: null,
                retryAfter: null,
                message: "The server took too long to respond. It may be starting up. Please wait a moment and try again.",
            };
        }
        if (!axiosError.response) {
            return {
                kind: "network",
                status: null,
                code: null,
                retryAfter: null,
                message: "Can't reach the server. Please check your internet connection and try again.",
            };
        }
        const { status, data } = axiosError.response;
        const code = typeof data?.code === "string" ? data.code : null;
        const retryAfter = typeof data?.retry_after === "number" ? data.retry_after : null;
        const detail = typeof data?.detail === "string" ? data.detail : null;
        const message =
            (code && FRIENDLY[code]?.(retryAfter)) ||
            detail ||
            (status >= 500 ? "Something went wrong on our side. Please try again in a moment." : "Something went wrong. Please try again.");
        return { kind: "http", status, code, message, retryAfter };
    }
    return { kind: "network", status: null, code: null, retryAfter: null, message: "Something went wrong. Please try again." };
}
