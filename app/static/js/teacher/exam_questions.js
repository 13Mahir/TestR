/**
 * teacher/exam_questions.js
 * Extracted from teacher/exam_questions.html
 */

// ── State ─────────────────────────────────────────────────────────
var urlP = new URLSearchParams(window.location.search);
var examId = parseInt(urlP.get("exam_id"));
var examData = null;

// ── Initialization ────────────────────────────────────────────────
(function init() {
    // MCQ Modal Setup
    var mcqModalEl = document.getElementById("mcqModal");
    if (mcqModalEl) {
        mcqModalEl.addEventListener("show.bs.modal", function () {
            var container = document.getElementById("mcqOptions");
            if (!container) return;
            var labels = ["A", "B", "C", "D"];
            container.innerHTML = labels.map(function(label) {
                return '<div class="input-group">' +
                    '<div class="input-group-text">' +
                    '<input type="radio" name="correctOption" value="' + label + '" id="opt' + label + '" ' +
                    'class="form-check-input mt-0" ' + (label === "A" ? "checked" : "") + '/>' +
                    '</div>' +
                    '<span class="input-group-text fw-bold">' + label + '</span>' +
                    '<input type="text" class="form-control" id="optText' + label + '" ' +
                    'placeholder="Option ' + label + ' text" required/>' +
                    '</div>';
            }).join("");
        });
    }
})();

// ── Auth ready ────────────────────────────────────────────────────
(function () {
    var prev = window.__onAuthReady;
    window.__onAuthReady = async function (user) {
        if (typeof prev === "function") await prev(user);
        if (!examId || isNaN(examId)) {
            _showPageAlert("No exam ID in URL.", "danger");
            return;
        }
        await loadExamInfo();
        await loadQuestions();
    };
})();

// ══════════════════════════════════════════════════════════════════
// DATA LOADING
// ══════════════════════════════════════════════════════════════════

async function loadExamInfo() {
    try {
        examData = await window.apiFetch("/api/teacher/exams/" + examId);
        if (!examData) return;

        document.getElementById("examTitle").textContent = examData.title;
        document.title = examData.title + " \u2014 EMS";

        var infoBar = document.getElementById("examInfoBar");
        infoBar.innerHTML = 
            '<div class="row g-3 align-items-center">' +
            '<div class="col-12 col-md-8">' +
            '<div class="d-flex align-items-center gap-2 mb-1">' +
            '<code class="small">' + window._esc(examData.course_code) + '</code>' +
            '<span class="badge ' + (examData.is_published ? 'bg-success' : 'bg-warning text-dark') + '">' +
            (examData.is_published ? 'Published' : 'Draft') +
            '</span>' +
            '</div>' +
            '<div class="small text-muted">' +
            'Duration: <strong>' + examData.duration_minutes + 'min</strong>' +
            ' \u00B7 Negative: <strong>' + examData.negative_marking_factor + 'x</strong>' +
            ' \u00B7 Passing: <strong>' + examData.passing_marks + '</strong>' +
            '</div>' +
            '<div class="small text-muted">' +
            'Start: ' + new Date(examData.start_time).toLocaleString() +
            ' \u00B7 End: ' + new Date(examData.end_time).toLocaleString() +
            '</div>' +
            '</div>' +
            '<div class="col-12 col-md-4 text-md-end">' +
            '<div class="fs-4 fw-bold text-primary">' + examData.total_marks + '</div>' +
            '<div class="small text-muted">Total marks</div>' +
            '</div>' +
            '</div>';

        // UI state based on publication
        var settingsBtnContainer = document.getElementById("editSettingsBtnContainer");
        var addBtnsRow = document.getElementById("addBtnsRow");

        if (examData.is_published) {
            if (settingsBtnContainer) settingsBtnContainer.innerHTML = "";
            if (addBtnsRow) {
                addBtnsRow.innerHTML = 
                    '<div class="alert alert-success mb-0 py-2 small w-100">' +
                    '<i class="bi bi-check-circle-fill me-2"></i>' +
                    'This exam is published. Questions cannot be modified.' +
                    '<a href="/static/pages/teacher/gradebook.html?exam_id=' + examId + '" class="ms-2 alert-link">' +
                    'View Grade Book \u2192</a></div>';
            }
        } else {
            if (settingsBtnContainer) {
                settingsBtnContainer.innerHTML = 
                    '<button class="btn btn-outline-danger btn-sm me-2" onclick="deleteExam()">' +
                    '<i class="bi bi-trash3 me-1"></i>Delete Exam</button>' +
                    '<a href="/static/pages/teacher/exam_create.html?exam_id=' + examId + '" class="btn btn-outline-primary btn-sm">' +
                    '<i class="bi bi-gear-fill me-1"></i>Edit Settings</a>';
            }
        }
    } catch (err) {
        _showPageAlert(err.detail || "Failed to load exam.", "danger");
    }
}

async function loadQuestions() {
    var container = document.getElementById("questionsList");
    try {
        var data = await window.apiFetch("/api/teacher/exams/" + examId + "/questions");
        if (!data) return;

        document.getElementById("questionCountLabel").textContent = 
            data.total + " question" + (data.total !== 1 ? "s" : "");

        // Refresh total_marks from exam
        var exam = await window.apiFetch("/api/teacher/exams/" + examId);
        if (exam) {
            var marksDisplay = document.getElementById("totalMarksDisplay");
            if (marksDisplay) marksDisplay.textContent = exam.total_marks;
            examData = exam;
        }

        if (data.total === 0) {
            container.innerHTML = 
                '<div class="text-center text-muted py-4">' +
                '<i class="bi bi-question-circle fs-3 d-block mb-2 opacity-50"></i>' +
                'No questions yet. Add MCQ or subjective questions above.</div>';
            return;
        }

        container.innerHTML = data.items.map(function (q, i) {
            var typeBadge = q.question_type === 'mcq' ? 'bg-primary' : 'bg-warning text-dark';
            var typeText = q.question_type === 'mcq' ? 'MCQ' : 'Subjective';
            var marksText = q.marks + ' mark' + (q.marks !== 1 ? 's' : '');
            var wordLimitText = q.word_limit ? ' \u00B7 ' + q.word_limit + ' words max' : '';
            
            var optionsHtml = "";
            if (q.options && q.options.length > 0) {
                optionsHtml = '<div class="d-flex flex-wrap gap-2">' +
                    q.options.map(function (o) {
                        var optBadge = o.is_correct ? 'bg-success' : 'bg-light text-dark';
                        var optCheck = o.is_correct ? '<i class="bi bi-check-lg ms-1"></i>' : '';
                        return '<span class="badge ' + optBadge + ' border small">' +
                            window._esc(o.option_label) + '. ' + window._esc(o.option_text) + optCheck + '</span>';
                    }).join("") + '</div>';
            }

            var deleteBtn = (!examData || !examData.is_published)
                ? '<button class="btn btn-outline-danger btn-sm flex-shrink-0" onclick="deleteQuestion(' + q.id + ')" title="Delete question">' +
                  '<i class="bi bi-trash3"></i></button>'
                : "";

            var borderClass = q.question_type === 'mcq' ? 'border-primary-subtle' : 'border-warning-subtle';

            return '<div class="border rounded p-3 mb-2 ' + borderClass + '">' +
                '<div class="d-flex justify-content-between align-items-start gap-2">' +
                '<div class="flex-fill">' +
                '<div class="d-flex align-items-center gap-2 mb-1">' +
                '<span class="badge ' + typeBadge + ' small">' + typeText + '</span>' +
                '<span class="small text-muted">Q' + (i + 1) + ' \u00B7 ' + marksText + wordLimitText + '</span>' +
                '</div>' +
                '<p class="mb-2 small fw-medium">' + window._esc(q.question_text) + '</p>' +
                optionsHtml +
                '</div>' +
                deleteBtn +
                '</div></div>';
        }).join("");

    } catch (err) {
        container.innerHTML = 
            '<div class="text-center text-danger py-3 small">' +
            '<i class="bi bi-exclamation-triangle me-2"></i>' +
            window._esc(err.detail || "Failed to load questions.") + '</div>';
    }
}

// ══════════════════════════════════════════════════════════════════
// MCQ SUBMISSION
// ══════════════════════════════════════════════════════════════════

async function submitMcq() {
    var alertEl = document.getElementById("mcqAlert");
    var btn = document.getElementById("mcqSubmitBtn");
    var btnText = document.getElementById("mcqBtnText");
    var spinner = document.getElementById("mcqSpinner");

    var text = document.getElementById("mcqText").value.trim();
    var marks = parseFloat(document.getElementById("mcqMarks").value);
    var order = parseInt(document.getElementById("mcqOrder").value || "0");
    var correctRadio = document.querySelector('input[name="correctOption"]:checked');
    var correct = correctRadio ? correctRadio.value : null;

    if (!text || isNaN(marks) || marks <= 0) {
        window._showAlert(alertEl, "Question text and valid marks are required.", "danger");
        return;
    }

    var options = ["A", "B", "C", "D"].map(function(label) {
        var optVal = document.getElementById("optText" + label).value.trim();
        return {
            option_label: label,
            option_text: optVal,
            is_correct: label === correct,
        };
    });

    if (options.some(function(o) { return !o.option_text; })) {
        window._showAlert(alertEl, "All four option texts are required.", "danger");
        return;
    }

    window._setLoading(btn, btnText, spinner, true, "Adding...");
    window._hideAlert(alertEl);

    try {
        await window.apiFetch("/api/teacher/exams/" + examId + "/questions/mcq", {
            method: "POST",
            body: JSON.stringify({
                question_text: text,
                marks: marks,
                order_index: order,
                options: options,
            }),
        });

        // Reset
        var form = document.getElementById("mcqForm");
        if (form) form.reset();
        var modal = bootstrap.Modal.getInstance(document.getElementById("mcqModal"));
        if (modal) modal.hide();
        await loadQuestions();

    } catch (err) {
        window._showAlert(alertEl, err.detail || "Failed to add MCQ.", "danger");
    } finally {
        window._setLoading(btn, btnText, spinner, false, "Add Question");
    }
}

// ══════════════════════════════════════════════════════════════════
// SUBJECTIVE SUBMISSION
// ══════════════════════════════════════════════════════════════════

async function submitSubjective() {
    var alertEl = document.getElementById("subjAlert");
    var btn = document.getElementById("subjSubmitBtn");
    var btnText = document.getElementById("subjBtnText");
    var spinner = document.getElementById("subjSpinner");

    var text = document.getElementById("subjText").value.trim();
    var marks = parseFloat(document.getElementById("subjMarks").value);
    var order = parseInt(document.getElementById("subjOrder").value || "0");
    var wordLimitVal = document.getElementById("subjWordLimit").value;
    var wordLimit = wordLimitVal ? parseInt(wordLimitVal) : null;

    if (!text || isNaN(marks) || marks <= 0) {
        window._showAlert(alertEl, "Question text and valid marks are required.", "danger");
        return;
    }

    window._setLoading(btn, btnText, spinner, true, "Adding...");
    window._hideAlert(alertEl);

    try {
        await window.apiFetch("/api/teacher/exams/" + examId + "/questions/subjective", {
            method: "POST",
            body: JSON.stringify({
                question_text: text,
                marks: marks,
                order_index: order,
                word_limit: wordLimit,
            }),
        });

        var form = document.getElementById("subjForm");
        if (form) form.reset();
        var modal = bootstrap.Modal.getInstance(document.getElementById("subjModal"));
        if (modal) modal.hide();
        await loadQuestions();

    } catch (err) {
        window._showAlert(alertEl, err.detail || "Failed to add question.", "danger");
    } finally {
        window._setLoading(btn, btnText, spinner, false, "Add Question");
    }
}

// ══════════════════════════════════════════════════════════════════
// DELETE & PUBLISH
// ══════════════════════════════════════════════════════════════════

async function deleteQuestion(qId) {
    if (!confirm("Delete this question?")) return;
    try {
        await window.apiFetch("/api/teacher/questions/" + qId, { method: "DELETE" });
        await loadQuestions();
    } catch (err) {
        _showPageAlert(err.detail || "Failed to delete question.", "danger");
    }
}

async function publishExam() {
    if (!confirm("Publish this exam? Students will be notified immediately and questions cannot be changed after publishing.")) return;

    var btn = document.getElementById("publishBtn");
    var btnText = document.getElementById("publishBtnText");
    var spinner = document.getElementById("publishSpinner");

    window._setLoading(btn, btnText, spinner, true, "Publishing...");

    try {
        var data = await window.apiFetch("/api/teacher/exams/" + examId + "/publish", { method: "POST" });
        _showPageAlert(data.message + " " + (data.notified_students || 0) + " student(s) notified.", "success");

        setTimeout(async function() {
            await loadExamInfo();
            await loadQuestions();
        }, 1000);

    } catch (err) {
        _showPageAlert(err.detail || (err.message || "Failed to publish exam."), "danger");
        window._setLoading(btn, btnText, spinner, false, "Publish Exam");
    }
}

async function deleteExam() {
    if (!confirm("Are you sure you want to delete this exam draft? This action cannot be undone.")) return;
    try {
        await window.apiFetch("/api/teacher/exams/" + examId, { method: "DELETE" });
        window.location.href = "/static/pages/teacher/courses.html";
    } catch (err) {
        _showPageAlert(err.detail || "Failed to delete exam.", "danger");
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
    el.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// Global exposure
window.submitMcq = submitMcq;
window.submitSubjective = submitSubjective;
window.deleteQuestion = deleteQuestion;
window.publishExam = publishExam;
window.deleteExam = deleteExam;
window.loadExamInfo = loadExamInfo;
window.loadQuestions = loadQuestions;
