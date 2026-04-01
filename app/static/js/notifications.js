/**
 * notifications.js
 * In-app notification bell icon with dropdown.
 *
 * Responsibilities:
 *   1. Inject a notification bell button into #notification-bar.
 *   2. Poll GET /api/notifications/unread-count every 30 seconds.
 *   3. On bell click: fetch and render the notification list in a
 *      Bootstrap dropdown, mark all as read when opened.
 *   4. Show unread count badge on the bell icon.
 *
 * Dependencies (loaded before this file):
 *   - Bootstrap 5.3 JS bundle (for dropdown)
 *   - auth.js  (window.apiFetch)
 *   - sidebar.js
 *
 * This script chains onto window.__onAuthReady automatically so it
 * initialises after sidebar.js without overwriting it.
 */

// ── Constants ─────────────────────────────────────────────────────────────────

const NOTIF_POLL_INTERVAL_MS = 30_000;  // 30 seconds
const NOTIF_API_LIST = "/api/notifications/?page=1&per_page=10";
const NOTIF_API_COUNT = "/api/notifications/unread-count";
const NOTIF_API_READ_ALL = "/api/notifications/read-all";
const NOTIF_API_READ_ONE = (id) => `/api/notifications/${id}/read`;

// ── State ─────────────────────────────────────────────────────────────────────

let _pollTimer = null;

// ── Bell HTML builder ─────────────────────────────────────────────────────────

/**
 * Builds and injects the notification bell into #notification-bar.
 * Called once during initialisation.
 */
function _buildBell() {
  const bar = document.getElementById("notification-bar");
  if (!bar) return;

  bar.innerHTML = `
    <div class="notif-bar-inner">
      <div class="dropdown" id="notifDropdownWrapper">
        <button
          class="btn btn-link notif-bell-btn p-0"
          type="button"
          id="notifBellBtn"
          aria-expanded="false"
          aria-label="Notifications"
          title="Notifications"
        >
          <i class="bi bi-bell-fill notif-bell-icon"></i>
          <span
            class="badge rounded-pill bg-danger notif-badge d-none"
            id="notifBadge"
            aria-label="unread notifications"
          >0</span>
        </button>

        <div
          class="dropdown-menu dropdown-menu-end notif-dropdown"
          id="notifDropdown"
          aria-labelledby="notifBellBtn"
        >
          <!-- Header -->
          <div class="notif-dropdown-header">
            <span class="fw-semibold">Notifications</span>
            <button
              class="btn btn-link btn-sm p-0 text-muted notif-mark-all-btn"
              id="notifMarkAllBtn"
              onclick="_notifMarkAll()"
            >
              Mark all read
            </button>
          </div>
          <div class="dropdown-divider my-0"></div>

          <!-- List area — populated on open -->
          <div id="notifList" class="notif-list">
            <div class="notif-empty text-muted text-center py-3 small">
              <i class="bi bi-bell-slash d-block fs-4 mb-1 opacity-50"></i>
              No notifications
            </div>
          </div>

          <!-- Footer -->
          <div class="dropdown-divider my-0"></div>
          <div class="text-center py-2">
            <small class="text-muted" id="notifFooter">—</small>
          </div>
        </div>
      </div>
    </div>`;

  // Custom rock-solid dropdown toggle
  const bellBtn = document.getElementById("notifBellBtn");
  const dropdownMenu = document.getElementById("notifDropdown");

  if (bellBtn && dropdownMenu) {
    bellBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      const isShown = dropdownMenu.classList.contains("show");

      // Close all other dropdowns if any
      document.querySelectorAll(".notif-dropdown.show").forEach(m => m.classList.remove("show"));

      if (!isShown) {
        dropdownMenu.classList.add("show");
        bellBtn.setAttribute("aria-expanded", "true");
        _notifLoadList();
      } else {
        dropdownMenu.classList.remove("show");
        bellBtn.setAttribute("aria-expanded", "false");
      }
    });

    // Close when clicking outside
    document.addEventListener("click", function (e) {
      if (!dropdownMenu.contains(e.target) && e.target !== bellBtn && !bellBtn.contains(e.target)) {
        dropdownMenu.classList.remove("show");
        bellBtn.setAttribute("aria-expanded", "false");
      }
    });
  }
}

// ── Badge update ──────────────────────────────────────────────────────────────

/**
 * Updates the red badge count on the bell icon.
 * Hides the badge when count is 0.
 */
function _updateBadge(count) {
  const badge = document.getElementById("notifBadge");
  if (!badge) return;
  if (count > 0) {
    badge.textContent = count > 99 ? "99+" : String(count);
    badge.classList.remove("d-none");
  } else {
    badge.classList.add("d-none");
  }
}

// ── Polling ───────────────────────────────────────────────────────────────────

/**
 * Polls the unread count endpoint every NOTIF_POLL_INTERVAL_MS ms.
 * Updates the badge silently in the background.
 * Uses window.apiFetch so token refresh is handled automatically.
 */
async function _startPolling() {
  // Immediate first fetch
  await _pollUnreadCount();

  // Schedule recurring polls
  _pollTimer = setInterval(async function () {
    await _pollUnreadCount();
  }, NOTIF_POLL_INTERVAL_MS);
}

async function _pollUnreadCount() {
  try {
    const data = await window.apiFetch(NOTIF_API_COUNT);
    if (data && typeof data.unread_count === "number") {
      _updateBadge(data.unread_count);
    }
  } catch (_) {
    // Silently ignore poll errors — badge stays as-is
  }
}

// ── List loading ──────────────────────────────────────────────────────────────

/**
 * Fetches the latest 10 notifications and renders them in the dropdown.
 * Called every time the dropdown opens.
 */
async function _notifLoadList() {
  const list = document.getElementById("notifList");
  const footer = document.getElementById("notifFooter");
  if (!list) return;

  // Show loading state
  list.innerHTML = `
    <div class="text-center py-3">
      <div class="spinner-border spinner-border-sm text-secondary"
           role="status"></div>
    </div>`;

  try {
    const data = await window.apiFetch(NOTIF_API_LIST);
    if (!data) return;

    // Update badge with fresh count
    _updateBadge(data.unread_count);

    // Render notifications
    if (!data.notifications || data.notifications.length === 0) {
      list.innerHTML = `
        <div class="notif-empty text-muted text-center py-3 small">
          <i class="bi bi-bell-slash d-block fs-4 mb-1 opacity-50"></i>
          No notifications yet
        </div>`;
      if (footer) footer.textContent = "—";
      return;
    }

    list.innerHTML = data.notifications
      .map(n => _buildNotifItem(n))
      .join("");

    if (footer) {
      footer.textContent =
        data.total > 10
          ? `Showing 10 of ${data.total} notifications`
          : `${data.total} notification${data.total !== 1 ? "s" : ""}`;
    }

    // Mark all visible notifications as read automatically
    const unreadIds = data.notifications
      .filter(n => !n.is_read)
      .map(n => n.id);

    if (unreadIds.length > 0) {
      // Fire-and-forget — don't await so UI isn't blocked
      _markAllRead();
    }

  } catch (err) {
    list.innerHTML = `
      <div class="text-center py-3 text-danger small">
        <i class="bi bi-exclamation-triangle d-block fs-4 mb-1"></i>
        Failed to load notifications
      </div>`;
  }
}

/**
 * Builds HTML for a single notification item.
 */
function _buildNotifItem(n) {
  const date = new Date(n.created_at);
  const timeStr = _formatRelativeTime(date);
  const unread = !n.is_read;

  return `
    <div class="notif-item ${unread ? "notif-item--unread" : ""}">
      <div class="notif-item-header">
        <span class="notif-item-title">${_escapeHtml(n.title)}</span>
        <span class="notif-item-time text-muted">${timeStr}</span>
      </div>
      <p class="notif-item-body mb-0">${_escapeHtml(n.body)}</p>
    </div>`;
}

/**
 * Marks ALL notifications as read.
 * Called automatically when dropdown opens or by "Mark all read" button.
 */
async function _markAllRead() {
  try {
    await window.apiFetch(NOTIF_API_READ_ALL, {
      method: "PATCH",
    });
    _updateBadge(0);
  } catch (_) {
    // Silently ignore
  }
}

/**
 * Marks ALL notifications as read and reloads the list.
 */
async function _notifMarkAll() {
  await _markAllRead();
  await _notifLoadList();
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Formats a Date object as a relative time string.
 * e.g. "just now", "5m ago", "2h ago", "3d ago"
 */
function _formatRelativeTime(date) {
  const now = Date.now();
  const diffMs = now - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 30) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

/**
 * Escapes HTML special characters to prevent XSS in notification
 * titles and messages (which may contain user-supplied data).
 */
function _escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ── Initialisation ────────────────────────────────────────────────────────────

/**
 * Chains onto window.__onAuthReady (set by sidebar.js).
 * Builds the bell, then starts background polling.
 */
(function registerNotifications() {
  const existingHandler = window.__onAuthReady;

  window.__onAuthReady = async function (user) {
    // Run sidebar handler first (already set by sidebar.js)
    if (typeof existingHandler === "function") {
      await existingHandler(user);
    }

    // Build bell and start polling
    _buildBell();
    await _startPolling();
  };
})();

// Expose mark-all for inline onclick attribute
window._notifMarkAll = _notifMarkAll;
