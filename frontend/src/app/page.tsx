import Link from "next/link";
import { Shield, EyeOff, Lock, ArrowRight } from "lucide-react";

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center space-y-12 text-center max-w-4xl">
      {/* Hero */}
      <div className="space-y-6 animate-fade-in">
        <div className="mx-auto w-20 h-20 glass-panel rounded-full flex items-center justify-center mb-8 border-white/20">
          <Shield className="w-10 h-10 text-emerald-400" />
        </div>
        <h1 className="text-6xl font-bold tracking-tighter text-transparent bg-clip-text bg-gradient-to-b from-white to-white/60 neon-text">
          Beacon AI
        </h1>
        <p className="text-xl text-white/70 max-w-2xl mx-auto leading-relaxed">
          The government-grade, anonymous corruption reporting system.
          Powered by advanced AI to protect your identity and ensure justice.
        </p>
      </div>

      {/* Features */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full px-4">
        {[
          {
            icon: <EyeOff className="w-6 h-6 text-blue-400" />,
            title: "100% Anonymous",
            desc: "No personal data collected. Your identity remains hidden forever."
          },
          {
            icon: <Lock className="w-6 h-6 text-purple-400" />,
            title: "End-to-End Encrypted",
            desc: "Military-grade encryption ensures your evidence is secure."
          },
          {
            icon: <Shield className="w-6 h-6 text-emerald-400" />,
            title: "AI Sanitization",
            desc: "Automated PII redaction removes traces before human review."
          }
        ].map((feature, i) => (
          <div key={i} className="glass-panel p-6 rounded-2xl flex flex-col items-center gap-4 hover:bg-white/5 transition-colors">
            <div className="p-3 bg-white/5 rounded-full">{feature.icon}</div>
            <h3 className="font-semibold text-lg">{feature.title}</h3>
            <p className="text-sm text-white/50">{feature.desc}</p>
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="flex flex-col sm:flex-row gap-4 w-full justify-center pt-8">
        <Link href="/report">
          <button className="group relative px-8 py-4 bg-white text-black font-bold rounded-xl hover:bg-white/90 transition-all flex items-center gap-2 text-lg w-full sm:w-auto justify-center shadow-[0_0_20px_rgba(255,255,255,0.3)] hover:shadow-[0_0_30px_rgba(255,255,255,0.5)]">
            Start Secure Report
            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
          </button>
        </Link>
        <button className="px-8 py-4 glass-button text-white font-semibold rounded-xl w-full sm:w-auto hover:bg-white/10">
          Check Status
        </button>
      </div>

      {/* Footer */}
      <div className="absolute bottom-8 text-xs text-white/20 font-mono">
        SECURE CONNECTION • 256-BIT ENCRYPTION • V5.0.0
      </div>
    </div>
  );
}
