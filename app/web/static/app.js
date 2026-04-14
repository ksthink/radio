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
            if (!resp.ok) {
                console.error(`❌ API ERROR ${resp.status}: ${path}`);
            }
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

    async function del(path) {
        try {
            const resp = await fetch(API + path, { method: "DELETE" });
            return await resp.json();
        } catch (e) {
            console.error("DELETE 오류:", path, e);
            return null;
        }
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
        if (data) {
            console.log("✓ 상태 갱신:", data);
            updateStatus(data);
        } else {
            console.warn("⚠️  /api/status 응답 없음");
        }
    }

    // ─── PLAYLISTS ───
    async function loadPlaylists() {
        const data = await api("/api/playlists");
        if (!data || !data.playlists) {
            console.warn("⚠️  /api/playlists 응답 없음");
            return;
        }
        
        console.log(`✓ 재생목록 로드됨: ${data.playlists.length}개`);
        
        const list = $("#playlists-list");
        list.innerHTML = "";
        
        (data.playlists || []).forEach(function (pl) {
            const div = document.createElement("div");
            div.className = "playlist-item";
            div.innerHTML = `
                <div class="pl-info">
                    <div class="pl-name">${escapeHtml(pl.title)}</div>
                    <div class="pl-url">${escapeHtml(pl.url)}</div>
                </div>
                <div class="pl-actions">
                    <button class="pl-del" data-id="${pl.id}" title="삭제">✕</button>
                </div>
            `;
            
            div.querySelector(".pl-info").onclick = () => playPlaylist(pl.url);
            div.querySelector(".pl-del").onclick = (e) => {
                e.stopPropagation();
                deletePlaylist(pl.id);
            };
            
            list.appendChild(div);
        });
    }

    function escapeHtml(text) {
        const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
        return String(text).replace(/[&<>"']/g, (m) => map[m]);
    }

    async function playPlaylist(url) {
        try {
            const res = await post("/api/play-url", { url: url });
            if (res && res.ok) {
                setTimeout(() => refreshStatus(), 500);
            } else {
                alert("❌ " + (res ? res.message : "재생 실패"));
            }
        } catch (e) {
            alert("❌ 오류: " + e.message);
        }
    }

    async function addPlaylist() {
        const title = document.getElementById("playlist-title").value.trim();
        const url = document.getElementById("playlist-url").value.trim();

        if (!title || !url) {
            alert("제목과 URL을 입력하세요");
            return;
        }

        const res = await post("/api/playlists", {
            title: title,
            url: url
        });

        if (res && res.ok) {
            document.getElementById("playlist-title").value = "";
            document.getElementById("playlist-url").value = "";
            loadPlaylists();
        } else {
            alert("❌ " + (res ? res.message : "저장 실패"));
        }
    }

    async function deletePlaylist(playlistId) {
        if (!confirm("이 재생목록을 삭제하시겠습니까?")) return;
        
        const res = await del(`/api/playlists/${playlistId}`);
        if (res && res.ok) {
            loadPlaylists();
        } else {
            alert("❌ " + (res ? res.message : "삭제 실패"));
        }
    }

    // ─── PLAYER CONTROLS ───
    function setupControls() {
        $("#btn-play").onclick = () => post("/api/play");
        $("#btn-prev").onclick = () => post("/api/previous");
        $("#btn-next").onclick = () => post("/api/next");
        $("#btn-stop").onclick = () => post("/api/stop");

        const volSlider = document.getElementById("volume-slider");
        if (volSlider) {
            volSlider.onchange = function () {
                post("/api/volume", { volume: parseInt(this.value) });
            };
        }

        $("#btn-vol-down").onclick = () => post("/api/volume/down");
        $("#btn-vol-up").onclick = () => post("/api/volume/up");

        const sleepSelect = document.getElementById("sleep-select");
        if (sleepSelect) {
            sleepSelect.onchange = function () {
                post("/api/sleep", { minutes: parseInt(this.value) });
            };
        }
    }

    // ─── LOGIN MODAL & YOUTUBE (REMOVED) ───
    // Login and YouTube library loading removed - using URL-based playback instead

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
        console.log("🔌 Socket.IO 초기화 중...");
        socket = io("", {
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            reconnectionAttempts: Infinity
        });

        socket.on("connect", () => {
            console.log("✓ Socket 연결됨");
            refreshStatus();
        });

        socket.on("status_update", (data) => {
            console.log("📡 Socket status_update:", data);
            updateStatus(data);
        });

        socket.on("disconnect", () => {
            console.log("❌ Socket 연결 해제");
        });

        socket.on("error", (err) => {
            console.error("❌ Socket 에러:", err);
        });
    }

    // ─── INIT ───
    function init() {
        console.log("🚀 PiRadio 초기화 시작");
        
        setupTabs();
        console.log("✓ 탭 설정 완료");
        
        setupControls();
        console.log("✓ 컨트롤 설정 완료");

        // Playlist add button
        const btnAddPlaylist = document.getElementById("btn-add-playlist");
        if (btnAddPlaylist) {
            btnAddPlaylist.onclick = addPlaylist;
            console.log("✓ 재생목록 추가 버튼 연결");
        } else {
            console.warn("⚠️  btn-add-playlist 버튼 없음");
        }

        // URL play button (in player tab)
        const btnPlayUrl = document.getElementById("btn-play-url");
        if (btnPlayUrl) {
            btnPlayUrl.onclick = async () => {
                const url = document.getElementById("playlist-url-input")?.value.trim() || "";
                if (!url) {
                    alert("URL을 입력하세요");
                    return;
                }

                btnPlayUrl.disabled = true;
                btnPlayUrl.textContent = "재생 중...";

                try {
                    const res = await post("/api/play-url", { url: url });
                    if (res && res.ok) {
                        document.getElementById("playlist-url-input").value = "";
                        setTimeout(() => refreshStatus(), 500);
                    } else {
                        alert("❌ " + (res ? res.message : "재생 실패"));
                    }
                } catch (e) {
                    alert("❌ 오류: " + e.message);
                }

                btnPlayUrl.disabled = false;
                btnPlayUrl.textContent = "🎵 재생";
            };
            console.log("✓ URL 재생 버튼 연결");
        } else {
            console.warn("⚠️  btn-play-url 버튼 없음");
        }

        // Enter key in URL input
        const urlInput = document.getElementById("playlist-url-input");
        if (urlInput) {
            urlInput.addEventListener("keypress", (e) => {
                if (e.key === "Enter") {
                    btnPlayUrl?.click();
                }
            });
        }

        // Load initial data
        console.log("📡 상태 로드 중...");
        refreshStatus();
        console.log("📦 재생목록 로드 중...");
        loadPlaylists();

        // Poll for updates
        pollTimer = setInterval(refreshStatus, 2000);
        console.log("⏱️  폴링 시작 (2초 간격)");

        // Connect socket
        connectSocket();
        console.log("🔌 Socket.IO 연결 중...");
        
        console.log("✅ PiRadio 초기화 완료!");
    }

    // Start when DOM is ready
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
