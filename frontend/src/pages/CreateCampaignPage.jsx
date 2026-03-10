import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  downloadProtectedAsset,
  runFullCampaignPipeline,
  generateSystemPrompt,
  extractIdentityLite,
  analyzeCategoryTrends,
  analyzeCompetitors,
} from "../services/campaigns";
import { downloadJson, saveCampaignRecord } from "../services/contentStore";
import LiveJobTracker from "../components/LiveJobTracker";
import {
  Megaphone,
  Upload,
  Loader2,
  CheckCircle2,
  Download,
  ChevronRight,
  Image,
  Video,
  Globe,
  Users,
  Sparkles,
  AlertCircle,
  Library,
  FileText,
  TrendingUp,
  BarChart2,
  ArrowUpRight,
  Search,
} from "lucide-react";
import clsx from "clsx";

const STEPS = ["Product", "Audience", "Creative", "Launch"];

function StepIndicator({ current }) {
  return (
    <div className="flex items-center gap-0 mb-8">
      {STEPS.map((step, i) => (
        <div key={step} className="flex items-center">
          <div className="flex items-center gap-2">
            <div
              className={clsx(
                "w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold transition-all",
                i < current
                  ? "bg-neutral-900 text-white"
                  : i === current
                    ? "bg-neutral-900 text-white ring-4 ring-neutral-100"
                    : "bg-neutral-100 text-neutral-400"
              )}
            >
              {i < current ? <CheckCircle2 size={14} /> : i + 1}
            </div>
            <span
              className={clsx(
                "text-sm font-medium",
                i <= current ? "text-neutral-900" : "text-neutral-400"
              )}
            >
              {step}
            </span>
          </div>
          {i < STEPS.length - 1 && (
            <div
              className={clsx(
                "w-12 h-px mx-3",
                i < current ? "bg-neutral-900" : "bg-neutral-200"
              )}
            />
          )}
        </div>
      ))}
    </div>
  );
}

function Field({ label, hint, children }) {
  return (
    <div>
      <label className="block text-xs font-medium text-neutral-700 mb-1.5">{label}</label>
      {children}
      {hint && <p className="text-xs text-neutral-400 mt-1">{hint}</p>}
    </div>
  );
}

export default function CreateCampaignPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const savedState = JSON.parse(sessionStorage.getItem("cn_campaign_state") || "null");

  const [step, setStep] = useState(savedState?.step ?? 0);
  const [form, setForm] = useState(savedState?.form || {
    product_name: "Pigeon Air Fryer",
    product_description: "Affordable air fryer for healthy cooking in 3k-5k INR range",
    target_audience: "India budget-conscious home cooks",
    category: "Kitchen Appliances",
    region_code: "IN",
    product_image_url: "",
    product_image_name: "",
    identity_notes: "",
    competitor_handles: "philipsindia, havellsindia, agaro_lifestyle",
    poster_generation_count: 1,
    video_duration_seconds: 6,
    video_generation_enabled: true,
  });
  const [result, setResult] = useState(savedState?.result || null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [selectedImage, setSelectedImage] = useState(null);
  const [compareInput, setCompareInput] = useState(savedState?.compareInput || "");
  const [compareResults, setCompareResults] = useState(savedState?.compareResults || null);
  const [isComparing, setIsComparing] = useState(false);
  const [compareError, setCompareError] = useState("");
  const [imagePreview, setImagePreview] = useState("");
  const [imageDataUrl, setImageDataUrl] = useState("");
  const [error, setError] = useState("");
  const [jobId, setJobId] = useState(null);
  const [isOtherCategory, setIsOtherCategory] = useState(false);
  const [systemPrompt, setSystemPrompt] = useState("");
  const [generatingPrompt, setGeneratingPrompt] = useState(false);

  // ── Progressive pipeline background state ──────────────────────────────
  const [visualDna, setVisualDna] = useState(null);
  const [extractingDna, setExtractingDna] = useState(false);
  const [dnaStatus, setDnaStatus] = useState(""); // "", "running", "done", "failed"
  const [trendData, setTrendData] = useState(null);
  const [trendStatus, setTrendStatus] = useState(""); // "", "running", "done", "failed"
  const [competitorData, setCompetitorData] = useState(null);
  const [competitorStatus, setCompetitorStatus] = useState(""); // "", "running", "done", "failed"
  // Use ref to capture the latest imageDataUrl in async closures
  const imageDataUrlRef = useRef("");

  useEffect(() => {
    const state = location.state || {};
    if (!state || Object.keys(state).length === 0) return;

    const recommendedAngles = Array.isArray(state.gapAnalysis?.recommended_angles)
      ? state.gapAnalysis.recommended_angles
      : [];
    const opportunityGap = state.gapAnalysis?.opportunity_gap || "";
    const insightNote = [opportunityGap, ...recommendedAngles].filter(Boolean).join("\n• ");

    setForm((prev) => ({
      ...prev,
      product_name: state.productName || prev.product_name,
      category: state.category || prev.category,
      identity_notes: insightNote ? `Market insights:\n• ${insightNote}` : prev.identity_notes,
      competitor_handles:
        Array.isArray(state.gapAnalysis?.competitor_handles)
          ? state.gapAnalysis.competitor_handles.join(", ")
          : prev.competitor_handles,
    }));
  }, [location.state]);

  // Persist state
  useEffect(() => {
    sessionStorage.setItem(
      "cn_campaign_state",
      JSON.stringify({ step, form, result, compareInput, compareResults })
    );
  }, [step, form, result, compareInput, compareResults]);

  const update = (k, v) => setForm((p) => ({ ...p, [k]: v }));

  const readAsDataUrl = (file) =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(new Error("Unable to read selected image."));
      reader.readAsDataURL(file);
    });

  const handleImageSelect = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setSelectedImage(file);
    const url = URL.createObjectURL(file);
    setImagePreview(url);
    update("product_image_name", file.name);
    // Pre-read data URL so it's ready for identity extraction
    try {
      const dataUrl = await readAsDataUrl(file);
      setImageDataUrl(dataUrl);
      imageDataUrlRef.current = dataUrl;
    } catch (err) {
      console.warn("Failed to pre-read image:", err);
    }
  };

  // ── Step 0 → Step 1 transition: fire identity extraction + system prompt ──
  const onLeaveStep0 = async () => {
    // 1. System prompt generation (already existed)
    if (form.category && form.category.trim() !== "") {
      setGeneratingPrompt(true);
      generateSystemPrompt(form.category, form.product_name)
        .then((res) => {
          if (res && res.system_prompt) setSystemPrompt(res.system_prompt);
        })
        .catch((err) => console.warn("System prompt failed:", err))
        .finally(() => setGeneratingPrompt(false));
    }

    // 2. Identity extraction from product image
    const imgData = imageDataUrlRef.current || imageDataUrl;
    if (imgData || form.product_image_url) {
      setDnaStatus("running");
      setExtractingDna(true);
      extractIdentityLite({
        productName: form.product_name,
        imageDataUrl: imgData || undefined,
        imageUrl: form.product_image_url || undefined,
        identityNotes: form.identity_notes || undefined,
      })
        .then((res) => {
          if (res && res.status === "success" && res.visual_dna) {
            setVisualDna(res.visual_dna);
            setDnaStatus("done");
          } else {
            setDnaStatus("failed");
          }
        })
        .catch((err) => {
          console.warn("Identity extraction failed:", err);
          setDnaStatus("failed");
        })
        .finally(() => setExtractingDna(false));
    }
  };

  // ── Step 1 → Step 2 transition: fire competitor + trend analysis ──
  const onLeaveStep1 = async () => {
    // 1. Trend analysis
    setTrendStatus("running");
    analyzeCategoryTrends({
      category: form.category,
      platform: "youtube",
      region_code: form.region_code,
      max_results: 10,
    })
      .then((res) => {
        if (res) {
          setTrendData(res);
          setTrendStatus("done");
        } else {
          setTrendStatus("failed");
        }
      })
      .catch((err) => {
        console.warn("Trend analysis failed:", err);
        setTrendStatus("failed");
      });

    // 2. Competitor analysis
    const handles = String(form.competitor_handles || "")
      .split(/[\n,]/)
      .map((x) => x.trim())
      .filter(Boolean);
    if (handles.length > 0) {
      setCompetitorStatus("running");
      analyzeCompetitors(handles)
        .then((res) => {
          if (res) {
            setCompetitorData(res);
            setCompetitorStatus("done");
          } else {
            setCompetitorStatus("failed");
          }
        })
        .catch((err) => {
          console.warn("Competitor analysis failed:", err);
          setCompetitorStatus("failed");
        });
    }
  };

  const run = async () => {
    setLoading(true);
    setStatus("Initializing campaign pipeline...");
    setError("");
    setJobId(null);
    setResult(null);
    try {
      let imagePayload = imageDataUrl;
      if (selectedImage && !imagePayload) {
        imagePayload = await readAsDataUrl(selectedImage);
        setImageDataUrl(imagePayload);
      }

      const competitor_handles = String(form.competitor_handles || "")
        .split(/[\n,]/)
        .map((x) => x.trim())
        .filter(Boolean);

      const payload = {
        ...form,
        competitor_handles,
        poster_generation_count: Number(form.poster_generation_count || 1),
        video_duration_seconds: Number(form.video_duration_seconds || 6),
        product_image_data_url: imagePayload || undefined,
        system_prompt: systemPrompt || undefined,
        // ── Pass pre-computed data from progressive pipeline ──
        ...(visualDna ? { visual_dna_precomputed: visualDna } : {}),
      };

      setStatus("Running AI pipeline...");
      const data = await runFullCampaignPipeline(payload);

      // Text results arrive immediately — show them right away!
      setResult(data);
      if (data) saveCampaignRecord(data);
      // Auto-fill compare input with handles they already typed
      if (form.competitor_handles) {
        setCompareInput(form.competitor_handles);
      }
      setStatus("Campaign strategy generated! Media assets rendering...");

      // If a background media job was created, track it via WebSocket
      if (data && data.media_render_job_id) {
        setJobId(data.media_render_job_id);
      } else {
        setLoading(false);
      }
    } catch (err) {
      setError(err.message || "Pipeline failed");
      setStatus("");
      setLoading(false);
    }
  };

  const stepContent = [
    // Step 0: Product
    <div key="product" className="space-y-4">
      <Field label="Product Name">
        <input
          type="text"
          value={form.product_name}
          onChange={(e) => update("product_name", e.target.value)}
          className="cn-input"
          placeholder="e.g. Pigeon Air Fryer"
        />
      </Field>
      <Field label="Product Description" hint="Describe your product, price range, and key benefits">
        <textarea
          value={form.product_description}
          onChange={(e) => update("product_description", e.target.value)}
          className="cn-input min-h-[80px] resize-none"
          placeholder="Affordable air fryer for healthy cooking..."
        />
      </Field>
      <Field label="Category" hint="Select a category or type your own">
        <select
          value={isOtherCategory ? "Other" : form.category}
          onChange={(e) => {
            const val = e.target.value;
            if (val === "Other") {
              setIsOtherCategory(true);
              update("category", "");
            } else {
              setIsOtherCategory(false);
              update("category", val);
            }
          }}
          className="cn-input mb-2"
        >
          <option value="Kitchen Appliances">Kitchen Appliances</option>
          <option value="Tech">Tech</option>
          <option value="Fashion">Fashion</option>
          <option value="Finance">Finance</option>
          <option value="Other">Other</option>
        </select>
        {isOtherCategory && (
          <input
            type="text"
            value={form.category}
            onChange={(e) => update("category", e.target.value)}
            className="cn-input mt-2"
            placeholder="Type your category..."
            autoFocus
          />
        )}
      </Field>
      <Field label="Product Image (optional)">
        <div className="relative">
          <input
            type="file"
            accept="image/*"
            onChange={handleImageSelect}
            className="hidden"
            id="product-image"
          />
          <label
            htmlFor="product-image"
            className="flex items-center gap-3 p-4 border border-dashed border-neutral-300 rounded-xl cursor-pointer hover:border-neutral-900 hover:bg-neutral-50 transition-all"
          >
            {imagePreview ? (
              <img src={imagePreview} alt="Preview" className="w-12 h-12 object-cover rounded-lg" />
            ) : (
              <div className="w-12 h-12 bg-neutral-100 rounded-lg flex items-center justify-center">
                <Image size={20} className="text-neutral-400" strokeWidth={1.5} />
              </div>
            )}
            <div>
              <p className="text-sm font-medium text-neutral-900">
                {selectedImage ? selectedImage.name : "Upload product image"}
              </p>
              <p className="text-xs text-neutral-400">PNG, JPG up to 10MB</p>
            </div>
          </label>
        </div>
      </Field>
    </div>,

    // Step 1: Audience
    <div key="audience" className="space-y-4">
      <Field label="Target Audience">
        <input
          type="text"
          value={form.target_audience}
          onChange={(e) => update("target_audience", e.target.value)}
          className="cn-input"
          placeholder="e.g. India budget-conscious home cooks"
        />
      </Field>
      <Field label="Region">
        <select
          value={form.region_code}
          onChange={(e) => update("region_code", e.target.value)}
          className="cn-input"
        >
          <option value="IN">India (IN)</option>
          <option value="US">United States (US)</option>
          <option value="GB">United Kingdom (GB)</option>
          <option value="AE">UAE (AE)</option>
          <option value="SG">Singapore (SG)</option>
        </select>
      </Field>
      <Field label="Competitor Handles" hint="Instagram handles or keywords, comma-separated">
        <textarea
          value={form.competitor_handles}
          onChange={(e) => update("competitor_handles", e.target.value)}
          className="cn-input min-h-[80px] resize-none font-mono text-xs"
          placeholder="@philipsindia, @havellsindia"
        />
      </Field>
    </div>,

    // Step 2: Creative
    <div key="creative" className="space-y-4">
      <Field label="Brand Identity Notes" hint="Colors, tone, style preferences">
        <textarea
          value={form.identity_notes}
          onChange={(e) => update("identity_notes", e.target.value)}
          className="cn-input min-h-[80px] resize-none"
          placeholder="Modern, clean, blue and white palette..."
        />
      </Field>
      <Field label="Number of Posters">
        <div className="flex items-center gap-3">
          {[1, 2, 3].map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => update("poster_generation_count", n)}
              className={clsx(
                "w-10 h-10 rounded-lg border text-sm font-semibold transition-all",
                form.poster_generation_count === n
                  ? "bg-neutral-900 text-white border-neutral-900"
                  : "bg-white text-neutral-700 border-neutral-200 hover:border-neutral-400"
              )}
            >
              {n}
            </button>
          ))}
        </div>
      </Field>
      <Field label="Video Generation">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => update("video_generation_enabled", !form.video_generation_enabled)}
            className={clsx(
              "relative w-10 h-5 rounded-full transition-colors duration-200",
              form.video_generation_enabled ? "bg-neutral-900" : "bg-neutral-200"
            )}
          >
            <span
              className={clsx(
                "absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow-xs transition-transform duration-200",
                form.video_generation_enabled ? "translate-x-5" : ""
              )}
            />
          </button>
          <span className="text-sm text-neutral-700">
            {form.video_generation_enabled ? "Enabled" : "Disabled"}
          </span>
        </div>
      </Field>
      {form.video_generation_enabled && (
        <Field label="Video Duration">
          <div className="flex flex-col gap-3">
            {[
              { seconds: 6, label: "Short (6s)" },
              { seconds: 10, label: "Standard (10s)" },
              { seconds: 15, label: "Extended (15s)" }
            ].map((opt) => (
              <button
                key={opt.seconds}
                type="button"
                onClick={() => update("video_duration_seconds", opt.seconds)}
                className={clsx(
                  "flex items-center justify-between px-4 py-3 rounded-lg border transition-all text-left",
                  form.video_duration_seconds === opt.seconds
                    ? "bg-neutral-900 border-neutral-900 shadow-md ring-2 ring-neutral-900 ring-offset-2"
                    : "bg-white border-neutral-200 hover:border-neutral-400"
                )}
              >
                <div>
                  <div className={clsx(
                    "text-sm font-medium",
                    form.video_duration_seconds === opt.seconds ? "text-white" : "text-neutral-900"
                  )}>
                    {opt.label}
                  </div>
                </div>
              </button>
            ))}
            <p className="text-xs text-neutral-500 mt-1">
              Currently using OpenAI Sora direct API endpoints.
            </p>
          </div>
        </Field>
      )}
    </div>,

    // Step 3: Launch
    <div key="launch" className="space-y-4">
      <div className="cn-card bg-neutral-50 border-neutral-200">
        <h3 className="text-sm font-semibold text-neutral-900 mb-4">Campaign Summary</h3>
        <div className="space-y-2">
          {[
            { label: "Product", value: form.product_name },
            { label: "Category", value: form.category },
            { label: "Region", value: form.region_code },
            { label: "Audience", value: form.target_audience },
            { label: "Posters", value: `${form.poster_generation_count} poster(s)` },
            { label: "Video", value: form.video_generation_enabled ? `${form.video_duration_seconds}s video` : "Disabled" },
          ].map(({ label, value }) => (
            <div key={label} className="flex items-center justify-between text-sm">
              <span className="text-neutral-500">{label}</span>
              <span className="text-neutral-900 font-medium">{value}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Progressive Pipeline Status */}
      <div className="cn-card bg-neutral-50 border-neutral-200">
        <h3 className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-3">Pipeline Pre-processing</h3>
        <div className="space-y-2">
          {[
            { label: "System Prompt", status: generatingPrompt ? "running" : systemPrompt ? "done" : "" },
            { label: "Visual DNA Extraction", status: dnaStatus },
            { label: "Trend Analysis", status: trendStatus },
            { label: "Competitor Analysis", status: competitorStatus },
          ]
            .filter(({ status }) => status)
            .map(({ label, status: s }) => (
              <div key={label} className="flex items-center justify-between text-sm">
                <span className="text-neutral-600">{label}</span>
                <span className="flex items-center gap-1.5">
                  {s === "running" && <Loader2 size={12} className="text-blue-500 animate-spin" />}
                  {s === "done" && <CheckCircle2 size={12} className="text-green-600" />}
                  {s === "failed" && <AlertCircle size={12} className="text-amber-500" />}
                  <span className={clsx(
                    "text-xs font-medium",
                    s === "running" && "text-blue-600",
                    s === "done" && "text-green-700",
                    s === "failed" && "text-amber-600"
                  )}>
                    {s === "running" ? "Processing..." : s === "done" ? "Ready" : "Will retry on launch"}
                  </span>
                </span>
              </div>
            ))}
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
          <AlertCircle size={15} className="text-red-500 mt-0.5 flex-shrink-0" />
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}

      {status && !error && !jobId && (
        <div className="flex items-center gap-2 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <Loader2 size={14} className="text-blue-500 animate-spin" />
          <p className="text-sm text-blue-600">{status}</p>
        </div>
      )}

      {jobId && !error && (
        <LiveJobTracker
          jobId={jobId}
          onComplete={(mediaResult) => {
            // Merge media assets from the background job back into the result
            if (mediaResult && result) {
              setResult((prev) => ({
                ...prev,
                poster_assets: mediaResult.poster_assets || prev?.poster_assets || [],
                video_asset: mediaResult.video_asset || prev?.video_asset,
                downloads: {
                  ...(prev?.downloads || {}),
                  ...(mediaResult.downloads || {}),
                },
              }));
            }
            setStatus("Campaign + media assets generated successfully!");
            setLoading(false);
            setJobId(null);
          }}
          onTerminal={(payload) => {
            if (!payload) return;
            const state = String(payload.status || '').toLowerCase();

            if (state === 'failed' || state === 'cancelled') {
              setError(payload.error || payload.message || 'Media rendering did not complete. You can retry from Content Library.');
              setStatus('');
              setLoading(false);
              setJobId(null);
            }
          }}
        />
      )}

      {result && (
        <div className="space-y-4">
          <div className="cn-card border-emerald-200 bg-emerald-50">
            <div className="flex items-center gap-2 mb-3">
              <CheckCircle2 size={16} className="text-emerald-600" />
              <span className="text-sm font-semibold text-emerald-800">Campaign Generated!</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {/* Poster downloads */}
              {(result.poster_assets || []).map((asset, i) => (
                <button
                  key={i}
                  onClick={() => downloadProtectedAsset(asset.download_url, asset.name)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-emerald-200 rounded-lg text-xs font-medium text-emerald-700 hover:bg-emerald-50 transition-colors"
                >
                  <Download size={12} />
                  Poster {i + 1}
                </button>
              ))}
              {/* Video download */}
              {result.video_asset?.download_url && (
                <button
                  onClick={() => downloadProtectedAsset(result.video_asset.download_url, result.video_asset.name || "campaign_video.mp4")}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-emerald-200 rounded-lg text-xs font-medium text-emerald-700 hover:bg-emerald-50 transition-colors"
                >
                  <Download size={12} />
                  {result.video_asset.asset_type === "video_blueprint" ? "Video Blueprint" : "Video"}
                </button>
              )}
              {/* Full JSON bundle */}
              <button
                onClick={() => downloadJson("campaign_data.json", result)}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-emerald-200 rounded-lg text-xs font-medium text-emerald-700 hover:bg-emerald-50 transition-colors"
              >
                <Download size={12} />
                JSON Data
              </button>
            </div>
          </div>

          {/* Campaign strategy */}
          {result.campaign?.campaign_strategy && (
            <div className="cn-card">
              <h3 className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-2">Campaign Strategy</h3>
              <p className="text-sm text-neutral-700 leading-relaxed whitespace-pre-line">{result.campaign.campaign_strategy}</p>
            </div>
          )}

          {/* Generated ideas grid */}
          {[
            { key: "blog_ideas", label: "Blog Ideas" },
            { key: "tweet_ideas", label: "Tweet Ideas" },
            { key: "reel_ideas", label: "Reel Ideas" },
            { key: "poster_ideas", label: "Poster Concepts" },
            { key: "short_video_ideas", label: "Video Scripts" },
          ]
            .filter(({ key }) => result.campaign?.[key]?.length > 0)
            .map(({ key, label }) => (
              <div key={key} className="cn-card">
                <h3 className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-3">{label}</h3>
                <ul className="space-y-2">
                  {result.campaign[key].map((idea, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <span className="text-[10px] font-bold text-neutral-400 mt-1 w-4 shrink-0">{idx + 1}.</span>
                      <span className="text-sm text-neutral-700 leading-snug">
                        {typeof idea === "object" ? JSON.stringify(idea) : idea}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}

          {/* View in Library shortcut */}
          <button
            onClick={() => navigate("/content-library", { state: { newCampaign: true } })}
            className="mt-3 w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-neutral-900 text-white rounded-lg text-sm font-semibold hover:bg-neutral-700 transition-colors"
          >
            <Library size={14} />
            View in Content Library
          </button>

          {/* Competitor Analysis Section */}
          <div className="cn-card mt-6 border-blue-200 bg-blue-50/50">
            <div className="flex items-center gap-2 mb-4">
              <Globe size={16} className="text-blue-600" />
              <h3 className="text-sm font-bold text-blue-900">Compare with Competitors</h3>
            </div>
            <p className="text-xs text-blue-700 mb-4">
              See how your new campaign stacks up against current market players using real-time API web search.
            </p>

            <div className="flex flex-col sm:flex-row gap-2 mb-4">
              <input
                type="text"
                value={compareInput}
                onChange={(e) => setCompareInput(e.target.value)}
                placeholder="Competitor handles or keywords (e.g. nike, adidas)"
                className="cn-input bg-white flex-1"
                disabled={isComparing}
              />
              <button
                onClick={async () => {
                  if (!compareInput.trim()) return;
                  setCompareError("");
                  setIsComparing(true);
                  try {
                    const handleList = compareInput.split(",").map((h) => h.trim()).filter(Boolean);
                    const data = await analyzeCompetitors(handleList);
                    setCompareResults(data);
                  } catch (err) {
                    setCompareError(err.message || "Failed to analyze competitors.");
                  } finally {
                    setIsComparing(false);
                  }
                }}
                disabled={isComparing || !compareInput.trim()}
                className="btn-primary flex items-center gap-2 whitespace-nowrap px-4 py-2 text-sm h-10"
              >
                {isComparing ? (
                  <><Loader2 size={14} className="animate-spin" /> Analyzing...</>
                ) : (
                  <><Search size={14} /> Compare</>
                )}
              </button>
            </div>

            {compareError && (
              <div className="text-xs text-red-600 bg-red-50 p-2 rounded-lg mb-4 border border-red-200">
                ⚠️ {compareError}
              </div>
            )}

            {compareResults?.analyses && (
              <div className="space-y-4 mt-6">
                {compareResults.analyses.map((item, i) => (
                  <div key={i} className="bg-white rounded-xl p-5 border border-neutral-200 shadow-sm">
                    <div className="flex items-center gap-2 mb-4 border-b border-neutral-100 pb-3">
                      <Users size={16} className="text-neutral-500" />
                      <h4 className="font-semibold text-neutral-900 capitalize text-sm">{item.competitor}</h4>
                    </div>

                    {item.opportunity_gap && (
                      <div className="mb-4">
                        <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-600 mb-1.5 flex items-center gap-1">
                          <CheckCircle2 size={12} /> Opportunity Gap (Your Advantage)
                        </p>
                        <p className="text-xs text-neutral-700 leading-relaxed bg-emerald-50/50 p-3 rounded-lg border border-emerald-100">
                          {item.opportunity_gap}
                        </p>
                      </div>
                    )}

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {item.viral_hooks && item.viral_hooks.length > 0 && (
                        <div>
                          <p className="text-[10px] font-bold uppercase tracking-wider text-neutral-500 mb-2">Their Viral Hooks</p>
                          <ul className="space-y-1.5">
                            {item.viral_hooks.slice(0, 3).map((hook, j) => (
                              <li key={j} className="flex items-start gap-1.5 text-xs text-neutral-600">
                                <ArrowUpRight size={12} className="text-emerald-500 mt-0.5 shrink-0" />
                                <span>{hook}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {item.complaints && item.complaints.length > 0 && (
                        <div>
                          <p className="text-[10px] font-bold uppercase tracking-wider text-neutral-500 mb-2">Audience Complaints</p>
                          <ul className="space-y-1.5">
                            {item.complaints.slice(0, 3).map((comp, j) => (
                              <li key={j} className="flex items-start gap-1.5 text-xs text-neutral-600">
                                <TrendingUp size={12} className="text-amber-500 mt-0.5 shrink-0" />
                                <span>{comp}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>,
  ];

  return (
    <div className="p-8 animate-fade-in">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-xl font-semibold text-neutral-900 tracking-tight">Create Campaign</h1>
          <p className="text-sm text-neutral-500 mt-0.5">
            AI-powered campaign generation in minutes
          </p>
        </div>

        {/* Step Indicator */}
        <StepIndicator current={step} />

        {/* Step Content */}
        <div className="cn-card mb-6 px-6 py-6 sm:px-7 sm:py-7">
          <h2 className="text-sm font-semibold text-neutral-900 mb-5 flex items-center gap-2">
            {step === 0 && <><Megaphone size={15} className="text-neutral-400" /> Product Details</>}
            {step === 1 && <><Users size={15} className="text-neutral-400" /> Target Audience</>}
            {step === 2 && <><Sparkles size={15} className="text-neutral-400" /> Creative Settings</>}
            {step === 3 && <><Globe size={15} className="text-neutral-400" /> Review & Launch</>}
          </h2>
          {stepContent[step]}
        </div>

        {/* Navigation */}
        <div className="flex items-center justify-between gap-3">
          <button
            onClick={() => setStep((s) => Math.max(0, s - 1))}
            disabled={step === 0}
            className="btn-secondary disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Back
          </button>

          {step < STEPS.length - 1 ? (
            <button
              onClick={async () => {
                if (step === 0) await onLeaveStep0();
                if (step === 1) await onLeaveStep1();
                setStep((s) => s + 1);
              }}
              className="btn-primary"
            >
              Continue
              <ChevronRight size={15} />
            </button>
          ) : (
            <div className="flex items-center gap-3">
              <button
                type="button"
                className="px-4 py-2 border border-neutral-200 rounded-lg bg-white text-neutral-600 hover:bg-neutral-50 hover:text-neutral-900 font-medium transition-colors text-xs w-full"
                onClick={() => {
                  const yes = window.confirm("Are you sure you want to discard this campaign?");
                  if (!yes) return;
                  sessionStorage.removeItem("cn_campaign_state");
                  setResult(null);
                  setStep(0);
                  setStatus("");
                  setJobId(null);
                  setVisualDna(null);
                  setTrendData(null);
                  setCompetitorData(null);
                }}
              >
                Discard & Start New
              </button>
              <button
                onClick={run}
                disabled={loading}
                className="btn-primary"
              >
                {loading ? (
                  <><Loader2 size={15} className="animate-spin" /> Generating...</>
                ) : (
                  <><Sparkles size={15} /> Launch Campaign</>
                )}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
