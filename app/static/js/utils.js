/**
 * utils.js
 * Common helper functions for the TestR frontend.
 * Global functions are prefixed with window._ for easy access.
 */

/**
 * Escapes HTML special characters to prevent XSS.
 */
window._esc = function (str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
};

/**
 * Formats an ISO date string into a readable format.
 */
window._formatDate = function (dateStr) {
    if (!dateStr) return "-";
    const date = new Date(dateStr);
    return date.toLocaleString();
};

/**
 * Calculates relative time (e.g., "2m ago").
 */
window._relativeTime = function (isoString) {
    if (!isoString) return "-";
    const date = new Date(isoString);
    const now = new Date();
    const diffS = Math.floor((now - date) / 1000);
    if (diffS < 60) return "just now";
    const diffM = Math.floor(diffS / 60);
    if (diffM < 60) return `${diffM}m ago`;
    const diffH = Math.floor(diffM / 60);
    if (diffH < 24) return `${diffH}h ago`;
    const diffD = Math.floor(diffH / 24);
    if (diffD < 7) return `${diffD}d ago`;
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return `${date.getDate()} ${months[date.getMonth()]} ${date.getFullYear()}`;
};

/**
 * Toggles loading state on a button.
 */
window._setLoading = function (btn, btnTextEl, spinnerEl, isLoading, text = "Loading...") {
    if (!btn) return;
    btn.disabled = isLoading;
    if (btnTextEl) {
        if (isLoading) {
            btnTextEl._originalText = btnTextEl.innerText;
            btnTextEl.innerText = text;
        } else {
            btnTextEl.innerText = btnTextEl._originalText || btnTextEl.innerText;
        }
    }
    if (spinnerEl) {
        spinnerEl.classList.toggle("d-none", !isLoading);
    }
};

/**
 * Displays an alert message in a container.
 * Safely handles objects (like FastAPI validation errors) to avoid [object Object] display.
 */
window._showAlert = function (alertEl, message, type = "danger") {
    if (!alertEl) return;
    
    let displayMsg = message;
    
    // If message is an object or array, try to extract a readable string
    if (message && typeof message === 'object') {
        if (Array.isArray(message)) {
            // FastAPI validation errors often come as a list of detail objects
            displayMsg = message.map(err => {
                if (typeof err === 'string') return err;
                if (err && err.msg) return err.msg;
                return JSON.stringify(err);
            }).join(", ");
        } else if (message.detail) {
            // Handle { detail: "..." } or { detail: [...] }
            return window._showAlert(alertEl, message.detail, type);
        } else {
            displayMsg = message.message || JSON.stringify(message);
        }
    }

    alertEl.className = `alert alert-${type}`;
    alertEl.innerText = displayMsg;
    alertEl.classList.remove("d-none");
};

/**
 * Hides an alert container.
 */
window._hideAlert = function (alertEl) {
    if (alertEl) alertEl.classList.add("d-none");
};

/**
 * Debounce helper.
 */
window._debounce = function (fn, ms) {
    let timeout;
    return function (...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => fn.apply(this, args), ms);
    };
};

/**
 * Standard Role Badge HTML generator (Bootstrap styles).
 */
window._roleBadge = function (role) {
    const roleLower = String(role || "").toLowerCase();
    const badges = {
        admin: { text: "Admin", cls: "bg-danger" },
        teacher: { text: "Teacher", cls: "bg-success" },
        student: { text: "Student", cls: "bg-primary" }
    };
    const b = badges[roleLower] || { text: role, cls: "bg-secondary" };
    return `<span class="badge ${b.cls}">${b.text}</span>`;
};
