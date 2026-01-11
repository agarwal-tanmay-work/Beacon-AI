"use client";

import React, { useRef } from "react";
import { FireSphere } from "@/components/ui/fire-sphere";
import { SparklesCore } from "@/components/ui/sparkles";
import { FAQSection } from "@/components/ui/faq-section";
import { Hero } from "@/components/features/Hero";

export default function Home() {
  const containerRef = useRef<HTMLDivElement>(null);



  return (
    <div className="w-full relative bg-black text-white selection:bg-purple-500/30 overflow-hidden" ref={containerRef}>

      {/* --- HERO SECTION --- */}
      <Hero />


      {/* --- INTEGRITY / PROCESS SECTION (Was Forensic Verification) --- */}
      <section className="relative w-full py-24 bg-black overflow-hidden">
        <SparklesCore
          id="tsparticlesfull"
          background="transparent"
          minSize={0.6}
          maxSize={1.4}
          particleDensity={50}
          className="absolute inset-0 z-0 opacity-50"
          particleColor="#FFFFFF"
        />

        <div className="container mx-auto px-4 relative z-10 grid md:grid-cols-2 gap-12 items-start">

          {/* Left: Component - Data/Document Verification */}
          <div className="space-y-10">
            <h2 className="text-3xl md:text-[2.5rem] tracking-tight leading-tight font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60">
              How Beacon AI Works
            </h2>

            <div className="space-y-8">
              {/* 1. Optional Identity Disclosure */}
              <div className="space-y-2">
                <h3 className="text-lg font-semibold text-white/90">Optional Identity Disclosure</h3>
                <p className="text-lg text-white/60 leading-relaxed font-light">
                  Users can choose whether to remain anonymous or provide personal details. Identity disclosure is optional and controlled entirely by the reporter.
                </p>
              </div>

              {/* 2. Guided Reporting Flow */}
              <div className="space-y-2">
                <h3 className="text-lg font-semibold text-white/90">Guided Reporting Flow</h3>
                <p className="text-lg text-white/60 leading-relaxed font-light">
                  The system guides users through structured questions, including what happened, a full description, location, time, involved parties, and supporting evidence.
                </p>
              </div>

              {/* 3. Credibility Scoring */}
              <div className="space-y-2">
                <h3 className="text-lg font-semibold text-white/90">Credibility Scoring</h3>
                <p className="text-lg text-white/60 leading-relaxed font-light">
                  Each submission receives a single credibility score generated through AI-based analysis of consistency, context, and completeness across inputs.
                </p>
              </div>

              {/* 4. Case ID & Secret Key */}
              <div className="space-y-2">
                <h3 className="text-lg font-semibold text-white/90">Case ID & Secret Key</h3>
                <p className="text-lg text-white/60 leading-relaxed font-light">
                  After submission, the system generates a unique Case ID and Secret Key, which are required for secure, anonymous case tracking.
                </p>
              </div>
            </div>
          </div>

          {/* Right: Institutional Text */}
          <div className="space-y-10">
            <h2 className="text-3xl md:text-[2.5rem] tracking-tight leading-tight font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60">
              System Evaluation & Safeguards.
            </h2>
            <div className="space-y-8">
              {/* 1. Structured Evaluation Process */}
              <div className="flex flex-col gap-2">
                <h3 className="text-lg font-semibold text-white/90">Structured Evaluation Process</h3>
                <p className="text-lg text-white/60 leading-relaxed font-light">
                  Reports are evaluated across multiple internal AI-driven stages to assess consistency across responses and alignment between narrative and evidence.
                </p>
              </div>

              {/* 2. Independent Case Handling */}
              <div className="flex flex-col gap-2">
                <h3 className="text-lg font-semibold text-white/90">Independent Case Handling</h3>
                <p className="text-lg text-white/60 leading-relaxed font-light">
                  Each report is processed as an isolated case. There is no cross-report linking, profiling, or identity correlation across submissions.
                </p>
              </div>

              {/* 3. Secure Access Control */}
              <div className="flex flex-col gap-2">
                <h3 className="text-lg font-semibold text-white/90">Secure Access Control</h3>
                <p className="text-lg text-white/60 leading-relaxed font-light">
                  Access to any case strictly requires both the Case ID and Secret Key. Without both, case data cannot be retrieved.
                </p>
              </div>

              {/* 4. Purpose of Scoring */}
              <div className="flex flex-col gap-2">
                <h3 className="text-lg font-semibold text-white/90">Purpose of Scoring</h3>
                <p className="text-lg text-white/60 leading-relaxed font-light">
                  The credibility score is used to prioritize and organize reports responsibly. It is not a judgment, verdict, or enforcement action.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* --- TECH CORE --- */}
      <section className="relative w-full min-h-[45vh] bg-black flex flex-col items-center justify-center overflow-hidden py-24">
        {/* Sparkles Background */}
        <SparklesCore
          id="tsparticlescontrol"
          background="transparent"
          minSize={0.6}
          maxSize={1.4}
          particleDensity={40}
          className="absolute inset-0 z-0 opacity-50"
          particleColor="#FFFFFF"
        />

        <div className="absolute inset-0 z-0 opacity-25">
          <FireSphere
            color1={[201, 158, 72]}
            color0={[74, 30, 0]}
            bloomStrength={0.3}
          />
        </div>

        <div className="relative z-10 w-full max-w-3xl mx-auto px-6 text-center space-y-16 pointer-events-none">
          <div className="space-y-6">
            <h2 className="text-3xl md:text-[2.5rem] tracking-tight leading-tight font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60">
              You Are in Control
            </h2>
            <p className="text-lg font-semibold text-white/90">
              A protected space to speak, without pressure or exposure.
            </p>
          </div>

          <div className="space-y-10 flex flex-col items-center justify-center">
            <p className="text-lg text-white/80 leading-relaxed font-normal drop-shadow-lg">
              You are not required to reveal who you are.<br />
              Sharing personal details is optional and always your choice.
            </p>
            <p className="text-lg text-white/80 leading-relaxed font-normal drop-shadow-lg">
              You decide what to say, how much to say, and when to submit.<br />
              There are no public posts and no immediate judgments.
            </p>
            <p className="text-lg text-white/80 leading-relaxed font-normal drop-shadow-lg">
              Each report is handled as an isolated case and can only be accessed using the Case ID and Secret Key generated after submission.
            </p>
            <p className="text-lg text-white/80 leading-relaxed font-normal drop-shadow-lg">
              Beacon AI exists to give you time, privacy, and control when documenting difficult information.
            </p>
          </div>
        </div>
      </section>

      {/* --- FAQ / TRUST --- */}
      <FAQSection />

      {/* --- FOOTER --- */}
      <footer className="w-full py-12 px-6 border-t border-white/10 bg-black/95 backdrop-blur-xl relative z-20">
        <div className="container mx-auto flex flex-col md:flex-row justify-between items-center text-white/30 text-sm">
          <p>&copy; 2026 Beacon AI</p>
          <p className="font-mono mt-4 md:mt-0 opacity-70">Secure. Anonymous. Verified.</p>
        </div>
      </footer>

    </div>
  );
}
