/**
 * teacher/proctor_report.js
 * Extracted from teacher/proctor_report.html
 */

// ── State ─────────────────────────────────────────────────────────
var urlP = new URLSearchParams(window.location.search);
var examId = parseInt(urlP.get("exam_id")) || null;

// ── Initialization ────────────────────────────────────────────────
(function () {
    var prev = window.__onAuthReady;
    window.__onAuthReady = async function (user) {
        if (typeof prev === "function") await prev(user);
        await loadExamPicker();
        if (examId) {
            var picker = document.getElementById("examPicker");
            if (picker) picker.value = examId;
            await loadReport(examId);
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
                window._esc(e.course_code) + ' \u2014 ' + window._esc(e.title) + '</option>';
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
    loadReport(examId);
}

// ══════════════════════════════════════════════════════════════════
// REPORT LOADING
// ══════════════════════════════════════════════════════════════════

async function loadReport(eid) {
    var content = document.getElementById("reportContent");
    if (content) content.classList.remove("d-none");
    await loadTable(eid);
}

async function loadTable(eid) {
    var tbody = document.getElementById("reportTableBody");
    if (!tbody) return;

    try {
        var data = await window.apiFetch("/api/teacher/exams/" + eid + "/attempts");
        if (!data) return;

        if (!data.items.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">No enrolled students.</td></tr>';
            return;
        }

        data.items.sort(function(a, b) {
            return (b.violation_count || 0) - (a.violation_count || 0);
        });

        tbody.innerHTML = data.items.map(function(e, i) {
            var vSummary = _formatViolations(e.violation_summary);
            var violationHtml = "\u2014";
            if (e.violation_count > 0) {
                violationHtml = '<span style="cursor:help; border-bottom:1px dotted;" data-bs-toggle="tooltip" data-bs-placement="top" title="' + window._esc(vSummary) + '">' +
                    e.violation_count + '</span>';
            }

            var actionHtml = "\u2014";
            if (e.attempt_id) {
                actionHtml = '<button class="btn btn-outline-primary btn-sm px-2 py-0" style="font-size:0.75rem" onclick="showDetails(' + e.attempt_id + ', \'' + window._esc(e.student_name || e.student_email) + '\')">' +
                    '<i class="bi bi-info-circle me-1"></i>Details</button>';
            }

            return '<tr>' +
                '<td class="text-muted small">' + (i + 1) + '</td>' +
                '<td class="small font-monospace">' + window._esc(e.student_email) + '</td>' +
                '<td class="small">' + (window._esc(e.student_name) || "\u2014") + '</td>' +
                '<td><span class="badge ' + _statusBadge(e.status) + ' small">' + e.status.replace(/_/g, " ") + '</span></td>' +
                '<td class="small text-center fw-bold text-danger">' + violationHtml + '</td>' +
                '<td>' + actionHtml + '</td>' +
                '</tr>';
        }).join("");

        // Initialize Bootstrap tooltips
        if (typeof bootstrap !== "undefined" && bootstrap.Tooltip) {
            var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            tooltipTriggerList.map(function (tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });
        }

    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger py-3">' + window._esc(err.detail || "Failed to load report.") + '</td></tr>';
    }
}

async function showDetails(attemptId, studentName) {
    var titleEl = document.getElementById("detailStudentName");
    if (titleEl) titleEl.textContent = studentName;
    
    var timelineContainer = document.getElementById("timelineContainer");
    var snapshotContainer = document.getElementById("snapshotContainer");
    
    if (timelineContainer) {
        timelineContainer.innerHTML = '<div class="text-center py-4"><div class="spinner-border spinner-border-sm text-primary" role="status"></div><div class="small text-muted mt-2">Loading timeline...</div></div>';
    }
    if (snapshotContainer) {
        snapshotContainer.innerHTML = '<div class="text-center py-4 w-100"><div class="spinner-border spinner-border-sm text-primary" role="status"></div><div class="small text-muted mt-2">Loading snapshots...</div></div>';
    }

    if (typeof bootstrap !== "undefined" && bootstrap.Modal) {
        var modalEl = document.getElementById('detailModal');
        if (modalEl) {
            var modal = new bootstrap.Modal(modalEl);
            modal.show();
        }
    }

    try {
        // Fetch Violations
        var vData = await window.apiFetch("/api/teacher/attempts/" + attemptId + "/violations");
        if (vData && vData.items && timelineContainer) {
            if (vData.items.length === 0) {
                timelineContainer.innerHTML = '<div class="text-muted small">No violations recorded.</div>';
            } else {
                timelineContainer.innerHTML = vData.items.map(function(v) {
                    var type = v.type || v.violation_type;
                    var typeLabel = type ? type.replace(/_/g, ' ') : "Violation";
                    var isSerious = ['camera_unavailable', 'fullscreen_exit'].includes(type);
                    var borderClass = isSerious ? 'border-danger' : 'border-warning';
                    
                    return '<div class="mb-3 ps-3 border-start border-3 ' + borderClass + '">' +
                        '<div class="fw-bold small text-uppercase text-muted" style="font-size:0.65rem">' + typeLabel + '</div>' +
                        '<div class="small fw-medium">' + window._esc(v.details || "No payload details") + '</div>' +
                        '<div class="text-muted" style="font-size:0.65rem">' + new Date(v.occurred_at).toLocaleString() + '</div>' +
                        '</div>';
                }).join("");
            }
        }

        // Fetch Snapshots
        var sData = await window.apiFetch("/api/teacher/attempts/" + attemptId + "/snapshots");
        if (sData && sData.items && snapshotContainer) {
            if (sData.items.length === 0) {
                snapshotContainer.innerHTML = '<div class="text-muted small w-100">No snapshots available.</div>';
            } else {
                snapshotContainer.innerHTML = sData.items.map(function(s) {
                    return '<div class="text-center">' +
                        '<img src="' + s.url + '" class="rounded border mb-1" ' +
                        'style="width:180px; height:135px; object-fit:cover; cursor:pointer;" ' +
                        'onclick="window.open(\'' + s.url + '\')" ' +
                        'title="Captured at ' + new Date(s.captured_at).toLocaleString() + '"/>' +
                        '<div class="text-muted" style="font-size:0.6rem">' + new Date(s.captured_at).toLocaleTimeString() + '</div>' +
                        '</div>';
                }).join("");
            }
        }
    } catch (err) {
        console.error(err);
        if (timelineContainer) timelineContainer.innerHTML = '<div class="text-danger small">Error loading details.</div>';
    }
}

// ══════════════════════════════════════════════════════════════════
// UTILITIES
// ══════════════════════════════════════════════════════════════════

function _formatViolations(summary) {
    if (!summary || Object.keys(summary).length === 0) return "";
    return Object.entries(summary).map(function(pair) {
        var type = pair[0];
        var count = pair[1];
        var label = type.replace(/_/g, ' ').replace(/\b\w/g, function(c) { return c.toUpperCase(); });
        return label + ": " + count;
    }).join(", ");
}

function _statusBadge(status) {
    var map = {
        submitted: "bg-success-subtle text-success",
        auto_submitted: "bg-warning-subtle text-warning",
        in_progress: "bg-info-subtle text-info",
        not_attempted: "bg-secondary-subtle text-secondary",
    };
    return map[status] || "bg-secondary-subtle text-secondary";
}

// Global exposure
window.loadFromPicker = loadFromPicker;
window.showDetails = showDetails;
window.loadReport = loadReport;
window.loadExamPicker = loadExamPicker;
