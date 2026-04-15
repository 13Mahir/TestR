/**
 * change-password.js
 * Extracted from change-password.html to comply with CSP.
 */

// Show why reset is required if force_password_reset is set
window.__onAuthReady = function (user) {
    if (user.force_password_reset) {
        document.getElementById("reasonText").textContent =
            "An administrator requires you to change your password before continuing.";
    }
};

const form = document.getElementById("cpForm");
const currentPass = document.getElementById("currentPass");
const newPass = document.getElementById("newPass");
const confirmPass = document.getElementById("confirmPass");
const cpBtn = document.getElementById("cpBtn");
const cpBtnText = document.getElementById("cpBtnText");
const cpSpinner = document.getElementById("cpSpinner");
const alertBox = document.getElementById("cpAlert");
const alertMsg = document.getElementById("cpAlertMsg");
const alertIcon = document.getElementById("cpAlertIcon");

function showAlert(msg, type = "danger") {
    alertBox.className = `alert alert-${type} d-flex align-items-center gap-2`;
    alertIcon.className = type === "success"
        ? "bi bi-check-circle-fill flex-shrink-0"
        : "bi bi-exclamation-triangle-fill flex-shrink-0";
    alertMsg.textContent = msg;
}

function setLoading(on) {
    cpBtn.disabled = on;
    cpBtnText.textContent = on ? "Updating..." : "Update password";
    cpSpinner.classList.toggle("d-none", !on);
}

form.addEventListener("submit", async function (e) {
    e.preventDefault();

    const password = newPass.value;
    const feedback = document.getElementById("newPassFeedback");
    let errorMsg = "";

    if (password.length < 8) {
        errorMsg = "Password must be at least 8 characters.";
    } else if (!/[A-Z]/.test(password)) {
        errorMsg = "Password must contain at least one uppercase letter.";
    } else if (!/[a-z]/.test(password)) {
        errorMsg = "Password must contain at least one lowercase letter.";
    } else if (!/[0-9]/.test(password)) {
        errorMsg = "Password must contain at least one digit.";
    }

    if (errorMsg) {
        newPass.setCustomValidity(errorMsg);
        feedback.textContent = errorMsg;
        form.classList.add("was-validated");
        return;
    }
    newPass.setCustomValidity("");

    // Confirm match
    if (newPass.value !== confirmPass.value) {
        confirmPass.setCustomValidity("Passwords do not match.");
        form.classList.add("was-validated");
        return;
    }
    confirmPass.setCustomValidity("");

    if (!form.checkValidity()) {
        form.classList.add("was-validated");
        return;
    }

    setLoading(true);

    try {
        await window.apiFetch("/api/auth/change-password", {
            method: "POST",
            body: JSON.stringify({
                current_password: currentPass.value,
                new_password: newPass.value,
            }),
        });

        showAlert("Password updated successfully. Redirecting...", "success");

        // Re-fetch user to get updated role for redirect
        setTimeout(async () => {
            const user = await window.apiFetch("/api/auth/me");
            if (user) {
                const destinations = {
                    admin: "/static/pages/admin/overview.html",
                    teacher: "/static/pages/teacher/courses.html",
                    student: "/static/pages/student/dashboard.html",
                };
                window.location.href =
                    destinations[user.role] || "/static/pages/login.html";
            }
        }, 1200);

    } catch (err) {
        showAlert(err.detail || "Failed to update password. Try again.");
    } finally {
        setLoading(false);
    }
});

// logout button handler
const logoutBtn = document.getElementById("logoutBtn");
if (logoutBtn) {
    logoutBtn.addEventListener("click", function() {
        if (typeof window.logout === "function") window.logout();
    });
}
