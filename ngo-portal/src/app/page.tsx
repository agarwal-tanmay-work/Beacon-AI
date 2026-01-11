"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";
import { AlertCircle, CheckCircle, Clock, FileText, Filter, MoreHorizontal, RefreshCw, XCircle } from "lucide-react";
import { clsx } from "clsx";
import { format } from "date-fns";

// Types matching backend
type ReportStatus = 'NEW' | 'ANALYZING' | 'VERIFIED' | 'IN_REVIEW' | 'ESCALATED' | 'CLOSED' | 'DISMISSED';
type ReportPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

interface Report {
  id: string;
  case_id?: string; // BCN ID
  status: ReportStatus;
  priority: ReportPriority;
  credibility_score?: number;
  created_at: string;
  // ... other fields
}

export default function Dashboard() {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const fetchReports = async () => {
    try {
      const res = await api.get("/admin/reports/");
      setReports(res.data);
      setError(null);
    } catch (err: any) {
      console.error(err);
      // If auth error, handled by interceptor redirecting
      if (err.response?.status !== 401) {
        setError("Failed to load reports. Is the backend running?");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, [router]);

  const getStatusColor = (status: ReportStatus) => {
    switch (status) {
      case 'NEW': return "bg-red-500/10 text-red-500 border-red-500/20";
      case 'ANALYZING': return "bg-yellow-500/10 text-yellow-500 border-yellow-500/20";
      case 'VERIFIED': return "bg-green-500/10 text-green-500 border-green-500/20";
      case 'IN_REVIEW': return "bg-blue-500/10 text-blue-500 border-blue-500/20";
      case 'ESCALATED': return "bg-purple-500/10 text-purple-500 border-purple-500/20";
      case 'CLOSED': return "bg-gray-500/10 text-gray-500 border-gray-500/20";
      case 'DISMISSED': return "bg-gray-500/10 text-gray-500 border-gray-500/20";
      default: return "bg-gray-500/10 text-gray-500";
    }
  }

  const getPriorityColor = (priority: ReportPriority) => {
    switch (priority) {
      case 'CRITICAL': return "text-red-500 font-bold";
      case 'HIGH': return "text-orange-500 font-semibold";
      case 'MEDIUM': return "text-yellow-500";
      case 'LOW': return "text-blue-500";
      default: return "text-gray-500";
    }
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white">Dashboard</h1>
          <p className="text-muted-foreground mt-1">Overview of corruption reporting activity.</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => fetchReports()}
            className="p-2 rounded-md bg-secondary text-muted-foreground hover:text-white hover:bg-white/5 transition-colors"
            title="Refresh"
          >
            <RefreshCw className={clsx("h-5 w-5", loading && "animate-spin")} />
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-md text-sm font-semibold hover:bg-primary/90">
            <Filter className="h-4 w-4" />
            Filter View
          </button>
        </div>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
          <div className="flex items-center justify-between pb-2">
            <h3 className="text-sm font-medium text-muted-foreground">New Reports</h3>
            <FileText className="h-4 w-4 text-primary" />
          </div>
          <div className="text-2xl font-bold text-white">{reports.filter(r => r.status === 'NEW').length}</div>
          <p className="text-xs text-muted-foreground mt-1">+2 from yesterday</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
          <div className="flex items-center justify-between pb-2">
            <h3 className="text-sm font-medium text-muted-foreground">Pending Review</h3>
            <Clock className="h-4 w-4 text-yellow-500" />
          </div>
          <div className="text-2xl font-bold text-white">{reports.filter(r => ['ANALYZING', 'IN_REVIEW'].includes(r.status)).length}</div>
          <p className="text-xs text-muted-foreground mt-1 text-yellow-500">Requires attention</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
          <div className="flex items-center justify-between pb-2">
            <h3 className="text-sm font-medium text-muted-foreground">Actioned Cases</h3>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </div>
          <div className="text-2xl font-bold text-white">{reports.filter(r => ['VERIFIED', 'ESCALATED', 'CLOSED'].includes(r.status)).length}</div>
          <p className="text-xs text-muted-foreground mt-1 text-green-500">12% increase</p>
        </div>
      </div>

      {/* Reports Table */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="p-6 border-b border-border">
          <h3 className="font-semibold text-white">Recent Reports</h3>
        </div>

        {loading ? (
          <div className="p-12 text-center text-muted-foreground">Loading secure data...</div>
        ) : error ? (
          <div className="p-12 text-center text-destructive flex flex-col items-center gap-2">
            <AlertCircle className="h-8 w-8" />
            {error}
          </div>
        ) : reports.length === 0 ? (
          <div className="p-12 text-center text-muted-foreground">No reports found in the system.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-white/5 text-muted-foreground">
                <tr>
                  <th className="px-6 py-3 font-medium">Case ID</th>
                  <th className="px-6 py-3 font-medium">Status</th>
                  <th className="px-6 py-3 font-medium">Priority</th>
                  <th className="px-6 py-3 font-medium">Credibility</th>
                  <th className="px-6 py-3 font-medium">Submitted</th>
                  <th className="px-6 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {reports.map((report) => (
                  <tr
                    key={report.id}
                    className="hover:bg-white/5 transition-colors cursor-pointer"
                    onClick={() => router.push(`/case/${report.id}`)}
                  >
                    <td className="px-6 py-4 font-mono text-white">
                      {report.case_id || report.id.substring(0, 8).toUpperCase() + "..."}
                    </td>
                    <td className="px-6 py-4">
                      <span className={clsx("inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ring-1 ring-inset", getStatusColor(report.status))}>
                        {report.status}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={clsx("text-xs font-medium uppercase", getPriorityColor(report.priority))}>
                        {report.priority}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <div className="h-2 w-16 bg-secondary rounded-full overflow-hidden">
                          <div
                            className={clsx("h-full", report.credibility_score && report.credibility_score > 70 ? "bg-green-500" : "bg-yellow-500")}
                            style={{ width: `${report.credibility_score || 0}%` }}
                          />
                        </div>
                        <span className="text-muted-foreground">{report.credibility_score || 0}%</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-muted-foreground">
                      {format(new Date(report.created_at), 'MMM d, yyyy HH:mm')}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button className="text-muted-foreground hover:text-white">
                        <MoreHorizontal className="h-5 w-5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
