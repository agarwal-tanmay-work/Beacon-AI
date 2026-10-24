"use client";

import { StatusReportsPage } from "@/components/reports/StatusReportsPage";

export default function OngoingReportsPage() {
    return <StatusReportsPage status="Ongoing" title="Ongoing Cases" subtitle="Cases under active investigation." emptyText="No ongoing cases." />;
}
