"use client";

import React from "react";
import * as AccordionPrimitive from "@radix-ui/react-accordion";
import { Plus } from "lucide-react";
import { cn } from "@/lib/utils";

// --- Types ---
interface FAQItem {
    question: string;
    answer: string;
}

interface FAQSectionProps {
    title?: string;
    subtitle?: string;
    description?: string;
    className?: string;
}

// --- Accordion Components ---
const Accordion = AccordionPrimitive.Root;

const AccordionItem = React.forwardRef<
    React.ElementRef<typeof AccordionPrimitive.Item>,
    React.ComponentPropsWithoutRef<typeof AccordionPrimitive.Item>
>(({ className, ...props }, ref) => (
    <AccordionPrimitive.Item
        ref={ref}
        className={cn("border-b border-white/10 last:border-0", className)}
        {...props}
    />
));
AccordionItem.displayName = "AccordionItem";

const AccordionTrigger = React.forwardRef<
    React.ElementRef<typeof AccordionPrimitive.Trigger>,
    React.ComponentPropsWithoutRef<typeof AccordionPrimitive.Trigger>
>(({ className, children, ...props }, ref) => (
    <AccordionPrimitive.Header className="flex">
        <AccordionPrimitive.Trigger
            ref={ref}
            className={cn(
                "flex flex-1 items-center justify-between py-4 font-medium transition-all text-left [&[data-state=open]>svg]:rotate-45",
                "text-white/80 hover:text-white",
                className
            )}
            {...props}
        >
            {children}
            <Plus className="h-4 w-4 shrink-0 transition-transform duration-200" />
        </AccordionPrimitive.Trigger>
    </AccordionPrimitive.Header>
));
AccordionTrigger.displayName = AccordionPrimitive.Trigger.displayName;

const AccordionContent = React.forwardRef<
    React.ElementRef<typeof AccordionPrimitive.Content>,
    React.ComponentPropsWithoutRef<typeof AccordionPrimitive.Content>
>(({ className, children, ...props }, ref) => (
    <AccordionPrimitive.Content
        ref={ref}
        className="overflow-hidden text-sm transition-all data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down"
        {...props}
    >
        <div className={cn("pb-4 pt-0 text-white/60 leading-relaxed", className)}>
            {children}
        </div>
    </AccordionPrimitive.Content>
));
AccordionContent.displayName = AccordionPrimitive.Content.displayName;

// --- Main Component ---
export function FAQSection({
    title = "General Questions",
    subtitle = "Secure & Anonymous",
    description = "Common questions about security, anonymity, and report handling.",
    className,
}: FAQSectionProps) {
    const leftFAQs = [
        {
            question: "How is my anonymity protected?",
            answer: "Beacon AI does not require you to identify yourself. You may submit a report without sharing personal details, and any information you choose to provide remains optional. Identity is never inferred or required to submit or track a case."
        },
        {
            question: "Can I choose what information I share?",
            answer: "Yes. You decide what details to include, how much context to provide, and whether to attach evidence. You remain in control throughout the reporting process and can proceed at your own pace."
        },
        {
            question: "What happens after I submit a report?",
            answer: "After submission, your report is processed as an isolated case. A Case ID and Secret Key are generated immediately. These are required to securely access or track the report in the future."
        }
    ];

    const rightFAQs = [
        {
            question: "How does Beacon AI evaluate reports?",
            answer: "Beacon AI assigns a credibility score based on internal consistency, contextual completeness, and alignment across responses. The system is designed to organize and prioritize reports responsibly, not to judge or reach conclusions."
        },
        {
            question: "Who can access my report?",
            answer: "Only someone with both the Case ID and the Secret Key can access a report. Without both, the report cannot be viewed or retrieved by anyone."
        },
        {
            question: "Is there any public visibility or immediate action?",
            answer: "No. Reports are not made public and do not result in instant outcomes. Beacon AI provides a secure environment to document information responsibly without pressure, exposure, or immediate judgment."
        }
    ];

    return (
        <section className={cn("pt-12 md:pt-24 pb-2 bg-black text-white relative overflow-hidden", className)}>
            <div className="container mx-auto px-4 md:px-6 relative z-10">
                {/* Header */}
                <div className="flex flex-col md:flex-row justify-between items-start md:items-end mb-8 md:mb-16 gap-8">
                    <div className="max-w-2xl">
                        <h3 className="text-secondary-foreground font-semibold mb-2">{subtitle}</h3>
                        <h2 className="text-4xl md:text-5xl font-bold mb-4 tracking-tight">{title}</h2>
                        <p className="text-white/60 text-lg max-w-xl">
                            {description}
                        </p>
                    </div>
                </div>

                {/* FAQ Grid */}
                <div className="grid md:grid-cols-2 gap-8 md:gap-12">
                    {/* Left Column */}
                    <Accordion type="single" collapsible className="w-full">
                        {leftFAQs.map((faq, index) => (
                            <AccordionItem key={`left-${index}`} value={`item-${index}`}>
                                <AccordionTrigger>{faq.question}</AccordionTrigger>
                                <AccordionContent>{faq.answer}</AccordionContent>
                            </AccordionItem>
                        ))}
                    </Accordion>

                    {/* Right Column */}
                    <Accordion type="single" collapsible className="w-full">
                        {rightFAQs.map((faq, index) => (
                            <AccordionItem key={`right-${index}`} value={`item-${index}`}>
                                <AccordionTrigger>{faq.question}</AccordionTrigger>
                                <AccordionContent>{faq.answer}</AccordionContent>
                            </AccordionItem>
                        ))}
                    </Accordion>
                </div>
            </div>
        </section>
    );
}
