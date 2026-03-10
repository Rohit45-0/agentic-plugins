const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";

export function toAbsoluteUrl(pathOrUrl) {
  if (!pathOrUrl) return "";
  if (/^https?:\/\//i.test(pathOrUrl)) return pathOrUrl;
  if (pathOrUrl.startsWith("//")) return `${window.location.protocol}${pathOrUrl}`;
  return `${window.location.origin}${pathOrUrl.startsWith("/") ? "" : "/"}${pathOrUrl}`;
}

function withTimeout(ms = 60000) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), ms);
  return { controller, clear: () => clearTimeout(id) };
}

export async function apiRequest(path, options = {}) {
  const token = localStorage.getItem("cn_access_token");
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (token) headers.Authorization = `Bearer ${token}`;

  const timer = withTimeout(options.timeoutMs || 60000);
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
      signal: options.signal || timer.controller.signal,
    });
  } catch (e) {
    if (e?.name === "AbortError") {
      throw new Error("Request timed out. Please try again.");
    }
    throw new Error("Cannot reach backend API. Ensure backend is running on http://localhost:8000.");
  } finally {
    timer.clear();
  }

  if (!response.ok) {
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const err = await response.json();
      const detail = typeof err?.detail === "string" ? err.detail : JSON.stringify(err?.detail || err);
      if (response.status === 401) throw new Error("Session expired. Please login again.");
      throw new Error(detail || `Request failed: ${response.status}`);
    }
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return response.json();
  return response.text();
}
