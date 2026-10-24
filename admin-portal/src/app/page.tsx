"use client";

import { CheckCircle, Clock, FileText } from "lucide-react";
import { ReportsTable } from "@/components/reports/ReportsTable";
import { useReports } from "@/components/reports/useReports";
import { SystemStatusBanner } from "@/components/system/SystemStatusBanner";

export default function Dashboard() {
  const { reports, loading, error } = useReports();
  const count = (status: string) => reports.filter((r) => r.status === status).length;

  const stats = [
    { label: "New Reports", hint: "Awaiting Review", value: count("Pending"), icon: FileText, color: "text-primary" },
    { label: "Ongoing Cases", hint: "In Progress", value: count("Ongoing"), icon: Clock, color: "text-yellow-500" },
    { label: "Completed", hint: "Closed Cases", value: count("Completed"), icon: CheckCircle, color: "text-green-500" },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-white">Dashboard</h1>
        <p className="text-muted-foreground mt-1">Overview of corruption reporting activity.</p>
      </div>

      <SystemStatusBanner />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {stats.map(({ label, hint, value, icon: Icon, color }) => (
          <div key={label} className="rounded-xl border border-border bg-card p-6 shadow-sm">
            <div className="flex items-center justify-between pb-2">
              <h3 className="text-sm font-medium text-muted-foreground">{label}</h3>
              <Icon className={`h-4 w-4 ${color}`} />
            </div>
            <div className="text-2xl font-bold text-white">{loading ? "–" : value}</div>
            <p className={`text-xs mt-1 ${color === "text-primary" ? "text-muted-foreground" : color}`}>{hint}</p>
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="p-6 border-b border-border">
          <h2 className="font-semibold text-white">All Reports</h2>
        </div>
        <ReportsTable reports={reports} loading={loading} error={error} emptyText="No reports found in the system." />
      </div>
    </div>
  );
}
