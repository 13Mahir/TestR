/**
 * admin/courses.js
 * Extracted from admin/courses.html
 */

var currentPage = 1;

// ── Auth ready ────────────────────────────────────────────────────
(function () {
    var prev = window.__onAuthReady;
    window.__onAuthReady = async function (user) {
        if (typeof prev === "function") await prev(user);
        await loadCourses(1);
    };
})();

// ── Load courses ──────────────────────────────────────────────────

async function loadCourses(page) {
    currentPage = page;
    var active = document.getElementById("filterActive").value;
    var branch = document.getElementById("filterBranch").value.trim().toUpperCase();
    var search = document.getElementById("filterSearch").value.trim();

    var url = "/api/admin/courses?page=" + page + "&page_size=15";
    if (active) url += "&is_active=" + active;
    if (branch) url += "&branch_code=" + encodeURIComponent(branch);
    if (search) url += "&search=" + encodeURIComponent(search);

    var tbody = document.getElementById("coursesTableBody");
    tbody.innerHTML = '<tr><td colspan="10" class="text-center text-muted py-4">' +
        '<div class="spinner-border spinner-border-sm me-2" role="status"></div>Loading&hellip;</td></tr>';

    try {
        var data = await window.apiFetch(url);
        if (!data) return;

        document.getElementById("courseCountLabel").textContent =
            data.total + " course" + (data.total !== 1 ? "s" : "") + " found";

        if (data.items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="10" class="text-center text-muted py-4">' +
                '<i class="bi bi-inbox d-block fs-4 mb-1 opacity-50"></i>' + window._esc("No courses match the filters.") + '</td></tr>';
            _renderPagination(data);
            return;
        }

        tbody.innerHTML = data.items.map(function (c, i) {
            var rowNum = (page - 1) * 15 + i + 1;
            var modeBadge = c.mode === "T"
                ? "bg-primary-subtle text-primary"
                : "bg-info-subtle text-info";
            var statusBadge = c.is_active
                ? "bg-success-subtle text-success"
                : "bg-danger-subtle text-danger";
            var toggleBtn = c.is_active
                ? "btn-outline-danger"
                : "btn-outline-success";
            var toggleIcon = c.is_active
                ? "bi-pause-circle-fill"
                : "bi-play-circle-fill";
            var toggleTitle = c.is_active ? "Deactivate" : "Activate";

            return '<tr>' +
                '<td class="text-muted small">' + rowNum + '</td>' +
                '<td><code class="small">' + window._esc(c.course_code) + '</code></td>' +
                '<td class="small">' + window._esc(c.name) + '</td>' +
                '<td><span class="badge bg-secondary-subtle text-secondary">' + window._esc(c.branch_code) + '</span></td>' +
                '<td><span class="badge ' + modeBadge + '">' + (c.mode === "T" ? "Theory" : "Practical") + '</span></td>' +
                '<td class="small text-muted text-center">' + window._esc(c.year) + '</td>' +
                '<td><span class="badge ' + statusBadge + '">' + (c.is_active ? "Active" : "Inactive") + '</span></td>' +
                '<td class="text-center small"><i class="bi bi-people-fill text-primary me-1"></i>' + c.enrolled_students + '</td>' +
                '<td class="text-center small"><i class="bi bi-person-badge-fill text-success me-1"></i>' + c.assigned_teachers + '</td>' +
                '<td><div class="d-flex gap-1 flex-wrap">' +
                '<a href="/static/pages/admin/course_detail.html?id=' + c.id + '" class="btn btn-outline-primary btn-sm" title="View course detail">' +
                '<i class="bi bi-eye-fill"></i></a>' +
                '<button class="btn btn-sm ' + toggleBtn + '" onclick="toggleCourse(' + c.id + ',' + c.is_active + ',\'' + window._esc(c.course_code) + '\')" title="' + toggleTitle + '">' +
                '<i class="bi ' + toggleIcon + '"></i></button>' +
                '</div></td>' +
                '</tr>';
        }).join("");

        _renderPagination(data);

    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="10" class="text-center text-danger py-4">' +
            '<i class="bi bi-exclamation-triangle me-2"></i>' + window._esc(err.detail || "Failed to load courses.") + '</td></tr>';
    }
}

// ── Toggle activate/deactivate ────────────────────────────────────

async function toggleCourse(courseId, isActive, code) {
    var action = isActive ? "deactivate" : "activate";
    if (!window.confirm((isActive ? "Deactivate" : "Activate") + " course " + code + "?")) return;

    try {
        await window.apiFetch("/api/admin/courses/" + courseId + "/" + action, { method: "POST" });
        await loadCourses(currentPage);
    } catch (err) {
        alert(err.detail || "Failed to " + action + " course.");
    }
}

// ── Clear filters ─────────────────────────────────────────────────

function clearFilters() {
    document.getElementById("filterActive").value = "";
    document.getElementById("filterBranch").value = "";
    document.getElementById("filterSearch").value = "";
    loadCourses(1);
}

// ── Enter key triggers filter ─────────────────────────────────────

document.getElementById("filterSearch").addEventListener("keydown", function (e) {
    if (e.key === "Enter") loadCourses(1);
});

// ── Create course ─────────────────────────────────────────────────

async function submitCreateCourse() {
    var form = document.getElementById("createCourseForm");
    var alertEl = document.getElementById("createCourseAlert");
    var btn = document.getElementById("createCourseBtn");
    var btnText = document.getElementById("createCourseBtnText");
    var spinner = document.getElementById("createCourseSpinner");

    if (!form.checkValidity()) { form.classList.add("was-validated"); return; }

    window._setLoading(btn, btnText, spinner, true, "Creating...");
    window._hideAlert(alertEl);

    try {
        await window.apiFetch("/api/admin/courses", {
            method: "POST",
            body: JSON.stringify({
                course_code: document.getElementById("ccCode").value.trim().toUpperCase(),
                name: document.getElementById("ccName").value.trim(),
                description: document.getElementById("ccDescription").value.trim() || null,
                branch_code: document.getElementById("ccBranch").value.trim().toUpperCase(),
                year: document.getElementById("ccYear").value.trim(),
                mode: document.getElementById("ccMode").value,
            }),
        });

        window._showAlert(alertEl, "Course created successfully.", "success");
        form.reset();
        form.classList.remove("was-validated");
        await loadCourses(1);

        setTimeout(function () {
            var modal = bootstrap.Modal.getInstance(document.getElementById("createCourseModal"));
            if (modal) modal.hide();
            window._hideAlert(alertEl);
        }, 1200);

    } catch (err) {
        window._showAlert(alertEl, err.detail || "Failed to create course.", "danger");
    } finally {
        window._setLoading(btn, btnText, spinner, false, "Create Course");
    }
}

// ── Pagination ────────────────────────────────────────────────────

function _renderPagination(data) {
    var info = document.getElementById("coursePaginationInfo");
    var nav = document.getElementById("coursePaginationControls");

    var start = (data.page - 1) * data.page_size + 1;
    var end = Math.min(data.page * data.page_size, data.total);
    info.textContent = data.total > 0
        ? "Showing " + start + "\u2013" + end + " of " + data.total
        : "";

    if (data.total_pages <= 1) { nav.innerHTML = ""; return; }

    var html = "";
    html += '<li class="page-item ' + (!data.has_prev ? "disabled" : "") + '">' +
        '<button class="page-link" onclick="loadCourses(' + (data.page - 1) + ')"' +
        (!data.has_prev ? " disabled" : "") + '><i class="bi bi-chevron-left"></i></button></li>';

    var sp = Math.max(1, data.page - 2);
    var ep = Math.min(data.total_pages, data.page + 2);

    if (sp > 1) {
        html += '<li class="page-item"><button class="page-link" onclick="loadCourses(1)">1</button></li>';
        if (sp > 2) html += '<li class="page-item disabled"><span class="page-link">&hellip;</span></li>';
    }

    for (var p = sp; p <= ep; p++) {
        html += '<li class="page-item ' + (p === data.page ? "active" : "") + '">' +
            '<button class="page-link" onclick="loadCourses(' + p + ')">' + p + '</button></li>';
    }

    if (ep < data.total_pages) {
        if (ep < data.total_pages - 1) html += '<li class="page-item disabled"><span class="page-link">&hellip;</span></li>';
        html += '<li class="page-item"><button class="page-link" onclick="loadCourses(' + data.total_pages + ')">' + data.total_pages + '</button></li>';
    }

    html += '<li class="page-item ' + (!data.has_next ? "disabled" : "") + '">' +
        '<button class="page-link" onclick="loadCourses(' + (data.page + 1) + ')"' +
        (!data.has_next ? " disabled" : "") + '><i class="bi bi-chevron-right"></i></button></li>';

    nav.innerHTML = html;
}

// Global exposure for onclick handlers
window.loadCourses = loadCourses;
window.clearFilters = clearFilters;
window.submitCreateCourse = submitCreateCourse;
window.toggleCourse = toggleCourse;
