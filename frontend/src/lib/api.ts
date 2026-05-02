import axios from "axios";

// Use a relative base URL so all requests go through the Next.js rewrite proxy
// defined in next.config.ts. This eliminates CORS entirely because the browser
// makes same-origin requests to Vercel, which then proxies to the Render backend.
//
// If NEXT_PUBLIC_API_URL is explicitly set (e.g. for direct-connect dev setups),
// that takes precedence. Otherwise fall back to the relative proxy path.
const getBaseUrl = (): string => {
    const explicit = process.env.NEXT_PUBLIC_API_URL;
    if (explicit) {
        let url = explicit.trim().replace(/\/$/, "");
        if (!url.endsWith("/api/v1")) url += "/api/v1";
        return url;
    }
    // Relative path — works with Next.js rewrites in both dev and prod
    return "/api/v1";
};

export const api = axios.create({
    baseURL: getBaseUrl(),
    headers: {
        "Content-Type": "application/json",
    },
    // 150 s — enough to survive a Render free-plan cold start (~30-60 s)
    timeout: 150000,
});

api.interceptors.request.use((request) => {
    const base = request.baseURL?.replace(/\/$/, "") ?? "";
    const path = request.url?.startsWith("/") ? request.url : `/${request.url ?? ""}`;
    console.log(`[API] ${request.method?.toUpperCase()} ${base}${path}`);
    return request;
});

api.interceptors.response.use(
    (response) => {
        console.log(`[API] ${response.status} ${response.config.url}`);
        return response;
    },
    (error) => {
        const url = error.config?.url ?? "unknown";
        const status = error.response?.status ?? "network error";
        console.error(`[API Error] ${status} ${url}:`, error.message);
        return Promise.reject(error);
    }
);
