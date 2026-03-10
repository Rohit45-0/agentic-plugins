import { useState, useEffect, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  Library,
  Image,
  Video,
  FileText,
  Search,
  Twitter,
  Instagram,
  Download,
  Clipboard,
  ChevronDown,
  ChevronRight,
  Sparkles,
  ExternalLink,
  Trash2,
  RefreshCw,
  Loader2,
  AlertCircle,
} from "lucide-react";
import clsx from "clsx";
import { getCampaignHistory, clearCampaignHistory } from "../services/contentStore";
import { downloadProtectedAsset, getCampaignsFromAPI, deleteCampaignFromAPI } from "../services/campaigns";
import { apiRequest } from "../services/api";
import { toAbsoluteUrl } from "../services/api";

// ─── Content type tabs ────────────────────────────────────────────────────────

const IDEA_TYPES = [
  { key: "tweet_ideas", label: "Tweets", icon: Twitter, color: "text-sky-600" },
  { key: "blog_ideas", label: "Blogs", icon: FileText, color: "text-amber-600" },
  { key: "reel_ideas", label: "Reels", icon: Video, color: "text-violet-600" },
  { key: "short_video_ideas", label: "Video Scripts", icon: Video, color: "text-rose-600" },
  { key: "poster_ideas", label: "Poster Concepts", icon: Image, color: "text-emerald-600" },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).catch(() => { });
}

function relativeTime(iso) {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// ─── IdeaCard ────────────────────────────────────────────────────────────────

function IdeaCard({ idea, type, context }) {
  const [copied, setCopied] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [generatedBlog, setGeneratedBlog] = useState(null);

  const [generatingReel, setGeneratingReel] = useState(false);
  const [generatedReel, setGeneratedReel] = useState(null);

  const [error, setError] = useState("");

  const text = typeof idea === "object" ? JSON.stringify(idea, null, 2) : idea;

  const handleGenerateBlog = async () => {
    setGenerating(true);
    setError("");
    try {
      const resp = await apiRequest("/market-intel/generate-blog", {
        method: "POST",
        body: JSON.stringify({
          idea: text,
          product_name: context?.product_name || "Product",
          campaign_strategy: context?.campaign_strategy || ""
        }),
        timeoutMs: 300000 // 5 minutes for blog
      });
      setGeneratedBlog(resp.blog_content);
    } catch (err) {
      setError(err.message || "Failed to generate blog");
    } finally {
      setGenerating(false);
    }
  };

  const handleGenerateReel = async () => {
    setGeneratingReel(true);
    setError("");
    try {
      const resp = await apiRequest("/market-intel/generate-reel", {
        method: "POST",
        body: JSON.stringify({
          idea: text,
          product_name: context?.product_name || "Product",
          campaign_id: context?.campaign_db_id || context?.id || null
        }),
        timeoutMs: 600000 // 10 minutes for Sora-2
      });
      setGeneratedReel(resp.video_url);
    } catch (err) {
      setError(err.message || "Failed to generate reel");
    } finally {
      setGeneratingReel(false);
    }
  };

  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 hover:border-neutral-400 hover:shadow-sm transition-all duration-150 flex flex-col h-full">
      <p className="text-sm text-neutral-700 leading-relaxed mb-auto">{text}</p>

      {generatedBlog && (
        <div className="mt-4 p-4 bg-neutral-50 rounded-lg border border-neutral-200">
          <h4 className="text-xs font-semibold text-neutral-900 mb-2 uppercase tracking-wide">Generated Blog</h4>
          <div className="text-sm text-neutral-700 whitespace-pre-wrap max-h-[300px] overflow-y-auto pr-2">
            {generatedBlog}
          </div>
        </div>
      )}

      {generatedReel && (
        <div className="mt-4 rounded-lg overflow-hidden border border-neutral-200">
          <h4 className="text-xs font-semibold text-neutral-900 mb-2 mt-2 px-3 uppercase tracking-wide">Generated Reel</h4>
          <video
            src={toAbsoluteUrl(generatedReel)}
            controls
            className="w-full max-h-[300px] object-cover bg-black"
          />
        </div>
      )}

      {error && <p className="text-xs text-red-500 mt-2">{error}</p>}

      <div className="flex items-center gap-2 mt-4 pt-4 border-t border-neutral-100 flex-wrap">
        <button
          onClick={() => { copyToClipboard(generatedBlog || text); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900 border border-neutral-200 hover:border-neutral-300 transition-all"
        >
          <Clipboard size={12} />
          {copied ? "Copied!" : "Copy"}
        </button>

        {type === "blog_ideas" && !generatedBlog && (
          <button
            onClick={handleGenerateBlog}
            disabled={generating}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-sky-700 hover:bg-sky-50 border border-sky-100 hover:border-sky-200 transition-all ml-auto focus:outline-none focus:ring-2 focus:ring-sky-500/20"
          >
            {generating ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
            {generating ? "Writing..." : "Generate Blog"}
          </button>
        )}

        {type === "reel_ideas" && !generatedReel && (
          <button
            onClick={handleGenerateReel}
            disabled={generatingReel}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-violet-700 hover:bg-violet-50 border border-violet-100 hover:border-violet-200 transition-all ml-auto focus:outline-none focus:ring-2 focus:ring-violet-500/20"
          >
            {generatingReel ? <Loader2 size={12} className="animate-spin" /> : <Video size={12} />}
            {generatingReel ? "Generating..." : "Generate Reel"}
          </button>
        )}
      </div>
    </div>
  );
}

// ─── PosterCard ──────────────────────────────────────────────────────────────

function PosterCard({ asset, idx }) {
  const [publishing, setPublishing] = useState(false);
  const [publishResult, setPublishResult] = useState(null);
  const [publishError, setPublishError] = useState("");
  const [caption, setCaption] = useState("Check out our latest campaign! #marketing #brand");
  const [showPublish, setShowPublish] = useState(false);

  const handlePublish = async () => {
    setPublishing(true);
    setPublishError("");
    try {
      const result = await apiRequest("/publish/instagram", {
        method: "POST",
        body: JSON.stringify({ media_url: asset.download_url, caption, add_tracking_link: true }),
      });
      setPublishResult(result);
    } catch (err) {
      setPublishError(err.message || "Publish failed");
    } finally {
      setPublishing(false);
    }
  };

  return (
    <div className="bg-white border border-neutral-200 rounded-xl overflow-hidden hover:border-neutral-400 hover:shadow-sm transition-all duration-150">
      <div className="aspect-square bg-gradient-to-br from-neutral-100 to-neutral-200 flex items-center justify-center relative overflow-hidden group">
        {asset?.download_url ? (
          asset.asset_type === "video" || asset.download_url.endsWith(".mp4") ? (
            <video
              src={toAbsoluteUrl(asset.download_url)}
              controls
              className="w-full h-full object-cover"
            />
          ) : (
            <img
              src={toAbsoluteUrl(asset.download_url)}
              alt="Campaign Asset"
              className="w-full h-full object-cover"
            />
          )
        ) : (
          <Image size={32} className="text-neutral-400" strokeWidth={1.5} />
        )}
      </div>
      <div className="p-3">
        <p className="text-xs font-medium text-neutral-700 mb-2">
          {asset.asset_type === "video_blueprint" ? "Video Blueprint" : `Poster ${idx + 1}`}
        </p>
        <div className="flex items-center gap-2">
          <button
            onClick={() => downloadProtectedAsset(asset.download_url, asset.name)}
            className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900 transition-colors"
          >
            <Download size={11} /> Download
          </button>
          <button
            onClick={() => setShowPublish((v) => !v)}
            className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium text-sky-600 hover:bg-sky-50 transition-colors ml-auto"
          >
            <Instagram size={11} /> Publish
          </button>
        </div>
        {showPublish && (
          <div className="mt-3 space-y-2">
            <textarea
              value={caption}
              onChange={(e) => setCaption(e.target.value)}
              rows={2}
              className="w-full text-xs border border-neutral-200 rounded-lg p-2 resize-none outline-none focus:border-neutral-400"
              placeholder="Instagram caption..."
            />
            <button
              onClick={handlePublish}
              disabled={publishing}
              className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-pink-500 to-violet-500 text-white rounded-lg text-xs font-semibold disabled:opacity-60 hover:opacity-90 transition-opacity"
            >
              <Instagram size={12} />
              {publishing ? "Publishing…" : "Post to Instagram"}
            </button>
            {publishError && <p className="text-xs text-red-500">{publishError}</p>}
            {publishResult?.success && (
              <p className="text-xs text-emerald-600 flex items-center gap-1">
                <ExternalLink size={10} /> Published! Post ID: {publishResult.post_id}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── CampaignSection ─────────────────────────────────────────────────────────

function CampaignSection({ record, isActive, onToggle, onDelete }) {
  const campaign = record?.campaign || record;
  const posters = record?.poster_assets || [];
  const video = record?.video_asset;
  const savedAt = record?.created_at || record?.generated_at;
  const [activeType, setActiveType] = useState("tweet_ideas");

  const availableTypes = IDEA_TYPES.filter((t) => campaign?.[t.key]?.length > 0);

  const titleText =
    campaign?.campaign_strategy?.slice(0, 70) ||
    record?.campaign_strategy?.slice(0, 70) ||
    record?.product_name ||
    "Campaign";

  return (
    <div className={clsx("border rounded-2xl overflow-hidden transition-all duration-200", isActive ? "border-neutral-900" : "border-neutral-200")}>
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-5 py-4 bg-white hover:bg-neutral-50 transition-colors text-left"
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-neutral-900 flex items-center justify-center shrink-0">
            <Sparkles size={14} className="text-white" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-neutral-900 truncate">{titleText}</p>
            <p className="text-xs text-neutral-400">
              {posters.length} poster{posters.length !== 1 ? "s" : ""} ·{" "}
              {availableTypes.length} content type{availableTypes.length !== 1 ? "s" : ""} ·{" "}
              {relativeTime(savedAt)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(); }}
            className="p-1 rounded-md text-neutral-300 hover:text-red-500 hover:bg-red-50 transition-colors"
            title="Delete campaign"
          >
            <Trash2 size={14} />
          </button>
          {isActive ? <ChevronDown size={16} className="text-neutral-400" /> : <ChevronRight size={16} className="text-neutral-400" />}
        </div>
      </button>

      {isActive && (
        <div className="border-t border-neutral-100 bg-neutral-50 p-5 space-y-5">
          {/* Poster grid */}
          {posters.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-3">Generated Posters</h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                {posters.map((asset, i) => (
                  <PosterCard key={i} asset={asset} idx={i} />
                ))}
                {video?.download_url && <PosterCard asset={video} idx={posters.length} />}
              </div>
            </div>
          )}

          {/* Tabs */}
          {availableTypes.length > 0 && (
            <div>
              <div className="flex items-center gap-2 flex-wrap mb-4">
                {availableTypes.map(({ key, label, icon: Icon, color }) => (
                  <button
                    key={key}
                    onClick={() => setActiveType(key)}
                    className={clsx(
                      "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-all duration-100",
                      activeType === key
                        ? "border-neutral-900 bg-neutral-900 text-white"
                        : "border-neutral-200 bg-white text-neutral-600 hover:border-neutral-400"
                    )}
                  >
                    <Icon size={11} />
                    {label} ({campaign[key]?.length})
                  </button>
                ))}
              </div>
              {campaign[activeType] && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {campaign[activeType].map((idea, idx) => (
                    <IdeaCard key={idx} idea={idea} type={activeType} context={campaign} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function ContentLibraryPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [activeIdx, setActiveIdx] = useState(0);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      // 1. Fetch from Supabase (source of truth)
      const apiRows = await getCampaignsFromAPI(100);

      // 2. Grab local records to merge video_asset (not stored in DB)
      const localRecords = getCampaignHistory();

      const merged = apiRows.map((row) => {
        const local = localRecords.find(
          (r) =>
            r?.campaign?.campaign_strategy?.includes(row.product_name) ||
            r?.product_name === row.product_name
        );
        return {
          ...row,
          video_asset: local?.video_asset || null,
          campaign: {
            campaign_strategy: row.campaign_strategy,
            blog_ideas: row.blog_ideas || [],
            tweet_ideas: row.tweet_ideas || [],
            reel_ideas: row.reel_ideas || [],
            short_video_ideas: row.short_video_ideas || [],
            poster_ideas: row.poster_ideas || [],
          },
        };
      });

      setCampaigns(merged);
    } catch (err) {
      // Fallback to localStorage if API unavailable
      const local = getCampaignHistory();
      if (local.length > 0) {
        setCampaigns(local);
        setError("Showing cached data — API unavailable: " + (err.message || ""));
      } else {
        setError("Could not load campaigns: " + (err.message || "Unknown error"));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  useEffect(() => {
    if (location.state?.newCampaign) { refresh(); setActiveIdx(0); }
  }, [location.state, refresh]);

  const handleDelete = async (record, idx) => {
    if (record.id) {
      try { await deleteCampaignFromAPI(record.id); } catch (err) { alert("Delete failed: " + err.message); return; }
    }
    setCampaigns((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleClearAll = async () => {
    if (!window.confirm("Delete ALL campaigns? This cannot be undone.")) return;
    try { await Promise.all(campaigns.filter((r) => r.id).map((r) => deleteCampaignFromAPI(r.id))); } catch (_) { }
    clearCampaignHistory();
    setCampaigns([]);
  };

  const filtered = campaigns.filter((r) => {
    const strategy = r?.campaign?.campaign_strategy || r?.campaign_strategy || "";
    const name = r?.product_name || "";
    const match = strategy.toLowerCase().includes(search.toLowerCase()) || name.toLowerCase().includes(search.toLowerCase());
    if (!match) return false;
    if (filter === "all") return true;
    if (filter === "image") return (r?.poster_assets?.length || 0) > 0 && r?.poster_assets?.some(a => a.asset_type !== "video");
    if (filter === "video") return !!r?.video_asset || (r?.poster_assets?.some(a => a.asset_type === "video"));
    if (filter === "text") return (r?.campaign?.tweet_ideas?.length || 0) > 0 || (r?.campaign?.blog_ideas?.length || 0) > 0;
    return true;
  });

  return (
    <div className="p-8 animate-fade-in max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-neutral-900 tracking-tight">Content Library</h1>
          <p className="text-sm text-neutral-500 mt-0.5">
            {loading ? "Loading from Supabase…" : `${campaigns.length} campaign${campaigns.length !== 1 ? "s" : ""} stored in Supabase`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={refresh}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-neutral-200 text-sm font-medium text-neutral-600 hover:border-neutral-400 hover:text-neutral-900 transition-all disabled:opacity-50"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            Refresh
          </button>
          <button onClick={() => navigate("/campaigns")} className="btn-primary">
            <Sparkles size={14} />
            New Campaign
          </button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-3 bg-amber-50 border border-amber-200 rounded-xl mb-5 text-sm text-amber-700">
          <AlertCircle size={14} className="shrink-0" />
          {error}
        </div>
      )}

      {/* Loading */}
      {loading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 size={28} className="animate-spin text-neutral-400" />
        </div>
      ) : (
        <>
          {/* Filters */}
          <div className="flex items-center gap-3 mb-6 flex-wrap">
            <div className="relative flex-1 min-w-[180px] max-w-xs">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search campaigns…"
                className="cn-input pl-9"
              />
            </div>
            <div className="flex items-center gap-1">
              {["all", "image", "video", "text"].map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={clsx(
                    "px-3 py-1.5 text-sm font-medium rounded-lg capitalize transition-all duration-100",
                    filter === f ? "bg-neutral-900 text-white" : "text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900"
                  )}
                >
                  {f}
                </button>
              ))}
            </div>
            {campaigns.length > 0 && (
              <button
                onClick={handleClearAll}
                className="ml-auto flex items-center gap-1.5 text-xs text-neutral-400 hover:text-red-500 transition-colors"
              >
                <Trash2 size={12} /> Clear all
              </button>
            )}
          </div>

          {/* List */}
          {filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="w-14 h-14 bg-neutral-100 rounded-2xl flex items-center justify-center mb-4">
                <Library size={24} className="text-neutral-400" strokeWidth={1.5} />
              </div>
              <p className="text-sm font-semibold text-neutral-900 mb-1">No campaigns yet</p>
              <p className="text-sm text-neutral-500 mb-4">
                {campaigns.length > 0 ? "No results match your filter." : "Generate your first campaign to see content here."}
              </p>
              <button onClick={() => navigate("/campaigns")} className="btn-primary">
                <Sparkles size={14} /> Create Campaign
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {filtered.map((record, i) => (
                <CampaignSection
                  key={record.id || i}
                  record={record}
                  isActive={activeIdx === i}
                  onToggle={() => setActiveIdx(activeIdx === i ? -1 : i)}
                  onDelete={() => handleDelete(record, i)}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
