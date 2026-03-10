import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
    Search,
    TrendingUp,
    Globe,
    Zap,
    Loader2,
    ChevronRight,
    AlertCircle,
    CheckCircle2,
    ExternalLink,
    MessageSquare,
    Flame,
    Target,
    Lightbulb,
    BarChart2,
    Plus,
    X,
    ArrowRight,
    Sparkles,
    Database,
    Link,
} from "lucide-react";
import clsx from "clsx";
import { runMarketScout } from "../services/marketScout";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function SourceBadge({ source }) {
    const map = {
        firecrawl_search: { label: "Firecrawl Search", color: "text-amber-700 bg-amber-50 border-amber-200" },
        firecrawl_scrape: { label: "Firecrawl Scrape", color: "text-orange-700 bg-orange-50 border-orange-200" },
        azure_openai_gpt4o: { label: "GPT-4o Analysis", color: "text-blue-700 bg-blue-50 border-blue-200" },
        llm_knowledge_fallback: { label: "AI Fallback", color: "text-neutral-600 bg-neutral-100 border-neutral-200" },
    };
    const s = map[source] || { label: source, color: "text-neutral-600 bg-neutral-100 border-neutral-200" };
    return (
        <span className={clsx("text-[10px] font-medium px-2 py-0.5 rounded-full border", s.color)}>
            {s.label}
        </span>
    );
}

function SectionCard({ icon: Icon, title, color = "violet", children }) {
    const colors = {
        violet: "text-indigo-600 bg-indigo-50 border-indigo-200",
        orange: "text-orange-600 bg-orange-50 border-orange-200",
        emerald: "text-emerald-600 bg-emerald-50 border-emerald-200",
        red: "text-red-600 bg-red-50 border-red-200",
        blue: "text-blue-600 bg-blue-50 border-blue-200",
    };
    return (
        <div className="bg-white border border-neutral-200 rounded-xl p-5 shadow-sm">
            <div className="flex items-center gap-2.5 mb-4">
                <div className={clsx("w-8 h-8 rounded-lg flex items-center justify-center border", colors[color])}>
                    <Icon size={15} />
                </div>
                <h3 className="text-neutral-900 font-semibold text-sm">{title}</h3>
            </div>
            {children}
        </div>
    );
}

// ─── Competitor Results ───────────────────────────────────────────────────────

function CompetitorCard({ result }) {
    const [expanded, setExpanded] = useState(false);
    return (
        <div className="bg-white border border-neutral-200 rounded-xl p-4 hover:border-neutral-300 transition shadow-sm">
            <div className="flex items-start justify-between gap-3 mb-2">
                <div className="min-w-0">
                    <p className="text-neutral-900 text-sm font-medium leading-snug truncate">
                        {result.title || result.url}
                    </p>
                    {result.title && (
                        <a
                            href={result.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-neutral-500 text-xs hover:text-blue-500 flex items-center gap-1 mt-0.5 transition truncate"
                        >
                            <Link size={10} />
                            <span className="truncate">{result.url}</span>
                        </a>
                    )}
                </div>
                <SourceBadge source={result.source} />
            </div>

            {result.description && (
                <p className="text-neutral-600 text-xs leading-relaxed line-clamp-2">{result.description}</p>
            )}

            {result.key_points?.length > 0 && (
                <div className="mt-3">
                    <button
                        onClick={() => setExpanded((e) => !e)}
                        className="text-blue-600 text-xs font-medium flex items-center gap-1 hover:text-blue-700 transition"
                    >
                        {expanded ? "Hide" : "Show"} key points
                        <ChevronRight size={12} className={clsx("transition-transform", expanded && "rotate-90")} />
                    </button>
                    {expanded && (
                        <ul className="mt-2 space-y-1.5">
                            {result.key_points.map((pt, i) => (
                                <li key={i} className="flex items-start gap-2 text-xs text-neutral-600">
                                    <span className="text-blue-500 mt-0.5 shrink-0">•</span>
                                    {pt}
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            )}
        </div>
    );
}

// ─── Gap Analysis Result ──────────────────────────────────────────────────────

function InsightList({ items, color = "violet" }) {
    const dotColor = {
        violet: "text-indigo-500",
        orange: "text-orange-500",
        emerald: "text-emerald-500",
        red: "text-red-500",
        blue: "text-blue-500",
    };
    return (
        <ul className="space-y-2">
            {(items || []).map((item, i) => (
                <li key={i} className="flex items-start gap-2.5 text-sm text-neutral-600">
                    <span className={clsx("mt-0.5 shrink-0 px-1 font-bold", dotColor[color])}>•</span>
                    {item}
                </li>
            ))}
        </ul>
    );
}

// ─── Loading State ────────────────────────────────────────────────────────────

const SCOUT_STEPS = [
    "Searching the web with Firecrawl...",
    "Scraping competitor pages...",
    "Extracting key content signals...",
    "Running GPT-4o gap analysis...",
    "Mapping opportunity landscape...",
];

function ScoutingLoader() {
    const [stepIdx, setStepIdx] = useState(0);
    useEffect(() => {
        const iv = setInterval(() => setStepIdx((i) => Math.min(i + 1, SCOUT_STEPS.length - 1)), 3000);
        return () => clearInterval(iv);
    }, []);
    return (
        <div className="flex flex-col items-center gap-6 py-10">
            <div className="relative w-24 h-24">
                <div className="absolute inset-0 rounded-full border-4 border-amber-100 animate-ping" />
                <div className="absolute inset-2 rounded-full border-4 border-t-amber-500 border-r-amber-300 border-b-amber-100 border-l-amber-100 animate-spin" />
                <div className="absolute inset-0 flex items-center justify-center">
                    <Globe size={24} className="text-amber-500" />
                </div>
            </div>
            <div className="text-center space-y-1">
                <p className="text-neutral-900 font-semibold text-lg">Scouting the Market</p>
                <p className="text-neutral-500 text-sm">Firecrawl + AI mapping competitor landscape...</p>
            </div>
            <div className="space-y-2 w-full max-w-xs">
                {SCOUT_STEPS.map((s, i) => (
                    <div key={s} className={clsx("flex items-center gap-2.5 text-sm transition-all", i < stepIdx ? "text-neutral-400" : i === stepIdx ? "text-neutral-900 font-medium" : "text-neutral-300")}>
                        {i < stepIdx ? <CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> : i === stepIdx ? <Loader2 size={14} className="animate-spin text-amber-500 shrink-0" /> : <div className="w-3.5 h-3.5 rounded-full border border-neutral-200 shrink-0" />}
                        {s}
                    </div>
                ))}
            </div>
        </div>
    );
}

// ─── URL Tag Input ────────────────────────────────────────────────────────────

function UrlTagInput({ urls, onChange }) {
    const [input, setInput] = useState("");
    const add = () => {
        const v = input.trim();
        if (!v || urls.includes(v)) { setInput(""); return; }
        if (urls.length >= 3) return;
        onChange([...urls, v]);
        setInput("");
    };
    const remove = (url) => onChange(urls.filter((u) => u !== url));
    return (
        <div className="space-y-2">
            <div className="flex gap-2">
                <input
                    className="cn-input"
                    placeholder="https://competitor.com/product-page"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), add())}
                />
                <button
                    onClick={add}
                    disabled={!input.trim() || urls.length >= 3}
                    className="px-3 py-2 rounded-lg bg-neutral-100 border border-neutral-200 hover:bg-neutral-200 text-neutral-600 transition disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
                >
                    <Plus size={16} />
                </button>
            </div>
            {urls.length > 0 && (
                <div className="flex flex-wrap gap-2">
                    {urls.map((u) => (
                        <div key={u} className="flex items-center gap-1.5 bg-neutral-100 border border-neutral-200 rounded-md px-2 py-1 text-xs text-neutral-700 max-w-full">
                            <Link size={10} className="shrink-0 text-neutral-400" />
                            <span className="truncate max-w-[200px]">{u}</span>
                            <button onClick={() => remove(u)} className="shrink-0 hover:text-red-500 transition text-neutral-400 ml-1">
                                <X size={12} />
                            </button>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function MarketScoutPage() {
    const navigate = useNavigate();
    const location = useLocation();

    // Pre-fill from Product Intake navigation state
    const passedData = location.state || {};

    const [form, setForm] = useState({
        productName: passedData.productName || "",
        category: passedData.category || "",
        keywords: "",
        region: "IN",
    });
    const [competitorUrls, setCompetitorUrls] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [result, setResult] = useState(null);

    const handleChange = (key, val) => setForm((f) => ({ ...f, [key]: val }));

    const handleSubmit = async () => {
        if (!form.productName.trim() || !form.category.trim()) return;
        setError(null);
        setLoading(true);
        setResult(null);
        try {
            const data = await runMarketScout({
                productName: form.productName,
                category: form.category,
                keywords: form.keywords.split(",").map((k) => k.trim()).filter(Boolean),
                competitorUrls,
                region: form.region,
            });
            setResult(data);
        } catch (err) {
            setError(err.message || "Market scout failed. Please try again.");
        } finally {
            setLoading(false);
        }
    };

    const canSubmit = form.productName.trim() && form.category.trim() && !loading;

    return (
        <div className="p-8 animate-fade-in max-w-4xl mx-auto">
            {/* Header */}
            <div className="mb-8 flex items-center justify-between">
                <div>
                    <h1 className="text-xl font-semibold text-neutral-900 tracking-tight flex items-center gap-2">
                        <Globe size={20} className="text-neutral-500" />
                        Market Scout
                    </h1>
                    <p className="text-sm text-neutral-500 mt-1">
                        Step 2 · Competitor intelligence powered by Firecrawl + AI
                    </p>
                </div>
            </div>

            <div className="space-y-6">
                {/* Input Card */}
                <div className="cn-card space-y-5">
                    <div className="flex items-center gap-2 mb-1">
                        <Search size={16} className="text-neutral-500" />
                        <h2 className="text-neutral-900 font-semibold text-sm">Scout Configuration</h2>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-xs font-medium text-neutral-700 mb-1.5">
                                Product Name <span className="text-red-500">*</span>
                            </label>
                            <input
                                className="cn-input"
                                placeholder="e.g. Arctic Glow Serum"
                                value={form.productName}
                                onChange={(e) => handleChange("productName", e.target.value)}
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-medium text-neutral-700 mb-1.5">
                                Category / Niche <span className="text-red-500">*</span>
                            </label>
                            <input
                                className="cn-input"
                                placeholder="e.g. Luxury skincare, India"
                                value={form.category}
                                onChange={(e) => handleChange("category", e.target.value)}
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-medium text-neutral-700 mb-1.5">
                                Extra Keywords{" "}
                                <span className="text-neutral-400 font-normal text-[10px]">(comma separated)</span>
                            </label>
                            <input
                                className="cn-input"
                                placeholder="e.g. anti-aging, hyaluronic, glow"
                                value={form.keywords}
                                onChange={(e) => handleChange("keywords", e.target.value)}
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-medium text-neutral-700 mb-1.5">Region</label>
                            <select
                                className="cn-input appearance-none cursor-pointer"
                                value={form.region}
                                onChange={(e) => handleChange("region", e.target.value)}
                            >
                                {[["IN", "India"], ["US", "United States"], ["GB", "United Kingdom"], ["AU", "Australia"], ["SG", "Singapore"]].map(([v, l]) => (
                                    <option key={v} value={v}>{l}</option>
                                ))}
                            </select>
                        </div>
                    </div>

                    {/* Competitor URLs */}
                    <div>
                        <label className="block text-xs font-medium text-neutral-700 mb-1.5">
                            Competitor URLs to scrape{" "}
                            <span className="text-neutral-400 font-normal text-[10px]">(optional, max 3)</span>
                        </label>
                        <UrlTagInput urls={competitorUrls} onChange={setCompetitorUrls} />
                    </div>

                    {/* Submit row */}
                    <div className="flex items-center justify-end pt-2">
                        <button
                            disabled={!canSubmit}
                            onClick={handleSubmit}
                            className={clsx(
                                "flex items-center gap-2 px-5 py-2.5 rounded-lg font-medium text-sm transition-all shadow-sm",
                                canSubmit
                                    ? "bg-neutral-900 hover:bg-neutral-800 text-white"
                                    : "bg-neutral-100 text-neutral-400 cursor-not-allowed border border-neutral-200"
                            )}
                        >
                            {loading ? (
                                <><Loader2 size={16} className="animate-spin" /> Scouting...</>
                            ) : (
                                <><Sparkles size={16} /> Run Market Scout</>
                            )}
                        </button>
                    </div>
                </div>

                {/* Error */}
                {error && (
                    <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                        <AlertCircle size={16} className="mt-0.5 shrink-0" />
                        {error}
                    </div>
                )}

                {/* Loading */}
                {loading && <div className="cn-card"><ScoutingLoader /></div>}

                {/* Results */}
                {result && !loading && (
                    <div className="space-y-6 animate-fade-in">
                        {/* Meta bar */}
                        <div className="flex items-center justify-between flex-wrap gap-3 py-2">
                            <div className="flex items-center gap-2 flex-wrap">
                                {result.data_sources.map((s) => <SourceBadge key={s} source={s} />)}
                            </div>
                            <div className="flex items-center gap-4 text-xs text-neutral-500 font-medium">
                                <span className="flex items-center gap-1.5">
                                    <Globe size={12} className="text-neutral-400" />
                                    {result.competitor_results?.length || 0} pages analysed
                                </span>
                            </div>
                        </div>

                        {/* Opportunity Gap — Hero card */}
                        <div className="bg-gradient-to-br from-amber-50 to-white border border-amber-200 rounded-2xl p-6 shadow-sm">
                            <div className="flex items-start gap-3">
                                <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center shrink-0 border border-amber-200/50">
                                    <Target size={20} className="text-amber-600" />
                                </div>
                                <div>
                                    <p className="text-amber-700 text-xs font-bold uppercase tracking-wider mb-2">
                                        Opportunity Gap
                                    </p>
                                    <p className="text-neutral-900 font-medium text-base leading-relaxed">
                                        {result.gap_analysis?.opportunity_gap}
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* 2-col gap grid */}
                        <div className="grid grid-cols-2 gap-4">
                            <SectionCard icon={MessageSquare} title="Top Unanswered Questions" color="violet">
                                <InsightList items={result.gap_analysis?.top_questions} color="violet" />
                            </SectionCard>

                            <SectionCard icon={AlertCircle} title="Audience Complaints & Pain Points" color="red">
                                <InsightList items={result.gap_analysis?.complaints} color="red" />
                            </SectionCard>

                            <SectionCard icon={Flame} title="Viral Hook Patterns" color="orange">
                                <InsightList items={result.gap_analysis?.viral_hooks} color="orange" />
                            </SectionCard>

                            <SectionCard icon={Lightbulb} title="Recommended Content Angles" color="emerald">
                                <InsightList items={result.gap_analysis?.recommended_angles} color="emerald" />
                            </SectionCard>
                        </div>

                        {/* Competitor results */}
                        {result.competitor_results?.length > 0 && (
                            <div>
                                <div className="flex items-center gap-2 mb-4 mt-6">
                                    <BarChart2 size={16} className="text-neutral-400" />
                                    <h3 className="text-neutral-700 text-sm font-semibold">
                                        Competitor Content Analysed ({result.competitor_results.length})
                                    </h3>
                                </div>
                                <div className="grid grid-cols-2 gap-3">
                                    {result.competitor_results.map((r, i) => (
                                        <CompetitorCard key={i} result={r} />
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* CTA */}
                        <div className="flex items-center justify-between p-5 bg-white border border-neutral-200 rounded-xl shadow-sm mt-8">
                            <div>
                                <p className="text-neutral-900 font-semibold text-sm">Ready to create your campaign?</p>
                                <p className="text-neutral-500 text-xs mt-0.5">Use these insights to generate targeted content</p>
                            </div>
                            <button
                                onClick={() => navigate("/campaigns", { state: { productName: result.product_name, category: result.category, gapAnalysis: result.gap_analysis } })}
                                className="flex items-center gap-2 px-5 py-2.5 rounded-lg font-medium text-sm bg-neutral-900 hover:bg-neutral-800 text-white shadow-sm transition-all"
                            >
                                Continue to Campaigns <ArrowRight size={16} />
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
