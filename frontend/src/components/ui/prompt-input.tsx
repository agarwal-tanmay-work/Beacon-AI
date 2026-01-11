"use client";

import React, { createContext, useContext, useEffect, useState, useRef, useCallback, memo, useMemo } from "react";
import { Plus, Send, Paperclip, ShieldCheck, Zap, Search, Layout } from "lucide-react";
import { cn } from "@/lib/utils";

// ===== TYPES =====

type MenuOption = "Standard" | "Forensic" | "Search" | "Priority";

interface RippleEffect {
    x: number;
    y: number;
    id: number;
}

interface Position {
    x: number;
    y: number;
}

interface ChatInputProps {
    placeholder?: string;
    onSubmit?: (value: string) => void;
    onUpload?: () => void;
    disabled?: boolean;
    glowIntensity?: number;
    expandOnFocus?: boolean;
    animationDuration?: number;
    textColor?: string;
    backgroundOpacity?: number;
    showEffects?: boolean;
    menuOptions?: MenuOption[];
}

// ===== CONTEXT =====

interface ChatInputContextProps {
    mousePosition: Position;
    ripples: RippleEffect[];
    addRipple: (x: number, y: number) => void;
    animationDuration: number;
    glowIntensity: number;
    textColor: string;
    showEffects: boolean;
}

const ChatInputContext = createContext<ChatInputContextProps | undefined>(undefined);

function useChatInputContext() {
    const context = useContext(ChatInputContext);
    if (context === undefined) {
        throw new Error("useChatInputContext must be used within a ChatInputProvider");
    }
    return context;
}

// ===== COMPONENTS =====

const GlowEffects = memo(({
    glowIntensity,
    mousePosition,
    animationDuration,
    enabled
}: {
    glowIntensity: number;
    mousePosition: Position;
    animationDuration: number;
    enabled: boolean;
}) => {
    if (!enabled) return null;

    return (
        <>
            <div className="absolute inset-0 bg-gradient-to-r from-white/5 via-white/8 to-white/5 backdrop-blur-2xl rounded-3xl" />

            <div
                className="absolute inset-0 rounded-3xl opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity duration-500 pointer-events-none"
                style={{
                    boxShadow: `
            0 0 0 1px rgba(16, 185, 129, ${0.1 * glowIntensity}),
            0 0 8px rgba(16, 185, 129, ${0.15 * glowIntensity}),
            0 0 16px rgba(59, 130, 246, ${0.1 * glowIntensity})
          `,
                    filter: 'blur(0.5px)',
                }}
            />

            <div
                className="absolute inset-0 rounded-3xl opacity-0 group-hover:opacity-30 transition-opacity duration-300 pointer-events-none blur-sm"
                style={{
                    background: `radial-gradient(circle 120px at ${mousePosition.x}% ${mousePosition.y}%, rgba(16,185,129,0.1) 0%, rgba(59,130,246,0.05) 60%, transparent 100%)`,
                }}
            />
        </>
    );
});

const RippleEffects = memo(({ ripples, enabled }: { ripples: RippleEffect[]; enabled: boolean }) => {
    if (!enabled || ripples.length === 0) return null;

    return (
        <>
            {ripples.map((ripple) => (
                <div
                    key={ripple.id}
                    className="absolute pointer-events-none blur-sm"
                    style={{
                        left: ripple.x - 25,
                        top: ripple.y - 25,
                        width: 50,
                        height: 50,
                    }}
                >
                    <div className="w-full h-full rounded-full bg-emerald-500/20 animate-ping" />
                </div>
            ))}
        </>
    );
});

const OptionIcon = ({ option }: { option: MenuOption }) => {
    switch (option) {
        case "Standard": return <Zap className="w-3 h-3" />;
        case "Forensic": return <ShieldCheck className="w-3 h-3" />;
        case "Search": return <Search className="w-3 h-3" />;
        case "Priority": return <Layout className="w-3 h-3" />;
        default: return null;
    }
}

export default function PromptInput({
    placeholder = "Secure message...",
    onSubmit,
    onUpload,
    disabled = false,
    glowIntensity = 0.6,
    expandOnFocus = true,
    animationDuration = 500,
    textColor = "#FFFFFF",
    backgroundOpacity = 0.05,
    showEffects = true,
    menuOptions = ["Standard", "Forensic", "Search", "Priority"] as MenuOption[]
}: ChatInputProps) {
    const [value, setValue] = useState("");
    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const [selectedOptions, setSelectedOptions] = useState<MenuOption[]>(["Standard"]);
    const [ripples, setRipples] = useState<RippleEffect[]>([]);
    const [mousePosition, setMousePosition] = useState<Position>({ x: 50, y: 50 });

    const containerRef = useRef<HTMLDivElement | null>(null);
    const menuRef = useRef<HTMLDivElement | null>(null);
    const textareaRef = useRef<HTMLTextAreaElement | null>(null);
    const throttleRef = useRef<number | null>(null);

    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setIsMenuOpen(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = "auto";
            textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
        }
    }, [value]);

    const handleSubmit = useCallback(
        (e?: React.FormEvent) => {
            e?.preventDefault();
            if (value.trim() && onSubmit && !disabled) {
                onSubmit(value.trim());
                setValue("");
            }
        },
        [value, onSubmit, disabled]
    );

    const handleKeyDown = useCallback(
        (e: React.KeyboardEvent) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
            }
        },
        [handleSubmit]
    );

    const handleMouseMove = useCallback((e: React.MouseEvent) => {
        if (!showEffects) return;
        if (containerRef.current && !throttleRef.current) {
            throttleRef.current = window.setTimeout(() => {
                const rect = containerRef.current?.getBoundingClientRect();
                if (rect) {
                    const x = ((e.clientX - rect.left) / rect.width) * 100;
                    const y = ((e.clientY - rect.top) / rect.height) * 100;
                    setMousePosition({ x, y });
                }
                throttleRef.current = null;
            }, 50);
        }
    }, [showEffects]);

    const addRipple = useCallback((x: number, y: number) => {
        if (!showEffects) return;
        const newRipple: RippleEffect = { x, y, id: Date.now() };
        setRipples(prev => [...prev.slice(-5), newRipple]);
        setTimeout(() => {
            setRipples(prev => prev.filter(ripple => ripple.id !== newRipple.id));
        }, 600);
    }, [showEffects]);

    const handleClick = useCallback((e: React.MouseEvent) => {
        if (containerRef.current) {
            const rect = containerRef.current.getBoundingClientRect();
            addRipple(e.clientX - rect.left, e.clientY - rect.top);
        }
    }, [addRipple]);

    const isSubmitDisabled = disabled || !value.trim();

    return (
        <div className="w-full max-w-4xl mx-auto px-4 py-4">
            <form
                onSubmit={handleSubmit}
                className={cn(
                    "relative group transition-all duration-500 ease-out",
                    "w-full rounded-3xl"
                )}
            >
                <div
                    ref={containerRef}
                    onMouseMove={handleMouseMove}
                    onClick={handleClick}
                    className={cn(
                        "relative flex flex-col w-full bg-white/5 backdrop-blur-2xl border border-white/10 rounded-3xl p-3 transition-all duration-300",
                        "hover:bg-white/10 hover:border-white/20 shadow-2xl"
                    )}
                >
                    <GlowEffects
                        glowIntensity={glowIntensity}
                        mousePosition={mousePosition}
                        animationDuration={animationDuration}
                        enabled={showEffects}
                    />
                    <RippleEffects ripples={ripples} enabled={showEffects} />

                    <div className="flex items-end gap-3 relative z-20">
                        <button
                            type="button"
                            onClick={onUpload}
                            className="p-3 rounded-2xl bg-white/5 hover:bg-white/10 text-white/40 hover:text-white transition-all flex items-center justify-center border border-white/5"
                            title="Upload Evidence"
                        >
                            <Paperclip className="w-5 h-5" />
                        </button>

                        <div className="flex-1 relative min-h-[52px] flex items-center">
                            <textarea
                                ref={textareaRef}
                                value={value}
                                onChange={(e) => setValue(e.target.value)}
                                onKeyDown={handleKeyDown}
                                placeholder={placeholder}
                                rows={1}
                                className="w-full bg-transparent text-white placeholder:text-white/20 border-none outline-none resize-none py-3 text-base leading-relaxed"
                                disabled={disabled}
                            />
                        </div>

                        <button
                            type="submit"
                            disabled={isSubmitDisabled}
                            className={cn(
                                "p-3 rounded-2xl transition-all flex items-center justify-center",
                                isSubmitDisabled
                                    ? "bg-white/5 text-white/10 cursor-not-allowed"
                                    : "bg-emerald-500 text-black hover:bg-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.3)]"
                            )}
                        >
                            <Send className="w-5 h-5" />
                        </button>
                    </div>

                    <div className="flex items-center gap-2 mt-3 px-1 relative z-20">
                        {menuOptions.map((opt) => (
                            <button
                                key={opt}
                                type="button"
                                onClick={() => setSelectedOptions([opt])}
                                className={cn(
                                    "flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[10px] font-mono uppercase tracking-wider transition-all border",
                                    selectedOptions.includes(opt)
                                        ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                                        : "bg-white/5 border-white/5 text-white/20 hover:text-white/40"
                                )}
                            >
                                <OptionIcon option={opt} />
                                {opt}
                            </button>
                        ))}

                        <div className="ml-auto flex items-center gap-2 text-[10px] text-white/20 font-mono">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                            ENCRYPTED TUNNEL
                        </div>
                    </div>
                </div>
            </form>
        </div>
    );
}
