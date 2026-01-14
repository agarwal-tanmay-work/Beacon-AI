import React from "react";
import { Loader2 } from "lucide-react";

export default function Loading() {
    return (
        <div className="w-full h-screen bg-black flex flex-col items-center justify-center space-y-4">
            <div className="relative">
                <div className="w-12 h-12 rounded-full border-2 border-white/10" />
                <Loader2 className="w-12 h-12 text-white/40 animate-spin absolute inset-0" />
            </div>
            <p className="text-white/20 text-sm font-medium tracking-widest uppercase animate-pulse">
                Preparing Tracking Interface
            </p>
        </div>
    );
}
