/**
 * admin/overview.js
 * Extracted from admin/overview.html
 */

// ── Auth ready ────────────────────────────────────────────────────
(function () {
    const prev = window.__onAuthReady;
    window.__onAuthReady = async function (user) {
        if (typeof prev === "function") await prev(user);

        // Set welcome message
        const heading = document.getElementById("welcomeHeading");
        const dateTime = document.getElementById("welcomeDateTime");
        
        if (heading) heading.textContent = `Welcome back, ${user.first_name} 👋`;
        if (dateTime) {
            dateTime.textContent = new Date().toLocaleDateString(undefined, {
                weekday: "long",
                year: "numeric",
                month: "long",
                day: "numeric",
            });
        }

        await loadStats();
    };
})();

// ── Load stats ────────────────────────────────────────────────────

async function loadStats() {
    const userStatsRow = document.getElementById("userStatsRow");
    try {
        const data = await window.apiFetch("/api/admin/overview/stats");
        if (!data) return;

        renderUserStats(data.users, data.enrollments);
        renderCourseExamStats(data.courses, data.exams);
        renderRecentLogs(data.recent_system_logs);

    } catch (err) {
        if (userStatsRow) {
            userStatsRow.innerHTML = `
                <div class="col-12 text-danger text-center small py-2">
                    <i class="bi bi-exclamation-triangle me-2"></i>
                    ${window._esc(err.detail || "Failed to load stats.")}
                </div>`;
        }
    }
}

// ── User stat cards ───────────────────────────────────────────────

function renderUserStats(users, enrollments) {
    const row = document.getElementById("userStatsRow");
    if (!row) return;
    row.innerHTML = `
        ${_statCard({
            icon: "bi-people-fill",
            iconBg: "bg-primary-subtle text-primary",
            value: users.total,
            label: "Total Users",
            sub: `${users.active} active · ${users.inactive} inactive`,
            cols: "col-6 col-md-3",
        })}
        ${_statCard({
            icon: "bi-person-fill",
            iconBg: "bg-info-subtle text-info",
            value: users.students,
            label: "Students",
            sub: "Registered accounts",
            cols: "col-6 col-md-3",
        })}
        ${_statCard({
            icon: "bi-person-badge-fill",
            iconBg: "bg-success-subtle text-success",
            value: users.teachers,
            label: "Teachers",
            sub: "Registered accounts",
            cols: "col-6 col-md-3",
        })}
        ${_statCard({
            icon: "bi-diagram-3-fill",
            iconBg: "bg-warning-subtle text-warning",
            value: enrollments.total,
            label: "Enrollments",
            sub: "Course-student links",
            cols: "col-6 col-md-3",
        })}`;
}

// ── Course + Exam stat cards ──────────────────────────────────────

function renderCourseExamStats(courses, exams) {
    const row = document.getElementById("courseExamStatsRow");
    if (!row) return;
    row.innerHTML = `
        ${_statCard({
            icon: "bi-mortarboard-fill",
            iconBg: "bg-primary-subtle text-primary",
            value: courses.total,
            label: "Courses",
            sub: `${courses.active} active · ${courses.inactive} inactive`,
            cols: "col-6 col-md-4",
        })}
        ${_statCard({
            icon: "bi-journal-check",
            iconBg: "bg-success-subtle text-success",
            value: exams.published,
            label: "Published Exams",
            sub: `${exams.total} total exams`,
            cols: "col-6 col-md-4",
        })}
        ${_statCard({
            icon: "bi-trophy-fill",
            iconBg: "bg-warning-subtle text-warning",
            value: exams.results_published,
            label: "Results Released",
            sub: "Students can see their scores",
            cols: "col-6 col-md-4",
        })}`;
}

// ── Recent logs ───────────────────────────────────────────────────

function renderRecentLogs(logs) {
    const area = document.getElementById("recentLogsArea");
    if (!area) return;

    if (!logs || logs.length === 0) {
        area.innerHTML = `
            <div class="text-center text-muted py-3 small">
                <i class="bi bi-inbox d-block fs-4 mb-1 opacity-50"></i>
                No recent activity
            </div>`;
        return;
    }

    area.innerHTML = `
        <div class="d-flex flex-column gap-0">
            ${logs.map(log => `
                <div class="d-flex align-items-start gap-3 py-2 border-bottom">
                    <div class="mt-1 flex-shrink-0">
                        <span class="badge log-event-badge ${_eventBadgeCls(log.event_type)}">
                            ${_formatEvent(log.event_type)}
                        </span>
                    </div>
                    <div class="flex-fill min-w-0">
                        <div class="small text-body"
                             style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
                             title="${window._esc(log.description)}">
                            ${window._esc(log.description)}
                        </div>
                        <div class="small text-muted">
                            ${window._relativeTime(log.created_at)}
                        </div>
                    </div>
                </div>`).join("")}
        </div>`;
}

// ── Stat card builder ─────────────────────────────────────────────

function _statCard({ icon, iconBg, value, label, sub, cols }) {
    return `
        <div class="${cols}">
            <div class="stat-card">
                <div class="d-flex align-items-start gap-3">
                    <div class="stat-card-icon ${iconBg}">
                        <i class="bi ${icon}"></i>
                    </div>
                    <div>
                        <div class="stat-card-value">${value}</div>
                        <div class="stat-card-label">${label}</div>
                        <div class="stat-card-sub">${sub}</div>
                    </div>
                </div>
            </div>
        </div>`;
}

// ── Helpers ───────────────────────────────────────────────────────

function _eventBadgeCls(type) {
    const map = {
        exam_created: "bg-primary-subtle text-primary",
        exam_published: "bg-success-subtle text-success",
        results_published: "bg-info-subtle text-info",
        users_created: "bg-warning-subtle text-warning",
        course_created: "bg-secondary-subtle text-secondary",
        course_activated: "bg-success-subtle text-success",
        course_deactivated: "bg-danger-subtle text-danger",
    };
    return map[type] || "bg-secondary-subtle text-secondary";
}

function _formatEvent(type) {
    return (type || "").replace(/_/g, " ");
}
