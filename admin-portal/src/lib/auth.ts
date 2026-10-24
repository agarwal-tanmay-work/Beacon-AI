// The admin session lives in sessionStorage: it ends when the tab is closed and is never sent anywhere except in the
// Authorization header of calls to the API.
const TOKEN_KEY = "admin_token";
const USER_KEY = "admin_user";

export function getToken(): string | null {
    try {
        return window.sessionStorage.getItem(TOKEN_KEY);
    } catch {
        return null;
    }
}

export function saveSession(token: string, user: unknown): void {
    window.sessionStorage.setItem(TOKEN_KEY, token);
    window.sessionStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession(): void {
    try {
        window.sessionStorage.removeItem(TOKEN_KEY);
        window.sessionStorage.removeItem(USER_KEY);
    } catch {
        /* ignore */
    }
}

/** True when the JWT is missing, malformed or expired (with a 30 s safety margin). */
export function isExpired(token: string | null): boolean {
    if (!token) return true;
    try {
        const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))) as { exp?: number };
        return typeof payload.exp !== "number" || payload.exp * 1000 < Date.now() + 30_000;
    } catch {
        return true;
    }
}
