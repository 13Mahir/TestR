/**
 * reset-password.js
 * Extracted from reset-password.html to comply with CSP.
 */

// Extract token from URL: /reset-password.html?token=<TOKEN>
const params = new URLSearchParams(window.location.search);
const resetToken = params.get("token");

if (!resetToken) {
    document.getElementById("noTokenState").classList.remove("d-none");
    document.getElementById("resetFormArea").classList.add("d-none");
}

const form = document.getElementById("rpForm");
const newPass = document.getElementById("rpNewPass");
const confirmPass = document.getElementById("rpConfirmPass");
const rpBtn = document.getElementById("rpBtn");
const rpBtnText = document.getElementById("rpBtnText");
const rpSpinner = document.getElementById("rpSpinner");
const alertBox = document.getElementById("rpAlert");

function showAlert(msg, type = "danger") {
    alertBox.className = `alert alert-${type}`;
    alertBox.textContent = msg;
    alertBox.classList.remove("d-none");
}

function setLoading(on) {
    rpBtn.disabled = on;
    rpBtnText.textContent = on ? "Resetting..." : "Reset password";
    rpSpinner.classList.toggle("d-none", !on);
}

form.addEventListener("submit", async function (e) {
    e.preventDefault();

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
        const url = `/api/admin/users/consume-reset-token`;

        const res = await fetch(url, { 
            method: "POST",
            headers: { 
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                token: resetToken,
                new_password: newPass.value
            })
        });
        const data = await res.json();

        if (!res.ok) {
            let errorMsg = "Reset failed. Please try again.";
            if (Array.isArray(data.detail)) {
                errorMsg = data.detail.map(err => err.msg).join(', ');
            } else if (typeof data.detail === 'string') {
                errorMsg = data.detail;
            } else if (data.detail && data.detail.message) {
                errorMsg = data.detail.message;
            }
            showAlert(errorMsg);
            return;
        }

        showAlert(
            "Password reset successfully. Redirecting to login...",
            "success"
        );

        setTimeout(() => {
            window.location.href = "/static/pages/login.html";
        }, 1500);

    } catch (err) {
        showAlert("Network error. Please check your connection.");
    } finally {
        setLoading(false);
    }
});
