/**
 * sidebar.js
 * Builds and injects the role-aware sidebar into every panel page.
 *
 * Dependencies (must be loaded before this file):
 *   - Bootstrap 5.3 CSS + JS bundle
 *   - Bootstrap Icons CSS
 *   - auth.js  (provides window.__user, window.apiFetch, window.logout)
 *   - theme.js (provides window.toggleTheme)
 *
 * Usage in any protected HTML page:
 *   1. Add <div id="sidebar-mount"></div> to <body>
 *   2. Wrap all page content in <div id="page-content" class="page-content">
 *   3. Add at end of <body>:
 *        <script src="/static/js/theme.js"></script>   ← in <head>
 *        <script src="/static/js/auth.js"></script>
 *        <script src="/static/js/sidebar.js"></script>
 *   sidebar.js registers itself as window.__onAuthReady so it runs
 *   automatically after auth.js confirms the session.
 */

// ── Nav link definitions per role ─────────────────────────────────────────────

const SIDEBAR_NAV = {
  admin: [
    { label: "Overview", href: "/static/pages/admin/overview.html", icon: "bi-speedometer2" },
    { label: "Manage Users", href: "/static/pages/admin/users.html", icon: "bi-people-fill" },
    { label: "System Logs", href: "/static/pages/admin/logs.html", icon: "bi-journal-text" },
    { label: "Manage Schools", href: "/static/pages/admin/schools.html", icon: "bi-building" },
    { label: "Manage Courses", href: "/static/pages/admin/courses.html", icon: "bi-mortarboard-fill" },
    { label: "Discussion Forum", href: "/static/pages/discussion.html", icon: "bi-chat-dots-fill" }
  ],


  teacher: [
    { label: "My Courses", href: "/static/pages/teacher/courses.html", icon: "bi-journal-bookmark-fill" },
    { label: "Grade Book", href: "/static/pages/teacher/gradebook.html", icon: "bi-journal-check" },
    { label: "Grading", href: "/static/pages/teacher/grading.html", icon: "bi-pencil-square" },
    { label: "Proctor Reports", href: "/static/pages/teacher/proctor_report.html", icon: "bi-shield-check" },
    { label: "Discussion Forum", href: "/static/pages/discussion.html", icon: "bi-chat-dots-fill" }
  ],
  student: [
    { label: "Dashboard", href: "/static/pages/student/dashboard.html", icon: "bi-speedometer2" },
    { label: "My Courses", href: "/static/pages/student/courses.html", icon: "bi-journal-bookmark-fill" },
    { label: "My Transcript", href: "/static/pages/student/transcript.html", icon: "bi-file-earmark-text-fill" },
    { label: "Discussion Forum", href: "/static/pages/discussion.html", icon: "bi-chat-dots-fill" }
  ]
};


// ── Role badge colours ────────────────────────────────────────────────────────

const ROLE_BADGE = {
  admin: { text: "Admin", cls: "bg-danger" },
  teacher: { text: "Teacher", cls: "bg-success" },
  student: { text: "Student", cls: "bg-primary" },
};

// ── Sidebar state ─────────────────────────────────────────────────────────────

const STORAGE_KEY = "ems-sidebar-retracted";

function isRetracted() {
  // On mobile, default to retracted
  if (window.innerWidth < 768) {
    return localStorage.getItem(STORAGE_KEY) !== "false";
  }
  return localStorage.getItem(STORAGE_KEY) === "true";
}

function setRetracted(value) {
  localStorage.setItem(STORAGE_KEY, value ? "true" : "false");
}

// ── Sidebar HTML builder ──────────────────────────────────────────────────────

/**
 * Builds the complete sidebar HTML string for the given user.
 * Called once on page load; retraction is applied via CSS class.
 */
function buildSidebarHTML(user) {
  const roleKey = String(user.role).toLowerCase();
  const navLinks = SIDEBAR_NAV[roleKey] || [];
  const badge = ROLE_BADGE[roleKey] || { text: user.role, cls: "bg-secondary" };
  const currentPath = window.location.pathname;

  // Build nav items
  const navItemsHTML = navLinks.map(function (item) {
    const isActive = currentPath === item.href ||
      currentPath.endsWith(item.href.split("/").pop());
    return `
      <li class="sidebar-nav-item">
        <a
          href="${item.href}"
          class="sidebar-nav-link ${isActive ? "active" : ""}"
          title="${item.label}"
        >
          <i class="bi ${item.icon} sidebar-nav-icon"></i>
          <span class="sidebar-nav-label">${item.label}</span>
        </a>
      </li>`;
  }).join("");

  return `
    <div id="sidebar" class="sidebar">

      <!-- Header -->
      <div class="sidebar-header">
        <div class="sidebar-brand">
          <i class="bi bi-book sidebar-logo-icon"></i>
          <span class="sidebar-brand-text">TestR</span>
        </div>
      </div>

      <!-- User info -->
      <div class="sidebar-user">
        <div class="sidebar-user-avatar">
          ${_initialsAvatar(user.first_name, user.last_name)}
        </div>
        <div class="sidebar-user-info">
          <div class="sidebar-user-name">${_escapeHtml(user.full_name)}</div>
          <span class="badge ${badge.cls} sidebar-user-badge">
            ${badge.text}
          </span>
        </div>
      </div>

      <!-- Navigation (Scrollable) -->
      <nav class="sidebar-nav" aria-label="Main navigation">
        <ul class="sidebar-nav-list">
          ${navItemsHTML}
        </ul>
      </nav>

      <!-- Bottom actions -->
      <div class="sidebar-bottom">
        <ul class="sidebar-nav-list pb-2">
          <li class="sidebar-nav-item">
            <button
              id="sidebarThemeBtn"
              class="sidebar-nav-link w-100 text-start border-0 bg-transparent"
              title="Toggle theme"
              aria-label="Toggle light/dark theme"
            >
              <i class="bi bi-moon-fill js-theme-icon sidebar-nav-icon"></i>
              <span class="sidebar-nav-label">Toggle theme</span>
            </button>
          </li>
          <li class="sidebar-nav-item">
            <button
              id="sidebarLogoutBtn"
              class="sidebar-nav-link w-100 text-start border-0 bg-transparent"
              title="Sign out"
              aria-label="Sign out"
            >
              <i class="bi bi-box-arrow-left sidebar-nav-icon"></i>
              <span class="sidebar-nav-label">Sign out</span>
            </button>
          </li>
          <li class="sidebar-nav-item">
            <button
              id="sidebarCollapseBtn"
              class="sidebar-nav-link w-100 text-start border-0 bg-transparent"
              title="Collapse sidebar"
              aria-label="Collapse sidebar"
            >
              <i class="bi bi-chevron-left sidebar-nav-icon" id="sidebarCollapseIcon"></i>
              <span class="sidebar-nav-label">Collapse sidebar</span>
            </button>
          </li>
        </ul>
      </div>
    </div>`;
}

// ── Helper: initials avatar ───────────────────────────────────────────────────

function _initialsAvatar(firstName, lastName) {
  const f = (firstName && firstName.length > 0) ? firstName[0].toUpperCase() : "?";
  const l = (lastName && lastName.length > 0) ? lastName[0].toUpperCase() : "";
  return `<span class="sidebar-avatar-initials">${f}${l}</span>`;
}

// ── Helper: escape HTML to prevent XSS in user-supplied names ────────────────

function _escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ── Retraction logic ──────────────────────────────────────────────────────────

/**
 * Applies or removes the "retracted" CSS class on #sidebar and
 * adjusts the page-content left margin accordingly.
 */
function _applyRetractedState(retracted) {
  const sidebar = document.getElementById("sidebar");
  const content = document.getElementById("page-content");
  const collapseIcon = document.getElementById("sidebarCollapseIcon");
  if (!sidebar) return;

  if (retracted) {
    sidebar.classList.add("sidebar--retracted");
    if (content) content.classList.add("page-content--sidebar-retracted");
    if (collapseIcon) collapseIcon.className = "bi bi-chevron-right sidebar-nav-icon";
  } else {
    sidebar.classList.remove("sidebar--retracted");
    if (content) content.classList.remove("page-content--sidebar-retracted");
    if (collapseIcon) collapseIcon.className = "bi bi-chevron-left sidebar-nav-icon";
  }
}

/**
 * Global toggle function — called by the toggle button onclick.
 */
window.__sidebarToggle = function () {
  const next = !isRetracted();
  setRetracted(next);
  _applyRetractedState(next);
};

// ── Initialisation ────────────────────────────────────────────────────────────

/**
 * Initialises the sidebar. Called by auth.js via __onAuthReady.
 * If a page defines its own __onAuthReady, it should call
 * window.__initSidebar(user) manually, or chain __onAuthReady.
 */
window.__initSidebar = function (user) {
  const mount = document.getElementById("sidebar-mount");
  if (!mount) {
    console.warn("sidebar.js: no #sidebar-mount element found on this page.");
    return;
  }

  // Inject sidebar HTML
  mount.innerHTML = buildSidebarHTML(user);

  // SECURE EVENT LISTENERS (Required by CSP)
  const themeBtn = document.getElementById("sidebarThemeBtn");
  if (themeBtn) {
    themeBtn.addEventListener("click", function() {
      if (typeof window.toggleTheme === "function") window.toggleTheme();
    });
  }

  const logoutBtn = document.getElementById("sidebarLogoutBtn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", function() {
      if (typeof window.logout === "function") window.logout();
    });
  }

  const collapseBtn = document.getElementById("sidebarCollapseBtn");
  if (collapseBtn) {
    collapseBtn.addEventListener("click", function() {
      if (typeof window.__sidebarToggle === "function") window.__sidebarToggle();
    });
  }

  // Apply correct retraction state immediately
  _applyRetractedState(isRetracted());

  // Update theme icon to match current theme
  const currentTheme = document.documentElement
    .getAttribute("data-bs-theme") || "light";
  document.querySelectorAll(".js-theme-icon").forEach(function (el) {
    el.className = currentTheme === "dark"
      ? "bi bi-sun-fill js-theme-icon sidebar-nav-icon"
      : "bi bi-moon-fill js-theme-icon sidebar-nav-icon";
  });
};

/**
 * Register as the __onAuthReady handler so sidebar initialises
 * automatically after auth.js confirms the session.
 *
 * If the page already defined window.__onAuthReady before sidebar.js
 * loaded, chain it so both run.
 */
(function registerOnAuthReady() {
  const existingHandler = window.__onAuthReady;

  window.__onAuthReady = async function (user) {
    window.__initSidebar(user);

    // Run the page's own handler if one was defined before this script
    if (typeof existingHandler === "function") {
      await existingHandler(user);
    }
  };
})();
