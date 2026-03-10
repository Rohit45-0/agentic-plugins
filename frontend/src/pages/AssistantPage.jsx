import { useState, useRef, useEffect } from "react";
import { useLocation } from "react-router-dom";
import {
  Globe,
  ArrowUp,
  ExternalLink,
  Loader2,
  Sparkles,
  Palette,
  Star,
  PenTool,
  ShoppingBag,
  Video,
  Image,
  Zap,
  User,
  Bot,
  Link,
} from "lucide-react";
import clsx from "clsx";
import { toAbsoluteUrl } from "../services/api";

const categories = [
  { label: "All", icon: Sparkles },
  { label: "Design", icon: Palette },
  { label: "Branding", icon: Star },
  { label: "Illustration", icon: PenTool },
  { label: "E-Commerce", icon: ShoppingBag },
  { label: "Video", icon: Video },
  { label: "Image", icon: Image },
];

const suggestions = [
  "Create an ad campaign for a chili sauce brand",
  "Design a logo for a tech startup",
  "Write a product description for organic coffee",
  "Generate social media posts for a fashion brand",
];

// ─── Message bubble ───────────────────────────────────────────────────────────

function MessageBubble({ msg }) {
  const isUser = msg.role === "user";
  return (
    <div className={clsx("flex gap-3 w-full", isUser ? "justify-end" : "justify-start")}>
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-neutral-900 flex items-center justify-center shrink-0 mt-1">
          <Bot size={15} className="text-white" />
        </div>
      )}
      <div
        className={clsx(
          "max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
          isUser
            ? "bg-neutral-900 text-white rounded-tr-sm"
            : "bg-white border border-neutral-200 text-neutral-800 rounded-tl-sm shadow-sm"
        )}
      >
        {msg.content.split("\n").map((line, i) => {
          // Check for video tag a bit loosely: [video](url.mp4) or just a direct mp4 link
          const videoMatch = line.match(/\[video\]\((.+?\.mp4)\)/i) || line.match(/^(https?:\/\/.+?\.mp4)$/i) || line.match(/\[video\]\((.+?)\)/i);
          if (videoMatch) {
            const url = toAbsoluteUrl(videoMatch[1]);
            return (
              <div key={i} className="mt-3 rounded-lg overflow-hidden border border-neutral-200">
                <video src={url} controls className="w-full max-h-[300px] object-cover bg-black" />
              </div>
            );
          }

          // Check for standard markdown image: ![alt](url)
          const imgMatch = line.match(/!\[.*?\]\((.+?)\)/);
          if (imgMatch) {
            const url = toAbsoluteUrl(imgMatch[1]);
            return (
              <div key={i} className="mt-3 rounded-lg overflow-hidden border border-neutral-200">
                <img src={url} alt="Generated Asset" className="w-full max-h-[300px] object-cover" />
              </div>
            );
          }

          return <p key={i} className={i > 0 ? "mt-1.5" : ""}>{line}</p>;
        })}

        {/* Show web results inline under AI reply */}
        {msg.web_results?.length > 0 && (
          <div className="mt-3 pt-3 border-t border-neutral-100 space-y-2">
            <p className="text-[10px] font-semibold text-blue-500 uppercase tracking-wider flex items-center gap-1">
              <Globe size={10} /> Sources
            </p>
            {msg.web_results.slice(0, 3).map((r, i) => (
              <a
                key={i}
                href={r.link}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-start gap-2 hover:bg-neutral-50 rounded-lg p-1.5 -mx-1.5 transition-colors group"
              >
                <ExternalLink size={11} className="text-neutral-300 group-hover:text-blue-500 mt-0.5 shrink-0 transition-colors" />
                <div className="min-w-0">
                  <p className="text-xs font-medium text-neutral-700 group-hover:text-blue-600 truncate transition-colors">{r.title}</p>
                  <p className="text-[10px] text-neutral-400 truncate">{r.link.replace(/^https?:\/\//, "").split("/")[0]}</p>
                </div>
              </a>
            ))}
          </div>
        )}

        {/* RAG source indicator */}
        {!isUser && msg.rag_source && msg.rag_source !== "none" && (
          <div className="mt-2 pt-2 border-t border-neutral-100">
            <span className={clsx(
              "inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full",
              msg.rag_source === "pgvector"
                ? "bg-emerald-50 text-emerald-600"
                : "bg-amber-50 text-amber-600"
            )}>
              {msg.rag_source === "pgvector" ? "🧠 RAG Memory" : "📋 Campaign Data"}
            </span>
          </div>
        )}
        {!isUser && msg.rag_source === "none" && (
          <div className="mt-2 pt-2 border-t border-neutral-100">
            <span className="inline-flex items-center gap-1 text-[10px] font-medium text-neutral-400 uppercase tracking-wider">
              ⚡ GPT only
            </span>
          </div>
        )}
      </div>
      {isUser && (
        <div className="w-8 h-8 rounded-full bg-neutral-100 flex items-center justify-center shrink-0 mt-1">
          <User size={15} className="text-neutral-500" />
        </div>
      )}
    </div>
  );
}

// ─── Typing indicator ─────────────────────────────────────────────────────────

function TypingIndicator() {
  return (
    <div className="flex gap-3 w-full justify-start">
      <div className="w-8 h-8 rounded-full bg-neutral-900 flex items-center justify-center shrink-0">
        <Bot size={15} className="text-white" />
      </div>
      <div className="bg-white border border-neutral-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
        <div className="flex items-center gap-1.5">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="w-2 h-2 rounded-full bg-neutral-300 animate-bounce"
              style={{ animationDelay: `${i * 0.15}s` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function AssistantPage() {
  const location = useLocation();
  const [query, setQuery] = useState(location.state?.query || "");
  const [messages, setMessages] = useState(() => {
    const saved = sessionStorage.getItem("cn_chat_history");
    return saved ? JSON.parse(saved) : [];
  });
  const [loading, setLoading] = useState(false);
  const [activeCategory, setActiveCategory] = useState("All");
  const [focused, setFocused] = useState(false);
  const [webSearch, setWebSearch] = useState(false);
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);

  // Scroll to bottom whenever messages change
  // Also save to sessionStorage
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    if (messages.length > 0) {
      sessionStorage.setItem("cn_chat_history", JSON.stringify(messages));
    } else {
      sessionStorage.removeItem("cn_chat_history");
    }
  }, [messages, loading]);

  const clearChat = () => {
    setMessages([]);
    setQuery("");
  };

  const handleSend = async (overrideMessage) => {
    const text = (overrideMessage ?? query).trim();
    if (!text || loading) return;

    const token = localStorage.getItem("cn_access_token");
    if (!token) return;

    // Optimistically add user message
    const userMsg = { role: "user", content: text };
    const newHistory = [...messages, userMsg];
    setMessages(newHistory);
    setQuery("");
    setLoading(true);

    try {
      const resp = await fetch("/api/v1/assistant/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          message: text,
          // Send history BEFORE the new user message (backend appends it itself)
          history: messages.map((m) => ({ role: m.role, content: m.content })),
          web_search: webSearch,
          max_history: 12,
        }),
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${resp.status}`);
      }

      const data = await resp.json();
      setMessages([
        ...newHistory,
        {
          role: "assistant",
          content: data.reply,
          web_results: data.web_results || [],
          rag_used: data.rag_used || false,
          rag_source: data.rag_source || "none",
        },
      ]);
    } catch (err) {
      setMessages([
        ...newHistory,
        {
          role: "assistant",
          content: `⚠️ ${err.message || "Something went wrong. Please try again."}`,
          web_results: [],
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    handleSend();
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const isConversation = messages.length > 0;

  return (
    <div className="flex flex-col h-[calc(100vh-56px)] animate-fade-in">
      {/* ── Chat area ── */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {!isConversation ? (
          /* ── Empty / hero state ── */
          <div className="flex flex-col items-center pt-10 pb-4">
            <div className="text-center mb-10">
              <h1 className="text-5xl font-bold tracking-tight text-neutral-900 mb-3">
                What can I help you{" "}
                <span className="bg-neutral-900 text-white px-3 py-1 rounded-xl">
                  create?
                </span>
              </h1>
              <p className="text-lg text-neutral-500">
                {webSearch
                  ? "🌐 Web search ON — I'll search the internet before answering"
                  : "⚡ AI mode — Ask me anything"}
              </p>
            </div>

            {/* Category Chips */}
            <div className="flex items-center gap-2 flex-wrap justify-center mb-8">
              {categories.map(({ label, icon: Icon }) => (
                <button
                  key={label}
                  onClick={() => setActiveCategory(label)}
                  className={clsx(
                    "flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-full border transition-all duration-100",
                    activeCategory === label
                      ? "bg-neutral-900 text-white border-neutral-900"
                      : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400 hover:text-neutral-900"
                  )}
                >
                  <Icon size={14} strokeWidth={1.75} />
                  {label}
                </button>
              ))}
            </div>

            {/* Quick suggestions */}
            <div className="w-full max-w-3xl">
              <p className="text-xs font-semibold text-neutral-400 uppercase tracking-widest mb-3 text-center">
                Try asking
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    onClick={() => { setQuery(s); handleSend(s); }}
                    className="text-left px-4 py-3 rounded-xl border border-neutral-200 text-sm text-neutral-600 hover:border-neutral-900 hover:text-neutral-900 hover:bg-neutral-50 transition-all duration-100 flex items-center gap-2"
                  >
                    <Zap size={13} className="text-neutral-400 flex-shrink-0" />
                    {s}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          /* ── Conversation bubbles ── */
          <div className="max-w-3xl mx-auto space-y-4 pb-4">
            {messages.map((msg, i) => (
              <MessageBubble key={i} msg={msg} />
            ))}
            {loading && <TypingIndicator />}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* ── Input bar (always at bottom) ── */}
      <div className="border-t border-neutral-100 bg-white px-6 py-4">
        <div className="max-w-3xl mx-auto">
          <form onSubmit={handleSubmit}>
            <div
              className={clsx(
                "bg-white border-2 rounded-3xl transition-all duration-200 overflow-hidden",
                focused
                  ? "border-neutral-900 shadow-[0_0_0_3px_rgba(23,23,23,0.08)]"
                  : "border-neutral-200 shadow-md"
              )}
            >
              {/* Textarea */}
              <div className="px-6 pt-4 pb-2">
                <textarea
                  ref={textareaRef}
                  rows={2}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onFocus={() => setFocused(true)}
                  onBlur={() => setFocused(false)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask Catalyst anything... (Shift+Enter for new line)"
                  className="w-full text-base text-neutral-900 placeholder-neutral-400 bg-transparent outline-none resize-none leading-relaxed"
                />
              </div>

              {/* Toolbar */}
              <div className="flex items-center justify-between px-4 pb-3 pt-1">
                {/* Web Search Toggle */}
                <button
                  type="button"
                  onClick={() => setWebSearch((v) => !v)}
                  title={webSearch ? "Web search ON — click to use AI only" : "Click to enable live web search"}
                  className={clsx(
                    "flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium border-2 transition-all duration-200",
                    webSearch
                      ? "bg-blue-600 text-white border-blue-600 shadow-md shadow-blue-200"
                      : "bg-white text-neutral-500 border-neutral-200 hover:border-neutral-400 hover:text-neutral-800"
                  )}
                >
                  <Globe size={15} strokeWidth={2} />
                  <span>{webSearch ? "Web Search ON" : "Web Search"}</span>
                  {webSearch && (
                    <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
                  )}
                </button>

                <div className="flex items-center gap-2">
                  {/* Mode label */}
                  <span className="text-xs text-neutral-400 hidden sm:block">
                    {webSearch ? "🌐 Brave + GPT" : "⚡ GPT only"}
                  </span>

                  {/* Clear Chat Button */}
                  {isConversation && (
                    <button
                      type="button"
                      onClick={clearChat}
                      className="px-3 py-2 text-xs font-medium text-neutral-500 hover:text-red-600 hover:bg-neutral-50 rounded-lg transition-colors"
                    >
                      Clear
                    </button>
                  )}

                  {/* Send */}
                  <button
                    type="submit"
                    disabled={loading || !query.trim()}
                    className={clsx(
                      "flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-semibold transition-all duration-150",
                      query.trim() && !loading
                        ? "bg-neutral-900 text-white hover:bg-neutral-700 shadow-md"
                        : "bg-neutral-100 text-neutral-400 cursor-not-allowed"
                    )}
                  >
                    {loading ? (
                      <Loader2 size={16} className="animate-spin" />
                    ) : (
                      <ArrowUp size={16} strokeWidth={2.5} />
                    )}
                    {loading ? "Thinking..." : "Send"}
                  </button>
                </div>
              </div>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
