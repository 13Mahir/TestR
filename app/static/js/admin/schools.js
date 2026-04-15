/**
 * admin/schools.js
 * Extracted from admin/schools.html
 */

(function () {
    var _prev = window.__onAuthReady;
    window.__onAuthReady = async function (user) {
        if (typeof _prev === "function") await _prev(user);
        await loadSchools();
    };
})();

async function loadSchools() {
    const container = document.getElementById("schoolsContainer");
    try {
        const schools = await window.apiFetch("/api/admin/schools");
        if (!schools) return;

        if (schools.length === 0) {
            container.innerHTML = `
            <div class="col-12 text-center py-5">
              <i class="bi bi-folder-x display-1 text-muted"></i>
              <p class="mt-3 text-muted">No schools found in the database.</p>
            </div>`;
            return;
        }

        container.innerHTML = schools.map(s => `
          <div class="col-12 col-lg-6">
            <div class="content-card school-card h-100">
              <div class="d-flex justify-content-between align-items-start mb-3">
                <div>
                  <div class="badge bg-primary-subtle text-primary mb-2">Code: ${window._esc(s.code)}</div>
                  <h4 class="fw-bold mb-1">${window._esc(s.name)}</h4>
                  <div class="small text-muted">${s.branches.length} Academic Branches</div>
                </div>
                <div class="logo-circle bg-primary bg-opacity-10 text-primary rounded-circle d-flex align-items-center justify-content-center" style="width:48px; height:48px;">
                   <i class="bi bi-building fs-4"></i>
                </div>
              </div>
              <div class="mb-3">
                 <button class="btn btn-outline-primary btn-xs" onclick="prepareAddBranch(${s.id}, '${window._esc(s.name)}')">
                   <i class="bi bi-plus"></i> Add Branch
                 </button>
              </div>
              <hr class="text-muted opacity-25" />
              <div class="mt-3">
                <h6 class="text-uppercase small fw-bold text-muted mb-3">Associated Branches</h6>
                <div class="d-flex flex-wrap">
                  ${s.branches.length > 0
                ? s.branches.map(b => `
                        <div class="branch-tag" title="${window._esc(b.name)}">
                          <span class="fw-bold text-primary me-2">${window._esc(b.code)}</span>
                          <span class="text-truncate" style="max-width: 200px;">${window._esc(b.name)}</span>
                        </div>
                      `).join('')
                : '<div class="text-muted small italic">No branches defined for this school.</div>'
            }
                </div>
              </div>
            </div>
          </div>
        `).join('');

    } catch (err) {
        container.innerHTML = `
          <div class="col-12">
            <div class="alert alert-danger">
              <i class="bi bi-exclamation-triangle me-2"></i>
              Failed to load schools: ${window._esc(err.detail || err.message)}
            </div>
          </div>`;
    }
}

// Global exposure
window.loadSchools = loadSchools;

async function handleCreateSchool(e) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());

    try {
        await window.apiFetch("/api/admin/schools", {
            method: "POST",
            body: JSON.stringify(data)
        });
        window.showNotification("School created successfully!", "success");
        form.reset();
        bootstrap.Modal.getInstance(document.getElementById("addSchoolModal")).hide();
        await loadSchools();
    } catch (err) {
        window.showNotification(err.detail || "Failed to create school", "danger");
    }
}

function prepareAddBranch(schoolId, schoolName) {
    document.getElementById("targetSchoolId").value = schoolId;
    document.getElementById("targetSchoolName").innerText = schoolName;
    new bootstrap.Modal(document.getElementById("addBranchModal")).show();
}

async function handleCreateBranch(e) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());
    data.school_id = parseInt(data.school_id);

    try {
        await window.apiFetch("/api/admin/branches", {
            method: "POST",
            body: JSON.stringify(data)
        });
        window.showNotification("Branch added successfully!", "success");
        form.reset();
        bootstrap.Modal.getInstance(document.getElementById("addBranchModal")).hide();
        await loadSchools();
    } catch (err) {
        window.showNotification(err.detail || "Failed to add branch", "danger");
    }
}

window.handleCreateSchool = handleCreateSchool;
window.prepareAddBranch = prepareAddBranch;
window.handleCreateBranch = handleCreateBranch;
