"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Shield, Lock, AlertCircle } from "lucide-react";
import { clsx } from "clsx";

export default function LoginPage() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const router = useRouter();

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);

        try {
            // OAuth2PasswordRequestForm expects form-data
            const formData = new FormData();
            formData.append("username", email);
            formData.append("password", password);

            const response = await api.post("/admin/auth/login", formData, {
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded", // Axios handles FormData usually, but being explicit.
                    // actually for FormData axios handles it, but OAuth2 spec expects form-urlencoded if sending string body, 
                    // or multipart if using FormData. Fastapi accepts both usually if Form(...) is used.
                    // Depends() with OAuth2PasswordRequestForm expects form-data.
                },
            });

            const { access_token } = response.data;
            localStorage.setItem("token", access_token);
            router.push("/");
        } catch (err: any) {
            console.error(err);
            setError(err.response?.data?.detail || "Invalid email or password");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4">
            {/* Background blobs for aesthetics */}
            <div className="absolute top-0 -left-4 w-72 h-72 bg-primary/10 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob"></div>
            <div className="absolute top-0 -right-4 w-72 h-72 bg-accent/10 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000"></div>

            <div className="w-full max-w-md space-y-8 relative z-10 bg-card p-8 rounded-xl border border-border shadow-2xl">
                <div className="flex flex-col items-center">
                    <div className="rounded-full bg-primary/10 p-4 ring-1 ring-primary/20 mb-4">
                        <Shield className="h-10 w-10 text-primary" />
                    </div>
                    <h2 className="text-3xl font-bold tracking-tight text-white mb-2">NGO Portal</h2>
                    <p className="text-sm text-muted-foreground">Authorized Personnel Only</p>
                </div>

                <form className="mt-8 space-y-6" onSubmit={handleLogin}>
                    {error && (
                        <div className="rounded-md bg-destructive/10 p-3 flex items-center gap-3 border border-destructive/20">
                            <AlertCircle className="h-5 w-5 text-destructive" />
                            <p className="text-sm text-destructive">{error}</p>
                        </div>
                    )}

                    <div className="space-y-4">
                        <div>
                            <label htmlFor="email" className="block text-sm font-medium leading-6 text-gray-200">
                                Email Address
                            </label>
                            <div className="mt-1">
                                <input
                                    id="email"
                                    name="email"
                                    type="email"
                                    required
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    className="block w-full rounded-md border-0 bg-secondary py-2 text-white shadow-sm ring-1 ring-inset ring-white/10 focus:ring-2 focus:ring-inset focus:ring-primary sm:text-sm sm:leading-6 px-3"
                                    placeholder="admin@beacon.gov"
                                />
                            </div>
                        </div>

                        <div>
                            <label htmlFor="password" className="block text-sm font-medium leading-6 text-gray-200">
                                Password
                            </label>
                            <div className="mt-1 relative">
                                <input
                                    id="password"
                                    name="password"
                                    type="password"
                                    required
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="block w-full rounded-md border-0 bg-secondary py-2 text-white shadow-sm ring-1 ring-inset ring-white/10 focus:ring-2 focus:ring-inset focus:ring-primary sm:text-sm sm:leading-6 px-3"
                                    placeholder="••••••••"
                                />
                            </div>
                        </div>
                    </div>

                    <div>
                        <button
                            type="submit"
                            disabled={loading}
                            className={clsx(
                                "flex w-full justify-center rounded-md bg-primary px-3 py-2 text-sm font-semibold leading-6 text-white shadow-sm hover:bg-primary/90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-all items-center gap-2",
                                loading && "opacity-70 cursor-not-allowed"
                            )}
                        >
                            {loading ? "Authenticating..." : (
                                <>
                                    <Lock className="h-4 w-4" />
                                    Sign In
                                </>
                            )}
                        </button>
                    </div>
                </form>
            </div>
            <div className="mt-8 text-center text-xs text-muted-foreground">
                <p>Restricted Access System. All activities are monitored.</p>
                <p>&copy; 2025 Beacon AI. Secured by End-to-End Encryption.</p>
            </div>
        </div>
    );
}
