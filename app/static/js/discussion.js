/**
 * discussion.js
 * Extracted from discussion.html
 */

let currentUser = null;
let currentPostId = null;
let savedScrollPos = 0;
let currentPage = 1;
let currentSearch = "";
let searchTimeout = null;

// Auth Ready
(function () {
    const originalOnAuthReady = window.__onAuthReady;
    window.__onAuthReady = async function (user) {
        if (typeof originalOnAuthReady === "function") await originalOnAuthReady(user);
        currentUser = user;
        initForum();
    };
})();

function initForum() {
    // Render New Post button if admin or teacher
    if (currentUser.role === 'admin' || currentUser.role === 'teacher') {
        const btnWrapper = document.getElementById("new-post-btn-wrapper");
        if (btnWrapper) {
            btnWrapper.innerHTML = `
                <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#newPostModal">
                    <i class="bi bi-plus-lg"></i> New Post
                </button>`;
        }
    }

    // Search debounce
    const searchInput = document.getElementById("forum-search");
    const clearBtn = document.getElementById("search-clear-btn");

    if (searchInput) {
        searchInput.addEventListener("input", (e) => {
            currentSearch = e.target.value.trim();
            if (clearBtn) clearBtn.style.display = currentSearch ? "block" : "none";
            window._debounce(() => loadPosts(1), 400)();
        });
    }

    if (clearBtn) {
        clearBtn.addEventListener("click", () => {
            if (searchInput) searchInput.value = "";
            currentSearch = "";
            clearBtn.style.display = "none";
            loadPosts(1);
        });
    }

    // Char counters
    const applyCounter = (id, countId, limit) => {
        const el = document.getElementById(id);
        const counter = document.getElementById(countId);
        if (!el || !counter) return;
        el.addEventListener("input", () => {
            const count = el.value.length;
            counter.innerText = `${count} / ${limit}`;
            counter.classList.toggle("limit-near", count > limit - 100);
        });
    };
    applyCounter("post-body", "post-body-count", 5000);

    loadPosts(1);

    // Fetch schools for restriction modal
    if (currentUser.role === 'admin' || currentUser.role === 'teacher') {
        const schoolSelect = document.getElementById("restrict-school");
        const branchSelect = document.getElementById("restrict-branch");
        const modal = document.getElementById("newPostModal");
        let _loadedSchools = [];

        if (modal && schoolSelect) {
            modal.addEventListener("show.bs.modal", async () => {
                if (schoolSelect.options.length <= 1) {
                    try {
                        _loadedSchools = await window.apiFetch("/api/admin/schools");
                        _loadedSchools.forEach(s => {
                            const opt = document.createElement("option");
                            opt.value = s.id;
                            opt.dataset.code = s.code;
                            opt.innerText = `${s.name} (${s.code})`;
                            schoolSelect.appendChild(opt);
                        });
                    } catch (e) { console.error("Failed to load schools", e); }
                }
            });

            schoolSelect.addEventListener("change", () => {
                if (branchSelect) {
                    branchSelect.innerHTML = '<option value="">-- All Branches --</option>';
                    if (!schoolSelect.value) {
                        branchSelect.disabled = true;
                        return;
                    }
                    branchSelect.disabled = false;
                    const school = _loadedSchools.find(s => String(s.id) === schoolSelect.value);
                    if (school && school.branches) {
                        school.branches.forEach(b => {
                            const opt = document.createElement("option");
                            opt.value = b.id;
                            opt.innerText = `${b.name} (${b.code})`;
                            branchSelect.appendChild(opt);
                        });
                    }
                }
            });
        }
    }
}

async function loadPosts(page) {
    currentPage = page;
    const container = document.getElementById("posts-container");
    if (!container) return;
    container.innerHTML = '<div class="text-center py-4"><div class="spinner-border text-primary" role="status"></div></div>';

    try {
        const url = `/api/discussion/posts?page=${page}&per_page=20&search=${encodeURIComponent(currentSearch)}`;
        const data = await window.apiFetch(url);

        if (!data.posts.length) {
            container.innerHTML = `
                <div class="text-center py-5">
                    <i class="bi bi-chat-dots display-1 text-muted"></i>
                    <p class="mt-3 text-muted">${currentUser.role === 'student' ? 'No posts yet.' : 'No posts yet. Be the first to start a discussion.'}</p>
                </div>`;
            const pag = document.getElementById("forum-pagination");
            if (pag) pag.innerHTML = "";
            return;
        }

        container.innerHTML = data.posts.map(p => `
            <div class="list-group-item post-item p-3" onclick="viewPost(${p.id})">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <h5 class="mb-0 fw-bold">
                        ${p.is_pinned ? '<span class="badge bg-warning text-dark me-2 pinned-badge"><i class="bi bi-pin-fill"></i> PINNED</span>' : ''}
                        ${p.is_restricted ? '<i class="bi bi-shield-lock-fill text-primary me-1" title="Restricted Access"></i>' : ''}
                        ${window._esc(p.title)}
                    </h5>
                    <div class="small text-muted d-flex align-items-center">
                         <span class="me-3"><i class="bi bi-reply"></i> ${p.reply_count} replies</span>
                         <span>${window._relativeTime(p.created_at)}</span>
                    </div>
                </div>
                <div class="small text-muted mb-2">
                    Posted by ${window._esc(p.author_email)} ${window._roleBadge(p.author_role)}
                </div>
                <p class="mb-0 text-secondary text-truncate" style="max-width: 90%;">${window._esc(p.body_preview)}</p>
            </div>
        `).join("");

        renderPagination(data);

    } catch (err) {
        container.innerHTML = `<div class="alert alert-danger">Failed to load posts: ${err.detail || err.message}</div>`;
    }
}

function renderPagination(data) {
    const nav = document.getElementById("forum-pagination");
    if (!nav) return;
    if (data.pages <= 1) {
        nav.innerHTML = "";
        return;
    }

    let html = '<ul class="pagination justify-content-center">';
    html += `<li class="page-item ${data.page === 1 ? 'disabled' : ''}"><a class="page-link" href="#" onclick="loadPosts(${data.page - 1})">Previous</a></li>`;

    for (let i = 1; i <= data.pages; i++) {
        html += `<li class="page-item ${data.page === i ? 'active' : ''}"><a class="page-link" href="#" onclick="loadPosts(${i})">${i}</a></li>`;
    }

    html += `<li class="page-item ${data.page === data.pages ? 'disabled' : ''}"><a class="page-link" href="#" onclick="loadPosts(${data.page + 1})">Next</a></li>`;
    html += '</ul>';
    nav.innerHTML = html;
}

window.viewPost = async function (id) {
    savedScrollPos = window.scrollY;
    currentPostId = id;

    const detailView = document.getElementById("view-post-detail");
    const listView = document.getElementById("view-post-list");
    const content = document.getElementById("post-detail-content");

    if (listView) listView.style.display = "none";
    if (detailView) detailView.style.display = "block";
    window.scrollTo(0, 0);

    if (content) content.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary" role="status"></div></div>';

    try {
        const post = await window.apiFetch(`/api/discussion/posts/${id}`);

        let restrictionHtml = '';
        if (post.is_restricted) {
            const parts = [];
            if (post.restrict_school_name) parts.push(`School: ${post.restrict_school_name}`);
            if (post.restrict_branch_name) parts.push(`Branch: ${post.restrict_branch_name}`);
            if (post.restrict_batch_year) parts.push(`Batch: ${post.restrict_batch_year}`);
            if (post.restrict_emails && post.restrict_emails.length) {
                parts.push(`Emails: ${post.restrict_emails.join(", ")}`);
            }
            restrictionHtml = `
                <div class="alert alert-info py-2 px-3 mb-3" style="font-size: 0.85rem;">
                    <i class="bi bi-shield-lock-fill me-2"></i> <strong>Restricted to:</strong> ${parts.join(" | ") || "Specific criteria"}
                </div>`;
        }

        if (content) {
            content.innerHTML = `
                ${restrictionHtml}
                <div class="d-flex justify-content-between align-items-start mb-3">
                    <div>
                        <h2 class="fw-bold mb-1">
                            ${post.is_pinned ? '<i class="bi bi-pin-angle-fill text-warning"></i> ' : ''}
                            ${window._esc(post.title)}
                        </h2>
                        <div class="small text-muted">
                            Posted by ${window._esc(post.author_email)} ${window._roleBadge(post.author_role)} &bull; ${new Date(post.created_at).toLocaleString()}
                        </div>
                    </div>
                    <div class="d-flex gap-2">
                        ${post.can_pin ? `<button class="btn btn-outline-warning btn-sm" onclick="togglePin(${post.id}, ${post.is_pinned})">
                            <i class="bi ${post.is_pinned ? 'bi-pin-angle' : 'bi-pin-angle-fill'}"></i> ${post.is_pinned ? 'Unpin Post' : 'Pin Post'}
                        </button>` : ''}
                        ${post.can_delete ? `<button class="btn btn-outline-danger btn-sm" onclick="deletePost(${post.id})">
                            <i class="bi bi-trash"></i> Delete Post
                        </button>` : ''}
                    </div>
                </div>

                <div class="content-card mb-4">
                     <div class="post-body" style="white-space: pre-wrap; line-height: 1.6;">${window._esc(post.body)}</div>
                </div>

                <hr class="my-5" />

                <h5 class="mb-4 fw-bold">Replies (<span id="reply-count-val">${post.replies.length}</span>)</h5>
                
                <div id="replies-list" class="mb-5">
                    ${post.replies.length === 0
                        ? '<p class="text-muted italic" id="no-replies-msg">No replies yet. Be the first to reply.</p>'
                        : post.replies.map(r => renderReplyCard(r)).join("")
                    }
                </div>

                <!-- Sticky Composer -->
                <div class="sticky-composer">
                    <div id="reply-alert" class="alert alert-danger d-none mb-2" role="alert"></div>
                    <div class="content-card border-primary">
                        <textarea id="reply-body" class="form-control mb-2" rows="3" placeholder="Write a reply..." maxlength="2000"></textarea>
                        <div class="d-flex justify-content-between align-items-center">
                            <span id="reply-body-count" class="char-counter">0 / 2000</span>
                            <button class="btn btn-primary" onclick="submitReply()">Post Reply</button>
                        </div>
                    </div>
                </div>
            `;

            // Add character counter listener for reply
            const rb = document.getElementById("reply-body");
            const rbc = document.getElementById("reply-body-count");
            if (rb && rbc) {
                rb.addEventListener("input", () => {
                    rbc.innerText = `${rb.value.length} / 2000`;
                    rbc.classList.toggle("limit-near", rb.value.length > 1900);
                });
            }
        }

    } catch (err) {
        if (content) content.innerHTML = `<div class="alert alert-danger">Failed to load post detail: ${err.detail || err.message}</div>`;
    }
}

function renderReplyCard(r) {
    return `
        <div class="card reply-card mb-3 shadow-sm border-0 bg-light-subtle" id="reply-${r.id}">
            <div class="card-body p-3">
                <div class="d-flex justify-content-between mb-2">
                    <div class="small fw-bold">
                        ${window._esc(r.author_email)} ${window._roleBadge(r.author_role)}
                    </div>
                    <div class="small text-muted d-flex align-items-center">
                        <span>${window._relativeTime(r.created_at)}</span>
                        ${r.can_delete ? `<button class="btn btn-link btn-sm text-danger p-0 ms-2" title="Delete Reply" onclick="deleteReply(${r.id})"><i class="bi bi-trash"></i></button>` : ''}
                    </div>
                </div>
                <div class="reply-text" style="white-space: pre-wrap;">${window._esc(r.body)}</div>
            </div>
        </div>
    `;
}

window.backToList = function () {
    const detailView = document.getElementById("view-post-detail");
    const listView = document.getElementById("view-post-list");
    if (detailView) detailView.style.display = "none";
    if (listView) listView.style.display = "block";
    window.scrollTo(0, savedScrollPos);
    loadPosts(currentPage);
}

window.submitNewPost = async function () {
    const title = document.getElementById("post-title").value.trim();
    const body = document.getElementById("post-body").value.trim();
    const alert = document.getElementById("modal-alert");
    const btn = document.getElementById("btn-submit-post");

    // Restrictions
    const schoolId = document.getElementById("restrict-school").value;
    const branchId = document.getElementById("restrict-branch").value;
    const year = document.getElementById("restrict-year").value.trim();
    const emailsRaw = document.getElementById("restrict-emails").value.trim();
    const emails = emailsRaw ? emailsRaw.split(",").map(e => e.trim()).filter(e => e) : null;

    if (!title || !body) return;

    if (btn) btn.disabled = true;
    if (alert) alert.classList.add("d-none");

    try {
        await window.apiFetch("/api/discussion/posts", {
            method: "POST",
            body: JSON.stringify({
                title,
                body,
                restrict_school_id: schoolId || null,
                restrict_branch_id: branchId || null,
                restrict_batch_year: year || null,
                restrict_emails: emails
            })
        });

        // Success
        const modalEl = document.getElementById('newPostModal');
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
        const form = document.getElementById("new-post-form");
        if (form) form.reset();
        
        const resBranch = document.getElementById("restrict-branch");
        if (resBranch) resBranch.disabled = true;
        const bodyCount = document.getElementById("post-body-count");
        if (bodyCount) bodyCount.innerText = "0 / 5000";
        
        if (typeof window._showToast === "function") window._showToast("success", "Post created successfully");
        loadPosts(1);
        window.scrollTo(0, 0);

    } catch (err) {
        if (alert) {
            alert.innerText = err.detail || err.message;
            alert.classList.remove("d-none");
        }
    } finally {
        if (btn) btn.disabled = false;
    }
}

window.submitReply = async function () {
    const body = document.getElementById("reply-body").value.trim();
    const alertArr = document.getElementById("reply-alert");

    if (!body) return;

    try {
        const res = await window.apiFetch(`/api/discussion/posts/${currentPostId}/replies`, {
            method: "POST",
            body: JSON.stringify({ body })
        });

        // Append to UI without full reload
        const list = document.getElementById("replies-list");
        const noMsg = document.getElementById("no-replies-msg");
        if (noMsg) noMsg.remove();

        const countVal = document.getElementById("reply-count-val");
        if (countVal) countVal.innerText = parseInt(countVal.innerText) + 1;

        const newReply = {
            id: res.id,
            body: body,
            author_email: currentUser.email,
            author_role: currentUser.role,
            created_at: new Date().toISOString(),
            can_delete: true
        };

        if (list) {
            const div = document.createElement("div");
            div.innerHTML = renderReplyCard(newReply);
            list.appendChild(div.firstElementChild);
        }

        const rb = document.getElementById("reply-body");
        if (rb) rb.value = "";
        const rbc = document.getElementById("reply-body-count");
        if (rbc) rbc.innerText = "0 / 2000";
        if (alertArr) alertArr.classList.add("d-none");
        if (typeof window._showToast === "function") window._showToast("success", "Reply posted");

    } catch (err) {
        if (alertArr) {
            alertArr.innerText = err.detail || err.message;
            alertArr.classList.remove("d-none");
        }
    }
}

window.togglePin = async function (postId, currentPinned) {
    try {
        const res = await window.apiFetch(`/api/discussion/posts/${postId}/pin`, { method: "PATCH" });
        if (typeof window._showToast === "function") window._showToast("success", res.message);
        viewPost(postId); // Refresh current view
    } catch (err) {
        if (typeof window._showToast === "function") window._showToast("error", err.detail || err.message);
    }
}

window.deletePost = async function (postId) {
    if (!confirm("Delete this post and all its replies?")) return;
    try {
        await window.apiFetch(`/api/discussion/posts/${postId}`, { method: "DELETE" });
        if (typeof window._showToast === "function") window._showToast("success", "Post deleted");
        backToList();
    } catch (err) {
        if (typeof window._showToast === "function") window._showToast("error", err.detail || err.message);
    }
}

window.deleteReply = async function (replyId) {
    if (!confirm("Delete this reply?")) return;
    try {
        await window.apiFetch(`/api/discussion/replies/${replyId}`, { method: "DELETE" });
        if (typeof window._showToast === "function") window._showToast("success", "Reply deleted");

        // Remove from UI
        const card = document.getElementById(`reply-${replyId}`);
        if (card) {
            card.remove();
            const countVal = document.getElementById("reply-count-val");
            if (countVal) countVal.innerText = Math.max(0, parseInt(countVal.innerText) - 1);
        }
    } catch (err) {
        if (typeof window._showToast === "function") window._showToast("error", err.detail || err.message);
    }
}
