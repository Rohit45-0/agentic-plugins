/**
 * Market Scout API Service
 * Calls the backend Step 2 endpoints.
 *
 * Note: apiRequest() prepends VITE_API_BASE_URL (default "/api/v1"),
 * so paths here are relative to that base.
 */
import { apiRequest } from "./api";

/**
 * Run full market scouting analysis (Firecrawl + GPT-4o gap analysis).
 */
export async function runMarketScout({ productName, category, keywords = [], competitorUrls = [], region = "IN" }) {
    return apiRequest("/market-scout/analyze", {
        method: "POST",
        body: JSON.stringify({
            product_name: productName,
            category,
            keywords: keywords.filter(Boolean),
            competitor_urls: competitorUrls.filter(Boolean),
            region,
        }),
        timeoutMs: 90000, // up to 90s for Firecrawl + LLM chain
    });
}

/**
 * Quick trending content fetch for a category (2 Firecrawl credits).
 */
export async function getTrending(category, limit = 6) {
    const params = new URLSearchParams({ category, limit: String(limit) });
    return apiRequest(`/market-scout/trending?${params}`);
}
