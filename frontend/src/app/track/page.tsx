"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { ShieldCheck, Lock, Search, AlertCircle, CheckCircle2, ChevronLeft } from "lucide-react";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export default function TrackPage() {
    const [caseId, setCaseId] = useState("");
    const [secretKey, setSecretKey] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<{
        status: string;
        last_updated: string;
        public_update: string | null;
    } | null>(null);

    const handleTrack = async () => {
        if (!caseId.trim() || !secretKey.trim()) {
            setError("Both Case ID and Secret Key are required.");
            return;
        }

        setLoading(true);
        setError(null);
        setResult(null);

        try {
            const response = await fetch(`${API_URL}/public/track`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    case_id: caseId.trim(),
                    secret_key: secretKey.trim()
                })
            });

            if (!response.ok) {
                // Generic error for security
                setError("Invalid Case ID or Secret Key. Please check and try again.");
                return;
            }

            const data = await response.json();
            setResult(data);
        } catch (err) {
            setError("Connection error. Please check your network and try again.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex flex-col items-center justify-center p-8 bg-gradient-to-b from-black to-gray-950">
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="w-full max-w-lg"
            >
                {/* Back Link */}
                <Link
                    href="/"
                    className="text-sm text-white/40 hover:text-white flex items-center gap-1 transition-colors mb-8"
                >
                    <ChevronLeft className="w-4 h-4" />
                    Back to Home
                </Link>

                {/* Title */}
                <div className="text-center mb-10">
                    <div className="w-16 h-16 bg-blue-500/10 rounded-full flex items-center justify-center mx-auto mb-4 border border-blue-500/20">
                        <ShieldCheck className="w-8 h-8 text-blue-400" />
                    </div>
                    <h1 className="text-3xl font-bold text-white mb-2">Track My Case</h1>
                    <p className="text-white/40 text-sm">Enter your Case ID and Secret Key to view your report status.</p>
                </div>

                {/* Form */}
                <div className="bg-white/5 border border-white/10 rounded-3xl p-8 backdrop-blur-xl space-y-6">
                    {/* Case ID Input */}
                    <div>
                        <label className="block text-xs text-white/50 uppercase tracking-wider mb-2">Case ID</label>
                        <input
                            type="text"
                            value={caseId}
                            onChange={(e) => setCaseId(e.target.value.toUpperCase())}
                            placeholder="BCN000000000000"
                            autoComplete="off"
                            className="w-full bg-black/40 border border-white/10 rounded-xl p-4 text-white font-mono placeholder:text-white/20 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 outline-none transition-all"
                        />
                    </div>

                    {/* Secret Key Input */}
                    <div>
                        <label className="block text-xs text-white/50 uppercase tracking-wider mb-2 flex items-center gap-2">
                            Secret Access Key
                            <Lock className="w-3 h-3 text-white/30" />
                        </label>
                        <input
                            type="text"
                            value={secretKey}
                            onChange={(e) => setSecretKey(e.target.value.toUpperCase())}
                            placeholder="XXXX-XXXX-XXXX-XXXX"
                            autoComplete="off"
                            className="w-full bg-black/40 border border-white/10 rounded-xl p-4 text-white font-mono placeholder:text-white/20 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 outline-none transition-all"
                        />
                    </div>

                    {/* Error Message */}
                    {error && (
                        <motion.div
                            initial={{ opacity: 0, y: -5 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="flex items-center gap-3 bg-red-500/10 border border-red-500/20 p-4 rounded-xl"
                        >
                            <AlertCircle className="w-5 h-5 text-red-400 shrink-0" />
                            <p className="text-sm text-red-200/80">{error}</p>
                        </motion.div>
                    )}

                    {/* Track Button */}
                    <button
                        onClick={handleTrack}
                        disabled={loading}
                        className="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold py-4 rounded-xl transition-all flex items-center justify-center gap-3 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {loading ? (
                            <>
                                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                Verifying...
                            </>
                        ) : (
                            <>
                                <Search className="w-5 h-5" />
                                Track Status
                            </>
                        )}
                    </button>
                </div>

                {/* Results */}
                {result && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="mt-8 bg-emerald-900/10 border border-emerald-500/20 rounded-3xl p-8 space-y-6"
                    >
                        <div className="flex items-center gap-3 pb-4 border-b border-emerald-500/10">
                            <CheckCircle2 className="w-6 h-6 text-emerald-400" />
                            <h2 className="text-xl font-semibold text-emerald-200">Case Status</h2>
                        </div>

                        {/* Status */}
                        <div>
                            <p className="text-xs text-white/40 uppercase tracking-wider mb-1">Status</p>
                            <p className="text-lg text-white font-semibold">{result.status}</p>
                        </div>

                        {/* Last Updated */}
                        <div>
                            <p className="text-xs text-white/40 uppercase tracking-wider mb-1">Last Updated</p>
                            <p className="text-white/80 font-mono text-sm">
                                {new Date(result.last_updated).toLocaleString()}
                            </p>
                        </div>

                        {/* Latest Update */}
                        {result.public_update && (
                            <div className="pt-4 border-t border-emerald-500/10">
                                <p className="text-xs text-white/40 uppercase tracking-wider mb-2">Latest Update</p>
                                <p className="text-white/80 leading-relaxed">{result.public_update}</p>
                            </div>
                        )}
                    </motion.div>
                )}

                {/* Footer */}
                <div className="mt-8 flex justify-center">
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/5">
                        <Lock className="w-3 h-3 text-blue-500/50" />
                        <span className="text-[10px] text-white/30 tracking-widest uppercase font-medium">Secure & Anonymous Lookup</span>
                    </div>
                </div>
            </motion.div>
        </div>
    );
}
