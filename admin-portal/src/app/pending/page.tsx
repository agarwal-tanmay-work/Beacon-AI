"use client";

import { StatusReportsPage } from "@/components/reports/StatusReportsPage";

export default function PendingReportsPage() {
    return <StatusReportsPage status="Pending" title="Pending Reports" subtitle="Cases awaiting initial review." emptyText="No pending reports found." />;
}
