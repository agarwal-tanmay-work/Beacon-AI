"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertCircle, ArrowRight, Lock, ShieldCheck } from "lucide-react";
import { clsx } from "clsx";
import { api, errorCode, errorMessage } from "@/lib/api";
import { saveSession } from "@/lib/auth";

function LoginForm() {
    const router = useRouter();
    const expired = useSearchParams().get("expired") === "1";
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState(expired ? "Your session expired. Please sign in again." : "");
    const [loading, setLoading] = useState(false);

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setLoading(true);
        try {
            const { data } = await api.post<{ access_token: string; user: unknown }>("/admin/auth/login", { username, password });
            saveSession(data.access_token, data.user);
            router.replace("/");
        } catch (err) {
            // Wrong credentials stay generic; "locked out" and "not configured" are worth telling the operator about.
            const code = errorCode(err);
            setError(code === "rate_limited" || code === "admin_login_not_configured" ? errorMessage(err, "Sign-in failed.") : "Invalid credentials");
            setPassword("");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="w-full max-w-md bg-zinc-900/50 backdrop-blur-xl border border-white/10 p-8 rounded-2xl shadow-2xl relative z-10">
            <div className="text-center mb-8">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-primary/20 to-purple-500/20 border border-white/10 mb-4">
                    <ShieldCheck className="w-8 h-8 text-primary" />
                </div>
                <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">Admin Portal Access</h1>
                <p className="text-sm text-muted-foreground mt-2">Authorized personnel only.</p>
            </div>

            <form onSubmit={handleLogin} className="space-y-4">
                {error && (
                    <div role="alert" className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-400">
                        <AlertCircle className="w-4 h-4 shrink-0" />
                        {error}
                    </div>
                )}

                <div className="space-y-2">
                    <label htmlFor="username" className="text-xs font-semibold text-gray-400 uppercase tracking-wider pl-1">
                        Username
                    </label>
                    <input
                        id="username"
                        type="text"
                        autoComplete="username"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        className="w-full bg-black/50 border border-white/10 rounded-lg p-3 text-white placeholder:text-gray-600 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all"
                        placeholder="Enter username"
                        required
                    />
                </div>

                <div className="space-y-2">
                    <label htmlFor="password" className="text-xs font-semibold text-gray-400 uppercase tracking-wider pl-1">
                        Password
                    </label>
                    <input
                        id="password"
                        type="password"
                        autoComplete="current-password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        className="w-full bg-black/50 border border-white/10 rounded-lg p-3 text-white placeholder:text-gray-600 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all"
                        placeholder="••••••••"
                        required
                    />
                </div>

                <button
                    type="submit"
                    disabled={loading}
                    className={clsx(
                        "w-full flex items-center justify-center gap-2 py-3 bg-white text-black rounded-lg font-bold hover:bg-gray-200 transition-all active:scale-[0.98] mt-6",
                        loading && "opacity-70 cursor-not-allowed",
                    )}
                >
                    {loading ? "Verifying..." : "Sign In"}
                    {!loading && <ArrowRight className="w-4 h-4" />}
                </button>

                <div className="text-center mt-4">
                    <span className="text-xs text-muted-foreground flex items-center justify-center gap-1">
                        <Lock className="w-3 h-3" /> Secure Session Access
                    </span>
                </div>
            </form>
        </div>
    );
}

export default function LoginPage() {
    return (
        <div className="min-h-screen bg-black text-white flex items-center justify-center p-4 relative overflow-hidden">
            <div className="absolute inset-0 z-0">
                <div className="absolute top-0 left-1/4 w-96 h-96 bg-primary/10 rounded-full blur-[128px] animate-pulse" />
                <div className="absolute bottom-0 right-1/4 w-64 h-64 bg-purple-500/10 rounded-full blur-[100px]" />
            </div>
            <Suspense fallback={null}>
                <LoginForm />
            </Suspense>
        </div>
    );
}
