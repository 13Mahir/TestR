/**
 * student/courses.js
 * Extracted from student/courses.html
 */

// ── Auth ready ────────────────────────────────────────────────────
(function () {
    var prev = window.__onAuthReady;
    window.__onAuthReady = async function (user) {
        if (typeof prev === "function") await prev(user);
        await loadCourses();
    };
})();

// ══════════════════════════════════════════════════════════════════
// DATA LOADING
// ══════════════════════════════════════════════════════════════════

async function loadCourses() {
    var grid = document.getElementById("coursesGrid");
    if (!grid) return;

    try {
        var data = await window.apiFetch("/api/student/courses");
        if (!data || !data.items.length) {
            grid.innerHTML = 
                '<div class="col-12 text-center text-muted py-5">' +
                '<i class="bi bi-journal-x fs-1 d-block mb-2 opacity-50"></i>' +
                '<p>You are not enrolled in any courses yet.</p>' +
                '<p class="small">Contact your administrator.</p></div>';
            return;
        }

        grid.innerHTML = data.items.map(function(c) {
            var modeClass = c.mode === 'T' ? 'bg-primary-subtle text-primary' : 'bg-info-subtle text-info';
            var modeText = c.mode === 'T' ? 'Theory' : 'Practical';
            var activeClass = c.is_active ? 'bg-success-subtle text-success' : 'bg-danger-subtle text-danger';
            var activeText = c.is_active ? 'Active' : 'Inactive';
            
            var desc = c.description ? window._esc(c.description.substring(0, 100)) + (c.description.length > 100 ? '\u2026' : '') : 'No description.';

            return '<div class="col-12 col-md-6 col-lg-4">' +
                '<div class="content-card h-100">' +
                '<div class="d-flex justify-content-between align-items-start mb-2">' +
                '<div class="d-flex gap-1 flex-wrap">' +
                '<span class="badge bg-secondary-subtle text-secondary small">' + window._esc(c.course_code) + '</span> ' +
                '<span class="badge ' + modeClass + ' small">' + modeText + '</span></div>' +
                '<span class="badge ' + activeClass + ' small">' + activeText + '</span></div>' +
                '<h5 class="fw-semibold mb-1">' + window._esc(c.name) + '</h5>' +
                '<p class="small text-muted mb-3">' + desc + '</p>' +
                '<div class="row g-2 mb-3">' +
                '<div class="col-6"><div class="bg-primary-subtle rounded p-2 text-center">' +
                '<div class="fw-bold text-primary">' + c.upcoming_exams + '</div>' +
                '<div class="small text-muted">Upcoming</div></div></div>' +
                '<div class="col-6"><div class="bg-success-subtle rounded p-2 text-center">' +
                '<div class="fw-bold text-success">' + c.completed_exams + '</div>' +
                '<div class="small text-muted">Completed</div></div></div></div>' +
                '<div class="small text-muted mb-3"><i class="bi bi-calendar3 me-1"></i>' +
                'Enrolled ' + _formatDate(c.enrolled_at) + ' \u00B7 Batch \'' + window._esc(c.year) + '</div>' +
                '<a href="/static/pages/student/exam_lobby.html?course_id=' + c.id + '" class="btn btn-outline-primary btn-sm w-100">' +
                '<i class="bi bi-list-check me-1"></i>View Exams</a></div></div>';
        }).join("");

    } catch (err) {
        grid.innerHTML = '<div class="col-12 text-center text-danger py-4">' +
            '<i class="bi bi-exclamation-triangle me-2"></i>' +
            window._esc(err.detail || "Failed to load courses.") + '</div>';
    }
}

// ══════════════════════════════════════════════════════════════════
// UTILITIES
// ══════════════════════════════════════════════════════════════════

function _formatDate(iso) {
    if (!iso) return "\u2014";
    return new Date(iso).toLocaleDateString(undefined, {
        year: "numeric", month: "short", day: "numeric"
    });
}

// Global exposure
window.loadCourses = loadCourses;
