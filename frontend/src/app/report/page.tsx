"use client";

import React, { useMemo } from "react";
import { ChatInterface } from "@/components/features/ChatInterface";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { SparklesCore } from "@/components/ui/sparkles";
import VaporizeTextCycle, { Tag } from "@/components/ui/vapour-text-effect";

export default function ReportPage() {
    return (
        <div className="w-full min-h-screen bg-black text-white selection:bg-purple-500/30 relative flex flex-col items-center overflow-hidden">
            {/* Background Sparkles */}
            <div className="absolute inset-0 z-0">
                <SparklesCore
                    id="report-sparkles"
                    background="transparent"
                    minSize={0.4}
                    maxSize={1.2}
                    particleDensity={30}
                    className="w-full h-full"
                    particleColor="#FFFFFF"
                />
            </div>

            <div className="relative z-10 w-full flex flex-col items-center gap-6 py-12 px-4">
                {/* Header / Navigation */}
                <div className="w-full max-w-4xl flex items-center justify-between mb-4">
                    <Link
                        href="/"
                        className="group text-sm text-white/50 hover:text-white flex items-center gap-1 transition-all duration-300 bg-white/5 px-4 py-2 rounded-full border border-white/10 hover:border-white/20"
                    >
                        <ChevronLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
                        <span>Return to Safety</span>
                    </Link>

                    <div className="hidden md:flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 text-[10px] text-white/40 font-mono tracking-widest uppercase">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                        Direct Secure Uplink
                    </div>
                </div>

                {/* Title Section */}
                <div className="flex flex-col items-center justify-center mb-4">
                    <div className="relative h-24 md:h-32 w-full flex flex-col items-center justify-center overflow-hidden rounded-md">
                        <VaporizeTextCycle
                            texts={useMemo(() => ["SECURE REPORTING"], [])}
                            font={useMemo(() => ({
                                fontFamily: "Inter, sans-serif",
                                fontSize: "48px",
                                fontWeight: 800,
                            }), [])}
                            color="rgba(255, 255, 255, 1)"
                            spread={3}
                            density={3}
                            animation={useMemo(() => ({
                                vaporizeDuration: 2,
                                fadeInDuration: 1,
                                waitDuration: 0.5,
                            }), [])}
                            direction="left-to-right"
                            alignment="center"
                            tag={Tag.H1}
                            mode="continuous"
                        />
                    </div>

                    {/* Subtle underline gradient */}
                    <div className="w-64 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent mt-[-10px]" />
                </div>

                {/* Chat Interface Container */}
                <div className="w-full max-w-5xl flex justify-center">
                    <ChatInterface />
                </div>

                {/* Footer Warning */}
                <div className="mt-8 flex flex-col items-center gap-4">
                    <p className="text-xs text-center text-white/30 max-w-md leading-relaxed">
                        Do not close this window until you receive your secure <span className="text-white/60 font-semibold tracking-tight">Access Token</span>.
                        <br />
                        History is not saved on this device. Logs are wiped upon session termination.
                    </p>

                    <div className="w-full h-px bg-gradient-to-r from-transparent via-white/5 to-transparent mt-4" />

                    <div className="flex items-center gap-6 text-[10px] text-white/20 font-mono uppercase tracking-[0.2em]">
                        <span>AES-256</span>
                        <span>End-to-End</span>
                        <span>Zero-Knowledge</span>
                    </div>
                </div>
            </div>
        </div>
    );
}

