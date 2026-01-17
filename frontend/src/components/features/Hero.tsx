"use client";

import React, { useMemo, useState, useEffect } from "react";
import Link from "next/link";
import { InteractiveHoverButton } from "@/components/ui/interactive-hover-button";
import VaporizeTextCycle, { Tag } from "@/components/ui/vapour-text-effect";
import { SparklesCore } from "@/components/ui/sparkles";

export function Hero() {
    const [fontSize, setFontSize] = useState("60px");

    useEffect(() => {
        const handleResize = () => {
            if (window.innerWidth >= 768) {
                setFontSize("140px");
            } else {
                setFontSize("60px");
            }
        };

        // Initial check
        handleResize();

        window.addEventListener("resize", handleResize);
        return () => window.removeEventListener("resize", handleResize);
    }, []);

    return (
        <section className="relative h-screen w-full flex flex-col items-center bg-black overflow-hidden">

            {/* 1️⃣ Beacon AI heading - Refined dominant element 
          Height set to 50vh to place the horizon line exactly in the middle of the screen.
          translate-y-28: Pushing text down significantly to sit just above the horizon line.
      */}
            <div className="relative h-[45vh] md:h-[50vh] w-full flex flex-col items-center justify-end overflow-hidden z-30 pb-0 translate-y-16 md:translate-y-28">
                <VaporizeTextCycle
                    texts={useMemo(() => ["Beacon AI"], [])}
                    font={useMemo(() => ({
                        fontFamily: "Inter, sans-serif",
                        fontSize: fontSize,
                        fontWeight: 800,
                    }), [fontSize])}
                    color="rgba(255, 255, 255, 1)"
                    spread={5}
                    density={5}
                    animation={useMemo(() => ({
                        vaporizeDuration: 3,
                        fadeInDuration: 1,
                        waitDuration: 0.5,
                    }), [])}
                    direction="left-to-right"
                    alignment="center"
                    tag={Tag.H1}
                    mode="continuous"
                />
            </div>

            {/* 2️⃣ Horizon + Sparkles + Content Stack */}
            <div className="w-full relative flex flex-col items-center flex-1">

                {/* Blue Horizon Line - Sharp full-width anchor at mid-screen */}
                <div className="w-full h-px relative z-50">
                    <div className="absolute inset-x-0 top-0 bg-gradient-to-r from-transparent via-indigo-500 to-transparent h-[2px] w-full blur-sm opacity-90" />
                    <div className="absolute inset-x-0 top-0 bg-gradient-to-r from-transparent via-indigo-500 to-transparent h-px w-full" />
                    <div className="absolute inset-x-0 top-0 bg-gradient-to-r from-transparent via-sky-500 to-transparent h-[8px] w-full blur-md opacity-50" />
                    <div className="absolute inset-x-[10%] top-0 bg-gradient-to-r from-transparent via-sky-500 to-transparent h-[12px] w-[80%] blur-xl opacity-30" />
                </div>

                {/* 3️⃣ Sparkle Effect Container - Constrained strictly BELOW the horizon line */}
                <div className="absolute inset-0 z-10 pointer-events-none">
                    <SparklesCore
                        background="transparent"
                        minSize={0.8}
                        maxSize={2.2}
                        particleDensity={400}
                        className="w-full h-full"
                        particleColor="#FFFFFF"
                    />

                    {/* 
              SHARPER CURVED RADIAL MASK
              Using 50% width to create a distinct curve, and 100% height to touch the bottom.
          */}
                    <div className="absolute inset-0 w-full h-full bg-black [mask-image:radial-gradient(ellipse_50%_100%_at_top,transparent_20%,white_100%)]"></div>

                    {/* Minimal bottom fade to ensure the tip is clearly visible at the edge */}
                    <div className="absolute bottom-0 inset-x-0 h-[5vh] bg-gradient-to-t from-black via-black/20 to-transparent z-20"></div>
                </div>

                {/* 4️⃣ Description + CTAs - Positioned within the sparkle field */}
                <div className="relative z-40 flex flex-col items-center pt-12 md:pt-16 space-y-12 text-center max-w-5xl px-6 pb-12">
                    <p className="text-xl md:text-2xl text-white/90 leading-relaxed font-light drop-shadow-[0_0_20px_rgba(0,0,0,1)] tracking-tight">
                        A secure space to report responsibly.
                    </p>

                    <div className="flex flex-wrap items-center justify-center gap-10">
                        <Link href="/report">
                            <InteractiveHoverButton text="Start Report" className="w-[220px] h-14 bg-white text-black hover:bg-white/90 shadow-[0_0_40px_rgba(255,255,255,0.2)] text-xl font-semibold" />
                        </Link>
                        <Link href="/track">
                            <InteractiveHoverButton text="Track Status" className="w-[220px] h-14 bg-white/5 text-white border-white/20 hover:bg-white/20 backdrop-blur-xl text-xl font-semibold transition-all duration-300" />
                        </Link>
                    </div>
                </div>
            </div>

        </section>
    );
}
