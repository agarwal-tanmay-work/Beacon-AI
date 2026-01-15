"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Lock, ArrowRight, ShieldCheck, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";
import { clsx } from "clsx";

export default function LoginPage() {
    const router = useRouter();
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    // Clear any existing session on mount
    useEffect(() => {
        sessionStorage.removeItem("ngo_token");
        sessionStorage.removeItem("ngo_user");
    }, []);

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setLoading(true);

        try {
            const res = await api.post("/admin/auth/login", {
                username,
                password
            });

            // Store session strictly in sessionStorage (Tab Session Only)
            sessionStorage.setItem("ngo_token", res.data.access_token);
            sessionStorage.setItem("ngo_user", JSON.stringify(res.data.user));

            // Redirect to dashboard
            router.push("/");

        } catch (err: unknown) {
            console.error(err);
            // Generic error message as required
            setError("Invalid credentials");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-black text-white flex items-center justify-center p-4 relative overflow-hidden">
            {/* Background Effects */}
            <div className="absolute inset-0 z-0">
                <div className="absolute top-0 left-1/4 w-96 h-96 bg-primary/10 rounded-full blur-[128px] animate-pulse" />
                <div className="absolute bottom-0 right-1/4 w-64 h-64 bg-purple-500/10 rounded-full blur-[100px]" />
            </div>

            <div className="w-full max-w-md bg-zinc-900/50 backdrop-blur-xl border border-white/10 p-8 rounded-2xl shadow-2xl relative z-10">
                <div className="text-center mb-8">
                    <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-primary/20 to-purple-500/20 border border-white/10 mb-4">
                        <ShieldCheck className="w-8 h-8 text-primary" />
                    </div>
                    <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">
                        NGO Portal Access
                    </h1>
                    <p className="text-sm text-muted-foreground mt-2">
                        Authorized personnel only.
                    </p>
                </div>

                <form onSubmit={handleLogin} className="space-y-4">
                    {error && (
                        <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-400">
                            <AlertCircle className="w-4 h-4" />
                            {error}
                        </div>
                    )}

                    <div className="space-y-2">
                        <label className="text-xs font-semibold text-gray-400 uppercase tracking-wider pl-1">
                            Username
                        </label>
                        <input
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            className="w-full bg-black/50 border border-white/10 rounded-lg p-3 text-white placeholder:text-gray-600 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all"
                            placeholder="Enter username"
                            required
                        />
                    </div>

                    <div className="space-y-2">
                        <label className="text-xs font-semibold text-gray-400 uppercase tracking-wider pl-1">
                            Password
                        </label>
                        <input
                            type="password"
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
                            loading && "opacity-70 cursor-not-allowed"
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
        </div>
    );
}
