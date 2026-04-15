/**
 * student/dashboard.js
 * Extracted from student/dashboard.html
 */

// ── State ─────────────────────────────────────────────────────────
let perfChartInstance = null;

// ── Initialization ────────────────────────────────────────────────
(function () {
    const prev = window.__onAuthReady;
    window.__onAuthReady = async function (user) {
        if (typeof prev === "function") await prev(user);
        const welcomeEl = document.getElementById("welcomeHeading");
        if (welcomeEl) {
            welcomeEl.textContent = `Welcome, ${user.first_name} \uD83D\uDC4B`;
        }
        await loadDashboard();
    };
})();

// ══════════════════════════════════════════════════════════════════
// DATA LOADING
// ══════════════════════════════════════════════════════════════════

async function loadDashboard() {
    try {
        const data = await window.apiFetch("/api/student/dashboard");
        if (!data) return;

        renderSummaryCards(data.summary);
        renderRecentResults(data.recent_results);
        renderUpcomingExams(data.upcoming_exams);
        renderPerfChart(data.subject_performance);

    } catch (err) {
        const cardsEl = document.getElementById("summaryCards");
        if (cardsEl) {
            cardsEl.innerHTML = `
                <div class="col-12 text-danger small text-center py-2">
                    <i class="bi bi-exclamation-triangle me-2"></i>
                    ${window._esc(err.detail || "Failed to load dashboard.")}
                </div>`;
        }
    }
}

// ══════════════════════════════════════════════════════════════════
// RENDERING
// ══════════════════════════════════════════════════════════════════

function renderSummaryCards(summary) {
    const container = document.getElementById("summaryCards");
    if (!container) return;

    container.innerHTML = [
        _miniCard("bi-journal-check text-primary", summary.total_attempted, "Exams Attempted", "bg-primary-subtle"),
        _miniCard("bi-check-circle-fill text-success", summary.total_pass, "Exams Passed", "bg-success-subtle"),
        _miniCard("bi-percent text-info", summary.pass_rate + "%", "Pass Rate", "bg-info-subtle"),
        _miniCard("bi-bar-chart-fill text-warning", summary.average_pct + "%", "Avg Score", "bg-warning-subtle")
    ].join("");
}

function _miniCard(iconCls, value, label, bgCls) {
    return `
    <div class="col-6 col-md-3">
      <div class="content-card ${bgCls} text-center py-3">
        <i class="bi ${iconCls} fs-4 d-block mb-1"></i>
        <div class="fw-bold fs-5">${value}</div>
        <div class="small text-muted">${label}</div>
      </div>
    </div>`;
}

function renderRecentResults(results) {
    const area = document.getElementById("recentResultsArea");
    if (!area) return;

    if (!results.length) {
        area.innerHTML = `
            <div class="text-center text-muted py-3 small">
                <i class="bi bi-inbox fs-3 d-block mb-1 opacity-50"></i>
                No published results yet.
            </div>`;
        return;
    }

    area.innerHTML = results.map(r => {
        const passClass = r.is_pass === true ? 'bg-success' : (r.is_pass === false ? 'bg-danger' : 'bg-secondary');
        const passText = r.is_pass === true ? 'PASS' : (r.is_pass === false ? 'FAIL' : '\u2014');
        const scoreColor = r.is_pass ? 'text-success' : 'text-danger';

        return `
            <div class="d-flex align-items-center gap-3 py-2 border-bottom">
                <div class="flex-fill min-w-0">
                    <div class="small fw-semibold text-truncate">${window._esc(r.exam_title)}</div>
                    <div class="small text-muted">${window._esc(r.course_code)}</div>
                </div>
                <div class="text-end flex-shrink-0">
                    <div class="small fw-bold ${scoreColor}">${r.total_marks_awarded} / ${r.total_marks_available}</div>
                    <div class="small text-muted">${r.percentage}%</div>
                </div>
                <span class="badge ${passClass} flex-shrink-0">${passText}</span>
            </div>`;
    }).join("");
}

function renderUpcomingExams(exams) {
    const area = document.getElementById("upcomingExamsArea");
    if (!area) return;

    if (!exams.length) {
        area.innerHTML = `
            <div class="text-center text-muted py-3 small">
                <i class="bi bi-calendar-x fs-3 d-block mb-1 opacity-50"></i>
                No upcoming exams.
            </div>`;
        return;
    }

    area.innerHTML = exams.map(e => {
        const start = new Date(e.start_time);
        const now = new Date();
        const mins = Math.round((start - now) / 60000);
        const soon = mins <= 30 && mins >= -5;
        const entryBtn = e.has_attempted
            ? `<span class="badge bg-secondary-subtle text-secondary small">Done</span>`
            : `<a href="/static/pages/student/exam_lobby.html?exam_id=${e.id}" class="btn btn-primary btn-sm">Enter</a>`;

        return `
            <div class="border rounded p-2 mb-2 ${soon ? 'border-warning bg-warning-subtle' : ''}">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-fill min-w-0 me-2">
                        <div class="small fw-semibold text-truncate">${window._esc(e.title)}</div>
                        <div class="small text-muted">${window._esc(e.course_code)} \u00B7 ${e.duration_minutes}min \u00B7 ${e.total_marks} marks</div>
                    </div>
                    ${entryBtn}
                </div>
                <div class="small text-muted mt-1">
                    <i class="bi bi-clock me-1"></i>${start.toLocaleString()}
                    ${soon && !e.has_attempted ? '<span class="text-warning fw-semibold ms-1">\u25CF Starting soon</span>' : ''}
                </div>
            </div>`;
    }).join("");
}

function renderPerfChart(performance) {
    const wrapper = document.getElementById("chartWrapper");
    const noMsg = document.getElementById("noChartMsg");
    if (!wrapper || !noMsg) return;

    if (!performance.length) {
        wrapper.classList.add("d-none");
        noMsg.classList.remove("d-none");
        return;
    }

    const labels = performance.map(p => p.course_code);
    const avgs = performance.map(p => p.average_pct);
    const passes = performance.map(p => p.pass_count);
    const fails = performance.map(p => p.fail_count);

    if (perfChartInstance) perfChartInstance.destroy();

    const isDark = document.documentElement.getAttribute("data-bs-theme") === "dark";
    const gridColor = isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.08)";
    const labelColor = isDark ? "#adb5bd" : "#6c757d";

    const ctx = document.getElementById("perfChart");
    if (!ctx) return;

    perfChartInstance = new Chart(ctx, {
        type: "bar",
        data: {
            labels,
            datasets: [{
                label: "Avg %",
                data: avgs,
                backgroundColor: "rgba(13,110,253,0.7)",
                borderRadius: 4,
                yAxisID: "y"
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        afterLabel: (ctx) => {
                            const i = ctx.dataIndex;
                            return `Pass: ${passes[i]}  Fail: ${fails[i]}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        color: labelColor,
                        callback: v => v + "%"
                    },
                    grid: { color: gridColor }
                },
                x: {
                    ticks: { color: labelColor },
                    grid: { display: false }
                }
            }
        }
    });
}

// Global exposure
window.loadDashboard = loadDashboard;
