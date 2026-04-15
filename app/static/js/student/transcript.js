/**
 * student/transcript.js
 * Extracted from student/transcript.html
 */

var trendChartInstance = null;

(function () {
    var prev = window.__onAuthReady;
    window.__onAuthReady = async function (user) {
        if (typeof prev === "function") await prev(user);
        await loadTranscript();
    };
})();

// ══════════════════════════════════════════════════════════════════
// DATA LOADING
// ══════════════════════════════════════════════════════════════════

async function loadTranscript() {
    var summaryEl = document.getElementById("transcriptSummary");
    try {
        var data = await window.apiFetch("/api/student/transcript");
        if (!data) return;

        renderSummary(data);
        renderTable(data.entries);
        renderTrend(data.entries);

    } catch (err) {
        if (summaryEl) {
            summaryEl.innerHTML = 
                '<div class="col-12 text-center text-danger py-3 small">' +
                '<i class="bi bi-exclamation-triangle me-2"></i>' +
                window._esc(err.detail || "Failed to load transcript.") + '</div>';
        }
    }
}

// ══════════════════════════════════════════════════════════════════
// RENDERING
// ══════════════════════════════════════════════════════════════════

function renderSummary(data) {
    var summaryEl = document.getElementById("transcriptSummary");
    if (!summaryEl) return;

    summaryEl.innerHTML = 
        '<div class="col-6 col-md-3">' +
        '  <div class="content-card bg-primary-subtle text-center py-3">' +
        '    <div class="fw-bold fs-5 text-primary">' + data.total + '</div>' +
        '    <div class="small text-muted">Exams Taken</div>' +
        '  </div>' +
        '</div>' +
        '<div class="col-6 col-md-3">' +
        '  <div class="content-card bg-success-subtle text-center py-3">' +
        '    <div class="fw-bold fs-5 text-success">' + data.pass_count + '</div>' +
        '    <div class="small text-muted">Passed</div>' +
        '  </div>' +
        '</div>' +
        '<div class="col-6 col-md-3">' +
        '  <div class="content-card bg-danger-subtle text-center py-3">' +
        '    <div class="fw-bold fs-5 text-danger">' + data.fail_count + '</div>' +
        '    <div class="small text-muted">Failed</div>' +
        '  </div>' +
        '</div>' +
        '<div class="col-6 col-md-3">' +
        '  <div class="content-card bg-info-subtle text-center py-3">' +
        '    <div class="fw-bold fs-5 text-info">' + data.overall_avg + '%</div>' +
        '    <div class="small text-muted">Overall Average</div>' +
        '  </div>' +
        '</div>';
}

function renderTable(entries) {
    var tbody = document.getElementById("transcriptTableBody");
    if (!tbody) return;

    if (!entries || !entries.length) {
        tbody.innerHTML = 
            '<tr><td colspan="7" class="text-center text-muted py-4">' +
            '<i class="bi bi-inbox fs-3 d-block mb-1 opacity-50"></i>' +
            'No published results yet.</td></tr>';
        return;
    }

    tbody.innerHTML = entries.map(function(e, i) {
        var pctCls = e.percentage >= 50 ? 'text-success' : 'text-danger';
        var passCls = e.is_pass === true ? 'bg-success' : (e.is_pass === false ? 'bg-danger' : 'bg-secondary');
        var passTxt = e.is_pass === true ? 'PASS' : (e.is_pass === false ? 'FAIL' : '\u2014');

        return '<tr>' +
            '<td class="text-muted small">' + (i + 1) + '</td>' +
            '<td><span class="badge bg-secondary-subtle text-secondary small">' + window._esc(e.course_code) + '</span>' +
            '<div class="small text-muted">' + window._esc(e.course_name) + '</div></td>' +
            '<td class="small">' + window._esc(e.exam_title) + '</td>' +
            '<td class="small text-nowrap"><strong>' + e.total_marks_awarded + '</strong> / ' + e.total_marks_available + '</td>' +
            '<td class="small"><span class="' + pctCls + ' fw-semibold">' + e.percentage + '%</span></td>' +
            '<td><span class="badge ' + passCls + ' small">' + passTxt + '</span></td>' +
            '<td class="small text-muted text-nowrap">' + window._formatDate(e.results_published_at) + '</td>' +
            '</tr>';
    }).join("");
}

function renderTrend(entries) {
    var wrapper = document.getElementById("trendWrapper");
    var noMsg = document.getElementById("noTrendMsg");
    if (!wrapper || !noMsg) return;

    if (!entries || entries.length < 2) {
        wrapper.classList.add("d-none");
        noMsg.classList.remove("d-none");
        return;
    }

    wrapper.classList.remove("d-none");
    noMsg.classList.add("d-none");

    var ordered = entries.slice().reverse();
    var labels = ordered.map(function(e, i) { return e.course_code + " #" + (i + 1); });
    var scores = ordered.map(function(e) { return e.percentage; });

    if (trendChartInstance) trendChartInstance.destroy();

    var isDark = document.documentElement.getAttribute("data-bs-theme") === "dark";
    var gridColor = isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.08)";
    var labelColor = isDark ? "#adb5bd" : "#6c757d";

    if (typeof Chart === "undefined") return;

    trendChartInstance = new Chart(document.getElementById("trendChart"), {
        type: "line",
        data: {
            labels: labels,
            datasets: [{
                label: "Score %",
                data: scores,
                borderColor: "#198754",
                backgroundColor: "rgba(25,135,84,0.12)",
                pointBackgroundColor: scores.map(function(s) { return s >= 50 ? "#198754" : "#dc3545"; }),
                tension: 0.35,
                fill: true,
                pointRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: { color: labelColor, callback: function(v) { return v + "%"; } },
                    grid: { color: gridColor }
                },
                x: {
                    ticks: { color: labelColor, maxRotation: 30, autoSkip: true },
                    grid: { display: false }
                }
            }
        }
    });
}

// Global exposure
window.loadTranscript = loadTranscript;
window._formatDate = window._formatDate || function(iso) {
    if (!iso) return "\u2014";
    var d = new Date(iso);
    return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
};
window._esc = window._esc || function(s) {
    return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;")
        .replace(/>/g, "&gt;").replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
};
