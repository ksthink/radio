// PiRadio 웹 리모컨 앱
(function () {
    "use strict";

    const API = "";
    let socket = null;
    let pollTimer = null;

    // ─── 유틸 ───
    function formatTime(sec) {
        sec = Math.floor(sec || 0);
        const m = Math.floor(sec / 60);
        const s = sec % 60;
        return m + ":" + String(s).padStart(2, "0");
    }

    function $(sel) { return document.querySelector(sel); }
    function $$(sel) { return document.querySelectorAll(sel); }

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

    // ─── 상태 업데이트 ───
    function updateStatus(data) {
        if (!data) return;

        // 트랙 정보
        const t = data.track || {};
        $("#track-title").textContent = t.title || "재생 대기 중";
        $("#track-artist").textContent = t.artist || "";

        // 앨범아트
        const artEl = $("#album-art");
        if (t.thumbnail) {
            artEl.innerHTML = `<img src="${t.thumbnail}" alt="앨범아트">`;
        } else {
            artEl.innerHTML = '<span class="music-icon">♫</span>';
        }

        // 채널
        const ch = data.channel || {};
        $("#channel-name").textContent = ch.name ? `📻 ${ch.name}` : "";

        // 재생 상태
        const playBtn = $("#btn-play");
        playBtn.textContent = data.state === "play" ? "⏸" : "▶";

        // 프로그레스
        $("#elapsed").textContent = formatTime(data.elapsed);
        $("#duration").textContent = formatTime(data.duration);
        const ratio = data.duration > 0 ? (data.elapsed / data.duration * 100) : 0;
        $("#progress-fill").style.width = ratio + "%";

        // 볼륨
        const volSlider = $("#volume-slider");
        if (document.activeElement !== volSlider) {
            volSlider.value = data.volume;
        }
        $("#volume-value").textContent = data.volume + "%";

        // 슬립 타이머
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

    // ─── 채널 ───
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
                    <div class="ch-desc">${escapeHtml(ch.description || ch.artist || "")}</div>
                </div>
                <div class="ch-actions">
                    <button class="ch-del" data-index="${i}" title="삭제">✕</button>
                </div>`;
            div.querySelector(".ch-info").addEventListener("click", function () {
                post("/api/channels/" + i + "/play");
            });
            div.querySelector(".ch-del").addEventListener("click", function (e) {
                e.stopPropagation();
                if (confirm("'" + ch.name + "' 채널을 삭제하시겠습니까?")) {
                    api("/api/channels/" + i, { method: "DELETE" }).then(loadChannels);
                }
            });
            list.appendChild(div);
        });
    }

    // ─── 검색 ───
    async function doSearch() {
        const q = $("#search-input").value.trim();
        const type = $("#search-type").value;
        if (!q) return;

        const data = await api("/api/search?q=" + encodeURIComponent(q) + "&type=" + type);
        const container = $("#search-results");
        container.innerHTML = "";
        if (!data || !data.results || data.results.length === 0) {
            container.innerHTML = '<div style="color:var(--text-dim);text-align:center;padding:20px">결과 없음</div>';
            return;
        }
        data.results.forEach(function (item) {
            const div = document.createElement("div");
            div.className = "search-result";
            div.innerHTML = `
                ${item.thumbnail ? `<img class="sr-thumb" src="${item.thumbnail}" alt="">` : '<div class="sr-thumb"></div>'}
                <div class="sr-info">
                    <div class="sr-title">${escapeHtml(item.title)}</div>
                    <div class="sr-artist">${escapeHtml(item.artist || item.author || "")}</div>
                </div>
                <div class="sr-actions">
                    <button class="sr-btn sr-btn-play">▶</button>
                    <button class="sr-btn sr-btn-fav">+♡</button>
                </div>`;
            div.querySelector(".sr-btn-play").addEventListener("click", function () {
                post("/api/search/play", { id: item.id, title: item.title });
            });
            div.querySelector(".sr-btn-fav").addEventListener("click", function () {
                post("/api/channels", {
                    id: item.id,
                    name: item.title,
                    type: item.type === "podcast" ? "playlist" : (item.type || "radio"),
                    description: item.artist || item.author || "",
                }).then(function () {
                    loadChannels();
                    alert("'" + item.title + "' 채널에 추가됨");
                });
            });
            container.appendChild(div);
        });
    }

    // ─── 알람 ───
    async function loadAlarms() {
        const data = await api("/api/alarms");
        if (!data) return;
        const list = $("#alarm-list");
        list.innerHTML = "";
        const dayNames = ["월", "화", "수", "목", "금", "토", "일"];
        (data.alarms || []).forEach(function (alarm) {
            const div = document.createElement("div");
            div.className = "alarm-item";
            const daysText = alarm.days
                ? alarm.days.map(function (d) { return dayNames[d]; }).join(" ")
                : "매일";
            const onOff = alarm.enabled ? "on" : "off";
            div.innerHTML = `
                <div class="alarm-time">${String(alarm.hour).padStart(2, "0")}:${String(alarm.minute).padStart(2, "0")}</div>
                <div class="alarm-info">
                    <div class="alarm-label">${escapeHtml(alarm.label || "알람")}</div>
                    <div class="alarm-days-text">${daysText}</div>
                </div>
                <button class="alarm-toggle ${onOff}" data-id="${alarm.id}"></button>
                <button class="alarm-del" data-id="${alarm.id}">✕</button>`;
            div.querySelector(".alarm-toggle").addEventListener("click", function () {
                post("/api/alarms/" + alarm.id + "/toggle").then(loadAlarms);
            });
            div.querySelector(".alarm-del").addEventListener("click", function () {
                api("/api/alarms/" + alarm.id, { method: "DELETE" }).then(loadAlarms);
            });
            list.appendChild(div);
        });
    }

    // ─── 시계 ───
    function updateClock() {
        const now = new Date();
        const h = String(now.getHours()).padStart(2, "0");
        const m = String(now.getMinutes()).padStart(2, "0");
        const s = String(now.getSeconds()).padStart(2, "0");
        $("#clock").textContent = h + ":" + m + ":" + s;
    }

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str || "";
        return div.innerHTML;
    }

    // ─── 초기화 ───
    function init() {
        // 탭 전환
        $$(".tab").forEach(function (tab) {
            tab.addEventListener("click", function () {
                $$(".tab").forEach(function (t) { t.classList.remove("active"); });
                $$(".tab-content").forEach(function (c) { c.classList.remove("active"); });
                tab.classList.add("active");
                $("#tab-" + tab.dataset.tab).classList.add("active");

                if (tab.dataset.tab === "channels") loadChannels();
                if (tab.dataset.tab === "alarm") loadAlarms();
            });
        });

        // 플레이어 컨트롤
        $("#btn-play").addEventListener("click", function () { post("/api/play"); });
        $("#btn-stop").addEventListener("click", function () { post("/api/stop"); });
        $("#btn-next").addEventListener("click", function () { post("/api/next"); });
        $("#btn-prev").addEventListener("click", function () { post("/api/previous"); });
        $("#btn-vol-up").addEventListener("click", function () { post("/api/volume/up"); });
        $("#btn-vol-down").addEventListener("click", function () { post("/api/volume/down"); });

        // 볼륨 슬라이더
        let volTimeout = null;
        $("#volume-slider").addEventListener("input", function () {
            const vol = parseInt(this.value);
            $("#volume-value").textContent = vol + "%";
            clearTimeout(volTimeout);
            volTimeout = setTimeout(function () {
                post("/api/volume", { volume: vol });
            }, 150);
        });

        // 슬립 타이머
        $("#sleep-select").addEventListener("change", function () {
            post("/api/sleep", { minutes: parseInt(this.value) });
        });

        // 검색
        $("#btn-search").addEventListener("click", doSearch);
        $("#search-input").addEventListener("keydown", function (e) {
            if (e.key === "Enter") doSearch();
        });

        // 채널 추가
        $("#btn-add-channel").addEventListener("click", function () {
            const name = $("#add-name").value.trim();
            const id = $("#add-id").value.trim();
            const type = $("#add-type").value;
            if (!name || !id) { alert("이름과 ID를 입력하세요"); return; }
            post("/api/channels", { name: name, id: id, type: type }).then(function () {
                $("#add-name").value = "";
                $("#add-id").value = "";
                loadChannels();
            });
        });

        // 알람 추가
        $("#btn-add-alarm").addEventListener("click", function () {
            const hour = parseInt($("#alarm-hour").value);
            const minute = parseInt($("#alarm-minute").value);
            const label = $("#alarm-label").value.trim();
            const dayCheckboxes = $$('.alarm-days input[type="checkbox"]:checked');
            let days = null;
            if (dayCheckboxes.length > 0 && dayCheckboxes.length < 7) {
                days = Array.from(dayCheckboxes).map(function (cb) { return parseInt(cb.value); });
            }
            post("/api/alarms", { hour: hour, minute: minute, days: days, label: label }).then(function () {
                $("#alarm-label").value = "";
                loadAlarms();
            });
        });

        // WebSocket
        try {
            socket = io();
            socket.on("status", updateStatus);
        } catch (e) {
            console.warn("WebSocket 연결 불가, 폴링 모드");
        }

        // 주기적 상태 갱신
        refreshStatus();
        pollTimer = setInterval(refreshStatus, 3000);
        setInterval(updateClock, 1000);
        updateClock();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
