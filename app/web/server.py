"""Flask 웹 서버 - 리모컨 UI 및 REST API"""

import logging
import os
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO

logger = logging.getLogger(__name__)

app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(__file__), "templates"),
            static_folder=os.path.join(os.path.dirname(__file__), "static"))
app.config["SECRET_KEY"] = os.urandom(24).hex()
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent")

# 전역 참조 (main에서 주입)
_radio = None


def init_web(radio_app):
    """웹 서버에 라디오 앱 참조를 주입한다."""
    global _radio
    _radio = radio_app


# ─────────── 페이지 라우트 ───────────

@app.route("/")
def index():
    """메인 리모컨 페이지."""
    return render_template("index.html")


# ─────────── REST API ───────────

@app.route("/api/status")
def api_status():
    """현재 상태 반환."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503

    status = _radio.mpd.get_status()
    current = _radio.yt_player.get_current_track_info()
    volume = _radio.mpd.get_volume()
    channel = _radio.favorites.get_current()

    return jsonify({
        "state": status.get("state", "stop"),
        "volume": volume,
        "track": {
            "title": current.get("title", "") if current else "",
            "artist": current.get("artist", "") if current else "",
            "thumbnail": current.get("thumbnail", "") if current else "",
        },
        "channel": {
            "name": channel.get("name", "") if channel else "",
            "index": _radio.favorites.get_current_index(),
        },
        "elapsed": float(status.get("elapsed", 0)),
        "duration": float(status.get("duration", 0)),
        "alarm": _radio.alarm.get_next_alarm_str(),
        "sleep_remaining": _radio.alarm.get_sleep_remaining(),
    })


@app.route("/api/play", methods=["POST"])
def api_play():
    """재생/일시정지."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    _radio.toggle_play_pause()
    return jsonify({"ok": True})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    """정지."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    _radio.mpd.stop()
    return jsonify({"ok": True})


@app.route("/api/next", methods=["POST"])
def api_next():
    """다음 채널."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    _radio.next_channel()
    return jsonify({"ok": True})


@app.route("/api/previous", methods=["POST"])
def api_previous():
    """이전 채널."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    _radio.previous_channel()
    return jsonify({"ok": True})


@app.route("/api/volume", methods=["POST"])
def api_volume():
    """볼륨 설정."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    data = request.get_json(silent=True) or {}
    vol = data.get("volume")
    if vol is not None:
        vol = max(0, min(100, int(vol)))
        _radio.mpd.set_volume(vol)
    return jsonify({"volume": _radio.mpd.get_volume()})


@app.route("/api/volume/up", methods=["POST"])
def api_volume_up():
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    vol = _radio.mpd.volume_up(_radio.config["volume"]["step"])
    return jsonify({"volume": vol})


@app.route("/api/volume/down", methods=["POST"])
def api_volume_down():
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    vol = _radio.mpd.volume_down(_radio.config["volume"]["step"])
    return jsonify({"volume": vol})


# ─────────── 채널 API ───────────

@app.route("/api/channels")
def api_channels():
    """채널 목록."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    return jsonify({
        "channels": _radio.favorites.get_channels(),
        "current": _radio.favorites.get_current_index(),
    })


@app.route("/api/channels/<int:index>/play", methods=["POST"])
def api_channel_play(index):
    """특정 채널 재생."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    _radio.play_channel(index)
    return jsonify({"ok": True})


@app.route("/api/channels", methods=["POST"])
def api_channel_add():
    """채널 추가."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    ch_id = data.get("id", "").strip()
    ch_type = data.get("type", "playlist")
    if not name or not ch_id:
        return jsonify({"error": "이름과 ID 필요"}), 400
    channel = _radio.favorites.add_channel(
        ch_id, name, ch_type,
        description=data.get("description", ""),
    )
    return jsonify({"ok": True, "channel": channel})


@app.route("/api/channels/<int:index>", methods=["DELETE"])
def api_channel_delete(index):
    """채널 삭제."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    if _radio.favorites.remove_channel(index):
        return jsonify({"ok": True})
    return jsonify({"error": "잘못된 인덱스"}), 404


# ─────────── 검색 API ───────────

@app.route("/api/search")
def api_search():
    """YouTube Music 검색."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    query = request.args.get("q", "").strip()
    search_type = request.args.get("type", "songs")
    if not query:
        return jsonify({"results": []})
    try:
        if search_type == "podcasts":
            results = _radio.yt_player.search_podcasts(query)
        else:
            results = _radio.yt_player.search(query, filter_type=search_type)
        return jsonify({"results": results})
    except Exception as e:
        logger.error("검색 오류: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/search/play", methods=["POST"])
def api_search_play():
    """검색 결과 재생."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    data = request.get_json(silent=True) or {}
    video_id = data.get("id", "")
    title = data.get("title", "")
    if not video_id:
        return jsonify({"error": "ID 필요"}), 400
    success = _radio.yt_player.play_track(video_id, title)
    return jsonify({"ok": success})


# ─────────── 알람 API ───────────

@app.route("/api/alarms")
def api_alarms():
    """알람 목록."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    return jsonify({
        "alarms": _radio.alarm.get_alarms(),
        "next": _radio.alarm.get_next_alarm_str(),
    })


@app.route("/api/alarms", methods=["POST"])
def api_alarm_add():
    """알람 추가."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    data = request.get_json(silent=True) or {}
    hour = data.get("hour", 7)
    minute = data.get("minute", 0)
    days = data.get("days")
    channel_id = data.get("channel_id")
    label = data.get("label", "")
    alarm = _radio.alarm.add_alarm(hour, minute, days, channel_id, label)
    return jsonify({"ok": True, "alarm": alarm})


@app.route("/api/alarms/<int:alarm_id>", methods=["DELETE"])
def api_alarm_delete(alarm_id):
    """알람 삭제."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    _radio.alarm.remove_alarm(alarm_id)
    return jsonify({"ok": True})


@app.route("/api/alarms/<int:alarm_id>/toggle", methods=["POST"])
def api_alarm_toggle(alarm_id):
    """알람 토글."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    enabled = _radio.alarm.toggle_alarm(alarm_id)
    return jsonify({"ok": True, "enabled": enabled})


@app.route("/api/sleep", methods=["POST"])
def api_sleep_timer():
    """슬립 타이머 설정."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    data = request.get_json(silent=True) or {}
    minutes = data.get("minutes", 30)
    if minutes <= 0:
        _radio.alarm.cancel_sleep_timer()
    else:
        _radio.alarm.start_sleep_timer(minutes, on_sleep=_radio.mpd.stop)
    return jsonify({"ok": True, "minutes": minutes})


# ─────────── WebSocket 이벤트 ───────────

@socketio.on("connect")
def on_connect():
    logger.debug("WebSocket 연결")


@socketio.on("button")
def on_button(data):
    """웹에서 버튼 시뮬레이션."""
    if _radio and _radio.buttons:
        name = data.get("name", "")
        long_press = data.get("long", False)
        _radio.buttons.simulate_press(name, long=long_press)


def broadcast_status(status_data):
    """상태 변경을 모든 클라이언트에 브로드캐스트."""
    socketio.emit("status", status_data)


def run_server(host="0.0.0.0", port=8080):
    """웹 서버 실행."""
    logger.info("웹 서버 시작: http://%s:%d", host, port)
    socketio.run(app, host=host, port=port, allow_unsafe_werkzeug=True)
