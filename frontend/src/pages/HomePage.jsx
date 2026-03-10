import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
    Search,
    Paperclip,
    Globe,
    Zap,
    Sparkles,
    ArrowUp,
    Star,
    Image,
    Video,
    Palette,
    ShoppingBag,
    PenTool,
} from "lucide-react";
import clsx from "clsx";

const categories = [
    { label: "Design", icon: Palette },
    { label: "Branding", icon: Star },
    { label: "Illustration", icon: PenTool },
    { label: "E-Commerce", icon: ShoppingBag },
    { label: "Video", icon: Video },
    { label: "Image", icon: Image },
];

const suggestions = [
    "Design a product launch campaign for a fitness app",
    "Create a brand identity for a luxury coffee brand",
    "Generate social media content for a tech startup",
    "Build a competitor analysis for the fashion industry",
];

export default function HomePage() {
    const [query, setQuery] = useState("");
    const [activeCategory, setActiveCategory] = useState(null);
    const [focused, setFocused] = useState(false);
    const navigate = useNavigate();

    const handleSubmit = (e) => {
        e.preventDefault();
        if (query.trim()) {
            navigate("/assistant", { state: { query } });
        }
    };

    return (
        <div className="flex flex-col items-center justify-center min-h-screen px-6 pb-20 animate-fade-in">
            {/* Upgrade Banner */}
            <div className="flex items-center gap-2 px-4 py-2 bg-amber-50 border border-amber-200 rounded-full text-sm mb-10">
                <span className="px-1.5 py-0.5 bg-amber-500 text-white text-xs font-bold rounded uppercase tracking-wide">
                    NEW
                </span>
                <span className="text-amber-800">
                    Upgrade now for Kling 3.0 & Nano Banana Pro for up to 50...
                </span>
                <button className="text-amber-700 font-semibold hover:underline ml-1">
                    Upgrade →
                </button>
            </div>

            {/* Hero Title */}
            <div className="text-center mb-8">
                <h1 className="text-5xl font-bold tracking-tight text-neutral-900 mb-3 flex items-center gap-3 justify-center">
                    Design is easier with
                    <span className="inline-flex items-center gap-2 bg-neutral-900 text-white px-3 py-1 rounded-xl">
                        <Zap size={22} className="text-amber-400" strokeWidth={2.5} />
                        Catalyst
                    </span>
                </h1>
                <p className="text-lg text-neutral-500 font-normal">
                    The AI agent that gets you and gets the job done
                </p>
            </div>

            {/* Search Box */}
            <div className="w-full max-w-2xl mb-5">
                <form onSubmit={handleSubmit}>
                    <div
                        className={clsx(
                            "relative bg-white border rounded-2xl transition-all duration-150 overflow-hidden",
                            focused
                                ? "border-neutral-900 shadow-[0_0_0_1px_#171717]"
                                : "border-neutral-200 shadow-card"
                        )}
                    >
                        {/* Text area */}
                        <div className="px-4 pt-4 pb-2">
                            <input
                                type="text"
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                onFocus={() => setFocused(true)}
                                onBlur={() => setFocused(false)}
                                placeholder="Ask Catalyst to design a beautiful wedding poster..."
                                className="w-full text-base text-neutral-900 placeholder-neutral-400 bg-transparent outline-none"
                            />
                        </div>

                        {/* Toolbar */}
                        <div className="flex items-center justify-between px-3 pb-3 pt-1">
                            <div className="flex items-center gap-1">
                                <button
                                    type="button"
                                    className="flex items-center justify-center w-8 h-8 rounded-lg text-neutral-400 hover:bg-neutral-100 hover:text-neutral-700 transition-colors"
                                >
                                    <Paperclip size={16} strokeWidth={1.75} />
                                </button>
                            </div>

                            <div className="flex items-center gap-1">
                                <button
                                    type="button"
                                    className="flex items-center justify-center w-8 h-8 rounded-full border border-neutral-200 text-neutral-400 hover:border-neutral-300 hover:text-neutral-700 transition-colors"
                                >
                                    <Search size={14} strokeWidth={1.75} />
                                </button>
                                <button
                                    type="button"
                                    className="flex items-center justify-center w-8 h-8 rounded-full border border-neutral-200 text-neutral-400 hover:border-neutral-300 hover:text-neutral-700 transition-colors"
                                >
                                    <Zap size={14} strokeWidth={1.75} />
                                </button>
                                <button
                                    type="button"
                                    className="flex items-center justify-center w-8 h-8 rounded-full border border-neutral-200 text-neutral-400 hover:border-neutral-300 hover:text-neutral-700 transition-colors"
                                >
                                    <Globe size={14} strokeWidth={1.75} />
                                </button>
                                <button
                                    type="button"
                                    className="flex items-center justify-center w-8 h-8 rounded-full border border-neutral-200 text-neutral-400 hover:border-neutral-300 hover:text-neutral-700 transition-colors"
                                >
                                    <Sparkles size={14} strokeWidth={1.75} />
                                </button>

                                <div className="w-px h-5 bg-neutral-200 mx-1" />

                                <button
                                    type="submit"
                                    className={clsx(
                                        "flex items-center justify-center w-8 h-8 rounded-full transition-all duration-100",
                                        query.trim()
                                            ? "bg-neutral-900 text-white hover:bg-neutral-800"
                                            : "bg-neutral-100 text-neutral-400 cursor-not-allowed"
                                    )}
                                >
                                    <ArrowUp size={15} strokeWidth={2.5} />
                                </button>
                            </div>
                        </div>
                    </div>
                </form>
            </div>

            {/* Category Chips */}
            <div className="flex items-center gap-2 flex-wrap justify-center mb-10">
                <button className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-full border border-amber-300 bg-amber-50 text-amber-800 hover:bg-amber-100 transition-colors">
                    <Sparkles size={13} strokeWidth={2} />
                    Nano Banana Pro
                </button>
                {categories.map(({ label, icon: Icon }) => (
                    <button
                        key={label}
                        onClick={() => setActiveCategory(activeCategory === label ? null : label)}
                        className={clsx(
                            "flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-full border transition-all duration-100",
                            activeCategory === label
                                ? "bg-neutral-900 text-white border-neutral-900"
                                : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-300 hover:text-neutral-900"
                        )}
                    >
                        <Icon size={13} strokeWidth={1.75} />
                        {label}
                    </button>
                ))}
            </div>

            {/* Quick Suggestions */}
            <div className="w-full max-w-2xl">
                <p className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-3 text-center">
                    Try these
                </p>
                <div className="grid grid-cols-2 gap-2">
                    {suggestions.map((s, i) => (
                        <button
                            key={i}
                            onClick={() => setQuery(s)}
                            className="text-left px-4 py-3 text-sm text-neutral-600 bg-neutral-50 border border-neutral-200 rounded-xl hover:bg-neutral-100 hover:border-neutral-300 hover:text-neutral-900 transition-all duration-100"
                        >
                            {s}
                        </button>
                    ))}
                </div>
            </div>
        </div>
    );
}
