import axios, { type AxiosError } from "axios";
import { clearSession, getToken } from "@/lib/auth";

function resolveBaseUrl(): string {
    const url = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").trim().replace(/\/$/, "");
    return url.endsWith("/api/v1") ? url : `${url}/api/v1`;
}

export const API_BASE = resolveBaseUrl();

export const api = axios.create({
    baseURL: API_BASE,
    headers: { "Content-Type": "application/json" },
    timeout: 120_000, // covers a Render cold start
});

api.interceptors.request.use((config) => {
    const token = getToken();
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
});

api.interceptors.response.use(
    (response) => response,
    (error: AxiosError) => {
        const isLogin = error.config?.url?.includes("/admin/auth/login");
        if (error.response?.status === 401 && !isLogin && typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
            clearSession();
            window.location.replace("/login?expired=1");
        }
        return Promise.reject(error);
    },
);

/** Signed file links from the API are relative to the API origin. */
export function resolveFileUrl(path: string | null | undefined): string | null {
    if (!path) return null;
    return /^https?:\/\//i.test(path) ? path : new URL(path, API_BASE).toString();
}

/** A short, safe-to-display message for a failed request. */
export function errorMessage(error: unknown, fallback: string): string {
    if (axios.isAxiosError(error)) {
        if (!error.response) return "Can't reach the server. Check your connection and try again.";
        const detail = (error.response.data as { detail?: unknown } | undefined)?.detail;
        if (typeof detail === "string" && detail) return detail;
        if (error.response.status === 429) return "Too many requests. Please wait a moment.";
    }
    return fallback;
}

export function errorCode(error: unknown): string | null {
    if (axios.isAxiosError(error)) {
        const code = (error.response?.data as { code?: unknown } | undefined)?.code;
        return typeof code === "string" ? code : null;
    }
    return null;
}
