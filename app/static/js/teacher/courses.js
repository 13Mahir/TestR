/**
 * teacher/courses.js
 * Extracted from teacher/courses.html
 */

(function () {
    const prev = window.__onAuthReady;
    window.__onAuthReady = async function (user) {
        if (typeof prev === "function") await prev(user);
        await loadCourses();
    };
})();

async function loadCourses() {
    const grid = document.getElementById("coursesGrid");
    try {
        const data = await window.apiFetch("/api/teacher/courses");
        if (!data || !data.items.length) {
            grid.innerHTML = `
        <div class="col-12 text-center text-muted py-5">
          <i class="bi bi-journal-x fs-1 d-block mb-2 opacity-50"></i>
          <p>You have not been assigned to any courses yet.</p>
        </div>`;
            return;
        }
        grid.innerHTML = data.items.map(c => `
      <div class="col-12 col-md-6 col-lg-4">
        <div class="content-card h-100">
          <div class="d-flex justify-content-between
                      align-items-start mb-2">
            <div>
              <span class="badge bg-secondary-subtle
                           text-secondary small">
                ${window._esc(c.course_code)}
              </span>
              <span class="badge ms-1 ${c.mode === 'T'
                ? 'bg-primary-subtle text-primary'
                : 'bg-info-subtle text-info'} small">
                ${c.mode === 'T' ? 'Theory' : 'Practical'}
              </span>
            </div>
            <span class="badge ${c.is_active
                ? 'bg-success-subtle text-success'
                : 'bg-danger-subtle text-danger'} small">
              ${c.is_active ? 'Active' : 'Inactive'}
            </span>
          </div>
          <h5 class="fw-semibold mb-1">${window._esc(c.name)}</h5>
          <p class="small text-muted mb-3">
            ${c.description
                ? window._esc(c.description.substring(0, 80))
                + (c.description.length > 80 ? '…' : '')
                : 'No description.'}
          </p>
          <div class="d-flex gap-3 small text-muted mb-3">
            <span>
              <i class="bi bi-people-fill text-primary me-1"></i>
              ${c.enrolled_students} students
            </span>
            <span>
              <i class="bi bi-calendar3 me-1"></i>
              Batch '${window._esc(c.year)}
            </span>
          </div>
          <div class="d-flex gap-2">
            <a href="/static/pages/teacher/exam_create.html?course_id=${c.id}&course_name=${encodeURIComponent(c.name)}"
               class="btn btn-primary btn-sm">
              <i class="bi bi-plus-circle me-1"></i>
              Create Exam
            </a>
            <a href="/static/pages/teacher/gradebook.html?course_id=${c.id}"
               class="btn btn-outline-secondary btn-sm">
              <i class="bi bi-journal-check me-1"></i>
              Exams
            </a>
          </div>
        </div>
      </div>`).join("");
    } catch (err) {
        grid.innerHTML = `
      <div class="col-12 text-center text-danger py-4">
        <i class="bi bi-exclamation-triangle me-2"></i>
        ${window._esc(err.detail || "Failed to load courses.")}
      </div>`;
    }
}

// Global exposure
window.loadCourses = loadCourses;
