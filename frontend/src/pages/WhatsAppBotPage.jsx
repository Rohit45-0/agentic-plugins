import { useState, useEffect } from "react";
import axios from "axios";
import { getCurrentUser, getAccessToken } from "../services/auth";
import { Copy, Check, Clock, Calendar, CheckSquare, BarChart, TrendingUp, Sparkles, Store, Scissors, UtensilsCrossed, ShoppingCart, GraduationCap, Globe, BookOpen, RefreshCw, FileText, Zap, ArrowRight, ArrowLeft, Phone, Building2, MessageSquare, Stethoscope, QrCode, Settings, Plus, Trash2 } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";

const PLUGINS_API = import.meta.env.VITE_PLUGINS_API_URL || "https://web-production-ba9e.up.railway.app";

const useCaseOptions = [
    { key: "restaurant", label: "Restaurant / Mess", desc: "Table bookings, menu enquiries, order updates", icon: UtensilsCrossed, color: "text-orange-400", border: "border-orange-500/30", bg: "bg-orange-500/10", gradient: "from-orange-500/20 to-orange-600/5" },
    { key: "salon", label: "Salon / Parlour", desc: "Appointment scheduling, service menu, reminders", icon: Scissors, color: "text-pink-400", border: "border-pink-500/30", bg: "bg-pink-500/10", gradient: "from-pink-500/20 to-pink-600/5" },
    { key: "dentist", label: "Dentist / Clinic", desc: "Patient appointments, treatment info, follow-ups", icon: Stethoscope, color: "text-cyan-400", border: "border-cyan-500/30", bg: "bg-cyan-500/10", gradient: "from-cyan-500/20 to-cyan-600/5" },
    { key: "tiffin", label: "Tiffin / Meals", desc: "Meal subscriptions, daily menu, delivery updates", icon: Store, color: "text-green-400", border: "border-green-500/30", bg: "bg-green-500/10", gradient: "from-green-500/20 to-green-600/5" },
    { key: "kirana", label: "Kirana / Grocery", desc: "Order placement, stock enquiries, delivery tracking", icon: ShoppingCart, color: "text-blue-400", border: "border-blue-500/30", bg: "bg-blue-500/10", gradient: "from-blue-500/20 to-blue-600/5" },
    { key: "coaching", label: "Coaching / Tuition", desc: "Class schedules, doubt solving, fee reminders", icon: GraduationCap, color: "text-yellow-400", border: "border-yellow-500/30", bg: "bg-yellow-500/10", gradient: "from-yellow-500/20 to-yellow-600/5" },
    { key: "general", label: "General Business", desc: "Flexible AI assistant for any business type", icon: Globe, color: "text-neutral-400", border: "border-neutral-500/30", bg: "bg-neutral-500/10", gradient: "from-neutral-500/20 to-neutral-600/5" },
];

export default function WhatsAppBotPage() {
    const [botConfig, setBotConfig] = useState(null);
    const [slots, setSlots] = useState({
        slot_duration_minutes: 15,
        max_capacity_per_slot: 1,
        working_hours: {
            monday: [{ start: "09:00", end: "23:00" }],
            tuesday: [{ start: "09:00", end: "23:00" }],
            wednesday: [{ start: "09:00", end: "23:00" }],
            thursday: [{ start: "09:00", end: "23:00" }],
            friday: [{ start: "09:00", end: "23:00" }],
            saturday: [{ start: "09:00", end: "23:00" }],
            sunday: [{ start: "09:00", end: "23:00" }]
        }
    });

    const [analytics, setAnalytics] = useState(null);
    const [hasCopied, setHasCopied] = useState(false);
    const [syncing, setSyncing] = useState(false);
    const [loading, setLoading] = useState(true);
    const [user, setUser] = useState(null);

    // --- Setup Wizard State ---
    const [setupStep, setSetupStep] = useState(1); // 1=Business Type, 2=Details, 3=Review & Create
    const [setupData, setSetupData] = useState({
        use_case_type: "",
        business_display_name: "",
        owner_phone_number: "",
        whatsapp_phone_number: "",
    });
    const [creating, setCreating] = useState(false);

    const loadBotConfig = async (currentUser) => {
        try {
            const res = await axios.get(`${PLUGINS_API}/api/v1/whatsapp/bot-config`, {
                headers: {
                    'user-id': currentUser.id,
                    'Authorization': `Bearer ${getAccessToken()}`
                }
            });
            if (res.data.data) {
                setBotConfig(res.data.data);
                loadSlotsConfig(res.data.data.id);
                loadAnalytics(res.data.data.id, currentUser.id);
            }
        } catch (err) {
            console.error("Failed to load bot config", err);
        } finally {
            setLoading(false);
        }
    };

    const loadAnalytics = async (botId, userId) => {
        try {
            const res = await axios.get(`${PLUGINS_API}/api/v1/dashboard/analytics?bot_config_id=${botId}&user_id=${userId}`, {
                headers: { 'Authorization': `Bearer ${getAccessToken()}` }
            });
            if (res.data.data) {
                setAnalytics(res.data.data);
            }
        } catch (err) {
            console.error("Analytics unavailable", err);
        }
    };

    const loadSlotsConfig = async (botId) => {
        try {
            const res = await axios.get(`${PLUGINS_API}/api/v1/slots/config/${botId}`, {
                headers: { 'Authorization': `Bearer ${getAccessToken()}` }
            });
            if (res.data.data) {
                setSlots(res.data.data);
            }
        } catch (err) {
            console.error("Failed to load slots", err);
        }
    };

    // --- New: Wizard Submit ---
    const createBotFromWizard = async () => {
        try {
            setCreating(true);
            const res = await axios.post(`${PLUGINS_API}/api/v1/whatsapp/bot-config`, {
                user_id: user.id,
                phone_number_id: "auto",
                owner_phone_number: setupData.owner_phone_number,
                whatsapp_phone_number: setupData.whatsapp_phone_number,
                business_display_name: setupData.business_display_name,
                use_case_type: setupData.use_case_type,
            }, {
                headers: { 'Authorization': `Bearer ${getAccessToken()}` }
            });
            setBotConfig(res.data.data);
            loadSlotsConfig(res.data.data.id);
        } catch (err) {
            console.error(err);
            alert("Failed to create bot. Please check your details and try again.");
        } finally {
            setCreating(false);
        }
    };

    const startReconfigure = () => {
        setSetupData({
            use_case_type: botConfig?.use_case_type || "",
            business_display_name: botConfig?.business_display_name || "",
            owner_phone_number: botConfig?.owner_phone_number || "",
            whatsapp_phone_number: botConfig?.whatsapp_phone_number || "",
        });
        setSetupStep(1);
        setBotConfig(null);
    };

    const saveSlotConfig = async () => {
        try {
            const payload = {
                user_id: user.id,
                bot_config_id: botConfig.id,
                working_hours: slots.working_hours,
                slot_duration_minutes: parseInt(slots.slot_duration_minutes) || 15,
                max_capacity_per_slot: parseInt(slots.max_capacity_per_slot) || 1
            };
            await axios.post(`${PLUGINS_API}/api/v1/slots/config`, payload, {
                headers: { 'Authorization': `Bearer ${getAccessToken()}` }
            });
            alert("Working hours saved!");
        } catch (err) {
            console.error(err);
            alert("Failed to save rules. Please check your network connection and try again.");
        }
    };

    const syncKnowledgeBase = async () => {
        try {
            setSyncing(true);
            const res = await axios.post(`${PLUGINS_API}/api/v1/knowledge/sync/${botConfig.id}`, {}, {
                headers: { 'Authorization': `Bearer ${getAccessToken()}` }
            });
            alert(res.data.message || "Sync successful!");
        } catch (err) {
            console.error(err);
            alert("Failed to sync knowledge base. Make sure your Google account is connected.");
        } finally {
            setSyncing(false);
        }
    };

    const updateUseCase = async (newUseCase) => {
        // Optimistic UI Update: change it visually instantly!
        const previousUseCase = botConfig.use_case_type;
        setBotConfig({ ...botConfig, use_case_type: newUseCase });

        try {
            await axios.post(`${PLUGINS_API}/api/v1/whatsapp/bot-config`, {
                user_id: user.id,
                phone_number_id: botConfig.phone_number_id,
                owner_phone_number: botConfig.owner_phone_number || "",
                business_display_name: botConfig.business_display_name || "My Business",
                use_case_type: newUseCase,
                is_active: true,
            }, {
                headers: { 'Authorization': `Bearer ${getAccessToken()}` }
            });
        } catch (err) {
            console.error(err);
            // Revert on failure
            setBotConfig({ ...botConfig, use_case_type: previousUseCase });
            alert("Failed to update business type.");
        }
    };

    useEffect(() => {
        getCurrentUser().then(res => {
            setUser(res);
            loadBotConfig(res);
        }).catch(err => {
            console.error(err);
            setLoading(false);
        });
    }, []);

    if (loading) return (
        <div className="flex-1 flex items-center justify-center bg-black">
            <div className="text-center">
                <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                <p className="text-neutral-400">Loading your dashboard...</p>
            </div>
        </div>
    );

    // --- Helper: find selected use case option ---
    const selectedOpt = useCaseOptions.find(o => o.key === setupData.use_case_type);

    return (
        <div className="flex-1 overflow-auto bg-black p-8">
            <div className="max-w-5xl mx-auto space-y-8">

                {/* Header */}
                <div>
                    <h1 className="text-3xl font-light text-white mb-2">WhatsApp Bot Manager</h1>
                    <p className="text-neutral-400">Configure your AI assistant, connect your calendar, and manage slots.</p>
                </div>

                {!botConfig ? (
                    /* ============ ONBOARDING WIZARD ============ */
                    <div className="max-w-2xl mx-auto">

                        {/* Progress Bar */}
                        <div className="flex items-center gap-2 mb-8">
                            {[1, 2, 3].map(step => (
                                <div key={step} className="flex-1 flex items-center gap-2">
                                    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300 ${setupStep >= step
                                        ? "bg-purple-600 text-white shadow-lg shadow-purple-500/30"
                                        : "bg-neutral-800 text-neutral-500"
                                        }`}>
                                        {setupStep > step ? <Check size={16} /> : step}
                                    </div>
                                    {step < 3 && (
                                        <div className={`flex-1 h-0.5 rounded transition-all duration-500 ${setupStep > step ? "bg-purple-600" : "bg-neutral-800"
                                            }`} />
                                    )}
                                </div>
                            ))}
                        </div>

                        {/* Step 1: Choose Business Type */}
                        {setupStep === 1 && (
                            <div className="space-y-6 animate-in fade-in">
                                <div className="text-center mb-8">
                                    <h2 className="text-2xl font-medium text-white mb-2">What kind of business do you run?</h2>
                                    <p className="text-neutral-400">This determines how your AI talks to customers and what features are enabled.</p>
                                </div>

                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                    {useCaseOptions.map(opt => {
                                        const Icon = opt.icon;
                                        const isActive = setupData.use_case_type === opt.key;
                                        return (
                                            <button
                                                key={opt.key}
                                                onClick={() => setSetupData({ ...setupData, use_case_type: opt.key })}
                                                className={`flex items-start gap-4 p-5 rounded-2xl border transition-all duration-200 text-left group ${isActive
                                                    ? `${opt.bg} ${opt.border} ring-1 ring-white/10`
                                                    : "bg-neutral-900 border-neutral-800 hover:border-neutral-600 hover:bg-neutral-900/80"
                                                    }`}
                                            >
                                                <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${isActive ? opt.bg : "bg-neutral-800"} transition-colors`}>
                                                    <Icon size={22} className={isActive ? opt.color : "text-neutral-500 group-hover:text-neutral-300"} />
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <p className={`text-sm font-semibold ${isActive ? "text-white" : "text-neutral-300"}`}>{opt.label}</p>
                                                    <p className={`text-xs mt-0.5 ${isActive ? "text-neutral-300" : "text-neutral-500"}`}>{opt.desc}</p>
                                                </div>
                                                {isActive && <Check size={18} className="text-purple-400 mt-1 flex-shrink-0" />}
                                            </button>
                                        );
                                    })}
                                </div>

                                <div className="flex justify-end pt-4">
                                    <button
                                        onClick={() => setSetupStep(2)}
                                        disabled={!setupData.use_case_type}
                                        className={`flex items-center gap-2 px-6 py-3 rounded-xl font-medium transition-all ${setupData.use_case_type
                                            ? "bg-purple-600 hover:bg-purple-500 text-white shadow-lg shadow-purple-500/20"
                                            : "bg-neutral-800 text-neutral-500 cursor-not-allowed"
                                            }`}
                                    >
                                        Continue <ArrowRight size={16} />
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* Step 2: Business Details */}
                        {setupStep === 2 && (
                            <div className="space-y-6 animate-in fade-in">
                                <div className="text-center mb-8">
                                    <h2 className="text-2xl font-medium text-white mb-2">Tell us about your business</h2>
                                    <p className="text-neutral-400">This information helps personalize the AI and route messages properly.</p>
                                </div>

                                <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6 space-y-5">
                                    <div>
                                        <label className="text-xs text-neutral-400 uppercase font-semibold mb-2 flex items-center gap-2">
                                            <Building2 size={14} /> Business Name
                                        </label>
                                        <input
                                            type="text"
                                            placeholder="e.g., Smile Dental Clinic"
                                            value={setupData.business_display_name}
                                            onChange={(e) => setSetupData({ ...setupData, business_display_name: e.target.value })}
                                            className="w-full bg-black border border-neutral-800 rounded-xl p-3.5 text-white placeholder-neutral-600 focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/20 outline-none transition-all"
                                        />
                                    </div>

                                    <div>
                                        <label className="text-xs text-neutral-400 uppercase font-semibold mb-2 flex items-center gap-2">
                                            <Phone size={14} /> Your Personal Phone (for Admin Notifications)
                                        </label>
                                        <input
                                            type="text"
                                            placeholder="e.g., 919325341766"
                                            value={setupData.owner_phone_number}
                                            onChange={(e) => setSetupData({ ...setupData, owner_phone_number: e.target.value })}
                                            className="w-full bg-black border border-neutral-800 rounded-xl p-3.5 text-white placeholder-neutral-600 focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/20 outline-none transition-all"
                                        />
                                        <p className="text-[11px] text-neutral-600 mt-1.5">Country code + number (no spaces or +). You'll get escalation alerts here.</p>
                                    </div>
                                    <div>
                                        <label className="text-xs text-neutral-400 uppercase font-semibold mb-2 flex items-center gap-2">
                                            <Phone size={14} /> WhatsApp Number for Bot
                                        </label>
                                        <input
                                            type="text"
                                            placeholder="e.g., 919876543210"
                                            value={setupData.whatsapp_phone_number}
                                            onChange={(e) => setSetupData({ ...setupData, whatsapp_phone_number: e.target.value })}
                                            className="w-full bg-black border border-neutral-800 rounded-xl p-3.5 text-white placeholder-neutral-600 focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/20 outline-none transition-all"
                                        />
                                        <p className="text-[11px] text-neutral-600 mt-1.5">Your official business WhatsApp number (with country code).</p>
                                    </div>
                                </div>

                                <div className="flex justify-between pt-4">
                                    <button
                                        onClick={() => setSetupStep(1)}
                                        className="flex items-center gap-2 px-5 py-3 rounded-xl bg-neutral-900 border border-neutral-800 text-neutral-300 hover:bg-neutral-800 transition-colors"
                                    >
                                        <ArrowLeft size={16} /> Back
                                    </button>
                                    <button
                                        onClick={() => setSetupStep(3)}
                                        disabled={!setupData.business_display_name || !setupData.owner_phone_number || !setupData.whatsapp_phone_number}
                                        className={`flex items-center gap-2 px-6 py-3 rounded-xl font-medium transition-all ${setupData.business_display_name && setupData.owner_phone_number && setupData.whatsapp_phone_number
                                            ? "bg-purple-600 hover:bg-purple-500 text-white shadow-lg shadow-purple-500/20"
                                            : "bg-neutral-800 text-neutral-500 cursor-not-allowed"
                                            }`}
                                    >
                                        Review <ArrowRight size={16} />
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* Step 3: Review & Launch */}
                        {setupStep === 3 && selectedOpt && (
                            <div className="space-y-6 animate-in fade-in">
                                <div className="text-center mb-8">
                                    <h2 className="text-2xl font-medium text-white mb-2">Review & Launch Your Bot</h2>
                                    <p className="text-neutral-400">Everything looks good? Hit launch and your AI assistant goes live!</p>
                                </div>

                                <div className={`bg-gradient-to-br ${selectedOpt.gradient} border ${selectedOpt.border} rounded-2xl p-6 space-y-4`}>
                                    <div className="flex items-center gap-3 mb-2">
                                        <selectedOpt.icon size={28} className={selectedOpt.color} />
                                        <div>
                                            <p className="text-lg font-semibold text-white">{setupData.business_display_name}</p>
                                            <p className="text-sm text-neutral-400">{selectedOpt.label} Bot</p>
                                        </div>
                                    </div>

                                    <div className="pt-4 border-t border-white/10">
                                        <div>
                                            <p className="text-[10px] text-neutral-500 uppercase font-semibold mb-1">Admin Notification Phone</p>
                                            <p className="text-sm text-white font-mono">{setupData.owner_phone_number}</p>
                                        </div>
                                        <div className="mt-2">
                                            <p className="text-[10px] text-neutral-500 uppercase font-semibold mb-1">Bot WhatsApp Number</p>
                                            <p className="text-sm text-white font-mono">{setupData.whatsapp_phone_number}</p>
                                        </div>
                                    </div>
                                </div>

                                {/* What Happens Next */}
                                <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6">
                                    <h3 className="text-sm font-semibold text-white mb-4">What happens after launch?</h3>
                                    <div className="space-y-3">
                                        {[
                                            { icon: Zap, text: "Your AI bot starts listening on WhatsApp instantly", color: "text-green-400" },
                                            { icon: Calendar, text: "Connect Google to sync Calendar, Docs & Drive (next step)", color: "text-blue-400" },
                                            { icon: BookOpen, text: "A Knowledge Base doc is auto-created for training your AI", color: "text-purple-400" },
                                            { icon: MessageSquare, text: "Customers message your WhatsApp → AI replies automatically", color: "text-orange-400" },
                                        ].map((item, i) => (
                                            <div key={i} className="flex items-center gap-3 text-sm text-neutral-300">
                                                <item.icon size={16} className={item.color} />
                                                {item.text}
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                <div className="flex justify-between pt-4">
                                    <button
                                        onClick={() => setSetupStep(2)}
                                        className="flex items-center gap-2 px-5 py-3 rounded-xl bg-neutral-900 border border-neutral-800 text-neutral-300 hover:bg-neutral-800 transition-colors"
                                    >
                                        <ArrowLeft size={16} /> Back
                                    </button>
                                    <button
                                        onClick={createBotFromWizard}
                                        disabled={creating}
                                        className={`flex items-center gap-2 px-8 py-3.5 rounded-xl font-bold text-base transition-all ${creating
                                            ? "bg-purple-500/30 text-purple-300 cursor-not-allowed"
                                            : "bg-gradient-to-r from-purple-600 to-purple-500 hover:from-purple-500 hover:to-purple-400 text-white shadow-xl shadow-purple-500/30"
                                            }`}
                                    >
                                        {creating ? (
                                            <>
                                                <div className="w-4 h-4 border-2 border-purple-300 border-t-transparent rounded-full animate-spin" />
                                                Creating...
                                            </>
                                        ) : (
                                            <>
                                                <Zap size={18} />
                                                Launch My AI Bot
                                            </>
                                        )}
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="space-y-6">

                        {/* Top Analytics Banner */}
                        {analytics && (
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                                <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6">
                                    <h3 className="text-neutral-400 text-sm font-medium mb-2 flex items-center gap-2">
                                        <TrendingUp size={16} className="text-blue-400" />
                                        Total Footfalls / Users
                                    </h3>
                                    <p className="text-3xl font-light text-white">{analytics.total_conversations}</p>
                                    <p className="text-xs text-neutral-500 mt-2">Active WhatsApp Chats</p>
                                </div>
                                <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6">
                                    <h3 className="text-neutral-400 text-sm font-medium mb-2 flex items-center gap-2">
                                        <BarChart size={16} className="text-orange-400" />
                                        Peak Hours
                                    </h3>
                                    <div className="space-y-1 mt-2">
                                        {analytics.peak_hours.map((hourStr, i) => (
                                            <p key={i} className="text-lg font-light text-white flex justify-between">
                                                {hourStr.includes("(") ? (
                                                    <>
                                                        <span>{hourStr.split(' ')[0]} {hourStr.split(' ')[1]}</span>
                                                        <span className="text-sm text-neutral-500">{hourStr.split('(')[1].replace(')', '')}</span>
                                                    </>
                                                ) : (
                                                    <span className="text-sm text-neutral-500 italic">{hourStr}</span>
                                                )}
                                            </p>
                                        ))}
                                    </div>
                                </div>
                                <div className="bg-neutral-900/40 border border-[#8b5cf6]/30 rounded-2xl p-6 relative overflow-hidden group">
                                    <div className="absolute inset-0 bg-gradient-to-br from-[#8b5cf6]/10 to-transparent pointer-events-none" />
                                    <h3 className="text-[#a78bfa] text-sm font-medium mb-3 flex items-center gap-2 relative z-10">
                                        <Sparkles size={16} />
                                        AI Profile Insights
                                    </h3>
                                    <p className="text-sm font-light text-neutral-300 leading-relaxed max-h-24 overflow-y-auto relative z-10">
                                        {analytics.ai_summary}
                                    </p>
                                </div>
                            </div>
                        )}

                        {/* Business Type Selector */}
                        <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6">
                            <h2 className="text-lg font-medium text-white mb-1 flex items-center gap-2">
                                <Store size={18} className="text-purple-400" />
                                Business Type
                            </h2>
                            <p className="text-sm text-neutral-400 mb-4">Select your business type. This changes the AI's personality and how it talks to your customers.</p>
                            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                                {useCaseOptions.map(opt => {
                                    const Icon = opt.icon;
                                    const isActive = botConfig.use_case_type === opt.key;
                                    return (
                                        <button
                                            key={opt.key}
                                            onClick={() => updateUseCase(opt.key)}
                                            className={`flex flex-col items-center gap-2 p-4 rounded-xl border transition-all duration-200 ${isActive
                                                ? `${opt.bg} ${opt.border} ring-1 ring-white/10`
                                                : "bg-black border-neutral-800 hover:border-neutral-600 hover:bg-neutral-900"
                                                }`}
                                        >
                                            <Icon size={22} className={isActive ? opt.color : "text-neutral-500"} />
                                            <span className={`text-xs font-medium text-center leading-tight ${isActive ? "text-white" : "text-neutral-500"}`}>
                                                {opt.label}
                                            </span>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>

                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

                            {/* Left Column: Calendar & Integrations */}
                            <div className="space-y-6">

                                {/* Google Calendar Card */}
                                <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6">
                                    <div className="flex justify-between items-start mb-6">
                                        <div>
                                            <h2 className="text-lg font-medium text-white mb-1 flex items-center gap-2">
                                                <Calendar size={18} className="text-blue-400" />
                                                Integrations (Calendar & Docs)
                                            </h2>
                                            <p className="text-sm text-neutral-400">Connect Google to manage bookings and your bot's training doc.</p>
                                        </div>
                                    </div>

                                    {botConfig.has_calendar ? (
                                        <div className="flex items-center gap-3 text-sm text-green-400 bg-green-500/10 border border-green-500/20 p-4 rounded-xl mb-4">
                                            <CheckSquare size={18} />
                                            Google Account Connected
                                        </div>
                                    ) : (
                                        <button
                                            onClick={() => window.open(`${PLUGINS_API}/api/v1/calendar/connect/${botConfig.id}`, '_blank')}
                                            className="w-full flex justify-center items-center gap-2 px-4 py-3 bg-neutral-800 hover:bg-neutral-700 text-white rounded-xl transition-colors border border-neutral-700 mb-4"
                                        >
                                            <img src="https://www.google.com/favicon.ico" className="w-4 h-4" alt="Google" />
                                            Connect Google Account
                                        </button>
                                    )}

                                    {/* Knowledge Base Section */}
                                    <div className="pt-6 border-t border-neutral-800">
                                        <div className="flex items-center gap-2 mb-4">
                                            <BookOpen size={18} className="text-purple-400" />
                                            <span className="text-sm font-medium text-white">AI Knowledge Base</span>
                                        </div>

                                        {botConfig.google_doc_id ? (
                                            <div className="grid grid-cols-2 gap-3">
                                                <button
                                                    onClick={() => window.open(`https://docs.google.com/document/d/${botConfig.google_doc_id}/edit`, '_blank')}
                                                    className="flex justify-center items-center gap-2 px-3 py-2.5 bg-neutral-800 hover:bg-neutral-700 text-xs text-neutral-300 rounded-lg transition-colors border border-neutral-700"
                                                >
                                                    <FileText size={14} />
                                                    Edit Doc
                                                </button>
                                                <button
                                                    onClick={syncKnowledgeBase}
                                                    disabled={syncing}
                                                    className={`flex justify-center items-center gap-2 px-3 py-2.5 rounded-lg text-xs transition-all ${syncing ? "bg-purple-500/20 text-purple-300 cursor-not-allowed" : "bg-purple-600 hover:bg-purple-500 text-white"
                                                        }`}
                                                >
                                                    <RefreshCw size={14} className={syncing ? "animate-spin" : ""} />
                                                    {syncing ? "Syncing..." : "Sync Brain"}
                                                </button>
                                            </div>
                                        ) : (
                                            <p className="text-xs text-neutral-500 italic">Connect Google to generate your training document.</p>
                                        )}
                                    </div>
                                </div>

                                {/* WhatsApp Official Connection */}
                                <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6">
                                    <div className="flex justify-between items-center mb-4">
                                        <h2 className="text-lg font-medium text-white flex items-center gap-2">
                                            <Zap size={18} className="text-green-400" />
                                            WhatsApp Connection
                                        </h2>
                                        <div className="flex items-center gap-3">
                                            <span className="px-2 py-0.5 bg-green-500/10 text-green-500 text-[10px] rounded border border-green-500/20 uppercase font-bold tracking-wider">Active</span>
                                            <button
                                                onClick={startReconfigure}
                                                className="text-neutral-400 hover:text-white transition-colors bg-neutral-800 hover:bg-neutral-700 px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-2 border border-neutral-700 hover:border-neutral-600"
                                            >
                                                <Settings size={14} />
                                                Reconfigure Bot
                                            </button>
                                        </div>
                                    </div>
                                    <p className="text-sm text-neutral-400 mb-6">Your official number is connected via Meta Cloud API.</p>

                                    <div className="p-4 bg-black rounded-xl border border-neutral-800 space-y-3">
                                        <div className="flex justify-between items-center text-xs">
                                            <span className="text-neutral-500">Phone Number ID</span>
                                            <span className="text-neutral-300 font-mono">{botConfig.phone_number_id}</span>
                                        </div>
                                        <div className="flex justify-between items-center text-xs">
                                            <span className="text-neutral-500">Status</span>
                                            <span className="text-green-400 flex items-center gap-1">
                                                <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
                                                Live & Accepting Messages
                                            </span>
                                        </div>
                                    </div>
                                </div>

                                {/* Share / Test Bot */}
                                <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6">
                                    <div className="flex items-center gap-2 mb-4">
                                        <QrCode size={18} className="text-white" />
                                        <h2 className="text-lg font-medium text-white">Share Your Bot</h2>
                                    </div>
                                    <p className="text-sm text-neutral-400 mb-6">
                                        Show this QR code to your clients on their visits, so they can scan it to instantly message your AI for their next booking or query.
                                    </p>

                                    <div className="flex flex-col sm:flex-row gap-6 items-center sm:items-stretch">
                                        {/* QR Code */}
                                        <div className="bg-white p-3 rounded-xl shadow-sm shrink-0">
                                            <QRCodeSVG
                                                value={`https://wa.me/${botConfig.whatsapp_phone_number}?text=Hi! I would like to book an appointment.`}
                                                size={120}
                                                bgColor={"#ffffff"}
                                                fgColor={"#000000"}
                                                level={"Q"}
                                            />
                                        </div>

                                        {/* Number Copier */}
                                        <div className="flex-1 flex flex-col justify-center space-y-3 w-full">
                                            <label className="text-xs text-neutral-500 uppercase tracking-wider font-semibold">Or share Direct Number</label>
                                            <div className="flex bg-black border border-neutral-800 rounded-lg p-3 justify-between items-center group">
                                                <code className="text-neutral-300 font-mono text-sm sm:text-base">+{botConfig.whatsapp_phone_number}</code>
                                                <button
                                                    onClick={() => {
                                                        navigator.clipboard.writeText(`+${botConfig.whatsapp_phone_number}`);
                                                        setHasCopied(true);
                                                        setTimeout(() => setHasCopied(false), 2000);
                                                    }}
                                                    className="text-neutral-500 hover:text-white transition-colors p-1"
                                                >
                                                    {hasCopied ? <Check size={18} className="text-green-500" /> : <Copy size={18} />}
                                                </button>
                                            </div>
                                            <p className="text-[11px] text-neutral-500">
                                                Test it yourself: Message this number to talk to your AI.
                                            </p>
                                        </div>
                                    </div>
                                </div>

                            </div>

                            {/* Right Column: Slot Configurations */}
                            <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6 flex flex-col">
                                <h2 className="text-lg font-medium text-white mb-1 flex items-center gap-2">
                                    <Clock size={18} className="text-orange-400" />
                                    Slot Engine Rules
                                </h2>
                                <p className="text-sm text-neutral-400 mb-6">Define your mathematical working hours. AI will cross-reference this with your Google Calendar.</p>

                                <div className="space-y-4 flex-1">
                                    <div className="grid grid-cols-2 gap-4">
                                        <div>
                                            <label className="text-xs text-neutral-500 uppercase font-semibold mb-1 block">Slot Duration (Mins)</label>
                                            <input
                                                type="number"
                                                value={slots.slot_duration_minutes}
                                                onChange={(e) => setSlots({ ...slots, slot_duration_minutes: parseInt(e.target.value) })}
                                                className="w-full bg-black border border-neutral-800 rounded-lg p-3 text-white focus:border-neutral-500 outline-none"
                                            />
                                        </div>
                                        <div>
                                            <label className="text-xs text-neutral-500 uppercase font-semibold mb-1 block">Max Capacity</label>
                                            <input
                                                type="number"
                                                value={slots.max_capacity_per_slot}
                                                onChange={(e) => setSlots({ ...slots, max_capacity_per_slot: parseInt(e.target.value) })}
                                                className="w-full bg-black border border-neutral-800 rounded-lg p-3 text-white focus:border-neutral-500 outline-none"
                                            />
                                        </div>
                                    </div>

                                    <div className="pt-4 border-t border-neutral-800 flex flex-col flex-1 overflow-visible">
                                        <div className="flex items-center justify-between mb-4">
                                            <label className="text-xs text-neutral-500 uppercase font-semibold block">Daily Operating Hours</label>
                                            <span className="text-[10px] text-green-500 bg-green-500/10 px-2 py-1 rounded border border-green-500/20 font-semibold tracking-wide">Applies to all 7 days</span>
                                        </div>

                                        <div className="bg-neutral-800/30 p-4 rounded-xl border border-neutral-800">
                                            <div className="flex justify-between items-center mb-4">
                                                <span className="text-sm font-medium text-neutral-200">Everyday Schedule</span>
                                                <button
                                                    onClick={() => {
                                                        const newHours = { ...slots.working_hours };
                                                        Object.keys(newHours).forEach(day => {
                                                            newHours[day] = [...(newHours[day] || []), { start: "09:00", end: "23:00" }];
                                                        });
                                                        setSlots({ ...slots, working_hours: newHours });
                                                    }}
                                                    className="text-neutral-400 hover:text-white bg-neutral-800 hover:bg-neutral-700 p-1.5 px-3 rounded-lg transition-colors flex items-center gap-1.5 text-xs font-medium border border-neutral-700/50"
                                                >
                                                    <Plus size={14} /> Add Time Block
                                                </button>
                                            </div>

                                            <div className="space-y-3">
                                                {(slots.working_hours['monday'] || []).length === 0 ? (
                                                    <div className="flex justify-center py-6 bg-black/20 rounded-lg border border-neutral-800/50">
                                                        <span className="text-sm text-neutral-600 italic">Currently Marked as Closed</span>
                                                    </div>
                                                ) : (
                                                    (slots.working_hours['monday'] || []).map((block, idx) => (
                                                        <div key={idx} className="flex items-center gap-3 relative bg-black/40 p-2.5 rounded-lg border border-neutral-800/50">
                                                            <input
                                                                type="time"
                                                                value={block.start}
                                                                onChange={(e) => {
                                                                    const val = e.target.value;
                                                                    const newHours = { ...slots.working_hours };
                                                                    Object.keys(newHours).forEach(day => {
                                                                        if (newHours[day][idx]) newHours[day][idx].start = val;
                                                                    });
                                                                    setSlots({ ...slots, working_hours: newHours });
                                                                }}
                                                                className="w-full bg-black border border-neutral-700/50 hover:border-neutral-500 focus:border-neutral-400 rounded-md p-2.5 text-white text-sm font-medium text-center outline-none transition-all focus:ring-1 focus:ring-neutral-500"
                                                            />
                                                            <span className="text-neutral-500 text-[10px] font-bold uppercase tracking-wider">To</span>
                                                            <input
                                                                type="time"
                                                                value={block.end}
                                                                onChange={(e) => {
                                                                    const val = e.target.value;
                                                                    const newHours = { ...slots.working_hours };
                                                                    Object.keys(newHours).forEach(day => {
                                                                        if (newHours[day][idx]) newHours[day][idx].end = val;
                                                                    });
                                                                    setSlots({ ...slots, working_hours: newHours });
                                                                }}
                                                                className="w-full bg-black border border-neutral-700/50 hover:border-neutral-500 focus:border-neutral-400 rounded-md p-2.5 text-white text-sm font-medium text-center outline-none transition-all focus:ring-1 focus:ring-neutral-500"
                                                            />
                                                            <button
                                                                onClick={() => {
                                                                    const newHours = { ...slots.working_hours };
                                                                    Object.keys(newHours).forEach(day => {
                                                                        newHours[day].splice(idx, 1);
                                                                    });
                                                                    setSlots({ ...slots, working_hours: newHours });
                                                                }}
                                                                className="p-2.5 text-neutral-500 hover:text-red-400 hover:bg-red-500/10 rounded-md transition-colors"
                                                                title="Remove Time Block"
                                                            >
                                                                <Trash2 size={16} />
                                                            </button>
                                                        </div>
                                                    ))
                                                )}
                                            </div>
                                        </div>

                                        <p className="mt-4 text-[11px] text-neutral-500 text-center px-4 leading-relaxed">
                                            These hours apply to <strong>every day of the week</strong>. <br />
                                            {slots.slot_duration_minutes}-minute slots are mathematically generated between these times automatically!
                                        </p>
                                    </div>
                                </div>

                                <div className="pt-6 border-t border-neutral-800 mt-auto">
                                    <button
                                        onClick={saveSlotConfig}
                                        className="w-full px-4 py-3 bg-white text-black font-medium rounded-xl hover:bg-neutral-200 transition-colors"
                                    >
                                        Save Configuration
                                    </button>
                                </div>

                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
