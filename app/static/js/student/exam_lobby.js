/**
 * student/exam_lobby.js
 * Extracted from student/exam_lobby.html
 */

// ── State ─────────────────────────────────────────────────────────
var urlP = new URLSearchParams(window.location.search);
var examId = parseInt(urlP.get("exam_id")) || null;
var courseId = parseInt(urlP.get("course_id")) || null;
var pollTimer = null;

// ── Initialization ────────────────────────────────────────────────
(function () {
    var prev = window.__onAuthReady;
    window.__onAuthReady = async function (user) {
        if (typeof prev === "function") await prev(user);
        
        var singleArea = document.getElementById("singleLobbyArea");
        var courseArea = document.getElementById("courseExamsArea");
        var lobbyCard = document.getElementById("lobbyCard");

        if (examId) {
            if (singleArea) singleArea.classList.remove("d-none");
            await loadLobby();
            // Poll eligibility every 30s so page updates automatically when exam window opens
            pollTimer = setInterval(loadLobby, 30000);
        } else if (courseId) {
            if (courseArea) courseArea.classList.remove("d-none");
            await loadCourseExams();
        } else {
            if (singleArea) singleArea.classList.remove("d-none");
            if (lobbyCard) {
                lobbyCard.innerHTML = 
                    '<div class="text-center text-muted py-4">' +
                    '<i class="bi bi-exclamation-triangle fs-2 d-block mb-2"></i>' +
                    'No exam or course ID in URL. ' +
                    '<a href="/static/pages/student/courses.html" class="d-block mt-2">Back to courses</a>' +
                    '</div>';
            }
        }
    };
})();

// ══════════════════════════════════════════════════════════════════
// SINGLE EXAM LOBBY
// ══════════════════════════════════════════════════════════════════

async function loadLobby() {
    var card = document.getElementById("lobbyCard");
    if (!card) return;

    try {
        var e = await window.apiFetch("/api/student/exams/" + examId + "/lobby");
        if (!e) return;

        var start = new Date(e.start_time);
        var end = new Date(e.end_time);
        var now = new Date();
        var minsUntil = Math.max(0, Math.round((start - now) / 60000));
        var hasEnded = now > end;

        var statusClass = e.can_attempt ? 'alert-success' : (hasEnded ? 'alert-secondary' : 'alert-info');
        var statusIcon = e.can_attempt ? 'bi-check-circle-fill' : (hasEnded ? 'bi-lock-fill' : 'bi-clock-fill');
        var statusMsg = e.can_attempt ? "Exam window is open. You may begin now." : window._esc(e.reason || "Check back later.");
        var timerHtml = (!e.can_attempt && !hasEnded && minsUntil > 0) 
            ? '<div class="fw-bold">Starts in ' + minsUntil + ' minute' + (minsUntil !== 1 ? 's' : '') + '</div>' 
            : "";

        var negativeMarkingHtml = (e.negative_marking_factor > 0)
            ? '<div class="d-flex justify-content-between py-1">' +
              '<span class="text-muted">Negative Marking</span>' +
              '<span class="text-danger">-' + e.negative_marking_factor + '\u00D7 per wrong MCQ</span></div>'
            : "";

        var actionHtml = e.can_attempt
            ? '<div class="alert alert-warning small mb-2 py-2">' +
              '<i class="bi bi-camera-video-fill me-2"></i><strong>Proctoring is active.</strong> ' +
              'Your camera will be used and the exam must remain fullscreen. Tab switching is monitored.</div>' +
              '<button class="btn btn-primary w-100" id="startExamBtn" onclick="startExam(' + examId + ')">' +
              '<i class="bi bi-play-circle-fill me-2"></i>Start Exam</button>'
            : '<button class="btn btn-secondary w-100" disabled>' + (hasEnded ? 'Exam Closed' : 'Not Available Yet') + '</button>';

        card.innerHTML = 
            '<div class="text-center mb-3"><h4 class="fw-bold mb-1">' + window._esc(e.title) + '</h4>' +
            '<span class="badge bg-secondary-subtle text-secondary">' + window._esc(e.course_code) + '</span></div>' +
            '<div class="row g-3 mb-3">' +
            _statCol(e.duration_minutes, "Minutes") +
            _statCol(e.total_marks, "Total Marks") +
            _statCol(e.passing_marks, "Passing Marks") +
            _statCol(e.question_count, "Questions") +
            '</div>' +
            '<div class="mb-2 small">' +
            '<div class="d-flex justify-content-between border-bottom py-1"><span class="text-muted">Start</span><span>' + start.toLocaleString() + '</span></div>' +
            '<div class="d-flex justify-content-between border-bottom py-1"><span class="text-muted">End</span><span>' + end.toLocaleString() + '</span></div>' +
            negativeMarkingHtml +
            '</div>' +
            '<div class="alert ' + statusClass + ' d-flex align-items-center gap-2 mb-2">' +
            '<i class="bi ' + statusIcon + ' flex-shrink-0"></i><div>' + statusMsg + timerHtml + '</div></div>' +
            actionHtml;

    } catch (err) {
        card.innerHTML = 
            '<div class="text-center text-danger py-4 small">' +
            '<i class="bi bi-exclamation-triangle fs-2 d-block mb-2"></i>' +
            window._esc(err.detail || "Failed to load exam details.") + '</div>';
    }
}

function _statCol(val, label) {
    return '<div class="col-sm-6 col-md-3"><div class="bg-body-secondary rounded p-2 text-center">' +
           '<div class="fw-bold text-primary">' + val + '</div>' +
           '<div class="small text-muted">' + label + '</div></div></div>';
}

// ══════════════════════════════════════════════════════════════════
// START EXAM
// ══════════════════════════════════════════════════════════════════

async function startExam(eid) {
    var btn = document.getElementById("startExamBtn");
    if (btn) {
        btn.disabled = true;
        btn.textContent = "Starting...";
    }

    try {
        var data = await window.apiFetch("/api/student/attempts?exam_id=" + eid, { method: "POST" });
        if (!data) return;

        if (pollTimer) clearInterval(pollTimer);

        window.location.href = "/static/pages/student/exam_attempt.html" +
            "?attempt_id=" + data.attempt_id + "&exam_id=" + eid;

    } catch (err) {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-play-circle-fill me-2"></i>Start Exam';
        }
        var card = document.getElementById("lobbyCard");
        if (card) {
            card.insertAdjacentHTML("beforeend", 
                '<div class="alert alert-danger mt-2 small">' + window._esc(err.detail || "Failed to start exam.") + '</div>');
        }
    }
}

// ══════════════════════════════════════════════════════════════════
// COURSE EXAM LIST
// ══════════════════════════════════════════════════════════════════

async function loadCourseExams() {
    var list = document.getElementById("courseExamsList");
    if (!list) return;

    try {
        var data = await window.apiFetch("/api/student/exams");
        if (!data) return;

        var filtered = courseId ? data.items.filter(function(e) { return e.course_id === courseId; }) : data.items;

        if (!filtered.length) {
            list.innerHTML = 
                '<div class="col-12 text-center text-muted py-5">' +
                '<i class="bi bi-calendar-x fs-2 d-block mb-2"></i>' +
                'No upcoming exams for this course.</div>';
            return;
        }

        list.innerHTML = filtered.map(function(e) {
            var actionBtn = e.has_attempted
                ? '<span class="badge bg-secondary-subtle text-secondary">Already Attempted</span>'
                : '<a href="/static/pages/student/exam_lobby.html?exam_id=' + e.id + '" class="btn btn-primary btn-sm w-100">View Lobby \u2192</a>';

            return '<div class="col-12 col-md-6"><div class="content-card h-100">' +
                '<h6 class="fw-semibold mb-1">' + window._esc(e.title) + '</h6>' +
                '<div class="small text-muted mb-3">' + window._esc(e.course_code) + ' \u00B7 ' + e.duration_minutes + 'min \u00B7 ' + e.total_marks + ' marks</div>' +
                '<div class="small mb-3">' +
                '<div class="text-muted">Start: ' + new Date(e.start_time).toLocaleString() + '</div>' +
                '<div class="text-muted">End: ' + new Date(e.end_time).toLocaleString() + '</div></div>' +
                actionBtn + '</div></div>';
        }).join("");

    } catch (err) {
        list.innerHTML = 
            '<div class="col-12 text-danger text-center py-3 small">' +
            window._esc(err.detail || "Failed to load exams.") + '</div>';
    }
}

// Global exposure
window.startExam = startExam;
window.loadLobby = loadLobby;
window.loadCourseExams = loadCourseExams;
