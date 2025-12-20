"use client";

import { useState } from "react";
import { Lock } from "lucide-react";
import { api } from "@/lib/api";
import { useAdminAuth } from "@/lib/auth-context";

export default function LoginPage() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);
    const { login } = useAdminAuth();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setLoading(true);

        try {
            // Must use form-encoded data for OAuth2 spec compliance in backend
            const formData = new FormData();
            formData.append("username", email);
            formData.append("password", password);

            const res = await api.post("/admin/auth/login", formData, {
                headers: { "Content-Type": "application/x-www-form-urlencoded" }
            });

            login(res.data.access_token);
        } catch (err: unknown) {
            const errorMessage = (err as any).response?.data?.detail || "Login failed";
            setError(errorMessage);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col items-center justify-center min-h-[80vh] w-full max-w-md mx-auto p-4">
            <div className="glass-panel w-full p-8 rounded-2xl space-y-8 relative overflow-hidden">
                {/* Decorative background glow */}
                <div className="absolute -top-20 -right-20 w-40 h-40 bg-purple-500/20 rounded-full blur-3xl pointer-events-none" />

                <div className="text-center space-y-2">
                    <div className="mx-auto w-12 h-12 glass-panel rounded-full flex items-center justify-center border-white/10 mb-4">
                        <Lock className="w-6 h-6 text-purple-400" />
                    </div>
                    <h1 className="text-2xl font-bold tracking-tight text-white">Admin Portal</h1>
                    <p className="text-sm text-white/50">Restricted Access Only</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-6">
                    <div className="space-y-2">
                        <label className="text-xs font-mono uppercase text-white/40 ml-1">Email</label>
                        <input
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="w-full glass-input p-3 rounded-xl"
                            required
                        />
                    </div>

                    <div className="space-y-2">
                        <label className="text-xs font-mono uppercase text-white/40 ml-1">Password</label>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            className="w-full glass-input p-3 rounded-xl"
                            required
                        />
                    </div>

                    {error && (
                        <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-200 text-sm text-center">
                            {error}
                        </div>
                    )}

                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full py-3 glass-button rounded-xl text-white font-semibold flex items-center justify-center gap-2 hover:bg-white/10"
                    >
                        {loading ? "Authenticating..." : "Sign In"}
                    </button>
                </form>
            </div>
        </div>
    );
}
