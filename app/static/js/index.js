/**
 * index.js
 * Extracted from index.html
 */

(async function checkSession() {
    try {
        const res = await fetch("/api/auth/me", { credentials: "include" });
        if (res.ok) {
            const user = await res.json();
            if (user.force_password_reset) {
                window.location.href = "/static/pages/change-password.html";
                return;
            }
            const map = {
                admin: "/static/pages/admin/overview.html",
                teacher: "/static/pages/teacher/courses.html",
                student: "/static/pages/student/dashboard.html",
            };
            window.location.href = map[user.role] || "/static/pages/login.html";
        }
        // Not logged in → stay on landing page
    } catch (_) { }
})();

// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener("click", function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute("href"));
        if (target) target.scrollIntoView({ behavior: "smooth" });
    });
});

// Update theme icons on load
(function () {
    const theme = localStorage.getItem("ems-theme") || "light";
    document.querySelectorAll(".js-theme-icon").forEach(el => {
        el.className = theme === "dark"
            ? "bi bi-sun-fill js-theme-icon"
            : "bi bi-moon-fill js-theme-icon";
    });
})();
