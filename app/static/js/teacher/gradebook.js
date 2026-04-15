/**
 * teacher/gradebook.js
 * Extracted from teacher/gradebook.html
 */

// ── State ─────────────────────────────────────────────────────────
var urlP = new URLSearchParams(window.location.search);
var examId = parseInt(urlP.get("exam_id")) || null;

// ── Auth ready ────────────────────────────────────────────────────
(function () {
    var prev = window.__onAuthReady;
    window.__onAuthReady = async function (user) {
        if (typeof prev === "function") await prev(user);
        await loadExamPicker();
        if (examId) {
            var picker = document.getElementById("examPicker");
            if (picker) picker.value = examId;
            await loadGradeBook(examId);
        }
    };
})();

// ══════════════════════════════════════════════════════════════════
// EXAM PICKER
// ══════════════════════════════════════════════════════════════════

async function loadExamPicker() {
    try {
        var data = await window.apiFetch("/api/teacher/exams?page_size=100");
        if (!data) return;

        var picker = document.getElementById("examPicker");
        if (!picker) return;

        var optionsHtml = '<option value="">\u2014 Select an exam \u2014</option>';
        optionsHtml += data.items.map(function(e) {
            return '<option value="' + e.id + '" ' + (e.id === examId ? 'selected' : '') + '>' +
                window._esc(e.course_code) + ' \u2014 ' + window._esc(e.title) + 
                (e.results_published ? ' \u2713' : '') + '</option>';
        }).join("");
        picker.innerHTML = optionsHtml;
    } catch (_) { }
}

function loadFromPicker() {
    var picker = document.getElementById("examPicker");
    if (!picker) return;
    var val = picker.value;
    if (!val) return;
    examId = parseInt(val);
    history.replaceState(null, "", "?exam_id=" + examId);
    loadGradeBook(examId);
}

// ══════════════════════════════════════════════════════════════════
// GRADE BOOK LOADING
// ══════════════════════════════════════════════════════════════════

async function loadGradeBook(eid) {
    var content = document.getElementById("gradeBookContent");
    if (content) content.classList.remove("d-none");
    
    var gradeLink = document.getElementById("gradeLink");
    if (gradeLink) gradeLink.href = "/static/pages/teacher/grading.html?exam_id=" + eid;

    await loadExamInfo(eid);
    await loadTable(eid);
}

async function loadExamInfo(eid) {
    var card = document.getElementById("examInfoCard");
    if (!card) return;

    try {
        var gb = await window.apiFetch("/api/teacher/exams/" + eid + "/gradebook");
        if (!gb) return;

        var titleEl = document.getElementById("pageTitle");
        if (titleEl) titleEl.textContent = "Grade Book \u2014 " + gb.exam_title;
        document.title = "Grade Book: " + gb.exam_title + " \u2014 EMS";

        var actionBtnsHtml = "";
        if (!gb.is_published) {
            actionBtnsHtml = 
                '<a href="/static/pages/teacher/exam_questions.html?exam_id=' + eid + '" class="btn btn-outline-primary btn-sm">' +
                '<i class="bi bi-question-circle me-1"></i>Questions</a> ' +
                '<a href="/static/pages/teacher/exam_create.html?exam_id=' + eid + '" class="btn btn-outline-secondary btn-sm">' +
                '<i class="bi bi-gear-fill me-1"></i>Settings</a>';
        }

        var publishBadgeHtml = '<span class="badge ' + (gb.results_published ? 'bg-success' : 'bg-warning text-dark') + '">' +
            (gb.results_published ? '\u2713 Results Published' : 'Results Not Published') + '</span>';

        var publishBtnHtml = "";
        if (!gb.results_published && gb.is_published) {
            publishBtnHtml = '<button class="btn btn-success btn-sm" id="publishResultsBtn" onclick="publishResults(' + eid + ')">' +
                '<i class="bi bi-send-check me-1"></i>Publish Results</button>';
        }

        card.innerHTML = 
            '<div class="d-flex justify-content-between align-items-center flex-wrap gap-3">' +
            '<div><h6 class="fw-semibold mb-1">' + window._esc(gb.exam_title) + '</h6>' +
            '<div class="small text-muted">' +
            'Course: <strong>' + window._esc(gb.course_code) + '</strong>' +
            ' \u00B7 Total: <strong>' + gb.total_marks + '</strong>' +
            ' \u00B7 Passing: <strong>' + gb.passing_marks + '</strong></div></div>' +
            '<div class="d-flex align-items-center gap-2">' + actionBtnsHtml + publishBadgeHtml + publishBtnHtml + '</div></div>';

        // Stat cards
        var statsHtml = [
            _statCard("bi-people-fill text-primary", gb.attempted_count, "Attempted", "bg-primary-subtle"),
            _statCard("bi-person-dash text-secondary", gb.not_attempted_count, "Not Attempted", "bg-secondary-subtle"),
            _statCard("bi-check-circle-fill text-success", gb.pass_count, "Passed", "bg-success-subtle"),
            _statCard("bi-x-circle-fill text-danger", gb.fail_count, "Failed", "bg-danger-subtle")
        ].join("");
        var statCardsEl = document.getElementById("statCards");
        if (statCardsEl) statCardsEl.innerHTML = statsHtml;

    } catch (err) {
        card.innerHTML = '<div class="text-danger small">' + window._esc(err.detail || "Failed to load exam info.") + '</div>';
    }
}

function _statCard(iconCls, value, label, bgCls) {
    return '<div class="col-6 col-md-3">' +
        '<div class="content-card ' + bgCls + ' text-center py-3">' +
        '<i class="bi ' + iconCls + ' fs-4 d-block mb-1"></i>' +
        '<div class="fw-bold fs-5">' + value + '</div>' +
        '<div class="small text-muted">' + label + '</div>' +
        '</div></div>';
}

async function loadTable(eid) {
    var tbody = document.getElementById("gradeTableBody");
    if (!tbody) return;
    
    try {
        var gb = await window.apiFetch("/api/teacher/exams/" + eid + "/gradebook");
        if (!gb) return;

        if (!gb.entries.length) {
            tbody.innerHTML = '<tr><td colspan="11" class="text-center text-muted py-4">No enrolled students.</td></tr>';
            return;
        }

        tbody.innerHTML = gb.entries.map(function(e, i) {
            var passBadgeClass = e.is_pass === true ? 'bg-success' : (e.is_pass === false ? 'bg-danger' : 'bg-secondary');
            var passText = e.is_pass === true ? 'PASS' : (e.is_pass === false ? 'FAIL' : '\u2014');
            var negMarks = e.negative_marks_deducted > 0 ? '-' + e.negative_marks_deducted : '\u2014';

            return '<tr>' +
                '<td class="text-muted small">' + (i + 1) + '</td>' +
                '<td class="small font-monospace">' + window._esc(e.student_email) + '</td>' +
                '<td class="small">' + (window._esc(e.student_name) || "\u2014") + '</td>' +
                '<td><span class="badge ' + _statusBadge(e.status) + ' small">' + e.status.replace(/_/g, " ") + '</span></td>' +
                '<td class="small text-center">' + e.mcq_marks_awarded + '</td>' +
                '<td class="small text-center">' + e.subjective_marks_awarded + '</td>' +
                '<td class="small text-center text-danger">' + negMarks + '</td>' +
                '<td class="small text-center fw-semibold">' + e.total_marks_awarded + '</td>' +
                '<td class="small text-center text-muted">' + e.total_marks_available + '</td>' +
                '<td class="small text-center">' + e.percentage + '%</td>' +
                '<td><span class="badge small ' + passBadgeClass + '">' + passText + '</span></td>' +
                '</tr>';
        }).join("");

    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="11" class="text-center text-danger py-3">' + window._esc(err.detail || "Failed to load grade book.") + '</td></tr>';
    }
}

// ══════════════════════════════════════════════════════════════════
// ACTIONS
// ══════════════════════════════════════════════════════════════════

async function publishResults(eid) {
    if (!confirm("Publish results? Students will be notified and will see their scores immediately.")) return;

    var btn = document.getElementById("publishResultsBtn");
    if (btn) { btn.disabled = true; btn.textContent = "Publishing..."; }

    try {
        var data = await window.apiFetch("/api/teacher/exams/" + eid + "/publish-results", { method: "POST" });
        _showPageAlert(data.message + " " + (data.notified_students || 0) + " student(s) notified.", "success");
        await loadExamInfo(eid);
        await loadTable(eid);
    } catch (err) {
        _showPageAlert(err.detail || "Failed to publish results.", "danger");
        if (btn) { btn.disabled = false; btn.textContent = "Publish Results"; }
    }
}

async function exportCsv() {
    if (!examId) return;
    try {
        var res = await window.apiFetch("/api/teacher/exams/" + examId + "/gradebook/export/csv");
        if (!res) return;
        var blob = await res.blob();
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = "gradebook_" + examId + ".csv";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    } catch (err) {
        alert(err.detail || "CSV export failed.");
    }
}

async function exportPdf() {
    if (!examId) return;
    try {
        var res = await window.apiFetch("/api/teacher/exams/" + examId + "/gradebook/export/pdf");
        if (!res) return;
        var blob = await res.blob();
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = "gradebook_" + examId + ".pdf";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    } catch (err) {
        alert(err.detail || "PDF export failed.");
    }
}

// ══════════════════════════════════════════════════════════════════
// UTILITIES
// ══════════════════════════════════════════════════════════════════

function _statusBadge(status) {
    var map = {
        submitted: "bg-success-subtle text-success",
        auto_submitted: "bg-warning-subtle text-warning",
        in_progress: "bg-info-subtle text-info",
        not_attempted: "bg-secondary-subtle text-secondary",
    };
    return map[status] || "bg-secondary-subtle text-secondary";
}

function _showPageAlert(msg, type) {
    var el = document.getElementById("pageAlert");
    if (!el) return;
    el.className = "alert alert-" + type;
    el.textContent = msg;
    el.classList.remove("d-none");
}

// Global exposure
window.loadFromPicker = loadFromPicker;
window.publishResults = publishResults;
window.exportCsv = exportCsv;
window.exportPdf = exportPdf;
window.loadGradeBook = loadGradeBook;
window.loadExamPicker = loadExamPicker;
