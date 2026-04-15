/**
 * admin/logs.js
 * Extracted from admin/logs.html
 */

// ── State ─────────────────────────────────────────────────────────
var systemLogsPage = 1;
var auditLogsPage = 1;
var _auditLoaded = false;

// ── Auth ready — load system logs immediately ─────────────────────
(function () {
    var prev = window.__onAuthReady;
    window.__onAuthReady = async function (user) {
        if (typeof prev === "function") await prev(user);
        await loadSystemLogs(1);
    };
})();

// ══════════════════════════════════════════════════════════════════
// SYSTEM LOGS
// ══════════════════════════════════════════════════════════════════

async function loadSystemLogs(page) {
    systemLogsPage = page;
    var eventTypeSelector = document.getElementById("slEventType");
    var eventType = eventTypeSelector ? eventTypeSelector.value : "";

    var url = "/api/admin/logs/system?page=" + page + "&page_size=20";
    if (eventType) url += "&event_type=" + encodeURIComponent(eventType);

    var tbody = document.getElementById("systemLogsBody");
    tbody.innerHTML = _loadingRow(6);

    try {
        var data = await window.apiFetch(url);
        if (!data) return;

        document.getElementById("systemLogsBadge").textContent = data.total;

        if (data.items.length === 0) {
            tbody.innerHTML = _emptyRow(6, "No system log entries found.");
            _renderPagination("slPaginationControls", "slPaginationInfo", data, "loadSystemLogs");
            return;
        }

        tbody.innerHTML = data.items.map(function (log, i) {
            var rowNum = (page - 1) * 20 + i + 1;
            var metaHtml = log.metadata
                ? '<code class="small text-muted d-block" ' +
                'style="max-width:190px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" ' +
                'title="' + window._esc(JSON.stringify(log.metadata)) + '">' +
                window._esc(JSON.stringify(log.metadata)) + '</code>'
                : '<span class="text-muted small">&mdash;</span>';

            return '<tr>' +
                '<td class="text-muted small">' + rowNum + '</td>' +
                '<td><span class="badge ' + _eventTypeBadge(log.event_type) +
                ' text-wrap text-start lh-sm" style="font-size:0.7rem">' +
                _formatEventType(log.event_type) + '</span></td>' +
                '<td class="small">' + window._esc(log.description) + '</td>' +
                '<td class="small text-muted text-center">' + (log.actor_id || '&mdash;') + '</td>' +
                '<td>' + metaHtml + '</td>' +
                '<td class="small text-muted text-nowrap">' + window._formatDateTime(log.created_at) + '</td>' +
                '</tr>';
        }).join("");

        _renderPagination("slPaginationControls", "slPaginationInfo", data, "loadSystemLogs");

    } catch (err) {
        tbody.innerHTML = _errorRow(6, err.detail || "Failed to load system logs.");
    }
}

function _eventTypeBadge(type) {
    var map = {
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

function _formatEventType(type) {
    return (type || "").replace(/_/g, " ").replace(/\b\w/g, function (c) {
        return c.toUpperCase();
    });
}

// ══════════════════════════════════════════════════════════════════
// AUDIT LOGS
// ══════════════════════════════════════════════════════════════════

async function loadAuditLogs(page) {
    _auditLoaded = true;
    auditLogsPage = page;
    var action = document.getElementById("alAction").value.trim().toUpperCase();
    var targetType = document.getElementById("alTargetType").value;

    var url = "/api/admin/logs/audit?page=" + page + "&page_size=20";
    if (action) url += "&action=" + encodeURIComponent(action);
    if (targetType) url += "&target_type=" + encodeURIComponent(targetType);

    var tbody = document.getElementById("auditLogsBody");
    tbody.innerHTML = _loadingRow(8);

    try {
        var data = await window.apiFetch(url);
        if (!data) return;

        document.getElementById("auditLogBadge").textContent = data.total;

        if (data.items.length === 0) {
            tbody.innerHTML = _emptyRow(8, "No audit log entries found.");
            _renderPagination("alPaginationControls", "alPaginationInfo", data, "loadAuditLogs");
            return;
        }

        tbody.innerHTML = data.items.map(function (log, i) {
            var rowNum = (page - 1) * 20 + i + 1;
            var detailsHtml = log.details
                ? '<code class="small text-muted d-block" ' +
                'style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" ' +
                'title="' + window._esc(JSON.stringify(log.details)) + '">' +
                window._esc(JSON.stringify(log.details)) + '</code>'
                : '<span class="text-muted small">&mdash;</span>';

            return '<tr>' +
                '<td class="text-muted small">' + rowNum + '</td>' +
                '<td><code class="small text-nowrap">' + window._esc(log.action) + '</code></td>' +
                '<td><span class="badge ' + _targetTypeBadge(log.target_type) + '">' +
                window._esc(log.target_type) + '</span></td>' +
                '<td class="small text-muted text-center">' + (log.target_id || '&mdash;') + '</td>' +
                '<td class="small text-muted text-center">' + (log.admin_id || '&mdash;') + '</td>' +
                '<td class="small font-monospace text-muted">' + window._esc(log.ip_address) + '</td>' +
                '<td>' + detailsHtml + '</td>' +
                '<td class="small text-muted text-nowrap">' + window._formatDateTime(log.created_at) + '</td>' +
                '</tr>';
        }).join("");

        _renderPagination("alPaginationControls", "alPaginationInfo", data, "loadAuditLogs");

    } catch (err) {
        tbody.innerHTML = _errorRow(8, err.detail || "Failed to load audit logs.");
    }
}

function _targetTypeBadge(type) {
    var map = {
        user: "bg-primary-subtle text-primary",
        course: "bg-success-subtle text-success",
        exam: "bg-warning-subtle text-warning",
        enrollment: "bg-info-subtle text-info",
        assignment: "bg-secondary-subtle text-secondary",
    };
    return map[type] || "bg-secondary-subtle text-secondary";
}

// ══════════════════════════════════════════════════════════════════
// CSV EXPORT
// ══════════════════════════════════════════════════════════════════

async function exportAuditCsv() {
    var action = document.getElementById("alAction").value.trim().toUpperCase();
    var targetType = document.getElementById("alTargetType").value;
    var btn = document.getElementById("exportCsvBtn");

    var url = "/api/admin/logs/audit/export?";
    if (action) url += "action=" + encodeURIComponent(action) + "&";
    if (targetType) url += "target_type=" + encodeURIComponent(targetType) + "&";

    btn.disabled = true;
    btn.innerHTML =
        '<span class="spinner-border spinner-border-sm me-1" role="status"></span>Exporting&hellip;';

    try {
        // apiFetch returns the raw Response for non-JSON (CSV) content
        var response = await window.apiFetch(url);
        if (!response) return;

        var blob = await response.blob();

        // Extract filename from Content-Disposition header
        var disposition = response.headers.get("Content-Disposition") || "";
        var match = disposition.match(/filename=([^;]+)/);
        var filename = match ? match[1].trim() : "audit_log.csv";

        // Trigger browser download
        var objectUrl = URL.createObjectURL(blob);
        var anchor = document.createElement("a");
        anchor.href = objectUrl;
        anchor.download = filename;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(objectUrl);

    } catch (err) {
        alert(err.detail || "CSV export failed. Please try again.");
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-download me-1"></i>Export CSV';
    }
}

// ══════════════════════════════════════════════════════════════════
// SHARED PAGINATION RENDERER
// ══════════════════════════════════════════════════════════════════

function _renderPagination(navId, infoId, data, loadFnName) {
    var info = document.getElementById(infoId);
    var nav = document.getElementById(navId);

    var pageSize = data.page_size;
    var start = (data.page - 1) * pageSize + 1;
    var end = Math.min(data.page * pageSize, data.total);

    info.textContent = data.total > 0
        ? "Showing " + start + "\u2013" + end + " of " + data.total
        : "No entries";

    if (data.total_pages <= 1) {
        nav.innerHTML = "";
        return;
    }

    var html = "";

    // Previous
    html +=
        '<li class="page-item ' + (!data.has_prev ? "disabled" : "") + '">' +
        '<button class="page-link" onclick="' + loadFnName + '(' + (data.page - 1) + ')"' +
        (!data.has_prev ? " disabled" : "") + '>' +
        '<i class="bi bi-chevron-left"></i></button></li>';

    // Page numbers (sliding window)
    var startP = Math.max(1, data.page - 2);
    var endP = Math.min(data.total_pages, data.page + 2);

    if (startP > 1) {
        html += '<li class="page-item"><button class="page-link" ' +
            'onclick="' + loadFnName + '(1)">1</button></li>';
        if (startP > 2) {
            html += '<li class="page-item disabled"><span class="page-link">&hellip;</span></li>';
        }
    }

    for (var p = startP; p <= endP; p++) {
        html +=
            '<li class="page-item ' + (p === data.page ? "active" : "") + '">' +
            '<button class="page-link" onclick="' + loadFnName + '(' + p + ')">' +
            p + '</button></li>';
    }

    if (endP < data.total_pages) {
        if (endP < data.total_pages - 1) {
            html += '<li class="page-item disabled"><span class="page-link">&hellip;</span></li>';
        }
        html += '<li class="page-item"><button class="page-link" ' +
            'onclick="' + loadFnName + '(' + data.total_pages + ')">' +
            data.total_pages + '</button></li>';
    }

    // Next
    html +=
        '<li class="page-item ' + (!data.has_next ? "disabled" : "") + '">' +
        '<button class="page-link" onclick="' + loadFnName + '(' + (data.page + 1) + ')"' +
        (!data.has_next ? " disabled" : "") + '>' +
        '<i class="bi bi-chevron-right"></i></button></li>';

    nav.innerHTML = html;
}

// ══════════════════════════════════════════════════════════════════
// UTILITY HELPERS
// ══════════════════════════════════════════════════════════════════

function _loadingRow(cols) {
    return '<tr><td colspan="' + cols + '" class="text-center text-muted py-4">' +
        '<div class="spinner-border spinner-border-sm me-2" role="status"></div>' +
        'Loading&hellip;</td></tr>';
}

function _emptyRow(cols, msg) {
    return '<tr><td colspan="' + cols + '" class="text-center text-muted py-4">' +
        '<i class="bi bi-inbox d-block fs-4 mb-1 opacity-50"></i>' +
        window._esc(msg) + '</td></tr>';
}

function _errorRow(cols, msg) {
    return '<tr><td colspan="' + cols + '" class="text-center text-danger py-4">' +
        '<i class="bi bi-exclamation-triangle me-2"></i>' +
        window._esc(msg) + '</td></tr>';
}

// Global exposure
window.loadSystemLogs = loadSystemLogs;
window.loadAuditLogs = loadAuditLogs;
window.exportAuditCsv = exportAuditCsv;
window._auditLoaded = _auditLoaded;
window.systemLogsPage = systemLogsPage;
window.auditLogsPage = auditLogsPage;

// Sync state when variables are modified (simple check)
Object.defineProperty(window, '_auditLoaded', {
    get: function() { return _auditLoaded; },
    set: function(v) { _auditLoaded = v; }
});
Object.defineProperty(window, 'systemLogsPage', {
    get: function() { return systemLogsPage; },
    set: function(v) { systemLogsPage = v; }
});
Object.defineProperty(window, 'auditLogsPage', {
    get: function() { return auditLogsPage; },
    set: function(v) { auditLogsPage = v; }
});
