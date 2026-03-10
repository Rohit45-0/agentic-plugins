/**
 * Intake API Service
 * ------------------
 * Calls the backend Product Intake endpoints.
 */
import { apiRequest } from "./api";

// Full URL used for raw fetch (multipart) — must include /api/v1
const FETCH_BASE = "/api/v1/intake";
// Relative path for apiRequest (which prepends /api/v1 itself)
const APIREQ_BASE = "/intake";

/**
 * Submit a product image + metadata for Visual DNA extraction.
 * Uses multipart/form-data so the image bytes are sent directly.
 *
 * @param {Object} params
 * @param {string} params.productName
 * @param {string} params.category
 * @param {string} params.targetAudience
 * @param {string} [params.additionalContext]
 * @param {string} [params.projectId]   existing project UUID (optional)
 * @param {File}   params.imageFile     the File object from the input
 */
export async function submitProductIntake({
    productName,
    category,
    targetAudience,
    additionalContext = "",
    projectId = null,
    imageFile,
}) {
    const token = localStorage.getItem("cn_access_token");
    if (!token) throw new Error("Not authenticated");

    const form = new FormData();
    form.append("product_name", productName);
    form.append("category", category);
    form.append("target_audience", targetAudience);
    if (additionalContext) form.append("additional_context", additionalContext);
    if (projectId) form.append("project_id", projectId);
    form.append("image", imageFile);

    const res = await fetch(`${FETCH_BASE}/product`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || "Intake failed");
    }
    return res.json();
}

/**
 * List all products (projects) for the logged-in user.
 */
export async function listProducts() {
    return apiRequest(`${APIREQ_BASE}/products`);
}
