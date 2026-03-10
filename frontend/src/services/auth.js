import { apiRequest } from "./api";

const TOKEN_KEY = "cn_access_token";
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";

export function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function clearAccessToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export async function login(email, password) {
  const body = new URLSearchParams();
  body.append("username", email);
  body.append("password", password);

  let response;
  try {
    response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
  } catch {
    throw new Error("Cannot reach backend API. Ensure backend is running on http://localhost:8000.");
  }

  if (!response.ok) {
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const err = await response.json();
      throw new Error(err?.detail || "Login failed");
    }
    const text = await response.text();
    throw new Error(text || "Login failed");
  }

  const data = await response.json();
  localStorage.setItem(TOKEN_KEY, data.access_token);
  return data;
}

export async function register(payload) {
  return apiRequest("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getCurrentUser() {
  return apiRequest("/auth/me");
}

export async function getFacebookLoginUrl() {
  return apiRequest("/auth/instagram/login-url");
}
