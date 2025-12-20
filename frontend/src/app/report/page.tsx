import { ChatInterface } from "@/components/features/ChatInterface";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";

export default function ReportPage() {
    return (
        <div className="w-full flex flex-col items-center gap-6">
            <div className="self-start w-full max-w-2xl mx-auto">
                <Link
                    href="/"
                    className="text-sm text-white/50 hover:text-white flex items-center gap-1 transition-colors pl-2"
                >
                    <ChevronLeft className="w-4 h-4" />
                    Back to Safety
                </Link>
            </div>

            <ChatInterface />

            <p className="text-xs text-center text-white/20 max-w-md">
                Do not close this window until you receive your secure Access Token.
                History is not saved on this device.
            </p>
        </div>
    );
}
