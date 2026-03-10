import { useState } from "react";
import {
  BarChart2,
  TrendingUp,
  TrendingDown,
  Users,
  Heart,
  Eye,
  MousePointerClick,
  Youtube,
  Link2,
  FileText,
  Zap,
  ChevronDown,
  Instagram,
  Twitter,
  Linkedin,
  Plus,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
} from "lucide-react";
import clsx from "clsx";
import { getFacebookLoginUrl } from "../services/auth";

// ─── Mock Data ────────────────────────────────────────────────────────────────
const postMetrics = [
  { label: "Total Reach", value: "124.3K", change: +18.4, icon: Eye },
  { label: "Engagement Rate", value: "6.2%", change: +2.1, icon: Heart },
  { label: "Click-Throughs", value: "3,841", change: -4.3, icon: MousePointerClick },
  { label: "Followers Gained", value: "+892", change: +31.0, icon: Users },
];

const posts = [
  { platform: "instagram", title: "Red Chili Sauce Launch Reel", reach: "42.1K", eng: "8.4%", clicks: 1240, status: "published" },
  { platform: "linkedin", title: "Brand Story: From Farm to Table", reach: "18.7K", eng: "4.1%", clicks: 560, status: "published" },
  { platform: "twitter", title: "Spice Up Your Life — Thread", reach: "31.2K", eng: "5.9%", clicks: 890, status: "published" },
  { platform: "instagram", title: "Behind the Scenes — Production", reach: "22.4K", eng: "7.2%", clicks: 740, status: "scheduled" },
];

const refSources = [
  {
    type: "youtube",
    title: "How Hot Sauce Brands Win on Social Media",
    source: "youtube.com",
    url: "#",
    insights: ["Strong hook in first 3s", "Uses contrast lighting", "CTA at 80% mark"],
    score: 87,
  },
  {
    type: "youtube",
    title: "Viral Food Brand Marketing Strategies 2024",
    source: "youtube.com",
    url: "#",
    insights: ["Emotional storytelling", "User-generated content", "Trending audio"],
    score: 74,
  },
  {
    type: "article",
    title: "Competitor Analysis: Tabasco vs Cholula",
    source: "marketingweek.com",
    url: "#",
    insights: ["Price anchoring", "Heritage narrative", "Limited edition drops"],
    score: 68,
  },
  {
    type: "article",
    title: "How to Write Hooks That Stop the Scroll",
    source: "hubspot.com",
    url: "#",
    insights: ["Question-based hooks", "Shock stat openers", "Relatable pain points"],
    score: 91,
  },
];

const hookComparisons = [
  {
    ours: "🔥 This chili sauce will change your life forever",
    competitor: "The #1 hot sauce trusted by chefs worldwide",
    ourScore: 72,
    theirScore: 85,
    verdict: "competitor",
    tip: "Add social proof or a specific claim — 'trusted by chefs' outperforms vague superlatives.",
  },
  {
    ours: "Made from 100% organic chilies, harvested by hand",
    competitor: "Warning: Not for the faint-hearted 🌶️",
    ourScore: 68,
    theirScore: 79,
    verdict: "competitor",
    tip: "Emotional/curiosity hooks outperform feature-based hooks. Lead with the feeling, not the ingredient.",
  },
  {
    ours: "What if your hot sauce could actually make you healthier?",
    competitor: "New flavor. Same heat. Zero compromise.",
    ourScore: 88,
    theirScore: 71,
    verdict: "ours",
    tip: "Great! Question-based hooks with a surprising claim consistently drive higher engagement.",
  },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────
const platformIcon = { instagram: Instagram, twitter: Twitter, linkedin: Linkedin };
const platformColor = {
  instagram: "text-pink-500",
  twitter: "text-sky-500",
  linkedin: "text-blue-600",
};

function ChangeChip({ value }) {
  const up = value > 0;
  const flat = value === 0;
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-0.5 text-xs font-semibold px-2 py-0.5 rounded-full",
        up ? "bg-emerald-50 text-emerald-600" : flat ? "bg-neutral-100 text-neutral-500" : "bg-red-50 text-red-500"
      )}
    >
      {up ? <ArrowUpRight size={11} /> : flat ? <Minus size={11} /> : <ArrowDownRight size={11} />}
      {Math.abs(value)}%
    </span>
  );
}

function ScoreBar({ score, color = "bg-neutral-900" }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-neutral-100 rounded-full overflow-hidden">
        <div className={clsx("h-full rounded-full transition-all duration-500", color)} style={{ width: `${score}%` }} />
      </div>
      <span className="text-xs font-bold text-neutral-700 w-7 text-right">{score}</span>
    </div>
  );
}

// ─── Tabs ─────────────────────────────────────────────────────────────────────
const TABS = [
  { id: "posts", label: "Post Analytics", icon: BarChart2 },
  { id: "reference", label: "Reference Content", icon: Youtube },
  { id: "hooks", label: "Hook Comparison", icon: Zap },
];

export default function AnalyticsPage() {
  const [tab, setTab] = useState("posts");
  const [period, setPeriod] = useState("30");
  const [connecting, setConnecting] = useState(false);

  const handleConnect = async () => {
    try {
      setConnecting(true);
      const data = await getFacebookLoginUrl();
      if (data && data.login_url) {
        window.location.href = data.login_url;
      } else {
        setConnecting(false);
      }
    } catch (err) {
      alert("Failed to get connection URL: " + err.message);
      setConnecting(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-50 p-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">Analytics</h1>
          <p className="text-sm text-neutral-500 mt-0.5">
            Track performance, reference content, and strategy insights
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="text-sm border border-neutral-200 rounded-lg px-3 py-2 bg-white text-neutral-700 outline-none cursor-pointer"
          >
            <option value="7">Last 7 days</option>
            <option value="30">Last 30 days</option>
            <option value="90">Last 90 days</option>
          </select>
        </div>
      </div>

      {/* Tab Nav */}
      <div className="flex gap-1 bg-white border border-neutral-200 rounded-xl p-1 mb-6 w-fit">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={clsx(
              "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-150",
              tab === id
                ? "bg-neutral-900 text-white shadow-sm"
                : "text-neutral-500 hover:text-neutral-900 hover:bg-neutral-50"
            )}
          >
            <Icon size={15} strokeWidth={1.75} />
            {label}
          </button>
        ))}
      </div>

      {/* ── TAB 1: POST ANALYTICS ── */}
      {tab === "posts" && (
        <div className="space-y-6 animate-fade-in">
          {/* Connect Account Banner */}
          <div className="bg-gradient-to-r from-neutral-900 to-neutral-700 rounded-2xl p-5 flex items-center justify-between">
            <div>
              <p className="text-white font-semibold text-base mb-1">Connect your social accounts</p>
              <p className="text-neutral-400 text-sm">
                Link Instagram, LinkedIn, or Twitter to pull real post metrics automatically.
              </p>
            </div>
            <button
              onClick={handleConnect}
              disabled={connecting}
              className="flex items-center gap-2 bg-white text-neutral-900 text-sm font-semibold px-4 py-2.5 rounded-xl hover:bg-neutral-100 transition-colors flex-shrink-0 disabled:opacity-75 disabled:cursor-not-allowed"
            >
              <Plus size={15} className={connecting ? "animate-spin" : ""} />
              {connecting ? "Connecting..." : "Connect Account"}
            </button>
          </div>

          {/* Metric Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {postMetrics.map(({ label, value, change, icon: Icon }) => (
              <div key={label} className="bg-white border border-neutral-200 rounded-2xl p-5">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-medium text-neutral-500">{label}</span>
                  <Icon size={16} className="text-neutral-400" strokeWidth={1.75} />
                </div>
                <p className="text-2xl font-bold text-neutral-900 mb-2">{value}</p>
                <ChangeChip value={change} />
              </div>
            ))}
          </div>

          {/* Posts Table */}
          <div className="bg-white border border-neutral-200 rounded-2xl overflow-hidden">
            <div className="px-5 py-4 border-b border-neutral-100">
              <h2 className="text-sm font-semibold text-neutral-900">Published Posts</h2>
            </div>
            <div className="divide-y divide-neutral-100">
              {posts.map((p, i) => {
                const PIcon = platformIcon[p.platform];
                return (
                  <div key={i} className="flex items-center gap-4 px-5 py-4 hover:bg-neutral-50 transition-colors">
                    <PIcon size={18} className={platformColor[p.platform]} strokeWidth={1.75} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-neutral-900 truncate">{p.title}</p>
                      <span className={clsx(
                        "text-xs font-medium px-2 py-0.5 rounded-full",
                        p.status === "published" ? "bg-emerald-50 text-emerald-600" : "bg-amber-50 text-amber-600"
                      )}>
                        {p.status}
                      </span>
                    </div>
                    <div className="text-right hidden sm:block">
                      <p className="text-sm font-semibold text-neutral-900">{p.reach}</p>
                      <p className="text-xs text-neutral-400">reach</p>
                    </div>
                    <div className="text-right hidden md:block">
                      <p className="text-sm font-semibold text-neutral-900">{p.eng}</p>
                      <p className="text-xs text-neutral-400">engagement</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-semibold text-neutral-900">{p.clicks.toLocaleString()}</p>
                      <p className="text-xs text-neutral-400">clicks</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* ── TAB 2: REFERENCE CONTENT ── */}
      {tab === "reference" && (
        <div className="space-y-6 animate-fade-in">
          <div className="flex items-center justify-between">
            <p className="text-sm text-neutral-500">
              Content sources used to inform your campaigns — scored by strategic value.
            </p>
            <button className="flex items-center gap-2 text-sm font-medium border border-neutral-200 bg-white px-4 py-2 rounded-xl hover:border-neutral-900 transition-colors">
              <Plus size={14} />
              Add Source
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {refSources.map((src, i) => (
              <div key={i} className="bg-white border border-neutral-200 rounded-2xl p-5 hover:border-neutral-400 transition-all">
                {/* Header */}
                <div className="flex items-start gap-3 mb-4">
                  <div className={clsx(
                    "w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0",
                    src.type === "youtube" ? "bg-red-50" : "bg-blue-50"
                  )}>
                    {src.type === "youtube"
                      ? <Youtube size={18} className="text-red-500" />
                      : <FileText size={18} className="text-blue-500" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-neutral-900 leading-snug">{src.title}</p>
                    <p className="text-xs text-neutral-400 mt-0.5 flex items-center gap-1">
                      <Link2 size={10} />
                      {src.source}
                    </p>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="text-xl font-bold text-neutral-900">{src.score}</p>
                    <p className="text-xs text-neutral-400">score</p>
                  </div>
                </div>

                {/* Score bar */}
                <ScoreBar score={src.score} color={src.score >= 80 ? "bg-emerald-500" : src.score >= 70 ? "bg-amber-400" : "bg-neutral-400"} />

                {/* Insights */}
                <div className="mt-4 space-y-1.5">
                  <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">Key Insights</p>
                  {src.insights.map((ins, j) => (
                    <div key={j} className="flex items-center gap-2 text-sm text-neutral-700">
                      <span className="w-1.5 h-1.5 rounded-full bg-neutral-400 flex-shrink-0" />
                      {ins}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── TAB 3: HOOK COMPARISON ── */}
      {tab === "hooks" && (
        <div className="space-y-5 animate-fade-in">
          <p className="text-sm text-neutral-500">
            Side-by-side comparison of your hooks vs competitor hooks — scored by predicted engagement.
          </p>

          {hookComparisons.map((h, i) => (
            <div key={i} className="bg-white border border-neutral-200 rounded-2xl p-5">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                {/* Our hook */}
                <div className={clsx(
                  "rounded-xl p-4 border-2",
                  h.verdict === "ours" ? "border-emerald-400 bg-emerald-50" : "border-neutral-200 bg-neutral-50"
                )}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold text-neutral-500 uppercase tracking-wider">Our Hook</span>
                    {h.verdict === "ours" && (
                      <span className="text-xs font-bold text-emerald-600 bg-emerald-100 px-2 py-0.5 rounded-full flex items-center gap-1">
                        <TrendingUp size={10} /> Winner
                      </span>
                    )}
                  </div>
                  <p className="text-sm font-medium text-neutral-900 mb-3 leading-relaxed">"{h.ours}"</p>
                  <ScoreBar score={h.ourScore} color={h.verdict === "ours" ? "bg-emerald-500" : "bg-neutral-400"} />
                </div>

                {/* Competitor hook */}
                <div className={clsx(
                  "rounded-xl p-4 border-2",
                  h.verdict === "competitor" ? "border-orange-400 bg-orange-50" : "border-neutral-200 bg-neutral-50"
                )}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold text-neutral-500 uppercase tracking-wider">Competitor Hook</span>
                    {h.verdict === "competitor" && (
                      <span className="text-xs font-bold text-orange-600 bg-orange-100 px-2 py-0.5 rounded-full flex items-center gap-1">
                        <TrendingUp size={10} /> Outperforming
                      </span>
                    )}
                  </div>
                  <p className="text-sm font-medium text-neutral-900 mb-3 leading-relaxed">"{h.competitor}"</p>
                  <ScoreBar score={h.theirScore} color={h.verdict === "competitor" ? "bg-orange-400" : "bg-neutral-400"} />
                </div>
              </div>

              {/* Strategy tip */}
              <div className="flex items-start gap-2 bg-neutral-50 border border-neutral-200 rounded-xl px-4 py-3">
                <Zap size={14} className="text-neutral-500 mt-0.5 flex-shrink-0" />
                <p className="text-sm text-neutral-600 leading-relaxed">
                  <span className="font-semibold text-neutral-900">Strategy tip: </span>
                  {h.tip}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
