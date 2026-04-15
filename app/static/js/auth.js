/**
 * auth.js
 * Shared authentication guard loaded by every protected HTML page.
 *
 * Responsibilities:
 *   1. On page load, call GET /api/auth/me to verify the session.
 *   2. If 401 → redirect to login page.
 *   3. If 403 with detail "PASSWORD_RESET_REQUIRED" → redirect to
 *      change-password page.
 *   4. If 200 → store user profile in window.__user for other scripts
 *      to read, then call window.__onAuthReady() if defined.
 *   5. Attempt one silent token refresh before giving up on 401.
 *   6. Expose a global apiFetch() wrapper that automatically retries
 *      once with a token refresh on 401, then redirects to login if
 *      the retry also fails.
 */

// ── Constants ────────────────────────────────────────────────────────────────

const LOGIN_PAGE = "/static/pages/login.html";
const CHANGE_PASSWORD_PAGE = "/static/pages/change-password.html";
const API_ME = "/api/auth/me";
const API_REFRESH = "/api/auth/refresh";
const API_LOGOUT = "/api/auth/logout";

// ── Core fetch wrapper ────────────────────────────────────────────────────────

/**
 * apiFetch(url, options)
 *
 * A drop-in replacement for fetch() used by every page in this app.
 * Automatically includes credentials (cookies) on every request.
 * On 401: attempts one silent token refresh, then retries the request.
 * If the retry also returns 401: redirects to login page.
 * On 403 with PASSWORD_RESET_REQUIRED: redirects to change-password page.
 *
 * Usage:
 *   const data = await apiFetch("/api/admin/users");
 *   // data is the parsed JSON body, or null if response has no body.
 *   // Throws an Error with .status and .detail set on HTTP errors
 *   // other than 401 (those are handled via redirect).
 */
async function apiFetch(url, options = {}) {
  const defaultOptions = {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "XMLHttpRequest",
      ...(options.headers || {}),
    },
    ...options,
  };

  let response = await fetch(url, defaultOptions);

  // ── 401: try refresh once ─────────────────────────────────────────────
  if (response.status === 401) {
    const refreshed = await _tryRefresh();
    if (!refreshed) {
      window.location.href = LOGIN_PAGE;
      return null;
    }
    // Retry original request with fresh cookies
    response = await fetch(url, defaultOptions);
    if (response.status === 401) {
      window.location.href = LOGIN_PAGE;
      return null;
    }
  }

  // ── 403: check for password reset requirement ─────────────────────────
  if (response.status === 403) {
    let body = null;
    try { body = await response.clone().json(); } catch (_) { }
    if (body && body.detail === "PASSWORD_RESET_REQUIRED") {
      window.location.href = CHANGE_PASSWORD_PAGE;
      return null;
    }
    // Other 403: throw so the calling page can handle it
    const err = new Error("Forbidden");
    err.status = 403;
    err.detail = body ? body.detail : "Forbidden";
    throw err;
  }

  // ── Other errors ──────────────────────────────────────────────────────
  if (!response.ok) {
    let body = null;
    try { body = await response.clone().json(); } catch (_) { }
    const err = new Error(
      body ? (body.detail || JSON.stringify(body)) : response.statusText
    );
    err.status = response.status;
    err.detail = body ? body.detail : response.statusText;
    throw err;
  }

  // ── Success ───────────────────────────────────────────────────────────
  const contentType = response.headers.get("Content-Type") || "";
  if (contentType.includes("application/json")) {
    return await response.json();
  }
  // For non-JSON responses (e.g. CSV/PDF file downloads) return the
  // Response object itself so the caller can call .blob() or .text()
  return response;
}

// ── Silent refresh ────────────────────────────────────────────────────────────

/**
 * Attempts to refresh tokens silently using the refresh cookie.
 * Returns true if refresh succeeded, false otherwise.
 * Never throws.
 */
async function _tryRefresh() {
  try {
    const res = await fetch(API_REFRESH, {
      method: "POST",
      credentials: "include",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
    return res.ok;
  } catch (_) {
    return false;
  }
}

// ── Logout helper ─────────────────────────────────────────────────────────────

/**
 * Logs the user out by calling the logout endpoint, then redirects
 * to the login page. Attached to any logout button via:
 *   <button onclick="logout()">Logout</button>
 */
async function logout() {
  try {
    await fetch(API_LOGOUT, {
      method: "POST",
      credentials: "include",
      headers: {
        "X-Requested-With": "XMLHttpRequest"
      }
    });
  } catch (_) {
    // Ignore errors — always redirect to login
  } finally {
    window.location.href = LOGIN_PAGE;
  }
}

// ── Page-load auth guard ──────────────────────────────────────────────────────

/**
 * Runs on every protected page load.
 * Calls /api/auth/me and handles all outcomes.
 *
 * After a successful auth check, the user profile is stored in
 * window.__user and window.__onAuthReady() is called if defined.
 *
 * Pages that need to run logic after auth is confirmed should define:
 *   window.__onAuthReady = async function(user) { ... }
 * BEFORE this script executes (i.e. in an inline <script> above this
 * file's <script> tag, or in a DOMContentLoaded handler defined before
 * auth.js loads).
 *
 * Protected pages must include this file FIRST in their script section.
 */
(async function guardPage() {
  // Show a loading overlay while checking auth
  _showLoadingOverlay();

  let user = null;
  try {
    user = await apiFetch(API_ME);
  } catch (err) {
    // apiFetch already redirects on 401 — only non-auth errors reach here
    console.error("Auth check failed:", err);
    window.location.href = LOGIN_PAGE;
    return;
  }

  if (!user) {
    // apiFetch returned null → redirect already triggered
    return;
  }

  // Store globally for sidebar.js and page scripts
  window.__user = user;

  // Handle forced password reset
  if (user.force_password_reset) {
    // Only allow access to change-password page
    const currentPage = window.location.pathname;
    if (!currentPage.includes("change-password")) {
      window.location.href = CHANGE_PASSWORD_PAGE;
      return;
    }
  }

  _hideLoadingOverlay();

  // Notify page scripts that auth is confirmed
  if (typeof window.__onAuthReady === "function") {
    await window.__onAuthReady(user);
  }
})();

// ── Loading overlay helpers ───────────────────────────────────────────────────

function _showLoadingOverlay() {
  const existing = document.getElementById("__auth-overlay");
  if (existing) return;
  const overlay = document.createElement("div");
  overlay.id = "__auth-overlay";
  overlay.style.cssText = [
    "position:fixed",
    "inset:0",
    "background:var(--bs-body-bg, #fff)",
    "display:flex",
    "align-items:center",
    "justify-content:center",
    "z-index:9999",
    "transition:opacity 0.2s ease",
  ].join(";");
  overlay.innerHTML = `
    <div class="text-center">
      <div class="spinner-border text-primary" role="status"
           style="width:2rem;height:2rem;">
        <span class="visually-hidden">Loading...</span>
      </div>
      <p class="mt-2 text-muted small">Verifying session...</p>
    </div>`;
  document.body.appendChild(overlay);
}

function _hideLoadingOverlay() {
  const overlay = document.getElementById("__auth-overlay");
  if (overlay) {
    overlay.style.opacity = "0";
    setTimeout(() => overlay.remove(), 200);
  }
}

// ── Expose globals ────────────────────────────────────────────────────────────

window.apiFetch = apiFetch;
window.logout = logout;
