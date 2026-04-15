/**
 * login.js
 * Extracted from login.html to comply with CSP (blocks inline scripts).
 */

// ── Redirect if already authenticated ──────────────────────────────────
(async function checkExistingSession() {
  try {
    const res = await fetch("/api/auth/me", { credentials: "include" });
    if (res.ok) {
      const user = await res.json();
      _redirectByRole(user.role, user.force_password_reset);
    }
  } catch (_) { }
})();

function _redirectByRole(role, forceReset) {
  if (forceReset) {
    window.location.href = "/static/pages/change-password.html";
    return;
  }
  const destinations = {
    admin: "/static/pages/admin/overview.html",
    teacher: "/static/pages/teacher/courses.html",
    student: "/static/pages/student/dashboard.html",
  };
  window.location.href = destinations[role] || "/static/pages/login.html";
}

// ── Form submission ─────────────────────────────────────────────────────
const form = document.getElementById("loginForm");
const emailInput = document.getElementById("emailInput");
const passInput = document.getElementById("passwordInput");
const loginBtn = document.getElementById("loginBtn");
const btnText = document.getElementById("loginBtnText");
const spinner = document.getElementById("loginBtnSpinner");
const alertBox = document.getElementById("loginAlert");
const alertMsg = document.getElementById("loginAlertMsg");

function showError(msg) {
  let displayMsg = msg;
  if (msg && typeof msg === 'object') {
    if (Array.isArray(msg)) {
      displayMsg = msg.map(e => (typeof e === 'string' ? e : (e.msg || JSON.stringify(e)))).join(", ");
    } else {
      displayMsg = msg.detail || msg.message || JSON.stringify(msg);
    }
  }
  alertMsg.textContent = displayMsg;
  alertBox.classList.remove("d-none");
  alertBox.classList.add("d-flex");
}

function hideError() {
  alertBox.classList.add("d-none");
  alertBox.classList.remove("d-flex");
}

function setLoading(loading) {
  loginBtn.disabled = loading;
  btnText.textContent = loading ? "Authenticating..." : "Sign In";
  spinner.classList.toggle("d-none", !loading);
}

form.addEventListener("submit", async function (e) {
  e.preventDefault();
  hideError();

  if (!form.checkValidity()) {
    form.classList.add("was-validated");
    return;
  }
  form.classList.remove("was-validated");

  const email = emailInput.value.trim().toLowerCase();
  const password = passInput.value;

  setLoading(true);

  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      credentials: "include",
      headers: { 
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest"
      },
      body: JSON.stringify({ email, password }),
    });

    const data = await res.json();

    if (!res.ok) {
      showError(data.detail || "Login failed. Please try again.");
      return;
    }

    _redirectByRole(data.role, data.force_password_reset);

  } catch (err) {
    showError("Network error. Please check your connection and retry.");
  } finally {
    setLoading(false);
  }
});

// ── Password visibility toggle ──────────────────────────────────────────
const toggleBtn = document.getElementById("togglePassword");
const toggleIcon = document.getElementById("togglePasswordIcon");

toggleBtn.addEventListener("click", function () {
  const isPassword = passInput.type === "password";
  passInput.type = isPassword ? "text" : "password";
  toggleIcon.className = isPassword
    ? "bi bi-eye-slash"
    : "bi bi-eye";
  toggleBtn.setAttribute(
    "aria-label",
    isPassword ? "Hide password" : "Show password"
  );
});

// Login page specific theme toggler logic (UI is unique to login)
const themeBtn = document.getElementById("themeToggleBtn");
if (themeBtn) {
  themeBtn.addEventListener("click", function () {
    if (typeof window.toggleTheme === "function") {
      window.toggleTheme();
    }
  });
}

