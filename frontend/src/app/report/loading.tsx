import React from "react";
import { Loader2 } from "lucide-react";

export default function Loading() {
    return (
        <div className="w-full h-screen bg-black flex flex-col items-center justify-center space-y-4">
            <div className="relative">
                <div className="w-12 h-12 rounded-full border-2 border-blue-500/20" />
                <Loader2 className="w-12 h-12 text-blue-500 animate-spin absolute inset-0" />
            </div>
            <p className="text-blue-100/40 text-sm font-medium tracking-widest uppercase animate-pulse">
                Initializing Secure Session
            </p>
        </div>
    );
}
