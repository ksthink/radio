// PiRadio 웹 리모컨 (간단버전)
(function () {
    "use strict";

    const API = "";
    let socket = null;
    let pollTimer = null;

    // ─── UTILS ───
    function $(sel) { return document.querySelector(sel); }
    function $$(sel) { return document.querySelectorAll(sel); }

    function formatTime(sec) {
        sec = Math.floor(sec || 0);
        const m = Math.floor(sec / 60);
        const s = sec % 60;
        return m + ":" + String(s).padStart(2, "0");
    }

    async function api(path, opts) {
        try {
            const resp = await fetch(API + path, opts);
            return await resp.json();
        } catch (e) {
            console.error("API 오류:", path, e);
            return null;
        }
    }

    function post(path, body) {
        return api(path, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: body ? JSON.stringify(body) : undefined,
        });
    }

    // ─── STATUS UPDATE ───
    function updateStatus(data) {
        if (!data) return;

        // Track info
        const t = data.track || {};
        $("#track-title").textContent = t.title || "재생 대기 중";
        $("#track-artist").textContent = t.artist || "";

        // Album art
        const artEl = $("#album-art");
        if (t.thumbnail) {
            artEl.innerHTML = `<img src="${t.thumbnail}" alt="앨범아트">`;
        } else {
            artEl.innerHTML = '<span class="music-icon">♫</span>';
        }

        // Channel
        const ch = data.channel || {};
        $("#channel-name").textContent = ch.name ? `📻 ${ch.name}` : "";

        // Play state
        const playBtn = $("#btn-play");
        playBtn.textContent = data.state === "play" ? "⏸" : "▶";

        // Progress
        $("#elapsed").textContent = formatTime(data.elapsed);
        $("#duration").textContent = formatTime(data.duration);
        const ratio = data.duration > 0 ? (data.elapsed / data.duration * 100) : 0;
        $("#progress-fill").style.width = ratio + "%";

        // Volume
        const volSlider = $("#volume-slider");
        if (document.activeElement !== volSlider) {
            volSlider.value = data.volume;
        }
        $("#volume-value").textContent = data.volume + "%";

        // Sleep timer
        const sleepRemain = $("#sleep-remaining");
        if (data.sleep_remaining && data.sleep_remaining > 0) {
            sleepRemain.textContent = formatTime(data.sleep_remaining) + " 남음";
        } else {
            sleepRemain.textContent = "";
        }
    }

    async function refreshStatus() {
        const data = await api("/api/status");
        if (data) updateStatus(data);
    }

    // ─── CHANNELS ───
    async function loadChannels() {
        const data = await api("/api/channels");
        if (!data) return;
        const list = $("#channel-list");
        list.innerHTML = "";
        (data.channels || []).forEach(function (ch, i) {
            const active = i === data.current ? " active" : "";
            const div = document.createElement("div");
            div.className = "channel-item" + active;
            div.innerHTML = `
                <div class="ch-info">
                    <div class="ch-name">${escapeHtml(ch.name)}</div>
                    <div class="ch-desc">${escapeHtml(ch.description || ch.type || "")}</div>
                </div>
                <div class="ch-actions">
                    <button class="ch-del" data-id="${i}" title="삭제">✕</button>
                </div>
            `;
            div.querySelector(".ch-info").onclick = () => post(`/api/channels/${i}/play`);
            div.querySelector(".ch-del").onclick = (e) => {
                e.stopPropagation();
                fetch(`/api/channels/${i}`, { method: "DELETE" }).then(() => loadChannels());
            };
            list.appendChild(div);
        });
    }

    function escapeHtml(text) {
        const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
        return String(text).replace(/[&<>"']/g, (m) => map[m]);
    }

    // ─── PLAYER CONTROLS ───
    function setupControls() {
        $("#btn-play").onclick = () => post("/api/play");
        $("#btn-prev").onclick = () => post("/api/prev");
        $("#btn-next").onclick = () => post("/api/next");
        $("#btn-stop").onclick = () => post("/api/stop");

        const volSlider = document.getElementById("volume-slider");
        if (volSlider) {
            volSlider.onchange = function () {
                post("/api/volume", { volume: parseInt(this.value) });
            };
        }

        $("#btn-vol-down").onclick = () => post("/api/volume/dec");
        $("#btn-vol-up").onclick = () => post("/api/volume/inc");

        const sleepSelect = document.getElementById("sleep-select");
        if (sleepSelect) {
            sleepSelect.onchange = function () {
                post("/api/sleep", { minutes: parseInt(this.value) });
            };
        }
    }

    // ─── ADD CHANNEL ───
    async function addChannel() {
        const name = document.getElementById("add-name").value.trim();
        const id = document.getElementById("add-id").value.trim();
        const type = document.getElementById("add-type").value;

        if (!name || !id) {
            alert("채널 이름과 ID를 입력하세요.");
            return;
        }

        const res = await post("/api/channels", {
            name: name,
            id: id,
            type: type
        });

        if (res && res.ok) {
            document.getElementById("add-name").value = "";
            document.getElementById("add-id").value = "";
            loadChannels();
        } else {
            alert("❌ " + (res ? res.message : "추가 실패"));
        }
    }

    // ─── LOGIN MODAL ───
    function setupLoginModal() {
        const modal = $("#login-modal");
        const loginBtn = $("#btn-login-header");
        const closeBtn = $("#btn-close-login");
        const doLoginBtn = $("#btn-do-login");
        const headersInput = $("#login-headers");

        loginBtn.onclick = () => {
            modal.style.display = "flex";
            headersInput.focus();
        };

        closeBtn.onclick = () => {
            modal.style.display = "none";
        };

        modal.onclick = (e) => {
            if (e.target === modal) modal.style.display = "none";
        };

        doLoginBtn.onclick = async () => {
            const headers = headersInput.value.trim();
            if (!headers) {
                alert("JSON을 붙여넣으세요.");
                return;
            }

            doLoginBtn.disabled = true;
            doLoginBtn.textContent = "로그인 중...";
            const status = $("#login-status");

            try {
                const result = await post("/api/youtube/auth", {
                    action: "login",
                    headers: headers
                });

                if (result && result.ok) {
                    status.className = "login-status success";
                    status.textContent = "✅ 로그인 성공!";
                    headersInput.value = "";
                    
                    setTimeout(() => {
                        modal.style.display = "none";
                        loadYouTubeLibrary();
                    }, 1000);
                } else {
                    status.className = "login-status error";
                    status.textContent = "❌ " + (result ? result.message : "로그인 실패");
                }
            } catch (e) {
                status.className = "login-status error";
                status.textContent = "❌ 오류: " + e.message;
            }

            doLoginBtn.disabled = false;
            doLoginBtn.textContent = "로그인";
        };

        headersInput.onkeypress = (e) => {
            if (e.key === "Enter" && e.ctrlKey) {
                doLoginBtn.click();
            }
        };
    }

    // ─── YOUTUBE LIBRARY ───
    async function loadYouTubeLibrary() {
        try {
            console.log("📚 YouTube 라이브러리 로드 중...");
            const data = await api("/api/youtube/library");
            
            if (!data) {
                console.error("❌ 라이브러리 API 응답 없음");
                return;
            }
            
            if (data.error) {
                console.error("❌ 라이브러리 오류:", data.error);
                return;
            }
            
            const playlists = data.playlists || [];
            console.log(`✓ ${playlists.length}개 플레이리스트 발견`);
            
            if (playlists.length === 0) {
                console.warn("⚠️  플레이리스트가 없습니다");
                return;
            }

            // Auto-add first 3 playlists (or configure as needed)
            let addedCount = 0;
            for (let i = 0; i < Math.min(playlists.length, 3); i++) {
                const pl = playlists[i];
                console.log(`  → 추가 중: "${pl.title}" (${pl.id})`);
                
                const res = await post("/api/channels", {
                    name: pl.title,
                    id: pl.id,
                    type: "playlist",
                    description: pl.description || pl.title
                });
                
                if (res && res.ok) {
                    addedCount++;
                    console.log(`  ✓ 추가됨: "${pl.title}"`);
                } else {
                    console.warn(`  ❌ 실패: "${pl.title}"`, res);
                }
            }

            console.log(`✓ ${addedCount}개 채널 추가 완료`);
            await loadChannels();
        } catch (e) {
            console.error("❌ YouTube 라이브러리 로드 오류:", e);
        }
    }

    // ─── TABS ───
    function setupTabs() {
        $$(".tab").forEach((btn) => {
            btn.onclick = function () {
                const tabId = this.getAttribute("data-tab");
                $$(".tab").forEach((b) => b.classList.remove("active"));
                $$(".tab-content").forEach((c) => c.classList.remove("active"));
                this.classList.add("active");
                document.getElementById("tab-" + tabId).classList.add("active");
            };
        });
    }

    // ─── SOCKET IO ───
    function connectSocket() {
        socket = io("", {
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            reconnectionAttempts: Infinity
        });

        socket.on("connect", () => {
            console.log("Socket connected");
            refreshStatus();
        });

        socket.on("status_update", (data) => {
            updateStatus(data);
        });

        socket.on("channels_changed", () => {
            loadChannels();
        });

        socket.on("disconnect", () => {
            console.log("Socket disconnected");
        });
    }

    // ─── INIT ───
    function init() {
        setupTabs();
        setupControls();
        setupLoginModal();

        // Channel add button
        document.getElementById("btn-add-channel").onclick = addChannel;

        // Load initial data
        refreshStatus();
        loadChannels();

        // Poll for updates
        pollTimer = setInterval(refreshStatus, 2000);

        // Connect socket
        connectSocket();
    }

    // Start when DOM is ready
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
