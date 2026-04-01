/**
 * theme.js
 * Applies the saved theme preference on every page load and exposes
 * a toggleTheme() global used by the sidebar theme button.
 *
 * Must be loaded in <head> BEFORE Bootstrap CSS to prevent flash.
 * On every page add:
 *   <script src="/static/js/theme.js"></script>
 * as the FIRST script tag in <head>.
 */

(function applyThemeImmediately() {
    var saved = localStorage.getItem("ems-theme") || "light";
    document.documentElement.setAttribute("data-bs-theme", saved);
})();

/**
 * Toggles between light and dark theme.
 * Updates the html[data-bs-theme] attribute and persists to localStorage.
 * Updates any theme icon elements that have id="themeIcon" or the
 * class "js-theme-icon" on the page.
 */
function toggleTheme() {
    var html = document.documentElement;
    var current = html.getAttribute("data-bs-theme") || "light";
    var next = current === "dark" ? "light" : "dark";

    html.setAttribute("data-bs-theme", next);
    localStorage.setItem("ems-theme", next);

    // Update all theme icon elements on the page
    document.querySelectorAll(".js-theme-icon").forEach(function (el) {
        el.className = next === "dark"
            ? "bi bi-sun-fill js-theme-icon"
            : "bi bi-moon-fill js-theme-icon";
    });
}

window.toggleTheme = toggleTheme;
