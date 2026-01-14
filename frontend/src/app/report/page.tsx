"use client";

import React from "react";
import { ChatInterface } from "@/components/features/ChatInterface";
import { SparklesCore } from "@/components/ui/sparkles";
import { FireSphere } from "@/components/ui/fire-sphere";

export default function ReportPage() {
    React.useEffect(() => {
        // Force resize for Three.js initialization
        window.dispatchEvent(new Event('resize'));
    }, []);

    return (
        <div className="w-full h-screen bg-black text-white relative flex flex-col items-center overflow-hidden font-sans selection:bg-blue-500/30">
            {/* Background Sparkles */}
            <div className="absolute inset-0 z-0">
                <SparklesCore
                    id="report-sparkles"
                    background="transparent"
                    minSize={0.6}
                    maxSize={1.4}
                    particleDensity={60}
                    className="w-full h-full"
                    particleColor="#FFFFFF"
                />
            </div>

            {/* Fire Sphere Effect - Grounded at the bottom */}
            <div className="absolute bottom-[-110px] left-0 w-full h-[400px] z-0 opacity-25 pointer-events-none">
                <FireSphere
                    color1={[201, 158, 72]}
                    color0={[74, 30, 0]}
                    bloomStrength={0.3}
                    bloomRadius={0.8}
                />
            </div>


            <div className="relative z-10 w-full flex-1 flex flex-col items-center pt-6 pb-8 px-4 max-w-7xl mx-auto overflow-hidden">
                {/* Header */}
                <div className="text-center mb-2 space-y-2 shrink-0">
                    <h1 className="text-4xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60 drop-shadow-2xl">
                        Submit Report
                    </h1>
                    <div className="h-[2px] w-32 bg-gradient-to-r from-transparent via-blue-600 to-transparent mx-auto my-3 shadow-[0_0_15px_rgba(37,99,235,0.6)]" />
                    <p className="text-blue-100/60 text-base font-normal tracking-wide">
                        Document sensitive information securely and anonymously.
                    </p>
                </div>

                {/* Chat Interface Container */}
                <div className="w-full flex-1 flex flex-col min-h-0">
                    <ChatInterface />
                </div>
            </div>
        </div>
    );
}

