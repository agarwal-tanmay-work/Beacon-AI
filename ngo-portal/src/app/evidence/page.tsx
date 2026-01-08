"use client";

import { FileText, Lock } from "lucide-react";

export default function EvidenceVault() {
    return (
        <div className="space-y-8">
            <div>
                <h1 className="text-3xl font-bold tracking-tight text-white">Evidence Vault</h1>
                <p className="text-muted-foreground mt-1">Secure storage for encrypted evidence files.</p>
            </div>

            <div className="rounded-xl border border-border bg-card p-12 text-center">
                <div className="flex justify-center mb-6">
                    <div className="h-24 w-24 rounded-full bg-secondary/30 flex items-center justify-center">
                        <Lock className="h-10 w-10 text-muted-foreground" />
                    </div>
                </div>
                <h3 className="text-lg font-medium text-white mb-2">Secure Access Required</h3>
                <p className="text-muted-foreground max-w-md mx-auto mb-6">
                    Access to the evidence vault requires multi-factor authentication.
                    This module is currently being configured for your organization level.
                </p>
                <button className="px-4 py-2 bg-secondary text-white rounded-md hover:bg-secondary/80 transition-colors">
                    Request Access
                </button>
            </div>
        </div>
    );
}
