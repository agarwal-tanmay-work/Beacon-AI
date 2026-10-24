"use client";

import { StatusReportsPage } from "@/components/reports/StatusReportsPage";

export default function CompletedReportsPage() {
    return <StatusReportsPage status="Completed" title="Completed Cases" subtitle="Closed and resolved cases." emptyText="No completed cases." />;
}
