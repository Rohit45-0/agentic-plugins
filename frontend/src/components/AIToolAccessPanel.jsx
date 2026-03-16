import { useState, useEffect, useCallback, useMemo } from "react";
import {
  ChevronDown,
  Loader2,
  Utensils,
  Scissors,
  Stethoscope,
  ShoppingCart,
  GraduationCap,
  Dumbbell,
  PackageOpen,
  Zap,
  Save,
  MapPin,
  CloudSun,
  BarChart3,
  Receipt,
  Users,
  Calendar,
  Star,
  QrCode,
  CreditCard,
  ClipboardList,
  Eye,
  Search,
  RotateCcw,
  Check,
} from "lucide-react";
import { getAccessToken } from "../services/auth";

const PLUGINS_API = import.meta.env.VITE_PLUGINS_API_URL || "https://web-production-ba9e.up.railway.app";

const VERTICAL_TOOLS = {
  core: {
    label: "Core Booking Tools",
    icon: Calendar,
    color: "from-neutral-700 to-neutral-500",
    tools: [
      { id: "check_available_slots", label: "Check Availability", description: "Let AI check your Google Calendar for free slots", icon: Eye, default: true },
      { id: "book_slot", label: "Instant Booking", description: "Allow AI to book slots into your calendar", icon: Check, default: true },
      { id: "check_customer_bookings", label: "My Bookings", description: "Let customers ask when is my appointment", icon: ClipboardList, default: true },
      { id: "cancel_bookings", label: "Cancellations", description: "Allow customers to cancel their own appointments", icon: Zap, default: false },
    ],
  },
  restaurant: {
    label: "Restaurant / Mess",
    icon: Utensils,
    color: "from-orange-500 to-amber-500",
    tools: [
      { id: "get_menu", label: "Live Menu", description: "Show menu from Google Sheets in real-time", icon: ClipboardList, default: true },
      { id: "check_item_availability", label: "Item Availability", description: "Check if a specific dish is available right now", icon: Check, default: true },
      { id: "create_order", label: "Order Taking", description: "Create and track customer orders automatically", icon: Receipt, default: true },
      { id: "get_order_history", label: "Order History", description: "Let customers reorder with same as last time", icon: BarChart3, default: false },
      { id: "check_weather_and_suggest", label: "Weather Promos", description: "Auto-suggest rain/cold day promotions", icon: CloudSun, default: false },
      { id: "check_delivery_distance", label: "Delivery Distance", description: "Calculate distance and delivery charges", icon: MapPin, default: false },
    ],
  },
  tiffin: {
    label: "Tiffin Service",
    icon: PackageOpen,
    color: "from-green-500 to-emerald-500",
    tools: [
      { id: "get_todays_menu", label: "Today's Menu", description: "Auto-display today's lunch and dinner", icon: ClipboardList, default: true },
      { id: "create_subscription", label: "Subscriptions", description: "Create daily/weekly tiffin subscriptions", icon: Users, default: true },
      { id: "pause_subscription", label: "Pause/Resume", description: "Let customers pause during travel or holidays", icon: Calendar, default: true },
      { id: "resume_subscription", label: "Auto Resume", description: "Automatically resume after pause period ends", icon: Zap, default: true },
      { id: "check_delivery_distance", label: "Delivery Range", description: "Check if address is within delivery area", icon: MapPin, default: false },
    ],
  },
  salon: {
    label: "Salon / Parlour",
    icon: Scissors,
    color: "from-pink-500 to-rose-500",
    tools: [
      { id: "get_salon_slots", label: "Staff Scheduling", description: "Show available slots per staff member", icon: Calendar, default: true },
      { id: "book_salon_appointment", label: "Auto Booking", description: "Book appointments directly from WhatsApp", icon: Check, default: true },
      { id: "get_loyalty_status", label: "Loyalty Program", description: "Track visits, tiers and rewards", icon: Star, default: false },
    ],
  },
  clinic: {
    label: "Doctor / Clinic",
    icon: Stethoscope,
    color: "from-blue-500 to-cyan-500",
    tools: [
      { id: "generate_token", label: "Queue Token", description: "Generate token numbers with estimated wait times", icon: QrCode, default: true },
      { id: "get_queue_status", label: "Live Queue", description: "Show current queue length and active token", icon: Users, default: true },
    ],
  },
  kirana: {
    label: "Kirana / Grocery",
    icon: ShoppingCart,
    color: "from-yellow-500 to-orange-500",
    tools: [
      { id: "search_catalog", label: "Product Search", description: "Search inventory by name with stock info", icon: Eye, default: true },
      { id: "get_udhar_balance", label: "Udhar / Khata", description: "Credit ledger and customer balances", icon: CreditCard, default: true },
      { id: "check_delivery_distance", label: "Home Delivery", description: "Distance and delivery charge estimation", icon: MapPin, default: false },
    ],
  },
  coaching: {
    label: "Coaching / Tuition",
    icon: GraduationCap,
    color: "from-violet-500 to-purple-500",
    tools: [
      { id: "get_attendance_report", label: "Attendance", description: "Monthly attendance reports per student", icon: ClipboardList, default: true },
      { id: "get_pending_fees", label: "Fee Tracking", description: "Show pending fee invoices to parents", icon: Receipt, default: true },
    ],
  },
  gym: {
    label: "Gym / Yoga Studio",
    icon: Dumbbell,
    color: "from-red-500 to-rose-500",
    tools: [
      { id: "check_membership", label: "Membership Status", description: "Show plan, days remaining, and streak", icon: BarChart3, default: true },
      { id: "get_class_schedule", label: "Class Schedule", description: "Upcoming classes with availability", icon: Calendar, default: true },
      { id: "book_class", label: "Class Booking", description: "Book spots with waitlist support", icon: Check, default: false },
    ],
  },
};

function buildDefaultToolsState() {
  const defaults = {};
  Object.values(VERTICAL_TOOLS).forEach((v) => {
    v.tools.forEach((t) => {
      defaults[t.id] = t.default;
    });
  });
  return defaults;
}

function isToolVisible(tool, query, statusFilter, toolStates) {
  const enabled = !!toolStates[tool.id];
  if (statusFilter === "active" && !enabled) return false;
  if (statusFilter === "inactive" && enabled) return false;
  if (!query) return true;
  const haystack = `${tool.label} ${tool.description}`.toLowerCase();
  return haystack.includes(query);
}

function ToolToggle({ tool, enabled, onToggle, accentColor }) {
  const Icon = tool.icon;
  return (
    <div className={`rounded-xl border px-3 py-3 transition-colors ${enabled ? "bg-slate-800/70 border-slate-600/60" : "bg-slate-950/70 border-slate-700/60 hover:border-slate-600/70"}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <div className={`mt-0.5 flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center transition-all duration-200 ${enabled ? `bg-gradient-to-br ${accentColor} text-white shadow-sm` : "bg-slate-800 text-slate-400"}`}>
            <Icon size={14} strokeWidth={2} />
          </div>
          <div className="min-w-0">
            <p className={`text-sm font-semibold ${enabled ? "text-slate-100" : "text-slate-300"}`}>{tool.label}</p>
            <p className="text-xs text-slate-400 leading-relaxed mt-0.5">{tool.description}</p>
          </div>
        </div>
        <button
          type="button"
          id={`tool-toggle-${tool.id}`}
          aria-label={`Toggle ${tool.label}`}
          onClick={() => onToggle(tool.id)}
          className={`relative flex-shrink-0 w-10 h-6 rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60 ${enabled ? "bg-cyan-500" : "bg-slate-500/45"}`}
          role="switch"
          aria-checked={enabled}
        >
          <span className={`absolute top-[2px] left-[2px] w-5 h-5 bg-white rounded-full shadow-sm transition-transform ${enabled ? "translate-x-4" : ""}`} />
        </button>
      </div>
    </div>
  );
}

function VerticalGroup({ verticalKey, vertical, toolStates, onToggle, onToggleAll, searchQuery, statusFilter }) {
  const [expanded, setExpanded] = useState(false);
  const query = searchQuery.trim().toLowerCase();
  const tools = vertical.tools.filter((tool) => isToolVisible(tool, query, statusFilter, toolStates));
  const enabledCount = tools.filter((t) => toolStates[t.id]).length;
  const allVisibleEnabled = tools.length > 0 && tools.every((t) => !!toolStates[t.id]);
  const IconComp = vertical.icon;

  useEffect(() => {
    if (query) setExpanded(true);
  }, [query]);

  if (tools.length === 0) return null;

  return (
    <div className="manager-card !p-0 overflow-hidden border border-slate-700/55">
      <button
        type="button"
        onClick={() => setExpanded((s) => !s)}
        className="w-full flex items-center justify-between px-4 py-3 bg-slate-900/65 hover:bg-slate-900/90 transition-colors"
        aria-label={`Toggle ${vertical.label} tools`}
      >
        <div className="flex items-center gap-3">
          <div className={`w-9 h-9 rounded-lg flex items-center justify-center bg-gradient-to-br ${vertical.color} text-white shadow-sm`}>
            <IconComp size={15} strokeWidth={2} />
          </div>
          <div className="text-left">
            <p className="text-sm font-semibold text-slate-100">{vertical.label}</p>
            <p className="text-xs text-slate-400">{enabledCount}/{tools.length} visible tools active</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-[11px] font-semibold px-2 py-1 rounded-full ${enabledCount > 0 ? "bg-cyan-500/20 text-cyan-200 border border-cyan-400/30" : "bg-slate-700/50 text-slate-300 border border-slate-600/50"}`}>
            {enabledCount} ON
          </span>
          <ChevronDown size={15} className={`text-slate-400 transition-transform ${expanded ? "rotate-180" : ""}`} />
        </div>
      </button>

      <div className={`overflow-hidden transition-all ${expanded ? "max-h-[900px] opacity-100" : "max-h-0 opacity-0"}`}>
        <div className="px-4 pb-4 border-t border-slate-700/55">
          <div className="flex items-center justify-between py-3">
            <p className="manager-label">Toggle visible tools</p>
            <button
              type="button"
              onClick={() => onToggleAll(verticalKey, !allVisibleEnabled, tools.map((t) => t.id))}
              className="btn-secondary-dark !text-xs !py-1.5 !px-2.5"
            >
              {allVisibleEnabled ? "Disable Visible" : "Enable Visible"}
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {tools.map((tool) => (
              <ToolToggle key={tool.id} tool={tool} enabled={!!toolStates[tool.id]} onToggle={onToggle} accentColor={vertical.color} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AIToolAccessPanel() {
  const [toolStates, setToolStates] = useState(() => buildDefaultToolsState());
  const [savedToolStates, setSavedToolStates] = useState(() => buildDefaultToolsState());
  const [loadingPreferences, setLoadingPreferences] = useState(true);
  const [toolsSaving, setToolsSaving] = useState(false);
  const [msg, setMsg] = useState({ text: "", type: "" });
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      setLoadingPreferences(false);
      return;
    }
    fetch(`${PLUGINS_API}/api/v1/whatsapp/tool-preferences`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.data?.enabled_tools && Object.keys(data.data.enabled_tools).length > 0) {
          setToolStates((prev) => ({ ...prev, ...data.data.enabled_tools }));
          setSavedToolStates((prev) => ({ ...prev, ...data.data.enabled_tools }));
        }
      })
      .finally(() => setLoadingPreferences(false));
  }, []);

  const hasUnsavedChanges = useMemo(() => {
    const keys = new Set([...Object.keys(toolStates), ...Object.keys(savedToolStates)]);
    for (const key of keys) {
      if (!!toolStates[key] !== !!savedToolStates[key]) return true;
    }
    return false;
  }, [toolStates, savedToolStates]);

  const handleToolToggle = useCallback((toolId) => {
    setToolStates((prev) => ({ ...prev, [toolId]: !prev[toolId] }));
  }, []);

  const handleToggleAll = useCallback((verticalKey, enable, targetToolIds = null) => {
    setToolStates((prev) => {
      const next = { ...prev };
      const ids = targetToolIds || VERTICAL_TOOLS[verticalKey].tools.map((t) => t.id);
      ids.forEach((id) => {
        next[id] = enable;
      });
      return next;
    });
  }, []);

  const handleReset = useCallback(() => {
    setToolStates({ ...savedToolStates });
    setMsg({ text: "", type: "" });
  }, [savedToolStates]);

  const handleSaveTools = useCallback(async () => {
    setToolsSaving(true);
    setMsg({ text: "", type: "" });
    try {
      const token = getAccessToken();
      const res = await fetch(`${PLUGINS_API}/api/v1/whatsapp/tool-preferences`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ enabled_tools: toolStates }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to save");
      }
      const data = await res.json();
      setSavedToolStates({ ...toolStates });
      setMsg({
        text: `Tool preferences saved. ${data.enabled_count}/${data.total_count} tools active.`,
        type: "success",
      });
    } catch (err) {
      setMsg({ text: err.message || "Failed to save tool preferences", type: "error" });
    } finally {
      setToolsSaving(false);
    }
  }, [toolStates]);

  const query = searchQuery.trim().toLowerCase();
  const visibleVerticalKeys = Object.entries(VERTICAL_TOOLS)
    .filter(([, vertical]) => vertical.tools.some((tool) => isToolVisible(tool, query, statusFilter, toolStates)))
    .map(([key]) => key);

  const visibleToolCount = Object.entries(VERTICAL_TOOLS).reduce((sum, [, vertical]) => {
    return sum + vertical.tools.filter((tool) => isToolVisible(tool, query, statusFilter, toolStates)).length;
  }, 0);
  const activeToolCount = Object.values(toolStates).filter(Boolean).length;
  const totalToolCount = Object.values(VERTICAL_TOOLS).reduce((sum, v) => sum + v.tools.length, 0);

  return (
    <section className="space-y-3">
      <div className="manager-card border border-cyan-400/25">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-500 flex items-center justify-center text-white shadow-sm">
              <Zap size={17} strokeWidth={2} />
            </div>
            <div>
              <h2 className="manager-title">AI Tool Access Studio</h2>
              <p className="manager-subtitle">{activeToolCount} of {totalToolCount} tools active</p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <button type="button" onClick={handleReset} disabled={!hasUnsavedChanges || toolsSaving} className="btn-secondary-dark !text-xs !px-3 !py-2">
              <RotateCcw size={14} />
              Revert
            </button>
            <button type="button" onClick={handleSaveTools} disabled={!hasUnsavedChanges || toolsSaving} className="btn-primary-dark !text-xs !px-3 !py-2">
              {toolsSaving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
              Save Preferences
            </button>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-3 items-center">
          <label className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              aria-label="Search tools"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search tools by name or capability..."
              className="manager-input-dark pl-9"
            />
          </label>
          <div className="flex items-center gap-2">
            {[
              { id: "all", label: "All" },
              { id: "active", label: "Active" },
              { id: "inactive", label: "Inactive" },
            ].map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setStatusFilter(item.id)}
                className={`px-3 py-2 rounded-lg text-xs border transition-colors ${statusFilter === item.id ? "bg-cyan-500/18 text-cyan-100 border-cyan-400/45" : "bg-slate-900/60 text-slate-300 border-slate-600/60 hover:border-slate-500/70"}`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-4 h-1.5 bg-slate-800 rounded-full overflow-hidden">
          <div className="h-full bg-gradient-to-r from-cyan-400 to-blue-400 rounded-full transition-all duration-500" style={{ width: `${(activeToolCount / totalToolCount) * 100}%` }} />
        </div>
      </div>

      {msg.text && (
        <div className={`px-3 py-2 rounded-lg text-sm flex items-center gap-2 ${msg.type === "success" ? "bg-emerald-500/15 text-emerald-200 border border-emerald-400/30" : "bg-red-500/15 text-red-200 border border-red-400/30"}`}>
          {msg.type === "success" && <Check size={14} />}
          {msg.text}
        </div>
      )}

      {loadingPreferences ? (
        <div className="manager-card flex items-center justify-center py-10 text-slate-300">
          <Loader2 size={16} className="animate-spin mr-2" />
          Loading preferences...
        </div>
      ) : visibleVerticalKeys.length === 0 ? (
        <div className="manager-card py-8 text-center">
          <p className="text-slate-200 text-sm font-medium">No tools match this filter.</p>
          <p className="text-slate-400 text-xs mt-1">Try changing status or search query.</p>
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between px-1">
            <p className="text-xs text-slate-400">Showing {visibleVerticalKeys.length} categories / {visibleToolCount} tools</p>
          </div>
          {Object.entries(VERTICAL_TOOLS).map(([key, vertical]) => (
            <VerticalGroup
              key={key}
              verticalKey={key}
              vertical={vertical}
              toolStates={toolStates}
              onToggle={handleToolToggle}
              onToggleAll={handleToggleAll}
              searchQuery={searchQuery}
              statusFilter={statusFilter}
            />
          ))}
        </>
      )}

      {hasUnsavedChanges && (
        <div className="sticky bottom-4 z-20 manager-card border border-cyan-400/35 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <p className="text-sm text-cyan-100">Unsaved changes detected. Save to apply this tool policy to your bot.</p>
          <button type="button" onClick={handleSaveTools} disabled={toolsSaving} className="btn-primary-dark">
            {toolsSaving ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}
            Save Tool Policy
          </button>
        </div>
      )}
    </section>
  );
}
