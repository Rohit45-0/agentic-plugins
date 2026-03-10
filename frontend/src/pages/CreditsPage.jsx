import { useState, useEffect } from "react";
import {
    Coins,
    Zap,
    FileText,
    Video,
    Bot,
    Sparkles,
    CheckCircle2,
    AlertTriangle,
    RefreshCw,
    CreditCard,
    ChevronRight,
} from "lucide-react";
import { apiRequest } from "../services/api";

const ICON_MAP = {
    "Full Campaign Pipeline": Sparkles,
    "Generate Blog Post": FileText,
    "Generate Reel (6s Sora)": Video,
    "AI Chatbot": Bot,
};

const TOPUP_PACKS = [
    { label: "Starter", credits: 500, price: "$5.00", popular: false },
    { label: "Growth", credits: 1500, price: "$13.00", popular: true, badge: "Best Value" },
    { label: "Pro", credits: 4000, price: "$30.00", popular: false },
];

function StatCard({ label, value, sub, accent }) {
    return (
        <div
            className={`rounded-2xl p-5 flex flex-col gap-1 border ${accent
                    ? "bg-gradient-to-br from-neutral-900 to-neutral-700 border-neutral-700 text-white"
                    : "bg-white border-neutral-200"
                }`}
        >
            <p className={`text-xs font-medium ${accent ? "text-neutral-400" : "text-neutral-500"}`}>
                {label}
            </p>
            <p className={`text-3xl font-bold tracking-tight ${accent ? "text-white" : "text-neutral-900"}`}>
                {value}
            </p>
            {sub && (
                <p className={`text-xs mt-0.5 ${accent ? "text-neutral-400" : "text-neutral-500"}`}>{sub}</p>
            )}
        </div>
    );
}

export default function CreditsPage() {
    const [wallet, setWallet] = useState(null);
    const [loading, setLoading] = useState(true);
    const [topupSuccess, setTopupSuccess] = useState(false);
    const [topupLoading, setTopupLoading] = useState(false);

    const fetchWallet = async () => {
        setLoading(true);
        try {
            const data = await apiRequest("/auth/wallet");
            setWallet(data);
        } catch {
            // silent
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchWallet();
    }, []);

    const handleTopup = async (pack) => {
        setTopupLoading(true);
        // Simulated top-up (Stripe integration will be wired here later)
        await new Promise((r) => setTimeout(r, 1200));
        setTopupLoading(false);
        setTopupSuccess(true);
        setTimeout(() => setTopupSuccess(false), 3000);
    };

    const balanceCents = wallet?.balance_cents ?? 0;
    const balancePct = Math.min((balanceCents / 500) * 100, 100);
    const isLow = balanceCents < 100;

    return (
        <div className="p-8 max-w-4xl animate-fade-in">
            {/* Header */}
            <div className="mb-8">
                <h1 className="text-xl font-semibold text-neutral-900 tracking-tight flex items-center gap-2">
                    <Coins size={20} strokeWidth={2} className="text-green-600" />
                    Credits &amp; Billing
                </h1>
                <p className="text-sm text-neutral-500 mt-0.5">
                    Manage your AI generation credits. Every new account starts with <strong>$5.00 free credits</strong>.
                </p>
            </div>

            {loading ? (
                <div className="flex items-center gap-2 text-neutral-400 py-12 justify-center">
                    <RefreshCw size={16} className="animate-spin" />
                    <span className="text-sm">Loading wallet…</span>
                </div>
            ) : (
                <>
                    {/* Balance Cards */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
                        <StatCard
                            accent
                            label="Available Balance"
                            value={wallet?.balance_display ?? "$0.00"}
                            sub="Your current credit balance"
                        />
                        <StatCard
                            label="Starting Credits"
                            value="$5.00"
                            sub="Free trial for new accounts"
                        />
                        <StatCard
                            label="Credits Spent"
                            value={`$${((500 - balanceCents) / 100).toFixed(2)}`}
                            sub="Since account creation"
                        />
                    </div>

                    {/* Progress Bar */}
                    <div className="bg-white border border-neutral-200 rounded-2xl p-5 mb-8">
                        <div className="flex items-center justify-between mb-3">
                            <p className="text-sm font-semibold text-neutral-900">Credit Usage</p>
                            <span
                                className={`text-xs font-medium px-2 py-0.5 rounded-full ${isLow
                                        ? "bg-red-50 text-red-600 border border-red-100"
                                        : "bg-green-50 text-green-700 border border-green-100"
                                    }`}
                            >
                                {isLow ? "Low Balance" : "Healthy"}
                            </span>
                        </div>
                        <div className="h-3 w-full bg-neutral-100 rounded-full overflow-hidden">
                            <div
                                className={`h-full rounded-full transition-all duration-700 ${isLow ? "bg-red-400" : "bg-gradient-to-r from-green-400 to-emerald-500"
                                    }`}
                                style={{ width: `${balancePct}%` }}
                            />
                        </div>
                        <div className="flex justify-between mt-2 text-xs text-neutral-400">
                            <span>$0.00</span>
                            <span>$5.00 (Free Trial)</span>
                        </div>
                        {isLow && (
                            <div className="flex items-start gap-2 mt-4 p-3 bg-red-50 border border-red-100 rounded-xl text-xs text-red-700">
                                <AlertTriangle size={14} className="mt-0.5 flex-shrink-0" />
                                <p>
                                    Your balance is running low. Top up to continue generating reels, blogs, and campaigns without
                                    interruption.
                                </p>
                            </div>
                        )}
                    </div>

                    {/* Pricing Table */}
                    <div className="bg-white border border-neutral-200 rounded-2xl p-5 mb-8">
                        <h2 className="text-sm font-semibold text-neutral-900 mb-4">Generation Pricing</h2>
                        <p className="text-xs text-neutral-500 mb-4">
                            Credits are deducted from your balance after each successful generation. The AI Chatbot is always free.
                        </p>
                        <div className="space-y-2">
                            {wallet?.pricing?.map((item) => {
                                const Icon = ICON_MAP[item.action] ?? Zap;
                                return (
                                    <div
                                        key={item.action}
                                        className="flex items-center justify-between py-3 px-4 rounded-xl bg-neutral-50 border border-neutral-100 hover:border-neutral-200 transition-all"
                                    >
                                        <div className="flex items-center gap-3">
                                            <div className="w-8 h-8 rounded-lg bg-white border border-neutral-200 flex items-center justify-center">
                                                <Icon size={15} className="text-neutral-600" strokeWidth={1.75} />
                                            </div>
                                            <span className="text-sm font-medium text-neutral-800">{item.action}</span>
                                        </div>
                                        <span
                                            className={`text-sm font-bold ${item.cost_cents === 0 ? "text-green-600" : "text-neutral-900"
                                                }`}
                                        >
                                            {item.label}
                                        </span>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* Top-Up Packs */}
                    <div className="bg-white border border-neutral-200 rounded-2xl p-5">
                        <div className="flex items-center justify-between mb-5">
                            <div>
                                <h2 className="text-sm font-semibold text-neutral-900">Top Up Credits</h2>
                                <p className="text-xs text-neutral-500 mt-0.5">
                                    Stripe payment integration coming soon. Select a pack to purchase.
                                </p>
                            </div>
                            {topupSuccess && (
                                <span className="flex items-center gap-1.5 text-xs text-green-700 font-medium bg-green-50 border border-green-100 px-3 py-1.5 rounded-full animate-fade-in">
                                    <CheckCircle2 size={12} />
                                    Top-up simulated!
                                </span>
                            )}
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                            {TOPUP_PACKS.map((pack) => (
                                <div
                                    key={pack.label}
                                    className={`relative rounded-2xl border p-5 flex flex-col gap-3 transition-all hover:shadow-md ${pack.popular
                                            ? "border-neutral-900 bg-neutral-900 text-white"
                                            : "border-neutral-200 bg-white"
                                        }`}
                                >
                                    {pack.badge && (
                                        <span className="absolute -top-2.5 left-1/2 -translate-x-1/2 text-[10px] font-bold bg-green-500 text-white px-3 py-0.5 rounded-full uppercase tracking-wide whitespace-nowrap">
                                            {pack.badge}
                                        </span>
                                    )}
                                    <p className={`text-xs font-semibold uppercase tracking-wider ${pack.popular ? "text-neutral-400" : "text-neutral-500"}`}>
                                        {pack.label}
                                    </p>
                                    <p className={`text-2xl font-bold tracking-tight ${pack.popular ? "text-white" : "text-neutral-900"}`}>
                                        {pack.price}
                                    </p>
                                    <p className={`text-xs ${pack.popular ? "text-neutral-400" : "text-neutral-500"}`}>
                                        +{(pack.credits / 100).toFixed(0)} credits added to your wallet
                                    </p>
                                    <button
                                        onClick={() => handleTopup(pack)}
                                        disabled={topupLoading}
                                        className={`mt-auto flex items-center justify-center gap-2 py-2 px-4 rounded-xl text-sm font-semibold transition-all ${pack.popular
                                                ? "bg-white text-neutral-900 hover:bg-neutral-100"
                                                : "bg-neutral-900 text-white hover:bg-neutral-800"
                                            } disabled:opacity-60`}
                                    >
                                        <CreditCard size={14} />
                                        {topupLoading ? "Processing…" : "Buy Now"}
                                        <ChevronRight size={14} />
                                    </button>
                                </div>
                            ))}
                        </div>
                        <p className="text-center text-xs text-neutral-400 mt-5">
                            🔒 Secure payments powered by Stripe — coming soon
                        </p>
                    </div>
                </>
            )}
        </div>
    );
}
