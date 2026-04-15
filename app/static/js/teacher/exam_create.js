/**
 * teacher/exam_create.js
 * Extracted from teacher/exam_create.html
 */

// ── State ─────────────────────────────────────────────────────────
var urlP = new URLSearchParams(window.location.search);
var courseId = parseInt(urlP.get("course_id"));
var editExamId = parseInt(urlP.get("exam_id")) || null;

// UI Initialization
(function initUI() {
    if (editExamId) {
        var pageTitle = document.querySelector(".page-title");
        if (pageTitle) pageTitle.textContent = "Edit Exam Settings";
        var submitBtnText = document.getElementById("submitBtnText");
        if (submitBtnText) submitBtnText.textContent = "Save Settings";
    }

    var courseNameDisplay = document.getElementById("courseNameDisplay");
    if (courseNameDisplay) {
        courseNameDisplay.textContent = urlP.get("course_name") || "\u2014";
    }

    // Pre-fill start/end with sensible defaults only for NEW exams
    if (!editExamId) {
        var tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        tomorrow.setHours(10, 0, 0, 0);
        var end = new Date(tomorrow);
        end.setHours(12, 0, 0, 0);
        var fmt = function(d) { return d.toISOString().slice(0, 16); };
        var startInput = document.getElementById("efStart");
        var endInput = document.getElementById("efEnd");
        if (startInput) startInput.value = fmt(tomorrow);
        if (endInput) endInput.value = fmt(end);
    }
})();

// ── Auth ready ────────────────────────────────────────────────────
(function () {
    var prev = window.__onAuthReady;
    window.__onAuthReady = async function (user) {
        if (typeof prev === "function") await prev(user);
        
        var alertEl = document.getElementById("formAlert");
        if ((!courseId || isNaN(courseId)) && !editExamId) {
            if (alertEl) {
                alertEl.className = "alert alert-danger";
                alertEl.textContent = "No course ID in URL. Return to My Courses.";
                alertEl.classList.remove("d-none");
            }
        }
        
        if (editExamId) {
            await loadExamData(editExamId);
        }
    };
})();

// ══════════════════════════════════════════════════════════════════
// DATA LOADING
// ══════════════════════════════════════════════════════════════════

async function loadExamData(eid) {
    try {
        var data = await window.apiFetch("/api/teacher/exams/" + eid);
        if (!data) return;

        document.getElementById("efTitle").value = data.title;
        document.getElementById("efDesc").value = data.description || "";
        document.getElementById("efDuration").value = data.duration_minutes;
        document.getElementById("efNegative").value = data.negative_marking_factor;
        document.getElementById("efPassing").value = data.passing_marks;

        if (data.course_code) {
            document.getElementById("courseNameDisplay").textContent = data.course_code;
        }

        // Convert ISO UTC to local simple format (YYYY-MM-DDTHH:mm)
        var toLocalFmt = function(iso) {
            if (!iso) return "";
            var d = new Date(iso);
            if (isNaN(d.getTime())) return "";
            var pad = function(n) { return String(n).padStart(2, '0'); };
            return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) + "T" + pad(d.getHours()) + ":" + pad(d.getMinutes());
        };

        document.getElementById("efStart").value = toLocalFmt(data.start_time);
        document.getElementById("efEnd").value = toLocalFmt(data.end_time);

        if (data.is_published) {
            var alertEl = document.getElementById("formAlert");
            window._showAlert(alertEl, "This exam is already published. Settings cannot be edited.", "warning");
            document.getElementById("submitBtn").disabled = true;
            // Disable all inputs
            document.querySelectorAll("input, textarea, select").forEach(function(i) { i.disabled = true; });
        }
    } catch (err) {
        window._showAlert(document.getElementById("formAlert"), err.detail || "Failed to load exam data.", "danger");
    }
}

// ══════════════════════════════════════════════════════════════════
// SUBMISSION
// ══════════════════════════════════════════════════════════════════

async function submitExam() {
    var form = document.getElementById("examForm");
    var alertEl = document.getElementById("formAlert");
    var btn = document.getElementById("submitBtn");
    var btnText = document.getElementById("submitBtnText");
    var spinner = document.getElementById("submitSpinner");

    if (!form.checkValidity()) {
        form.classList.add("was-validated");
        return;
    }

    var startLocal = document.getElementById("efStart").value;
    var endLocal = document.getElementById("efEnd").value;
    if (!startLocal || !endLocal) {
        window._showAlert(alertEl, "Start and end times are required.", "danger");
        return;
    }

    window._setLoading(btn, btnText, spinner, true, editExamId ? "Saving..." : "Creating...");
    window._hideAlert(alertEl);

    try {
        var url = editExamId ? "/api/teacher/exams/" + editExamId : "/api/teacher/exams";
        var method = editExamId ? "PATCH" : "POST";

        var payload = {
            title: document.getElementById("efTitle").value.trim(),
            description: document.getElementById("efDesc").value.trim() || null,
            duration_minutes: parseInt(document.getElementById("efDuration").value),
            negative_marking_factor: parseFloat(document.getElementById("efNegative").value || "0"),
            passing_marks: parseFloat(document.getElementById("efPassing").value || "0"),
            start_time: new Date(startLocal).toISOString(),
            end_time: new Date(endLocal).toISOString(),
        };

        if (!editExamId) {
            payload.course_id = courseId;
        }

        var data = await window.apiFetch(url, {
            method: method,
            body: JSON.stringify(payload),
        });

        if (editExamId) {
            window._showAlert(alertEl, "Exam settings updated successfully.", "success");
            setTimeout(function() {
                window.location.href = "/static/pages/teacher/exam_questions.html?exam_id=" + editExamId;
            }, 1500);
        } else {
            window.location.href = "/static/pages/teacher/exam_questions.html?exam_id=" + data.id;
        }

    } catch (err) {
        window._showAlert(alertEl, err.detail || "Failed to save exam.", "danger");
        window._setLoading(btn, btnText, spinner, false, editExamId ? "Save Settings" : "Create & Add Questions");
    }
}

// Global exposure
window.submitExam = submitExam;
window.loadExamData = loadExamData;
