import { apiRequest } from "./api";

export async function generateCampaignBrief(payload) {
  return apiRequest("/market-intel/generate-campaign-brief", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function generateSystemPrompt(category, productName) {
  return apiRequest("/market-intel/generate-system-prompt", {
    method: "POST",
    body: JSON.stringify({ category, product_name: productName }),
  });
}

export async function extractIdentityLite({ productName, imageDataUrl, imageUrl, identityNotes }) {
  return apiRequest("/market-intel/extract-identity-lite", {
    method: "POST",
    body: JSON.stringify({
      product_name: productName,
      image_data_url: imageDataUrl || undefined,
      image_url: imageUrl || undefined,
      identity_notes: identityNotes || undefined,
    }),
    timeoutMs: 60000,
  });
}

export async function runFullCampaignPipeline(payload) {
  return apiRequest("/market-intel/full-pipeline", {
    method: "POST",
    body: JSON.stringify(payload),
    timeoutMs: 300000,
  });
}

export async function analyzeCategoryTrends(payload) {
  return apiRequest("/market-intel/analyze-category-trends", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function analyzeCompetitors(usernames) {
  return apiRequest("/market-intel/analyze", {
    method: "POST",
    body: JSON.stringify({ usernames }),
    timeoutMs: 300000,
  });
}

export async function getAnalyticsDashboard(days = 7) {
  return apiRequest(`/analytics/dashboard?days=${days}`);
}

export async function assistantChat(payload) {
  return apiRequest("/market-intel/assistant-chat", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ── Supabase-backed campaign history ──────────────────────────────────────────

export async function getCampaignsFromAPI(limit = 50, offset = 0) {
  return apiRequest(`/campaigns?limit=${limit}&offset=${offset}`);
}

export async function deleteCampaignFromAPI(campaignId) {
  return apiRequest(`/campaigns/${campaignId}`, { method: "DELETE" });
}

export async function getServiceHealth() {
  const [api, analytics] = await Promise.allSettled([
    fetch("/health").then((r) => r.json()),
    apiRequest("/analytics/health"),
  ]);

  return {
    api: api.status === "fulfilled" ? { ok: true, data: api.value } : { ok: false, error: "API offline" },
    analytics:
      analytics.status === "fulfilled"
        ? { ok: true, data: analytics.value }
        : { ok: false, error: analytics.reason?.message || "Analytics offline" },
  };
}

export async function getCompetitorContentIntel(limit = 5) {
  return apiRequest(`/analytics/competitor-content-intel?limit=${limit}`);
}

export async function getContentLibrary() {
  return apiRequest("/content/library");
}

export async function createPosterJob(prompt) {
  return apiRequest("/jobs/generate", {
    method: "POST",
    body: JSON.stringify({
      job_type: "image_generation",
      priority: 5,
      parameters: {
        prompt,
        width: 1024,
        height: 1024,
        quality: "high",
      },
    }),
  });
}

export async function getJobStatus(jobId) {
  return apiRequest(`/jobs/${jobId}/status`);
}

export async function createProjectForIdentity(name) {
  return apiRequest("/projects", {
    method: "POST",
    body: JSON.stringify({
      name,
      description: "Auto-created for campaign identity image upload",
      settings: { source: "campaign-form" },
    }),
  });
}

export async function uploadImageAsset(projectId, file) {
  const token = localStorage.getItem("cn_access_token");
  const base = import.meta.env.VITE_API_BASE_URL || "/api/v1";
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${base}/projects/${projectId}/assets?asset_type=image`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });

  if (!res.ok) {
    let detail = "Image upload failed";
    try {
      const err = await res.json();
      detail = typeof err?.detail === "string" ? err.detail : JSON.stringify(err?.detail || err);
    } catch {
      detail = await res.text();
    }
    throw new Error(detail || "Image upload failed");
  }

  return res.json();
}

export async function downloadProtectedAsset(downloadPath, filename = "asset.bin") {
  const token = localStorage.getItem("cn_access_token");
  const base = import.meta.env.VITE_API_BASE_URL || "/api/v1";
  const url =
    downloadPath.startsWith("http://") || downloadPath.startsWith("https://")
      ? downloadPath
      : downloadPath.startsWith("/api/")
        ? downloadPath
        : `${base}${downloadPath.startsWith("/") ? "" : "/"}${downloadPath}`;

  const res = await fetch(url, {
    method: "GET",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Failed to download asset");
  }

  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(objectUrl);
}
