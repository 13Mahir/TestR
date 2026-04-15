/**
 * admin/users.js
 * Extracted from admin/users.html
 */

// ── State ─────────────────────────────────────────────────────────
let currentPage = 1;
let selectedUserId = null;
let selectedUserEmail = null;

// ── Auth ready ───────────────────────────────────────────────────
(function () {
    const _prev = window.__onAuthReady;
    window.__onAuthReady = async function (user) {
        if (typeof _prev === "function") await _prev(user);
        await loadUsers(1);
    };
})();

// ── Load users table ──────────────────────────────────────────────

async function loadUsers(page) {
    currentPage = page;
    const role = document.getElementById("filterRole").value;
    const isActive = document.getElementById("filterActive").value;
    const search = document.getElementById("filterSearch").value.trim();

    let url = "/api/admin/users?page=" + page + "&page_size=15";
    if (role) url += "&role=" + encodeURIComponent(role);
    if (isActive) url += "&is_active=" + isActive;
    if (search) url += "&search=" + encodeURIComponent(search);

    const tbody = document.getElementById("usersTableBody");
    tbody.innerHTML =
        '<tr><td colspan="7" class="text-center text-muted py-4">' +
        '<div class="spinner-border spinner-border-sm me-2" role="status">' +
        '</div>Loading...</td></tr>';

    try {
        const data = await window.apiFetch(url);
        if (!data) return;

        document.getElementById("userCountLabel").textContent =
            data.total + " user" + (data.total !== 1 ? "s" : "") + " found";

        if (data.items.length === 0) {
            tbody.innerHTML =
                '<tr><td colspan="7" class="text-center text-muted py-4">' +
                'No users match the current filters.</td></tr>';
            renderPagination(data);
            return;
        }

        tbody.innerHTML = data.items.map(function (u, i) {
            var rowNum = (page - 1) * 15 + i + 1;
            var resetBadge = u.force_password_reset
                ? ' <span class="badge bg-warning text-dark ms-1 small">Reset pending</span>'
                : '';
            var nameCell = u.full_name
                ? window._esc(u.full_name)
                : '<span class="text-muted">&mdash;</span>';
            var statusBadge = u.is_active
                ? '<span class="badge bg-success-subtle text-success">Active</span>'
                : '<span class="badge bg-secondary-subtle text-secondary">Inactive</span>';
            
            return '<tr>' +
                '<td class="text-muted small">' + rowNum + '</td>' +
                '<td><span class="font-monospace small">' + window._esc(u.email) + '</span>' + resetBadge + '</td>' +
                '<td>' + nameCell + '</td>' +
                '<td>' + window._roleBadge(u.role) + '</td>' +
                '<td>' + statusBadge + '</td>' +
                '<td class="small text-muted">' + window._formatDate(u.created_at) + '</td>' +
                '<td><div class="d-flex gap-1">' +
                '<button class="btn btn-outline-warning btn-sm" ' +
                'onclick="openForceReset(' + u.id + ', \'' + window._esc(u.email) + '\')" ' +
                'title="Force password reset">' +
                '<i class="bi bi-key-fill"></i>' +
                '</button>' +
                (u.is_active
                    ? '<button class="btn btn-outline-danger btn-sm" ' +
                    'onclick="toggleActive(' + u.id + ', \'' + window._esc(u.email) + '\', false)" ' +
                    'title="Deactivate user">' +
                    '<i class="bi bi-person-x-fill"></i>' +
                    '</button>'
                    : '<button class="btn btn-outline-success btn-sm" ' +
                    'onclick="toggleActive(' + u.id + ', \'' + window._esc(u.email) + '\', true)" ' +
                    'title="Activate user">' +
                    '<i class="bi bi-person-check-fill"></i>' +
                    '</button>'
                ) +
                '</div></td>' +
                '</tr>';
        }).join("");

        renderPagination(data);

    } catch (err) {
        tbody.innerHTML =
            '<tr><td colspan="7" class="text-center text-danger py-4">' +
            '<i class="bi bi-exclamation-triangle me-2"></i>' +
            window._esc(err.detail || "Failed to load users.") + '</td></tr>';
    }
}

// ── Pagination ────────────────────────────────────────────────────

function renderPagination(data) {
    var info = document.getElementById("paginationInfo");
    var nav = document.getElementById("paginationControls");

    var start = (data.page - 1) * data.page_size + 1;
    var end = Math.min(data.page * data.page_size, data.total);
    info.textContent = data.total > 0
        ? "Showing " + start + "–" + end + " of " + data.total
        : "";

    if (data.total_pages <= 1) {
        nav.innerHTML = "";
        return;
    }

    var html = "";

    // Previous
    html += '<li class="page-item ' + (!data.has_prev ? 'disabled' : '') + '">' +
        '<button class="page-link" onclick="loadUsers(' + (data.page - 1) + ')"' +
        (!data.has_prev ? ' disabled' : '') + '>' +
        '<i class="bi bi-chevron-left"></i></button></li>';

    // Page numbers
    var startP = Math.max(1, data.page - 2);
    var endP = Math.min(data.total_pages, data.page + 2);

    if (startP > 1) {
        html += '<li class="page-item"><button class="page-link" onclick="loadUsers(1)">1</button></li>';
        if (startP > 2) {
            html += '<li class="page-item disabled"><span class="page-link">&hellip;</span></li>';
        }
    }

    for (var p = startP; p <= endP; p++) {
        html += '<li class="page-item ' + (p === data.page ? 'active' : '') + '">' +
            '<button class="page-link" onclick="loadUsers(' + p + ')">' + p + '</button></li>';
    }

    if (endP < data.total_pages) {
        if (endP < data.total_pages - 1) {
            html += '<li class="page-item disabled"><span class="page-link">&hellip;</span></li>';
        }
        html += '<li class="page-item"><button class="page-link" onclick="loadUsers(' +
            data.total_pages + ')">' + data.total_pages + '</button></li>';
    }

    // Next
    html += '<li class="page-item ' + (!data.has_next ? 'disabled' : '') + '">' +
        '<button class="page-link" onclick="loadUsers(' + (data.page + 1) + ')"' +
        (!data.has_next ? ' disabled' : '') + '>' +
        '<i class="bi bi-chevron-right"></i></button></li>';

    nav.innerHTML = html;
}

// ── Search events ────────────────────────────────────────────────

document.getElementById("filterSearch").addEventListener("keydown", function (e) {
    if (e.key === "Enter") loadUsers(1);
});

// ── Create single user ────────────────────────────────────────────

async function submitCreateUser() {
    var form = document.getElementById("createUserForm");
    var email = document.getElementById("cuEmail").value.trim();
    var password = document.getElementById("cuPassword").value;
    var alertEl = document.getElementById("createUserAlert");
    var btn = document.getElementById("createUserBtn");
    var btnText = document.getElementById("createUserBtnText");
    var spinner = document.getElementById("createUserSpinner");

    if (!form.checkValidity()) {
        form.classList.add("was-validated");
        return;
    }

    window._setLoading(btn, btnText, spinner, true, "Creating...");
    window._hideAlert(alertEl);

    try {
        await window.apiFetch("/api/admin/users/single", {
            method: "POST",
            body: JSON.stringify({ email: email, password: password }),
        });

        window._showAlert(alertEl, "User created successfully.", "success");
        form.reset();
        form.classList.remove("was-validated");
        await loadUsers(1);

        setTimeout(function () {
            var modal = bootstrap.Modal.getInstance(document.getElementById("createUserModal"));
            if (modal) modal.hide();
            window._hideAlert(alertEl);
        }, 1200);

    } catch (err) {
        window._showAlert(alertEl, err.detail || "Failed to create user.", "danger");
    } finally {
        window._setLoading(btn, btnText, spinner, false, "Create User");
    }
}

// ── Bulk create students ──────────────────────────────────────────

async function submitBulkStudents() {
    var form = document.getElementById("bulkStudentsForm");
    var alertEl = document.getElementById("bulkStudentsAlert");
    var btn = document.getElementById("bulkStudentsBtn");
    var btnText = document.getElementById("bulkStudentsBtnText");
    var spinner = document.getElementById("bulkStudentsSpinner");

    if (!form.checkValidity()) {
        form.classList.add("was-validated");
        return;
    }

    var body = {
        batch_year: document.getElementById("bsBatchYear").value.trim(),
        branch_code: document.getElementById("bsBranchCode").value.trim().toUpperCase(),
        roll_start: parseInt(document.getElementById("bsRollStart").value, 10),
        roll_end: parseInt(document.getElementById("bsRollEnd").value, 10),
        default_password: document.getElementById("bsPassword").value,
    };

    window._setLoading(btn, btnText, spinner, true, "Creating...");
    window._hideAlert(alertEl);

    try {
        var data = await window.apiFetch("/api/admin/users/bulk-students", {
            method: "POST",
            body: JSON.stringify(body),
        });

        var msg = data.message;
        if (data.errors && data.errors.length > 0) {
            msg += "\nErrors: " + data.errors.join("; ");
        }

        window._showAlert(alertEl, msg, data.failed > 0 ? "warning" : "success");
        form.reset();
        form.classList.remove("was-validated");
        await loadUsers(1);

    } catch (err) {
        window._showAlert(alertEl, err.detail || "Failed to create students.", "danger");
    } finally {
        window._setLoading(btn, btnText, spinner, false, "Create Students");
    }
}

// ── Bulk create teachers ──────────────────────────────────────────

async function submitBulkTeachers() {
    var form = document.getElementById("bulkTeachersForm");
    var alertEl = document.getElementById("bulkTeachersAlert");
    var btn = document.getElementById("bulkTeachersBtn");
    var btnText = document.getElementById("bulkTeachersBtnText");
    var spinner = document.getElementById("bulkTeachersSpinner");

    if (!form.checkValidity()) {
        form.classList.add("was-validated");
        return;
    }

    var fileInput = document.getElementById("btCsvFile");
    var password = document.getElementById("btPassword").value;

    if (!fileInput.files[0]) {
        window._showAlert(alertEl, "Please select a CSV file.", "danger");
        return;
    }

    window._setLoading(btn, btnText, spinner, true, "Uploading...");
    window._hideAlert(alertEl);

    try {
        var formData = new FormData();
        formData.append("default_password", password);
        formData.append("csv_file", fileInput.files[0]);

        // Using native fetch for FormData
        var resp = await fetch("/api/admin/users/bulk-teachers", {
            method: "POST",
            credentials: "include",
            body: formData,
            headers: {
                "X-Requested-With": "XMLHttpRequest" // Ensure CSRF protection header is present
            }
        });

        if (!resp.ok) {
            var errBody = null;
            try { errBody = await resp.json(); } catch (_) { }
            var errMsg = errBody ? (errBody.detail || JSON.stringify(errBody)) : resp.statusText;
            throw { detail: errMsg };
        }

        var data = await resp.json();

        window._showAlert(alertEl, data.message, data.failed > 0 ? "warning" : "success");
        form.reset();
        form.classList.remove("was-validated");
        await loadUsers(1);

    } catch (err) {
        window._showAlert(alertEl, err.detail || "Failed to create teachers.", "danger");
    } finally {
        window._setLoading(btn, btnText, spinner, false, "Upload & Create");
    }
}

// ── Bulk deactivate / activate ─────────────────────────────────────

async function submitBulkDeactivate() {
    const form = document.getElementById("bulkDeactivateForm");
    const alertEl = document.getElementById("bulkDeactivateAlert");
    const btn = document.getElementById("bulkDeactivateBtn");
    const btnText = document.getElementById("bulkDeactivateBtnText");
    const spinner = document.getElementById("bulkDeactivateSpinner");
    const batchYear = document.getElementById("bdBatchYear").value.trim();
    const branchCode = document.getElementById("bdBranchCode").value.trim().toUpperCase() || null;

    if (!form.checkValidity()) {
        form.classList.add("was-validated");
        return;
    }

    window._setLoading(btn, btnText, spinner, true, "Deactivating...");
    window._hideAlert(alertEl);

    try {
        const data = await window.apiFetch("/api/admin/users/bulk-deactivate", {
            method: "POST",
            body: JSON.stringify({ batch_year: batchYear, branch_code: branchCode }),
        });
        window._showAlert(alertEl, data.message, "success");
        form.reset();
        form.classList.remove("was-validated");
        await loadUsers(1);
    } catch (err) {
        window._showAlert(alertEl, err.detail || "Deactivation failed.", "danger");
    } finally {
        window._setLoading(btn, btnText, spinner, false, "Deactivate");
    }
}

async function submitBulkActivate() {
    const form = document.getElementById("bulkActivateForm");
    const alertEl = document.getElementById("bulkActivateAlert");
    const btn = document.getElementById("bulkActivateBtn");
    const btnText = document.getElementById("bulkActivateBtnText");
    const spinner = document.getElementById("bulkActivateSpinner");
    const batchYear = document.getElementById("baBatchYear").value.trim();
    const branchCode = document.getElementById("baBranchCode").value.trim().toUpperCase() || null;

    if (!form.checkValidity()) {
        form.classList.add("was-validated");
        return;
    }

    window._setLoading(btn, btnText, spinner, true, "Activating...");
    window._hideAlert(alertEl);

    try {
        const data = await window.apiFetch("/api/admin/users/bulk-activate", {
            method: "POST",
            body: JSON.stringify({ batch_year: batchYear, branch_code: branchCode }),
        });
        window._showAlert(alertEl, data.message, "success");
        form.reset();
        form.classList.remove("was-validated");
        await loadUsers(1);
    } catch (err) {
        window._showAlert(alertEl, err.detail || "Activation failed.", "danger");
    } finally {
        window._setLoading(btn, btnText, spinner, false, "Activate");
    }
}

// ── Single user actions ──────────────────────────────────────────

async function toggleActive(userId, email, willBeActive) {
    var verb = willBeActive ? 'activate' : 'deactivate';
    if (!confirm('Are you sure you want to ' + verb + ' ' + email + '?')) return;

    try {
        await window.apiFetch('/api/admin/users/' + userId + '/toggle-active', { method: 'POST' });
        await loadUsers(currentPage);
    } catch (err) {
        alert(err.detail || 'Failed to ' + verb + ' user.');
    }
}

function openForceReset(userId, email) {
    selectedUserId = userId;
    selectedUserEmail = email;
    document.getElementById("forceResetEmailDisplay").textContent = email;
    window._hideAlert(document.getElementById("forceResetAlert"));
    var modal = new bootstrap.Modal(document.getElementById("forceResetModal"));
    modal.show();
}

async function submitForceReset() {
    if (!selectedUserId) return;
    const alertEl = document.getElementById("forceResetAlert");
    const btn = document.getElementById("forceResetBtn");
    const btnText = document.getElementById("forceResetBtnText");
    const spinner = document.getElementById("forceResetSpinner");

    window._setLoading(btn, btnText, spinner, true, "Generating...");
    window._hideAlert(alertEl);

    try {
        const data = await window.apiFetch("/api/admin/users/" + selectedUserId + "/force-reset", { method: "POST" });
        const frModal = bootstrap.Modal.getInstance(document.getElementById("forceResetModal"));
        if (frModal) frModal.hide();

        setTimeout(() => _showTokenModal(data), 300);
        await loadUsers(currentPage);
    } catch (err) {
        window._showAlert(alertEl, err.detail || "Failed to generate token.", "danger");
    } finally {
        window._setLoading(btn, btnText, spinner, false, "Generate Token");
    }
}

function _showTokenModal(data) {
    const token = data.token;
    const expires = data.expires_at;
    const link = window.location.origin + "/static/pages/reset-password.html?token=" + token;

    document.getElementById("tokenDisplayValue").value = token;
    document.getElementById("tokenResetLink").value = link;
    document.getElementById("tokenExpiresAt").textContent = new Date(expires).toLocaleString();

    var modal = new bootstrap.Modal(document.getElementById("tokenDisplayModal"));
    modal.show();
}

function copyToken() {
    var val = document.getElementById("tokenDisplayValue").value;
    navigator.clipboard.writeText(val).then(function () {
        const icon = document.getElementById("copyTokenIcon");
        icon.className = "bi bi-clipboard-check text-success";
        setTimeout(() => icon.className = "bi bi-clipboard", 2000);
    });
}

function copyResetLink() {
    var val = document.getElementById("tokenResetLink").value;
    navigator.clipboard.writeText(val).then(function () {
        const icon = document.getElementById("copyLinkIcon");
        icon.className = "bi bi-clipboard-check text-success";
        setTimeout(() => icon.className = "bi bi-clipboard", 2000);
    });
}

// ── School Mapping helper ─────────────────────────────────────────

let _schoolsLoaded = false;
function toggleSchoolMapping(ev) {
    if (ev) ev.preventDefault();
    const container = document.getElementById("schoolMappingContainer");
    if (container.classList.contains("d-none")) {
        container.classList.remove("d-none");
        if (!_schoolsLoaded) {
            window.apiFetch('/api/admin/schools')
                .then(data => {
                    _schoolsLoaded = true;
                    let html = '<ul class="mb-0 ps-3">';
                    for (let s of data) {
                        let branches = s.branches.map(b => '<code>' + b.code + '</code>').join(', ');
                        let sCode = '<code>' + s.code + '</code>';
                        html += '<li>School ' + sCode + ' (' + window._esc(s.name) + '): Branches ' + (branches || 'None') + '</li>';
                    }
                    html += '</ul>';
                    container.innerHTML = html;
                })
                .catch(err => {
                    container.innerHTML = '<span class="text-danger">Failed to load mappings.</span>';
                });
        }
    } else {
        container.classList.add("d-none");
    }
}

// Global exposure for onclick handlers
window.loadUsers = loadUsers;
window.submitCreateUser = submitCreateUser;
window.submitBulkStudents = submitBulkStudents;
window.submitBulkTeachers = submitBulkTeachers;
window.submitBulkDeactivate = submitBulkDeactivate;
window.submitBulkActivate = submitBulkActivate;
window.toggleActive = toggleActive;
window.openForceReset = openForceReset;
window.submitForceReset = submitForceReset;
window.copyToken = copyToken;
window.copyResetLink = copyResetLink;
window.toggleSchoolMapping = toggleSchoolMapping;
