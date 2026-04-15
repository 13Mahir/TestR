/**
 * student/exam_attempt.js
 * Extracted from student/exam_attempt.html
 * Fully CSP-compliant (no inline event handlers)
 */

// ── State ─────────────────────────────────────────────────────────
var urlP = new URLSearchParams(window.location.search);
var attemptId = parseInt(urlP.get("attempt_id"));
var examId = parseInt(urlP.get("exam_id"));

var questions = [];
var answers = {};     // { questionId: { optionId, text } }
var currentIndex = 0;
var timerSeconds = 0;
var timerHandle = null;
var submitted = false;
var examDuration = 0;      // minutes, for proctor.js
var subjTimer = null;

// ── Initialization ────────────────────────────────────────────────
(function () {
    var prev = window.__onAuthReady;
    window.__onAuthReady = async function (user) {
        if (typeof prev === "function") await prev(user);
        
        var qArea = document.getElementById("questionArea");
        if (!attemptId || !examId || isNaN(attemptId)) {
            if (qArea) {
                qArea.innerHTML = 
                    '<div class="text-center text-danger py-5">' +
                    '<i class="bi bi-exclamation-triangle fs-2 d-block mb-2"></i>' +
                    'Invalid attempt URL. Return to <a href="/static/pages/student/courses.html">My Courses</a>.' +
                    '</div>';
            }
            return;
        }
        _setupEventListeners();
        await loadAttempt();
    };
})();

function _setupEventListeners() {
    // Top-level static buttons
    var submitBtn = document.getElementById("submitBtn");
    if (submitBtn) submitBtn.addEventListener("click", confirmSubmit);

    var doSubmitBtn = document.getElementById("doSubmitBtn");
    if (doSubmitBtn) doSubmitBtn.addEventListener("click", function() { doSubmit(false); });

    var retryCameraBtn = document.getElementById("retryCameraBtn");
    if (retryCameraBtn) retryCameraBtn.addEventListener("click", function() {
        if (typeof window.retryProctorCamera === "function") window.retryProctorCamera();
    });

    var startExamBtn = document.getElementById("startExamBtn");
    if (startExamBtn) startExamBtn.addEventListener("click", tryStartExam);

    var resumeFsBtn = document.getElementById("resumeFsBtn");
    if (resumeFsBtn) resumeFsBtn.addEventListener("click", resumeFullscreen);

    // Event Delegation for dynamic content
    // 1. Question Navigation Grid
    var navGrid = document.getElementById("navGrid");
    if (navGrid) {
        navGrid.addEventListener("click", function(e) {
            var btn = e.target.closest(".q-nav-btn");
            if (btn && btn.hasAttribute("data-index")) {
                showQuestion(parseInt(btn.getAttribute("data-index")));
            }
        });
    }

    // 2. Question Navigation Buttons (Prev/Next)
    var qArea = document.getElementById("questionArea");
    if (qArea) {
        qArea.addEventListener("click", function(e) {
            var btn = e.target.closest("[data-action='nav-question']");
            if (btn && btn.hasAttribute("data-index")) {
                showQuestion(parseInt(btn.getAttribute("data-index")));
            }
        });
        
        // 3. Option Selection (Radio buttons)
        qArea.addEventListener("change", function(e) {
            if (e.target.classList.contains("option-radio")) {
                var qId = e.target.getAttribute("data-qid");
                var oId = e.target.value;
                selectOption(qId, oId);
            }
        });

        // 4. Subjective Typing (Textareas)
        qArea.addEventListener("input", function(e) {
            if (e.target.tagName === "TEXTAREA" && e.target.hasAttribute("data-qid")) {
                var qId = e.target.getAttribute("data-qid");
                typeSubjective(qId, e.target.value);
            }
        });
    }
}

// ══════════════════════════════════════════════════════════════════
// DATA LOADING
// ══════════════════════════════════════════════════════════════════

async function loadAttempt() {
    var qArea = document.getElementById("questionArea");
    var titleBar = document.getElementById("examTitleBar");

    try {
        var data = await window.apiFetch("/api/student/attempts/" + attemptId + "/questions");
        if (!data) return;

        questions = data.items;
        
        var lobbyData = await window.apiFetch("/api/student/exams/" + examId + "/lobby");
        examDuration = lobbyData ? lobbyData.duration_minutes : 60;

        // Restore saved answers
        questions.forEach(function(q) {
            if (q.saved_answer) {
                answers[q.id] = {
                    optionId: q.saved_answer.selected_option_id,
                    text: q.saved_answer.subjective_text
                };
            }
        });

        if (titleBar) {
            titleBar.textContent = (lobbyData ? lobbyData.title : "Exam #" + examId);
        }

        // Show setup modal
        if (typeof bootstrap !== "undefined" && bootstrap.Modal) {
            var setupModalEl = document.getElementById('setupModal');
            if (setupModalEl) {
                var modal = new bootstrap.Modal(setupModalEl);
                modal.show();
            }
        }

        // Init proctor
        if (typeof window.initProctor === "function") {
            window.initProctor(attemptId);
        }

    } catch (err) {
        if (qArea) {
            qArea.innerHTML = 
                '<div class="text-center text-danger py-5 small">' +
                '<i class="bi bi-exclamation-triangle fs-2 d-block mb-2"></i>' +
                window._esc(err.detail || "Failed to load questions.") + '</div>';
        }
    }
}

// ══════════════════════════════════════════════════════════════════
// EXAM FLOW
// ══════════════════════════════════════════════════════════════════

async function tryStartExam() {
    var btn = document.getElementById('startExamBtn');
    if (btn) {
        btn.disabled = true;
        btn.textContent = "Starting...";
    }

    try {
        // 1. Request Fullscreen
        var doc = document.documentElement;
        if (doc.requestFullscreen) await doc.requestFullscreen();
        else if (doc.webkitRequestFullscreen) await doc.webkitRequestFullscreen();

        // 2. Hide modal
        if (typeof bootstrap !== "undefined" && bootstrap.Modal) {
            var modalEl = document.getElementById('setupModal');
            var instance = bootstrap.Modal.getInstance(modalEl);
            if (instance) instance.hide();
        }

        // 3. Start Timer
        timerSeconds = examDuration * 60;
        startTimer();

        // 4. Render first question
        renderNavGrid();
        showQuestion(0);

    } catch (err) {
        console.error("Failed to start exam:", err);
        if (btn) {
            btn.disabled = false;
            btn.textContent = "Start Exam Now";
        }
        alert("Failed to enter fullscreen. Please try again or check browser settings.");
    }
}

function resumeFullscreen() {
    var doc = document.documentElement;
    var p = (doc.requestFullscreen) ? doc.requestFullscreen() : doc.webkitRequestFullscreen();

    if (p && typeof p.then === "function") {
        p.then(function() {
            var overlay = document.getElementById('proctorOverlay');
            if (overlay) overlay.classList.add('d-none');
        }).catch(function(err) {
            console.error("Resume fullscreen failed:", err);
            alert("Failed to re-enter fullscreen. Please try again.");
        });
    }
}

// ══════════════════════════════════════════════════════════════════
// TIMER
// ══════════════════════════════════════════════════════════════════

function startTimer() {
    renderTimer();
    timerHandle = setInterval(async function() {
        timerSeconds--;
        renderTimer();
        if (timerSeconds <= 0) {
            clearInterval(timerHandle);
            await doSubmit(true);   // auto-submit
        }
    }, 1000);
}

function renderTimer() {
    var el = document.getElementById("timerDisplay");
    if (!el) return;

    var absTime = Math.abs(timerSeconds);
    var mins = Math.floor(absTime / 60);
    var secs = absTime % 60;
    
    el.textContent = (mins < 10 ? "0" + mins : mins) + ":" + (secs < 10 ? "0" + secs : secs);

    el.className = "exam-timer";
    if (timerSeconds <= 60) el.classList.add("danger");
    else if (timerSeconds <= 300) el.classList.add("warning");
}

// ══════════════════════════════════════════════════════════════════
// NAVIGATION & RENDERING
// ══════════════════════════════════════════════════════════════════

function renderNavGrid() {
    var grid = document.getElementById("navGrid");
    if (!grid) return;

    grid.innerHTML = questions.map(function(q, i) {
        var isAnswered = answers[q.id] && (answers[q.id].optionId != null || (answers[q.id].text && answers[q.id].text.trim()));
        var isCurrent = i === currentIndex;
        var cls = "q-nav-btn " + (isCurrent ? 'current' : '') + (isAnswered && !isCurrent ? 'answered' : '');
        
        return '<button class="' + cls + '" data-index="' + i + '" title="Q' + (i + 1) + '">' +
               (i + 1) + '</button>';
    }).join("");

    // Progress label
    var answeredCount = Object.values(answers).filter(function(a) {
        return a.optionId != null || (a.text && a.text.trim());
    }).length;
    var progressEl = document.getElementById("progressLabel");
    if (progressEl) {
        progressEl.textContent = answeredCount + " / " + questions.length;
    }
}

function showQuestion(index) {
    if (index < 0 || index >= questions.length) return;
    currentIndex = index;
    var q = questions[index];
    var saved = answers[q.id] || {};
    var area = document.getElementById("questionArea");
    if (!area) return;

    var body = "";
    if (q.question_type === "mcq") {
        body = q.options.map(function(o) {
            var sel = saved.optionId === o.id;
            var selClass = sel ? 'selected' : '';
            return '<label class="option-label ' + selClass + '" id="opt_label_' + o.id + '">' +
                '<input type="radio" class="option-radio form-check-input" name="mcq_' + q.id + '" value="' + o.id + '" ' + (sel ? 'checked' : '') + ' data-qid="' + q.id + '"/>' +
                '<span class="fw-semibold me-2">' + window._esc(o.option_label) + '</span>' +
                '<span class="small">' + window._esc(o.option_text) + '</span></label>';
        }).join("");
    } else {
        var limitAttr = q.word_limit ? 'maxlength="' + (q.word_limit * 7) + '"' : '';
        body = '<textarea class="form-control" id="subj_' + q.id + '" rows="8" placeholder="Type your answer here..." ' + limitAttr + ' data-qid="' + q.id + '">' +
               window._esc(saved.text || "") + '</textarea>' +
               (q.word_limit ? '<div class="small text-muted mt-1">Word limit: ' + q.word_limit + ' words</div>' : "");
    }

    var typeBadgeClass = q.question_type === 'mcq' ? 'bg-primary' : 'bg-warning text-dark';
    var typeLabel = q.question_type === 'mcq' ? 'MCQ' : 'Subjective';
    var marksLabel = q.marks + " mark" + (q.marks !== 1 ? 's' : '');

    area.innerHTML = 
        '<div style="max-width:680px">' +
        '<div class="d-flex align-items-center gap-2 mb-3">' +
        '<span class="badge ' + typeBadgeClass + '">Q' + (index + 1) + ' of ' + questions.length + ' \u00B7 ' + typeLabel + '</span>' +
        '<span class="small text-muted">' + marksLabel + '</span></div>' +
        '<p class="fw-medium mb-4">' + window._esc(q.question_text) + '</p>' +
        '<div id="answerArea">' + body + '</div>' +
        '<div class="d-flex gap-2 mt-4">' +
        '<button class="btn btn-outline-secondary btn-sm" data-action="nav-question" data-index="' + (index - 1) + '" ' + (index === 0 ? 'disabled' : '') + '>' +
        '<i class="bi bi-chevron-left me-1"></i>Previous</button>' +
        '<button class="btn btn-outline-primary btn-sm" data-action="nav-question" data-index="' + (index + 1) + '" ' + (index === questions.length - 1 ? 'disabled' : '') + '>' +
        'Next<i class="bi bi-chevron-right ms-1"></i></button></div></div>';

    renderNavGrid();
}

// ══════════════════════════════════════════════════════════════════
// ANSWER HANDLERS
// ══════════════════════════════════════════════════════════════════

async function selectOption(questionId, optionId) {
    answers[questionId] = { optionId: parseInt(optionId), text: null };
    renderNavGrid();

    // Highlight selected label
    document.querySelectorAll('[id^="opt_label_"]').forEach(function(el) {
        el.classList.remove("selected");
    });
    var lbl = document.getElementById("opt_label_" + optionId);
    if (lbl) lbl.classList.add("selected");

    // Save to server
    try {
        await window.apiFetch("/api/student/attempts/" + attemptId + "/answers?question_id=" + questionId + "&selected_option_id=" + optionId, { method: "POST" });
    } catch (_) { }
}

function typeSubjective(questionId, text) {
    answers[questionId] = { optionId: null, text: text };
    renderNavGrid();

    // Debounce server save
    if (subjTimer) clearTimeout(subjTimer);
    subjTimer = setTimeout(async function() {
        try {
            await window.apiFetch("/api/student/attempts/" + attemptId + "/answers?question_id=" + questionId + "&subjective_text=" + encodeURIComponent(text), { method: "POST" });
        } catch (_) { }
    }, 1500);
}

// ══════════════════════════════════════════════════════════════════
// SUBMISSION
// ══════════════════════════════════════════════════════════════════

function confirmSubmit() {
    var answeredCount = Object.values(answers).filter(function(a) {
        return a.optionId != null || (a.text && a.text.trim());
    }).length;
    var unansweredCount = questions.length - answeredCount;

    var warningHtml = (unansweredCount > 0) 
        ? '<p class="text-warning"><i class="bi bi-exclamation-triangle me-1"></i>' + unansweredCount + ' question' + (unansweredCount !== 1 ? 's' : '') + ' unanswered.</p>' 
        : "";

    var modalBody = document.getElementById("submitModalBody");
    if (modalBody) {
        modalBody.innerHTML = 
            '<p>You have answered <strong>' + answeredCount + '</strong> of <strong>' + questions.length + '</strong> questions.</p>' +
            warningHtml + '<p>Once submitted you cannot return to this exam.</p>';
    }

    if (typeof bootstrap !== "undefined" && bootstrap.Modal) {
        var modalEl = document.getElementById("submitModal");
        if (modalEl) {
            new bootstrap.Modal(modalEl).show();
        }
    }
}

async function doSubmit(auto) {
    if (submitted) return;
    submitted = true;

    if (timerHandle) clearInterval(timerHandle);

    // Stop proctoring
    if (typeof window.stopProctor === "function") {
        window.stopProctor();
    }

    // Exit fullscreen
    if (document.fullscreenElement || document.webkitFullscreenElement) {
        if (document.exitFullscreen) document.exitFullscreen().catch(function() {});
        else if (document.webkitExitFullscreen) document.webkitExitFullscreen();
    }

    var btn = document.getElementById("submitBtn");
    if (btn) {
        btn.disabled = true;
        btn.textContent = "Submitting...";
    }

    try {
        await window.apiFetch("/api/student/attempts/" + attemptId + "/submit?auto_submit=" + (auto || false), { method: "POST" });

        var successMsg = auto ? 'Your exam was automatically submitted.' : 'Your exam has been submitted successfully.';
        var title = auto ? 'Time Up!' : 'Exam Submitted!';

        // Replace shell content
        var shell = document.querySelector(".exam-shell");
        if (shell) {
            shell.innerHTML = 
                '<div class="d-flex flex-column align-items-center justify-content-center h-100 w-100 text-center">' +
                '<div style="max-width:500px; padding: 2rem;">' +
                '<div class="mb-4"><i class="bi bi-check-circle-fill text-success" style="font-size:5rem"></i></div>' +
                '<h2 class="fw-bold mb-3">' + title + '</h2>' +
                '<p class="text-muted mb-5 fs-5">' + successMsg + ' Results will be available after the teacher publishes them.</p>' +
                '<a href="/static/pages/student/dashboard.html" class="btn btn-primary"><i class="bi bi-speedometer2 me-2"></i>Go to Dashboard</a>' +
                '</div></div>';
        }

    } catch (err) {
        submitted = false;
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-send-check me-1"></i>Submit';
        }
        alert(err.detail || "Submit failed. Please try again.");
    }
}

// Global exposure (mostly for reuse and debug)
window.tryStartExam = tryStartExam;
window.resumeFullscreen = resumeFullscreen;
window.confirmSubmit = confirmSubmit;
window.doSubmit = doSubmit;
window.showQuestion = showQuestion;
window.selectOption = selectOption;
window.typeSubjective = typeSubjective;
window._esc = window._esc || function(s) {
    return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;")
        .replace(/>/g, "&gt;").replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
};
