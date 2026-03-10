import { useState } from "react";
import { analyzeCompetitors } from "../services/campaigns";
import { Users, Search, Loader2, TrendingUp, BarChart2, ArrowUpRight } from "lucide-react";

export default function CompetitorIntelPage() {
  const [handles, setHandles] = useState("");
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState("");

  const handleAnalyze = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const handleList = handles.split(",").map((h) => h.trim()).filter(Boolean);
      const data = await analyzeCompetitors(handleList, category);
      setResults(data);
    } catch (err) {
      setError(err.message || "Analysis failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 animate-fade-in max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-xl font-semibold text-neutral-900 tracking-tight">Competitor Intelligence</h1>
        <p className="text-sm text-neutral-500 mt-0.5">Analyze competitors and discover market gaps</p>
      </div>

      {/* Input Form */}
      <div className="cn-card mb-6">
        <form onSubmit={handleAnalyze} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-neutral-700 mb-1.5">
              Competitor handles or keywords
            </label>
            <input
              type="text"
              value={handles}
              onChange={(e) => setHandles(e.target.value)}
              placeholder="@nike, @adidas, or 'running shoes'"
              className="cn-input"
              required
            />
            <p className="text-xs text-neutral-400 mt-1">Separate multiple handles with commas</p>
          </div>
          <div>
            <label className="block text-xs font-medium text-neutral-700 mb-1.5">Category</label>
            <input
              type="text"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="e.g. sportswear, tech, beauty"
              className="cn-input"
            />
          </div>
          {error && (
            <div className="px-3 py-2.5 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
              {error}
            </div>
          )}
          <button type="submit" disabled={loading} className="btn-primary">
            {loading ? (
              <><Loader2 size={15} className="animate-spin" /> Analyzing...</>
            ) : (
              <><Search size={15} /> Analyze Competitors</>
            )}
          </button>
        </form>
      </div>

      {/* Results */}
      {results && (
        <div className="space-y-4 animate-slide-up">
          {results.analyses?.map((item, i) => (
            <div key={i} className="cn-card">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 bg-neutral-100 rounded-lg flex items-center justify-center">
                    <Users size={16} className="text-neutral-500" strokeWidth={1.75} />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-neutral-900 capitalize">{item.competitor}</p>
                    <p className="text-xs text-neutral-400">Market Analysis</p>
                  </div>
                </div>
                <span className="cn-badge-neutral">Global</span>
              </div>

              {item.opportunity_gap && (
                <div className="mb-5 pb-5 border-b border-neutral-100">
                  <p className="text-xs font-semibold uppercase tracking-wider text-neutral-500 mb-2">Opportunity Gap</p>
                  <p className="text-sm text-neutral-700 leading-relaxed">{item.opportunity_gap}</p>
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {item.viral_hooks && item.viral_hooks.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-wider text-neutral-500 mb-3">Viral Hooks</p>
                    {item.viral_hooks.slice(0, 3).map((hook, j) => (
                      <div key={j} className="flex items-start gap-2 text-sm text-neutral-600">
                        <ArrowUpRight size={14} className="text-emerald-500 mt-0.5 flex-shrink-0" />
                        <span>{hook}</span>
                      </div>
                    ))}
                  </div>
                )}

                {item.complaints && item.complaints.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-wider text-neutral-500 mb-3">Audience Complaints / Gaps</p>
                    {item.complaints.slice(0, 3).map((comp, j) => (
                      <div key={j} className="flex items-start gap-2 text-sm text-neutral-600">
                        <TrendingUp size={14} className="text-amber-500 mt-0.5 flex-shrink-0" />
                        <span>{comp}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!results && !loading && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="w-12 h-12 bg-neutral-100 rounded-xl flex items-center justify-center mb-4">
            <BarChart2 size={22} className="text-neutral-400" strokeWidth={1.5} />
          </div>
          <p className="text-sm font-medium text-neutral-900 mb-1">No analysis yet</p>
          <p className="text-sm text-neutral-500">Enter competitor handles above to get started</p>
        </div>
      )}
    </div>
  );
}
