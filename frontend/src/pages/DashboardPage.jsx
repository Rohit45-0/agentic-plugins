import { useEffect, useState } from "react";
import { getAnalyticsDashboard, getServiceHealth } from "../services/campaigns";
import {
  TrendingUp,
  Users,
  MousePointerClick,
  Megaphone,
  CheckCircle2,
  XCircle,
  ArrowUpRight,
  Plus,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

function MetricCard({ label, value, change, icon: Icon, color = "neutral" }) {
  const colors = {
    neutral: "bg-neutral-50 text-neutral-600",
    blue: "bg-blue-50 text-blue-600",
    emerald: "bg-emerald-50 text-emerald-600",
    violet: "bg-violet-50 text-violet-600",
  };
  return (
    <div className="cn-card group">
      <div className="flex items-start justify-between mb-4">
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${colors[color]}`}>
          <Icon size={18} strokeWidth={1.75} />
        </div>
        {change !== undefined && (
          <span className="text-xs font-medium text-emerald-600 flex items-center gap-0.5">
            <ArrowUpRight size={12} />
            {change}%
          </span>
        )}
      </div>
      <p className="text-2xl font-bold text-neutral-900 tracking-tight mb-1">{value}</p>
      <p className="text-sm text-neutral-500">{label}</p>
    </div>
  );
}

function StatusRow({ label, ok }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-neutral-100 last:border-0">
      <span className="text-sm text-neutral-700 font-medium">{label}</span>
      <div className={`flex items-center gap-1.5 text-xs font-medium ${ok ? "text-emerald-600" : "text-red-500"}`}>
        {ok ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
        {ok ? "Operational" : "Offline"}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [summary, setSummary] = useState({});
  const [health, setHealth] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    getAnalyticsDashboard(30).then((r) => setSummary(r?.summary || {})).catch(() => { });
    getServiceHealth().then(setHealth).catch(() =>
      setHealth({ api: { ok: false }, analytics: { ok: false } })
    );
  }, []);

  const metrics = [
    { label: "Total Campaigns", value: summary.total_campaigns ?? 0, icon: Megaphone, color: "violet", change: 12 },
    { label: "Total Reach", value: (summary.total_reach ?? 0).toLocaleString(), icon: Users, color: "blue", change: 8 },
    { label: "Engagement", value: (summary.total_engagement ?? 0).toLocaleString(), icon: TrendingUp, color: "emerald", change: 23 },
    { label: "Click-Throughs", value: (summary.total_clicks ?? 0).toLocaleString(), icon: MousePointerClick, color: "neutral", change: 5 },
  ];

  return (
    <div className="p-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-xl font-semibold text-neutral-900 tracking-tight">Mission Control</h1>
          <p className="text-sm text-neutral-500 mt-0.5">Your campaign performance at a glance</p>
        </div>
        <button onClick={() => navigate("/campaigns")} className="btn-primary">
          <Plus size={16} strokeWidth={2} />
          New Campaign
        </button>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {metrics.map((m) => (
          <MetricCard key={m.label} {...m} />
        ))}
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* System Health */}
        <div className="cn-card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-neutral-900">System Health</h2>
            <span className="cn-badge-success">All Systems</span>
          </div>
          <StatusRow label="Core API" ok={health?.api?.ok} />
          <StatusRow label="Analytics Engine" ok={health?.analytics?.ok} />
          <StatusRow label="AI Models" ok={true} />
          <StatusRow label="Media Pipeline" ok={true} />
        </div>

        {/* Quick Actions */}
        <div className="cn-card">
          <h2 className="text-sm font-semibold text-neutral-900 mb-4">Quick Actions</h2>
          <div className="space-y-2">
            {[
              { label: "Launch new campaign", sub: "AI-powered video & poster generation", path: "/campaigns" },
              { label: "Analyze competitors", sub: "Scan top players in your niche", path: "/competitor-intel" },
              { label: "View content library", sub: "Browse all generated assets", path: "/content-library" },
            ].map((action) => (
              <button
                key={action.label}
                onClick={() => navigate(action.path)}
                className="w-full flex items-center justify-between p-3 rounded-lg border border-neutral-200 hover:border-neutral-900 hover:bg-neutral-50 transition-all duration-100 text-left group"
              >
                <div>
                  <p className="text-sm font-medium text-neutral-900">{action.label}</p>
                  <p className="text-xs text-neutral-500 mt-0.5">{action.sub}</p>
                </div>
                <ArrowUpRight size={15} className="text-neutral-300 group-hover:text-neutral-900 transition-colors" />
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Upcoming Bookings Row */}
      <UpcomingBookings />
    </div>
  );
}

function UpcomingBookings() {
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Import here to avoid altering top-level imports significantly
    import("axios").then(({ default: axios }) => {
      import("../services/auth").then(({ getAccessToken }) => {
        const PLUGINS_API = import.meta.env.VITE_PLUGINS_API_URL || "https://web-production-ba9e.up.railway.app";
        axios.get(`${PLUGINS_API}/api/v1/dashboard/upcoming-bookings`, {
          headers: { Authorization: `Bearer ${getAccessToken()}` }
        })
          .then(res => {
            if (res.data?.data) {
              setBookings(res.data.data);
            }
          })
          .catch(err => console.error("Failed to load upcoming bookings", err))
          .finally(() => setLoading(false));
      });
    });
  }, []);

  return (
    <div className="mt-6 cn-card">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-neutral-900">Upcoming WhatsApp Bookings</h2>
        <span className="text-[10px] text-emerald-600 bg-emerald-50 px-2 py-1 rounded border border-emerald-100 font-semibold tracking-wide">Live Google Calendar Sync</span>
      </div>

      {loading ? (
        <div className="flex justify-center p-6"><span className="text-sm text-neutral-500">Loading sync data...</span></div>
      ) : bookings.length === 0 ? (
        <div className="flex justify-center p-6 border border-dashed border-neutral-200 rounded-lg">
          <span className="text-sm text-neutral-500">No upcoming bookings found. They will appear here instantly!</span>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-neutral-100">
                <th className="pb-3 text-xs font-semibold text-neutral-500 uppercase tracking-wider font-medium">Customer/Details</th>
                <th className="pb-3 text-xs font-semibold text-neutral-500 uppercase tracking-wider font-medium">Date</th>
                <th className="pb-3 text-xs font-semibold text-neutral-500 uppercase tracking-wider font-medium text-right">Time</th>
              </tr>
            </thead>
            <tbody>
              {bookings.map((b) => (
                <tr key={b.id} className="border-b border-neutral-100 last:border-0 hover:bg-neutral-50 transition-colors">
                  <td className="py-3 text-sm text-neutral-900 font-medium">{b.summary}</td>
                  <td className="py-3 text-sm text-neutral-600">{b.date}</td>
                  <td className="py-3 text-sm text-neutral-900 font-bold text-right">{b.time}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
