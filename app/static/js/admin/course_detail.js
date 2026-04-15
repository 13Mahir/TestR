/**
 * admin/course_detail.js
 * Extracted from admin/course_detail.html
 */

// ── State ─────────────────────────────────────────────────────────
var params = new URLSearchParams(window.location.search);
var courseId = parseInt(params.get("id"));
var studentsPage = 1;
var _teachersLoaded = false;

// ── Auth ready ────────────────────────────────────────────────────
(function () {
    var prev = window.__onAuthReady;
    window.__onAuthReady = async function (user) {
        if (typeof prev === "function") await prev(user);
        if (!courseId || isNaN(courseId)) {
            document.getElementById("courseInfoCard").innerHTML =
                '<div class="text-danger text-center py-3">' +
                '<i class="bi bi-exclamation-triangle me-2"></i>' +
                'No course ID in URL. Return to ' +
                '<a href="/static/pages/admin/courses.html">courses list</a>.</div>';
            return;
        }
        await loadCourseInfo();
        await loadStudents(1);
    };
})();

// ══════════════════════════════════════════════════════════════════
// COURSE INFO CARD
// ══════════════════════════════════════════════════════════════════

async function loadCourseInfo() {
    var card = document.getElementById("courseInfoCard");

    try {
        var c = await window.apiFetch("/api/admin/courses/" + courseId);
        if (!c) return;

        document.getElementById("coursePageTitle").textContent = c.course_code;
        document.title = c.course_code + " \u2014 EMS";

        var statusBadge = c.is_active ? "bg-success" : "bg-danger";
        var statusText = c.is_active ? "Active" : "Inactive";
        var toggleClass = c.is_active ? "btn-outline-danger" : "btn-outline-success";
        var toggleIcon = c.is_active ? "bi-pause-circle-fill" : "bi-play-circle-fill";
        var toggleLabel = c.is_active ? "Deactivate" : "Activate";
        var modeText = c.mode === "T" ? "Theory" : "Practical";
        var descHtml = c.description
            ? '<p class="small text-muted mb-0">' + window._esc(c.description) + '</p>'
            : '';

        card.innerHTML =
            '<div class="row g-3 align-items-start">' +
            '<div class="col-12 col-md-8">' +
            '<div class="d-flex align-items-center gap-2 mb-1">' +
            '<h5 class="mb-0 fw-semibold">' + window._esc(c.name) + '</h5>' +
            '<span class="badge ' + statusBadge + '">' + statusText + '</span>' +
            '</div>' +
            '<p class="text-muted small mb-2">' +
            '<code>' + window._esc(c.course_code) + '</code>' +
            ' &middot; Branch: <strong>' + window._esc(c.branch_code) + '</strong>' +
            ' &middot; Year: <strong>' + window._esc(c.year) + '</strong>' +
            ' &middot; Mode: <strong>' + modeText + '</strong>' +
            '</p>' +
            descHtml +
            '</div>' +
            '<div class="col-12 col-md-4">' +
            '<div class="d-flex gap-3 justify-content-md-end align-items-center flex-wrap">' +
            '<div class="text-center">' +
            '<div class="fw-semibold fs-5 text-primary">' + c.enrolled_students + '</div>' +
            '<div class="small text-muted">Students</div>' +
            '</div>' +
            '<div class="text-center">' +
            '<div class="fw-semibold fs-5 text-success">' + c.assigned_teachers + '</div>' +
            '<div class="small text-muted">Teachers</div>' +
            '</div>' +
            '<button class="btn btn-sm ' + toggleClass + '" id="toggleCourseBtn" ' +
            'onclick="toggleCourseStatus(' + c.is_active + ')">' +
            '<i class="bi ' + toggleIcon + ' me-1"></i>' + toggleLabel +
            '</button>' +
            '</div>' +
            '</div>' +
            '</div>';

        document.getElementById("studentCountBadge").textContent = c.enrolled_students;
        document.getElementById("teacherCountBadge").textContent = c.assigned_teachers;

    } catch (err) {
        card.innerHTML =
            '<div class="text-danger text-center py-3">' +
            '<i class="bi bi-exclamation-triangle me-2"></i>' +
            window._esc(err.detail || "Failed to load course info.") + '</div>';
    }
}

async function toggleCourseStatus(isActive) {
    var action = isActive ? "deactivate" : "activate";
    if (!confirm((isActive ? "Deactivate" : "Activate") + " this course?")) return;
    try {
        await window.apiFetch("/api/admin/courses/" + courseId + "/" + action, { method: "POST" });
        await loadCourseInfo();
    } catch (err) {
        alert(err.detail || "Failed to " + action + " course.");
    }
}

// ══════════════════════════════════════════════════════════════════
// STUDENTS TAB
// ══════════════════════════════════════════════════════════════════

async function loadStudents(page) {
    studentsPage = page;
    var url = "/api/admin/courses/" + courseId + "/enrollments?page=" + page + "&page_size=15";
    var tbody = document.getElementById("studentsTableBody");
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">' +
        '<div class="spinner-border spinner-border-sm me-2" role="status"></div>Loading&hellip;</td></tr>';

    try {
        var data = await window.apiFetch(url);
        if (!data) return;

        document.getElementById("studentCountBadge").textContent = data.total;

        if (data.items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">' +
                '<i class="bi bi-inbox d-block fs-4 mb-1 opacity-50"></i>' + window._esc("No students enrolled yet.") + '</td></tr>';
            _renderStudentPag(data);
            return;
        }

        tbody.innerHTML = data.items.map(function (s, i) {
            var rowNum = (page - 1) * 15 + i + 1;
            var statusBadge = s.is_active
                ? "bg-success-subtle text-success"
                : "bg-secondary-subtle text-secondary";
            return '<tr>' +
                '<td class="text-muted small">' + rowNum + '</td>' +
                '<td class="font-monospace small">' + window._esc(s.email) + '</td>' +
                '<td class="small">' + (window._esc(s.full_name) || '&mdash;') + '</td>' +
                '<td><span class="badge ' + statusBadge + '">' + (s.is_active ? "Active" : "Inactive") + '</span></td>' +
                '<td class="small text-muted text-nowrap">' + window._formatDate(s.enrolled_at) + '</td>' +
                '<td><button class="btn btn-outline-danger btn-sm" onclick="unenrollStudent(\'' + window._esc(s.email) + '\')" title="Unenroll student">' +
                '<i class="bi bi-person-x-fill"></i></button></td>' +
                '</tr>';
        }).join("");

        _renderStudentPag(data);

    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger py-4">' +
            '<i class="bi bi-exclamation-triangle me-2"></i>' + window._esc(err.detail || "Failed to load students.") + '</td></tr>';
    }
}

async function unenrollStudent(email) {
    if (!confirm("Unenroll " + email + " from this course?")) return;
    try {
        await window.apiFetch("/api/admin/courses/" + courseId + "/unenroll/single", {
            method: "POST",
            body: JSON.stringify({ student_email: email }),
        });
        await loadStudents(studentsPage);
        await loadCourseInfo();
    } catch (err) {
        alert(err.detail || "Failed to unenroll student.");
    }
}

function _renderStudentPag(data) {
    var info = document.getElementById("studentsPagInfo");
    var nav = document.getElementById("studentsPagControls");

    var start = (data.page - 1) * data.page_size + 1;
    var end = Math.min(data.page * data.page_size, data.total);
    info.textContent = data.total > 0
        ? "Showing " + start + "\u2013" + end + " of " + data.total
        : "";

    if (data.total_pages <= 1) { nav.innerHTML = ""; return; }

    var hasPrev = data.page > 1;
    var hasNext = data.page < data.total_pages;
    var html = '';

    html += '<li class="page-item ' + (!hasPrev ? "disabled" : "") + '">' +
        '<button class="page-link" onclick="loadStudents(' + (data.page - 1) + ')"' +
        (!hasPrev ? " disabled" : "") + '><i class="bi bi-chevron-left"></i></button></li>';

    for (var p = Math.max(1, data.page - 2); p <= Math.min(data.total_pages, data.page + 2); p++) {
        html += '<li class="page-item ' + (p === data.page ? "active" : "") + '">' +
            '<button class="page-link" onclick="loadStudents(' + p + ')">' + p + '</button></li>';
    }

    html += '<li class="page-item ' + (!hasNext ? "disabled" : "") + '">' +
        '<button class="page-link" onclick="loadStudents(' + (data.page + 1) + ')"' +
        (!hasNext ? " disabled" : "") + '><i class="bi bi-chevron-right"></i></button></li>';

    nav.innerHTML = html;
}

// ══════════════════════════════════════════════════════════════════
// TEACHERS TAB
// ══════════════════════════════════════════════════════════════════

async function loadTeachers() {
    _teachersLoaded = true;
    var tbody = document.getElementById("teachersTableBody");
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">' +
        '<div class="spinner-border spinner-border-sm me-2" role="status"></div>Loading&hellip;</td></tr>';

    try {
        var data = await window.apiFetch("/api/admin/courses/" + courseId + "/assignments");
        if (!data) return;

        document.getElementById("teacherCountBadge").textContent = data.total;
        document.getElementById("teachersTotalLabel").textContent =
            data.total + " teacher" + (data.total !== 1 ? "s" : "") + " assigned";

        if (data.items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">' +
                '<i class="bi bi-inbox d-block fs-4 mb-1 opacity-50"></i>' + window._esc("No teachers assigned yet.") + '</td></tr>';
            return;
        }

        tbody.innerHTML = data.items.map(function (t, i) {
            var statusBadge = t.is_active
                ? "bg-success-subtle text-success"
                : "bg-secondary-subtle text-secondary";
            return '<tr>' +
                '<td class="text-muted small">' + (i + 1) + '</td>' +
                '<td class="font-monospace small">' + window._esc(t.email) + '</td>' +
                '<td class="small">' + (window._esc(t.full_name) || '&mdash;') + '</td>' +
                '<td><span class="badge ' + statusBadge + '">' + (t.is_active ? "Active" : "Inactive") + '</span></td>' +
                '<td class="small text-muted text-nowrap">' + window._formatDate(t.assigned_at) + '</td>' +
                '<td><button class="btn btn-outline-danger btn-sm" onclick="unassignTeacher(\'' + window._esc(t.email) + '\')" title="Unassign teacher">' +
                '<i class="bi bi-person-x-fill"></i></button></td>' +
                '</tr>';
        }).join("");

    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger py-4">' +
            '<i class="bi bi-exclamation-triangle me-2"></i>' + window._esc(err.detail || "Failed to load teachers.") + '</td></tr>';
    }
}

async function unassignTeacher(email) {
    if (!confirm("Unassign " + email + " from this course?")) return;
    try {
        await window.apiFetch("/api/admin/courses/" + courseId + "/unassign/single", {
            method: "POST",
            body: JSON.stringify({ teacher_email: email }),
        });
        await loadTeachers();
        await loadCourseInfo();
    } catch (err) {
        alert(err.detail || "Failed to unassign teacher.");
    }
}

// ══════════════════════════════════════════════════════════════════
// MODAL SUBMISSIONS
// ══════════════════════════════════════════════════════════════════

async function submitEnrollSingle() {
    var form = document.getElementById("enrollSingleForm");
    var alertEl = document.getElementById("enrollSingleAlert");
    var btn = document.getElementById("enrollSingleBtn");
    var btnText = document.getElementById("enrollSingleBtnText");
    var spinner = document.getElementById("enrollSingleSpinner");

    if (!form.checkValidity()) { form.classList.add("was-validated"); return; }

    window._setLoading(btn, btnText, spinner, true, "Enrolling...");
    window._hideAlert(alertEl);

    try {
        var email = document.getElementById("esStudentEmail").value.trim().toLowerCase();
        await window.apiFetch("/api/admin/courses/" + courseId + "/enroll/single", {
            method: "POST",
            body: JSON.stringify({ student_email: email }),
        });
        window._showAlert(alertEl, "Student enrolled successfully.", "success");
        form.reset();
        form.classList.remove("was-validated");
        await loadStudents(studentsPage);
        await loadCourseInfo();
        setTimeout(function () {
            var modal = bootstrap.Modal.getInstance(document.getElementById("enrollSingleModal"));
            if (modal) modal.hide();
            window._hideAlert(alertEl);
        }, 1000);
    } catch (err) {
        window._showAlert(alertEl, err.detail || "Enrollment failed.", "danger");
    } finally {
        window._setLoading(btn, btnText, spinner, false, "Enroll");
    }
}

async function submitEnrollBulk() {
    var form = document.getElementById("enrollBulkForm");
    var alertEl = document.getElementById("enrollBulkAlert");
    var btn = document.getElementById("enrollBulkBtn");
    var btnText = document.getElementById("enrollBulkBtnText");
    var spinner = document.getElementById("enrollBulkSpinner");

    if (!form.checkValidity()) { form.classList.add("was-validated"); return; }

    window._setLoading(btn, btnText, spinner, true, "Enrolling...");
    window._hideAlert(alertEl);

    try {
        var data = await window.apiFetch("/api/admin/courses/" + courseId + "/enroll/bulk", {
            method: "POST",
            body: JSON.stringify({
                batch_year: document.getElementById("ebBatchYear").value.trim(),
                branch_code: document.getElementById("ebBranch").value.trim().toUpperCase(),
                roll_start: parseInt(document.getElementById("ebRollStart").value),
                roll_end: parseInt(document.getElementById("ebRollEnd").value),
            }),
        });
        window._showAlert(alertEl, data.message, data.failed > 0 ? "warning" : "success");
        form.reset();
        form.classList.remove("was-validated");
        await loadStudents(studentsPage);
        await loadCourseInfo();
    } catch (err) {
        window._showAlert(alertEl, err.detail || "Bulk enrollment failed.", "danger");
    } finally {
        window._setLoading(btn, btnText, spinner, false, "Bulk Enroll");
    }
}

async function submitAssignSingle() {
    var form = document.getElementById("assignSingleForm");
    var alertEl = document.getElementById("assignSingleAlert");
    var btn = document.getElementById("assignSingleBtn");
    var btnText = document.getElementById("assignSingleBtnText");
    var spinner = document.getElementById("assignSingleSpinner");

    if (!form.checkValidity()) { form.classList.add("was-validated"); return; }

    window._setLoading(btn, btnText, spinner, true, "Assigning...");
    window._hideAlert(alertEl);

    try {
        var email = document.getElementById("asTeacherEmail").value.trim().toLowerCase();
        await window.apiFetch("/api/admin/courses/" + courseId + "/assign/single", {
            method: "POST",
            body: JSON.stringify({ teacher_email: email }),
        });
        window._showAlert(alertEl, "Teacher assigned successfully.", "success");
        form.reset();
        form.classList.remove("was-validated");
        await loadTeachers();
        await loadCourseInfo();
        setTimeout(function () {
            var modal = bootstrap.Modal.getInstance(document.getElementById("assignSingleModal"));
            if (modal) modal.hide();
            window._hideAlert(alertEl);
        }, 1000);
    } catch (err) {
        window._showAlert(alertEl, err.detail || "Assignment failed.", "danger");
    } finally {
        window._setLoading(btn, btnText, spinner, false, "Assign");
    }
}

async function submitAssignCsv() {
    var form = document.getElementById("assignCsvForm");
    var alertEl = document.getElementById("assignCsvAlert");
    var btn = document.getElementById("assignCsvBtn");
    var btnText = document.getElementById("assignCsvBtnText");
    var spinner = document.getElementById("assignCsvSpinner");
    var fileInput = document.getElementById("acCsvFile");

    if (!form.checkValidity()) { form.classList.add("was-validated"); return; }
    if (!fileInput.files[0]) {
        window._showAlert(alertEl, "Please select a CSV file.", "danger");
        return;
    }

    window._setLoading(btn, btnText, spinner, true, "Uploading...");
    window._hideAlert(alertEl);

    try {
        var formData = new FormData();
        formData.append("csv_file", fileInput.files[0]);

        var data = await window.apiFetch(
            "/api/admin/courses/" + courseId + "/assign/bulk-csv",
            {
                method: "POST",
                body: formData,
                headers: {
                    "X-Requested-With": "XMLHttpRequest"
                }
            }
        );
        window._showAlert(alertEl, data.message, data.failed > 0 ? "warning" : "success");
        form.reset();
        form.classList.remove("was-validated");
        await loadTeachers();
        await loadCourseInfo();
    } catch (err) {
        window._showAlert(alertEl, err.detail || "CSV assignment failed.", "danger");
    } finally {
        window._setLoading(btn, btnText, spinner, false, "Upload & Assign");
    }
}

// Global exposure
window.loadTeachers = loadTeachers;
window.loadStudents = loadStudents;
window.submitEnrollSingle = submitEnrollSingle;
window.submitEnrollBulk = submitEnrollBulk;
window.submitAssignSingle = submitAssignSingle;
window.submitAssignCsv = submitAssignCsv;
window.toggleCourseStatus = toggleCourseStatus;
window.unenrollStudent = unenrollStudent;
window.unassignTeacher = unassignTeacher;
