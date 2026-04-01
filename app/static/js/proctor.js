/**
 * proctor.js
 * Hardened proctoring layer for student exams.
 * 
 * Features:
 *   - Camera access mandate before starting.
 *   - Fullscreen exit detection and UI blocking.
 *   - Tab switch detection.
 *   - Copy/Paste blocking.
 *   - Periodic snapshots.
 */

(function () {
    class Proctor {
        constructor() {
            this.attemptId = null;
            this.stream = null;
            this.captureInterval = null;
            this.SNAPSHOT_INTERVAL_MS = 60 * 1000; // 1 minute
            this.isStarted = false;
            this.cameraReady = false;

            // Bind methods
            this._onVisibilityChange = this._onVisibilityChange.bind(this);
            this._onFullscreenChange = this._onFullscreenChange.bind(this);
            this._onCopyPaste = this._onCopyPaste.bind(this);
        }

        /**
         * Called when the exam shell loads.
         * Starts monitoring for UI setup but doesn't start snapshots yet.
         */
        init(attemptId) {
            console.log("[Proctor] Initializing for attempt:", attemptId);

            // If already started for the SAME attempt, just re-check camera/FS
            if (this.isStarted && this.attemptId === attemptId) {
                this._initCamera();
                this._checkFullscreenStatus();
                return;
            }

            // If started for a DIFFERENT attempt or just clean start
            this.stop();

            this.attemptId = attemptId;
            this.cameraReady = false;

            // Global listeners (removed by stop() so add them back)
            document.addEventListener("visibilitychange", this._onVisibilityChange);
            document.addEventListener("fullscreenchange", this._onFullscreenChange);
            document.addEventListener("webkitfullscreenchange", this._onFullscreenChange);
            document.addEventListener("copy", this._onCopyPaste);
            document.addEventListener("paste", this._onCopyPaste);
            document.addEventListener("cut", this._onCopyPaste);

            // Start camera setup
            this._initCamera();

            // Monitor Fullscreen status for the setup UI
            this._intervalFs = setInterval(() => this._checkFullscreenStatus(), 500);

            this.isStarted = true;
            this._isStopping = false;
        }

        /**
         * Stop all proctoring activities (called on submit).
         */
        stop() {
            if (this.stream) {
                this.stream.getTracks().forEach(t => t.stop());
                this.stream = null;
            }
            if (this.captureInterval) clearInterval(this.captureInterval);
            if (this._intervalFs) clearInterval(this._intervalFs);

            document.removeEventListener("visibilitychange", this._onVisibilityChange);
            document.removeEventListener("fullscreenchange", this._onFullscreenChange);
            document.removeEventListener("webkitfullscreenchange", this._onFullscreenChange);
            document.removeEventListener("copy", this._onCopyPaste);
            document.removeEventListener("paste", this._onCopyPaste);
            document.removeEventListener("cut", this._onCopyPaste);

            this.isStarted = false;
            console.log("[Proctor] Stopped.");
        }

        // ── Internal Handlers ─────────────────────────────────────────────

        _onVisibilityChange() {
            if (document.visibilityState === "hidden") {
                this._logViolation("tab_switch", "User left the exam tab");
            }
        }

        _onFullscreenChange() {
            const isFs = !!(document.fullscreenElement || document.webkitFullscreenElement);
            // We only care if they EXIT fullscreen after the exam has started
            if (!isFs && this.isStarted && !this._isStopping) {
                console.warn("[Proctor] Fullscreen exited!");
                this._logViolation("fullscreen_exit", "User exited fullscreen mode");

                // Show the blocking overlay (defined in exam_attempt.html)
                const overlay = document.getElementById('proctorOverlay');
                if (overlay) overlay.classList.remove('d-none');
            }
        }

        _checkFullscreenStatus() {
            const isFs = !!(document.fullscreenElement || document.webkitFullscreenElement);
            const text = document.getElementById('fsStatusText');
            const icon = document.getElementById('fsCheckIcon');

            if (text && icon) {
                if (isFs) {
                    text.textContent = "Active";
                    text.className = "text-success small";
                    icon.innerHTML = '<i class="bi bi-check-circle-fill text-success"></i>';
                } else {
                    text.textContent = "Inactive (Required)";
                    text.className = "text-warning small";
                    icon.innerHTML = '<i class="bi bi-dash-circle text-muted"></i>';
                }
            }
            this._updateStartButton();
        }

        _onCopyPaste(e) {
            if (!this.isStarted) return;
            e.preventDefault();
            this._logViolation("copy_paste_attempt", `Blocked ${e.type} attempt`);
        }

        async _initCamera() {
            const video = document.getElementById("cameraPreview");
            const statusText = document.getElementById("cameraStatusText");
            const icon = document.getElementById("cameraCheckIcon");
            const warning = document.getElementById("setupWarning");
            const warningText = document.getElementById("setupWarningText");

            // Stop any existing stream tracks
            if (this.stream) {
                this.stream.getTracks().forEach(track => track.stop());
                this.stream = null;
            }

            try {
                this.stream = await navigator.mediaDevices.getUserMedia({
                    video: { width: { ideal: 320 }, height: { ideal: 240 } },
                    audio: false
                });

                if (video) video.srcObject = this.stream;
                console.log("[Proctor] Camera stream active");
                this.cameraReady = true;

                if (statusText) {
                    statusText.textContent = "Connected";
                    statusText.className = "text-success small";
                }
                if (icon) icon.innerHTML = '<i class="bi bi-check-circle-fill text-success"></i>';
                if (warning) warning.classList.add('d-none');

                // Start periodic snapshots
                if (!this.captureInterval) {
                    this.captureInterval = setInterval(() => this._takeSnapshot(), this.SNAPSHOT_INTERVAL_MS);
                }

            } catch (err) {
                console.error("[Proctor] Camera failed:", err);
                this.cameraReady = false;
                this._logViolation("camera_unavailable", err.name + ": " + err.message);

                if (statusText) {
                    statusText.textContent = "Access Denied / Not Found";
                    statusText.className = "text-danger small";
                }
                if (icon) icon.innerHTML = '<i class="bi bi-x-circle-fill text-danger"></i>';

                if (warning && warningText) {
                    warning.classList.remove('d-none');
                    warningText.textContent = "Camera access is mandatory. Please grant permission in your browser and click Retry.";
                }
            }
            this._updateStartButton();
        }

        _updateStartButton() {
            const btn = document.getElementById('startExamBtn');
            if (!btn) return;
            // Require camera + fullscreen to be ready (fullscreen check is usually manual or via click)
            // But here we only disable if camera is missing.
            btn.disabled = !this.cameraReady;
        }

        async _takeSnapshot() {
            if (!this.stream || document.visibilityState === 'hidden') return;

            const video = document.getElementById("cameraPreview");
            // ReadyState 4 = HAVE_ENOUGH_DATA
            if (!video || video.readyState !== 4) return;

            try {
                const canvas = document.createElement("canvas");
                canvas.width = video.videoWidth || 320;
                canvas.height = video.videoHeight || 240;
                const ctx = canvas.getContext("2d");
                ctx.drawImage(video, 0, 0);

                const b64 = canvas.toDataURL("image/jpeg", 0.6).split(",")[1];

                await fetch(`/api/student/attempts/${this.attemptId}/snapshots`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Authorization": `Bearer ${localStorage.getItem('access_token')}` // Fallback if apiFetch not used
                    },
                    body: JSON.stringify({ image_b64: b64 })
                });
            } catch (e) {
                console.warn("[Proctor] Snapshot failed", e);
            }
        }

        async _logViolation(type, details) {
            if (!this.attemptId || !this.isStarted) return;
            console.log(`[Proctor] Logging violation: ${type} - ${details}`);
            try {
                const url = `/api/student/attempts/${this.attemptId}/violations?violation_type=${type}&details=${encodeURIComponent(details)}`;
                // Use fetch directly if window.apiFetch is not yet initialized or for simplicity
                if (window.apiFetch) {
                    await window.apiFetch(url, { method: "POST" });
                } else {
                    await fetch(url, {
                        method: "POST",
                        headers: { "Authorization": `Bearer ${localStorage.getItem('access_token')}` }
                    });
                }
            } catch (err) {
                console.error("[Proctor] Failed to log violation", err);
            }
        }
    }

    // Singleton instance
    const instance = new Proctor();
    window.initProctor = (aid) => instance.init(aid);
    window.retryProctorCamera = () => instance._initCamera();
    window.stopProctor = () => {
        instance._isStopping = true;
        instance.stop();
    };
})();
