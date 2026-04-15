/**
 * teacher/grading.js
 * Extracted from teacher/grading.html
 */

// ── State ─────────────────────────────────────────────────────────
var urlP = new URLSearchParams(window.location.search);
var examId = parseInt(urlP.get("exam_id")) || null;
var selectedAttemptId = null;

// ── Initialization ────────────────────────────────────────────────
(function initUI() {
    var backBtn = document.getElementById("backToGradebook");
    if (backBtn) {
        if (examId) {
            backBtn.href = "/static/pages/teacher/gradebook.html?exam_id=" + examId;
        } else {
            backBtn.href = "/static/pages/teacher/gradebook.html";
        }
    }
})();

// ── Auth ready ────────────────────────────────────────────────────
(function () {
    var prev = window.__onAuthReady;
    window.__onAuthReady = async function (user) {
        if (typeof prev === "function") await prev(user);
        await loadExamPicker();
        if (examId) {
            var picker = document.getElementById("examPicker");
            if (picker) picker.value = examId;
            var content = document.getElementById("gradingContent");
            if (content) content.classList.remove("d-none");
            await loadAttempts();
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
        
        var options = '<option value="">\u2014 Select an exam \u2014</option>';
        options += data.items.map(function(e) {
            return '<option value="' + e.id + '" ' + (e.id === examId ? 'selected' : '') + '>' +
                window._esc(e.course_code) + ' \u2014 ' + window._esc(e.title) + '</option>';
        }).join("");
        picker.innerHTML = options;
    } catch (_) { }
}

function loadFromPicker() {
    var picker = document.getElementById("examPicker");
    if (!picker) return;
    var val = picker.value;
    if (!val) return;
    
    examId = parseInt(val);
    history.replaceState(null, "", "?exam_id=" + examId);
    
    var backBtn = document.getElementById("backToGradebook");
    if (backBtn) backBtn.href = "/static/pages/teacher/gradebook.html?exam_id=" + examId;
    
    var content = document.getElementById("gradingContent");
    if (content) content.classList.remove("d-none");
    
    loadAttempts();
}

// ══════════════════════════════════════════════════════════════════
// ATTEMPT LIST
// ══════════════════════════════════════════════════════════════════

async function loadAttempts() {
    var container = document.getElementById("attemptList");
    if (!container) return;
    
    try {
        var data = await window.apiFetch("/api/teacher/exams/" + examId + "/attempts");
        if (!data) return;

        // Update page title
        try {
            var exam = await window.apiFetch("/api/teacher/exams/" + examId);
            if (exam) {
                var titleEl = document.getElementById("pageTitle");
                if (titleEl) titleEl.textContent = "Grading \u2014 " + exam.title;
                document.title = "Grading: " + exam.title + " \u2014 EMS";
            }
        } catch (_) { }

        if (!data.items.length) {
            container.innerHTML = '<p class="text-muted small text-center py-3">No students enrolled.</p>';
            return;
        }

        container.innerHTML = data.items.map(function(s) {
            var rowId = "row_" + (s.attempt_id || "na_" + s.student_id);
            var statusBadge = _statusBadge(s.status);
            var statusText = s.status.replace(/_/g, " ");
            
            var violationHtml = "";
            if (s.violation_count > 0) {
                violationHtml = '<span class="badge bg-danger-subtle text-danger small">' +
                    '<i class="bi bi-exclamation-triangle me-1"></i>' +
                    s.violation_count + ' violation' + (s.violation_count !== 1 ? 's' : '') +
                    '</span>';
            }
            
            var gradedHtml = "";
            if (s.is_fully_graded && s.attempt_id) {
                gradedHtml = '<span class="badge bg-success-subtle text-success small">' +
                    '<i class="bi bi-check-circle me-1"></i>Graded</span>';
            }
            
            var marksHtml = "";
            if (s.attempt_id) {
                marksHtml = '<div class="small text-muted mt-1">' +
                    'MCQ: ' + s.mcq_marks + ' + ' +
                    'Subj: ' + s.subjective_marks + ' = ' +
                    '<strong>' + s.total_marks_awarded + '</strong></div>';
            }

            // Using onclick with quoted strings for safety
            var selectCall = "selectAttempt(" + (s.attempt_id || 0) + ", '" + window._esc(s.student_email) + "', '" + window._esc(s.student_name) + "')";

            return '<div class="d-flex align-items-start gap-2 p-2 rounded mb-1 attempt-row" ' +
                'style="cursor:pointer" id="' + rowId + '" onclick="' + selectCall + '">' +
                '<div class="flex-fill min-w-0">' +
                '<div class="small fw-medium text-truncate">' + window._esc(s.student_email) + '</div>' +
                '<div class="d-flex gap-1 flex-wrap mt-1">' +
                '<span class="badge ' + statusBadge + ' small">' + statusText + '</span>' +
                violationHtml + gradedHtml +
                '</div>' + marksHtml +
                '</div></div>';
        }).join("");

    } catch (err) {
        container.innerHTML = '<p class="text-danger small">' + window._esc(err.detail || "Failed to load attempts.") + '</p>';
    }
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

// ══════════════════════════════════════════════════════════════════
// ANSWER DETAIL
// ══════════════════════════════════════════════════════════════════

async function selectAttempt(attemptId, email, name) {
    if (!attemptId) {
        var panel = document.getElementById("answerPanel");
        if (panel) {
            panel.innerHTML = 
                '<div class="text-center text-muted py-5">' +
                '<i class="bi bi-journal-x fs-2 d-block mb-2 opacity-50"></i>' +
                '<strong>' + window._esc(email) + '</strong> did not attempt this exam.</div>';
        }
        return;
    }

    selectedAttemptId = attemptId;

    // Highlight selected row
    document.querySelectorAll(".attempt-row").forEach(function(r) {
        r.classList.remove("bg-primary-subtle");
    });
    var row = document.getElementById("row_" + attemptId);
    if (row) row.classList.add("bg-primary-subtle");

    var mainPanel = document.getElementById("answerPanel");
    if (!mainPanel) return;
    
    mainPanel.innerHTML = '<div class="text-center py-3"><div class="spinner-border spinner-border-sm" role="status"></div></div>';

    try {
        var data = await window.apiFetch("/api/teacher/exams/" + examId + "/attempts/" + attemptId);
        if (!data) return;

        mainPanel.innerHTML = 
            '<div class="d-flex justify-content-between align-items-center mb-3">' +
            '<div><h6 class="fw-semibold mb-0">' + window._esc(email) + '</h6>' +
            '<small class="text-muted">' + window._esc(name) + '</small></div>' +
            '<span class="small text-muted">' + data.total + ' answer' + (data.total !== 1 ? 's' : '') + '</span>' +
            '</div>' +
            '<div id="answersContainer">' +
            data.items.map(function(a, i) { return _renderAnswer(a, i + 1); }).join("") +
            '</div>';

    } catch (err) {
        mainPanel.innerHTML = '<div class="text-danger small text-center py-3">' + window._esc(err.detail || "Failed to load answers.") + '</div>';
    }
}

function _renderAnswer(a, num) {
    var isMcq = a.question_type === "mcq";
    var answerHtml = "";

    if (isMcq) {
        var marksColor = a.is_correct ? 'text-success' : 'text-danger';
        var badgeColor = a.is_correct ? 'bg-success' : 'bg-danger';
        var selLabel = a.selected_label ? window._esc(a.selected_label) + ". " + window._esc(a.selected_text || '') : 'Not answered';

        answerHtml = 
            '<div class="d-flex gap-2 flex-wrap">' +
            '<div class="small">Selected: <span class="badge ' + badgeColor + ' ms-1">' + selLabel + '</span></div>' +
            '<div class="small">Correct: <span class="badge bg-success-subtle text-success ms-1">' + window._esc(a.correct_label || '\u2014') + '</span></div>' +
            '<div class="small">Marks: <strong class="' + marksColor + '">' + (a.marks_awarded !== null ? a.marks_awarded : '0') + ' / ' + a.marks_available + '</strong></div>' +
            '</div>';
    } else {
        var subText = a.subjective_text ? window._esc(a.subjective_text) : '<span class="text-muted fst-italic">No answer provided.</span>';
        var wordLimitHtml = a.word_limit ? '<div class="small text-muted mb-2">Word limit: ' + a.word_limit + '</div>' : "";
        var gradedMsg = a.is_graded ? '<div class="small text-success mt-1"><i class="bi bi-check-circle me-1"></i>Graded: ' + a.marks_awarded + ' / ' + a.marks_available + '</div>' : "";

        answerHtml = 
            '<div class="mb-2">' +
            '<div class="p-2 rounded border bg-body-secondary small mb-2" style="min-height:60px;white-space:pre-wrap">' + subText + '</div>' +
            wordLimitHtml +
            '<div class="d-flex align-items-end gap-2 flex-wrap">' +
            '<div><label class="form-label small fw-medium mb-1">Marks (0 \u2013 ' + a.marks_available + ')</label>' +
            '<input type="number" class="form-control form-control-sm" id="marks_' + a.answer_id + '" min="0" max="' + a.marks_available + '" step="0.5" value="' + (a.marks_awarded !== null ? a.marks_awarded : '') + '" placeholder="0" style="width:90px"/></div>' +
            '<div class="flex-fill"><label class="form-label small fw-medium mb-1">Feedback <span class="text-muted">(optional)</span></label>' +
            '<input type="text" class="form-control form-control-sm" id="feedback_' + a.answer_id + '" value="' + window._esc(a.teacher_feedback || '') + '" placeholder="Optional comment..."/></div>' +
            '<button class="btn btn-primary btn-sm" id="gradeBtn_' + a.answer_id + '" onclick="submitGrade(' + a.answer_id + ', ' + a.marks_available + ')">' + (a.is_graded ? 'Update' : 'Save') + ' Grade</button>' +
            '</div>' + gradedMsg + '</div>';
    }

    var borderClass = isMcq ? 'border-primary-subtle' : 'border-warning-subtle';
    var badgeType = isMcq ? 'bg-primary' : 'bg-warning text-dark';
    var qType = isMcq ? 'MCQ' : 'Subjective';

    return '<div class="border rounded p-3 mb-3 ' + borderClass + '">' +
        '<div class="d-flex align-items-center gap-2 mb-2">' +
        '<span class="badge ' + badgeType + ' small">Q' + num + ' \u00B7 ' + qType + '</span>' +
        '<span class="small text-muted">' + a.marks_available + ' mark' + (a.marks_available !== 1 ? 's' : '') + '</span>' +
        '</div>' +
        '<p class="small fw-medium mb-2">' + window._esc(a.question_text) + '</p>' +
        answerHtml + '</div>';
}

// ══════════════════════════════════════════════════════════════════
// GRADE SUBMISSION
// ══════════════════════════════════════════════════════════════════

async function submitGrade(answerId, maxMarks) {
    var marksInput = document.getElementById("marks_" + answerId);
    var feedbackInput = document.getElementById("feedback_" + answerId);
    var btn = document.getElementById("gradeBtn_" + answerId);

    if (!marksInput || !btn) return;

    var marks = parseFloat(marksInput.value);
    if (isNaN(marks) || marks < 0 || marks > maxMarks) {
        alert("Marks must be between 0 and " + maxMarks + ".");
        return;
    }

    var origText = btn.textContent;
    btn.disabled = true;
    btn.textContent = "Saving...";

    try {
        await window.apiFetch("/api/teacher/exams/" + examId + "/grade/" + selectedAttemptId + "/" + answerId, {
            method: "POST",
            body: JSON.stringify({
                marks_awarded: marks,
                feedback: feedbackInput ? feedbackInput.value.trim() || null : null,
            }),
        });
        
        btn.textContent = "\u2713 Saved";
        btn.classList.replace("btn-primary", "btn-success");
        
        setTimeout(function() {
            btn.disabled = false;
            btn.textContent = "Update Grade";
            btn.classList.replace("btn-success", "btn-primary");
        }, 2000);

        // Refresh attempt list to update graded status
        await loadAttempts();

    } catch (err) {
        alert(err.detail || "Failed to save grade.");
        btn.disabled = false;
        btn.textContent = origText;
    }
}

// ══════════════════════════════════════════════════════════════════
// UTILITIES
// ══════════════════════════════════════════════════════════════════

function _showPageAlert(msg, type) {
    var el = document.getElementById("pageAlert");
    if (!el) return;
    el.className = "alert alert-" + type;
    el.textContent = msg;
    el.classList.remove("d-none");
}

// Global exposure
window.loadFromPicker = loadFromPicker;
window.selectAttempt = selectAttempt;
window.submitGrade = submitGrade;
window.loadAttempts = loadAttempts;
window.loadExamPicker = loadExamPicker;
