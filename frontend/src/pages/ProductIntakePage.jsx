import { useState, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
    Upload,
    Package,
    Users,
    Tag,
    FileText,
    ChevronRight,
    CheckCircle2,
    Loader2,
    Zap,
    Camera,
    Move3d,
    Palette,
    Lightbulb,
    Layers,
    AlertCircle,
    RefreshCw,
    ArrowRight,
} from "lucide-react";
import clsx from "clsx";
import { submitProductIntake } from "../services/intake";

// ─── Constants ────────────────────────────────────────────────────────────────

const CATEGORIES = [
    "Fashion & Apparel",
    "Beauty & Skincare",
    "Food & Beverage",
    "Electronics & Tech",
    "Home & Lifestyle",
    "Health & Wellness",
    "Jewellery & Accessories",
    "Sports & Fitness",
    "Toys & Kids",
    "Other",
];

const STEPS = ["Product Info", "Upload Image", "Analysing DNA", "Your DNA"];

// ─── Step Indicator ───────────────────────────────────────────────────────────

function StepIndicator({ current }) {
    return (
        <div className="flex items-center gap-0 justify-center mb-10">
            {STEPS.map((label, i) => (
                <div key={label} className="flex items-center">
                    <div className="flex flex-col items-center gap-1">
                        <div
                            className={clsx(
                                "w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300",
                                i < current
                                    ? "bg-emerald-50 text-emerald-600 border border-emerald-200"
                                    : i === current
                                        ? "bg-neutral-900 text-white ring-4 ring-neutral-100 shadow-md"
                                        : "bg-white text-neutral-400 border border-neutral-200"
                            )}
                        >
                            {i < current ? <CheckCircle2 size={14} /> : i + 1}
                        </div>
                        <span
                            className={clsx(
                                "text-[10px] font-medium whitespace-nowrap",
                                i <= current ? "text-neutral-900" : "text-neutral-400"
                            )}
                        >
                            {label}
                        </span>
                    </div>
                    {i < STEPS.length - 1 && (
                        <div
                            className={clsx(
                                "w-14 h-px mx-2 mb-4 transition-all duration-500",
                                i < current ? "bg-emerald-500" : "bg-neutral-200"
                            )}
                        />
                    )}
                </div>
            ))}
        </div>
    );
}

// ─── Step 1: Product Info ─────────────────────────────────────────────────────

function StepProductInfo({ form, onChange, onNext }) {
    const canContinue =
        form.productName.trim() && form.category && form.targetAudience.trim();

    return (
        <div className="space-y-5">
            <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1.5">
                    Product Name <span className="text-red-500">*</span>
                </label>
                <input
                    className="cn-input"
                    placeholder="e.g. Arctic Glow Serum"
                    value={form.productName}
                    onChange={(e) => onChange("productName", e.target.value)}
                />
            </div>

            <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1.5">
                    Category <span className="text-red-500">*</span>
                </label>
                <select
                    className="cn-input appearance-none cursor-pointer"
                    value={form.category}
                    onChange={(e) => onChange("category", e.target.value)}
                >
                    <option value="">
                        Select a category...
                    </option>
                    {CATEGORIES.map((c) => (
                        <option key={c} value={c}>
                            {c}
                        </option>
                    ))}
                </select>
            </div>

            <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1.5">
                    Target Audience <span className="text-red-500">*</span>
                </label>
                <input
                    className="cn-input"
                    placeholder="e.g. Women 25–40, interested in luxury skincare"
                    value={form.targetAudience}
                    onChange={(e) => onChange("targetAudience", e.target.value)}
                />
            </div>

            <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1.5">
                    Additional Context{" "}
                    <span className="text-neutral-400 text-xs font-normal">(optional)</span>
                </label>
                <textarea
                    rows={3}
                    className="cn-input resize-none"
                    placeholder="Key selling points, hero ingredients, USP, competitor notes..."
                    value={form.additionalContext}
                    onChange={(e) => onChange("additionalContext", e.target.value)}
                />
            </div>

            <button
                disabled={!canContinue}
                onClick={onNext}
                className={clsx(
                    "w-full flex items-center justify-center gap-2 py-2.5 rounded-lg font-medium text-sm transition-all shadow-sm",
                    canContinue
                        ? "bg-neutral-900 hover:bg-neutral-800 text-white"
                        : "bg-neutral-100 text-neutral-400 cursor-not-allowed border border-neutral-200"
                )}
            >
                Continue <ChevronRight size={16} />
            </button>
        </div>
    );
}

// ─── Step 2: Upload Image ─────────────────────────────────────────────────────

function StepUploadImage({ imageFile, imagePreview, onFileSet, onNext, onBack, loading }) {
    const inputRef = useRef(null);
    const [dragging, setDragging] = useState(false);

    const handleFile = (file) => {
        if (!file) return;
        const validTypes = ["image/jpeg", "image/png", "image/webp", "image/jpg"];
        if (!validTypes.includes(file.type)) {
            alert("Please upload a JPEG, PNG or WEBP image.");
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            alert("Image must be under 10 MB.");
            return;
        }
        const url = URL.createObjectURL(file);
        onFileSet(file, url);
    };

    const onDrop = useCallback(
        (e) => {
            e.preventDefault();
            setDragging(false);
            const file = e.dataTransfer.files[0];
            handleFile(file);
        },
        []
    );

    return (
        <div className="space-y-5">
            {/* Drop zone */}
            <div
                className={clsx(
                    "relative border-2 border-dashed rounded-xl transition-all duration-150 cursor-pointer overflow-hidden",
                    dragging
                        ? "border-blue-400 bg-blue-50"
                        : imagePreview
                            ? "border-neutral-200 bg-neutral-50"
                            : "border-neutral-200 hover:border-neutral-300 bg-white hover:bg-neutral-50"
                )}
                onDragOver={(e) => {
                    e.preventDefault();
                    setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                onClick={() => !imagePreview && inputRef.current?.click()}
            >
                {imagePreview ? (
                    <div className="relative">
                        <img
                            src={imagePreview}
                            alt="Product preview"
                            className="w-full max-h-64 object-contain p-4 bg-neutral-50"
                        />
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                onFileSet(null, null);
                            }}
                            className="absolute top-3 right-3 bg-white hover:bg-neutral-100 text-neutral-600 border border-neutral-200 shadow-sm rounded-full p-1.5 transition"
                        >
                            <RefreshCw size={14} />
                        </button>
                    </div>
                ) : (
                    <div className="flex flex-col items-center gap-3 py-12 px-6 text-center">
                        <div className="w-12 h-12 rounded-xl bg-neutral-100 border border-neutral-200 flex items-center justify-center">
                            <Upload size={20} className="text-neutral-500" />
                        </div>
                        <div>
                            <p className="text-neutral-900 font-medium text-sm">
                                Drag & drop your product image
                            </p>
                            <p className="text-neutral-500 text-xs mt-1">
                                or click to browse — JPEG, PNG, WEBP up to 10 MB
                            </p>
                        </div>
                    </div>
                )}
                <input
                    ref={inputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    className="hidden"
                    onChange={(e) => handleFile(e.target.files[0])}
                />
            </div>

            {imagePreview && (
                <div className="flex items-center gap-2 px-3 py-2 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-700">
                    <CheckCircle2 size={14} />
                    <span>Image ready — Generative AI will analyse it</span>
                </div>
            )}

            <div className="flex gap-3">
                <button
                    onClick={onBack}
                    className="flex-1 py-2.5 rounded-lg font-medium text-sm bg-white border border-neutral-200 hover:bg-neutral-50 text-neutral-700 transition"
                >
                    Back
                </button>
                <button
                    disabled={!imageFile || loading}
                    onClick={onNext}
                    className={clsx(
                        "flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg font-medium text-sm transition-all shadow-sm",
                        imageFile && !loading
                            ? "bg-neutral-900 hover:bg-neutral-800 text-white"
                            : "bg-neutral-100 text-neutral-400 cursor-not-allowed border border-neutral-200"
                    )}
                >
                    {loading ? (
                        <>
                            <Loader2 size={16} className="animate-spin" /> Uploading...
                        </>
                    ) : (
                        <>
                            Extract Features <Zap size={16} />
                        </>
                    )}
                </button>
            </div>
        </div>
    );
}

// ─── Step 3: Analysing ────────────────────────────────────────────────────────

const ANALYSIS_STEPS = [
    "Reading visual properties...",
    "Identifying materials & textures...",
    "Mapping lighting conditions...",
    "Detecting structural geometry...",
    "Generating 1536-dim embedding...",
    "Locking in the Geometric Lock™...",
];

function StepAnalysing() {
    const [stepIdx, setStepIdx] = useState(0);

    useState(() => {
        const interval = setInterval(() => {
            setStepIdx((i) => Math.min(i + 1, ANALYSIS_STEPS.length - 1));
        }, 2000);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="flex flex-col items-center gap-8 py-8">
            {/* Animated ring */}
            <div className="relative w-24 h-24 mb-4">
                <div className="absolute inset-0 rounded-full border-4 border-neutral-100 animate-ping" />
                <div className="absolute inset-2 rounded-full border-4 border-t-neutral-900 border-r-neutral-300 border-b-neutral-100 border-l-neutral-100 animate-spin" />
                <div className="absolute inset-0 flex items-center justify-center">
                    <Zap size={24} className="text-neutral-900" />
                </div>
            </div>

            <div className="text-center space-y-1 mb-2">
                <p className="text-neutral-900 font-semibold text-lg">
                    Extracting Product Features
                </p>
                <p className="text-neutral-500 text-sm">
                    AI is analysing your product image...
                </p>
            </div>

            <div className="w-full max-w-xs space-y-2">
                {ANALYSIS_STEPS.map((s, i) => (
                    <div
                        key={s}
                        className={clsx(
                            "flex items-center gap-2.5 text-sm transition-all duration-300",
                            i < stepIdx
                                ? "text-neutral-400"
                                : i === stepIdx
                                    ? "text-neutral-900 font-medium"
                                    : "text-neutral-300"
                        )}
                    >
                        {i < stepIdx ? (
                            <CheckCircle2 size={14} className="text-emerald-500 shrink-0" />
                        ) : i === stepIdx ? (
                            <Loader2 size={14} className="animate-spin text-neutral-900 shrink-0" />
                        ) : (
                            <div className="w-3.5 h-3.5 rounded-full border border-neutral-200 shrink-0" />
                        )}
                        {s}
                    </div>
                ))}
            </div>
        </div>
    );
}

// ─── Step 4: DNA Result ───────────────────────────────────────────────────────

function DNAChip({ label, value }) {
    if (!value || (Array.isArray(value) && value.length === 0)) return null;
    return (
        <div className="bg-neutral-50 border border-neutral-200 rounded-xl p-3">
            <p className="text-neutral-500 text-xs font-semibold uppercase tracking-wider mb-1.5">
                {label}
            </p>
            {Array.isArray(value) ? (
                <ul className="space-y-1">
                    {value.map((v, i) => (
                        <li key={i} className="text-neutral-700 text-sm flex gap-2">
                            <span className="text-blue-500 mt-0.5">•</span>
                            {v}
                        </li>
                    ))}
                </ul>
            ) : typeof value === "object" ? (
                <div className="space-y-0.5">
                    {Object.entries(value)
                        .filter(([, v]) => v && !(Array.isArray(v) && v.length === 0))
                        .map(([k, v]) => (
                            <p key={k} className="text-neutral-700 text-sm">
                                <span className="text-neutral-500 capitalize">
                                    {k.replace(/_/g, " ")}:
                                </span>{" "}
                                {Array.isArray(v) ? v.join(", ") : String(v)}
                            </p>
                        ))}
                </div>
            ) : (
                <p className="text-neutral-700 text-sm">{value}</p>
            )}
        </div>
    );
}

function StepDNAResult({ result, imagePreview, onContinue }) {
    const { visual_dna: dna } = result;
    const confidence = Math.round((dna.confidence_score || 0) * 100);

    return (
        <div className="space-y-5 animate-fade-in">
            {/* Header */}
            <div className="flex items-start gap-4">
                {imagePreview && (
                    <img
                        src={imagePreview}
                        alt="Product"
                        className="w-20 h-20 object-cover rounded-xl border border-neutral-200 shrink-0 bg-neutral-50 p-1"
                    />
                )}
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                        <CheckCircle2 size={16} className="text-emerald-600" />
                        <span className="text-emerald-600 text-sm font-semibold">
                            Visual DNA Extracted
                        </span>
                    </div>
                    <h3 className="text-neutral-900 font-bold text-lg leading-snug">
                        {result.product_name}
                    </h3>
                    <p className="text-neutral-500 text-sm mt-0.5">{dna.product_category}</p>
                    {/* Confidence bar */}
                    <div className="flex items-center gap-2 mt-2">
                        <div className="flex-1 h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                            <div
                                className="h-full bg-blue-500 rounded-full transition-all duration-700"
                                style={{ width: `${confidence}%` }}
                            />
                        </div>
                        <span className="text-xs text-neutral-500 font-medium">{confidence}% match</span>
                    </div>
                </div>
            </div>

            {/* Description */}
            {dna.product_description && (
                <p className="text-neutral-600 text-sm leading-relaxed bg-neutral-50 rounded-xl p-3 border border-neutral-200">
                    {dna.product_description}
                </p>
            )}

            {/* DNA Grid */}
            <div className="grid grid-cols-2 gap-3">
                <div className="col-span-2">
                    <DNAChip label="Materials" value={dna.materials} />
                </div>
                <DNAChip label="Lighting" value={dna.lighting} />
                <DNAChip label="Structure" value={dna.structure} />
                <div className="col-span-2">
                    <DNAChip label="Motion Recommendations" value={dna.motion_recommendations} />
                </div>
                <div className="col-span-2">
                    <DNAChip label="Camera Angle Suggestions" value={dna.camera_angle_suggestions} />
                </div>
            </div>

            {/* Vault IDs */}
            <div className="bg-neutral-50 border border-neutral-200 rounded-xl p-3 text-xs font-mono text-neutral-500">
                <p>
                    Project: <span className="text-neutral-900 font-semibold">{result.project_id}</span>
                </p>
                <p className="mt-1">
                    Embedding: <span className="text-neutral-900 font-semibold">{result.embedding_id}</span>
                </p>
            </div>

            <button
                onClick={() => onContinue(result)}
                className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg font-medium text-sm bg-neutral-900 hover:bg-neutral-800 text-white shadow-sm transition-all mt-4"
            >
                Continue to Market Scouting <ArrowRight size={16} />
            </button>
        </div>
    );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function ProductIntakePage() {
    const navigate = useNavigate();
    const [step, setStep] = useState(0);
    const [form, setForm] = useState({
        productName: "",
        category: "",
        targetAudience: "",
        additionalContext: "",
    });
    const [imageFile, setImageFile] = useState(null);
    const [imagePreview, setImagePreview] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [result, setResult] = useState(null);

    const handleFormChange = (key, value) => {
        setForm((f) => ({ ...f, [key]: value }));
    };

    const handleFileSet = (file, preview) => {
        setImageFile(file);
        setImagePreview(preview);
    };

    const handleSubmit = async () => {
        setLoading(true);
        setError(null);
        setStep(2); // show analysing step immediately

        try {
            const data = await submitProductIntake({
                productName: form.productName,
                category: form.category,
                targetAudience: form.targetAudience,
                additionalContext: form.additionalContext,
                imageFile,
            });
            setResult(data);
            setStep(3);
        } catch (err) {
            setError(err.message || "Something went wrong. Please try again.");
            setStep(1); // back to upload step
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="p-8 animate-fade-in max-w-2xl mx-auto">
            {/* Header */}
            <div className="mb-8">
                <h1 className="text-xl font-semibold text-neutral-900 tracking-tight flex items-center gap-2">
                    <Package size={20} className="text-neutral-500" />
                    Product Intake
                </h1>
                <p className="text-sm text-neutral-500 mt-1">
                    Step 1 · Create a digital twin of your product for AI video generation
                </p>
            </div>

            <StepIndicator current={step} />

            {/* Card */}
            <div className="cn-card">
                {/* Error banner */}
                {error && (
                    <div className="flex items-start gap-2 mb-6 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                        <AlertCircle size={16} className="mt-0.5 shrink-0" />
                        {error}
                    </div>
                )}

                {step === 0 && (
                    <StepProductInfo
                        form={form}
                        onChange={handleFormChange}
                        onNext={() => setStep(1)}
                    />
                )}
                {step === 1 && (
                    <StepUploadImage
                        imageFile={imageFile}
                        imagePreview={imagePreview}
                        onFileSet={handleFileSet}
                        onBack={() => setStep(0)}
                        onNext={handleSubmit}
                        loading={loading}
                    />
                )}
                {step === 2 && <StepAnalysing />}
                {step === 3 && result && (
                    <StepDNAResult
                        result={result}
                        imagePreview={imagePreview}
                        onContinue={(r) => navigate("/market-scout", { state: { productName: r.product_name, category: r.visual_dna?.product_category || form.category } })}
                    />
                )}
            </div>
        </div>
    );
}
