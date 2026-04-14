"""Flask 웹 서버 - 리모컨 UI 및 REST API"""

import logging
import os
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
from app.playlists import PlaylistManager

logger = logging.getLogger(__name__)

app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(__file__), "templates"),
            static_folder=os.path.join(os.path.dirname(__file__), "static"))
app.config["SECRET_KEY"] = os.urandom(24).hex()
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent")

# 전역 참조 (main에서 주입)
_radio = None
_playlists = None


def init_web(radio_app):
    """웹 서버에 라디오 앱 참조를 주입한다."""
    global _radio, _playlists
    _radio = radio_app
    _playlists = PlaylistManager(data_dir=os.path.dirname(os.path.dirname(os.path.dirname(__file__))) + "/data")


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
    try:
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
    except Exception as e:
        logger.error("상태 조회 오류: %s", e)
        return jsonify({"state": "stop", "volume": 50, "track": {}, "channel": {}, "elapsed": 0, "duration": 0})


@app.route("/api/play", methods=["POST"])
def api_play():
    """재생/일시정지."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    try:
        _radio.toggle_play_pause()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("재생 오류: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/stop", methods=["POST"])
def api_stop():
    """정지."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    try:
        _radio.mpd.stop()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("정지 오류: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/next", methods=["POST"])
def api_next():
    """다음 채널."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    try:
        _radio.next_channel()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("다음 채널 오류: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/previous", methods=["POST"])
def api_previous():
    """이전 채널."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    try:
        _radio.previous_channel()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("이전 채널 오류: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/volume", methods=["POST"])
def api_volume():
    """볼륨 설정."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    try:
        data = request.get_json(silent=True) or {}
        vol = data.get("volume")
        if vol is not None:
            vol = max(0, min(100, int(vol)))
            _radio.mpd.set_volume(vol)
        return jsonify({"volume": _radio.mpd.get_volume()})
    except Exception as e:
        logger.error("볼륨 오류: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/volume/up", methods=["POST"])
def api_volume_up():
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    try:
        vol = _radio.mpd.volume_up(_radio.config["volume"]["step"])
        return jsonify({"volume": vol})
    except Exception as e:
        logger.error("볼륨 업 오류: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/volume/down", methods=["POST"])
def api_volume_down():
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    try:
        vol = _radio.mpd.volume_down(_radio.config["volume"]["step"])
        return jsonify({"volume": vol})
    except Exception as e:
        logger.error("볼륨 다운 오류: %s", e)
        return jsonify({"error": str(e)}), 500


# ─────────── 채널 API ───────────

@app.route("/api/channels")
def api_channels():
    """채널 목록."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    try:
        return jsonify({
            "channels": _radio.favorites.get_channels(),
            "current": _radio.favorites.get_current_index(),
        })
    except Exception as e:
        logger.error("채널 목록 오류: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/channels/<int:index>/play", methods=["POST"])
def api_channel_play(index):
    """특정 채널 재생."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    try:
        _radio.play_channel(index)
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("채널 재생 오류: %s", e)
        return jsonify({"error": str(e)}), 500


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


# ─────────── 재생목록 API ───────────

@app.route("/api/playlists")
def api_playlists():
    """저장된 재생목록 목록."""
    if not _playlists:
        return jsonify({"error": "재생목록 미초기화"}), 503
    try:
        return jsonify({
            "playlists": _playlists.get_playlists(),
        })
    except Exception as e:
        logger.error("재생목록 조회 오류: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/playlists", methods=["POST"])
def api_playlist_add():
    """재생목록 추가."""
    if not _playlists:
        return jsonify({"error": "재생목록 미초기화"}), 503
    try:
        data = request.get_json(silent=True) or {}
        title = data.get("title", "").strip()
        url = data.get("url", "").strip()
        
        if not title or not url:
            return jsonify({"error": "제목과 URL이 필요합니다"}), 400
        
        playlist = _playlists.add_playlist(title, url)
        return jsonify({"ok": True, "playlist": playlist})
    except Exception as e:
        logger.error("재생목록 추가 오류: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/playlists/<int:playlist_id>", methods=["DELETE"])
def api_playlist_delete(playlist_id):
    """재생목록 삭제."""
    if not _playlists:
        return jsonify({"error": "재생목록 미초기화"}), 503
    try:
        if _playlists.remove_playlist(playlist_id):
            return jsonify({"ok": True})
        return jsonify({"error": "재생목록을 찾을 수 없습니다"}), 404
    except Exception as e:
        logger.error("재생목록 삭제 오류: %s", e)
        return jsonify({"error": str(e)}), 500


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
    try:
        data = request.get_json(silent=True) or {}
        video_id = data.get("id", "")
        title = data.get("title", "")
        artist = data.get("artist", "")
        thumbnail = data.get("thumbnail", "")
        if not video_id:
            return jsonify({"error": "ID 필요"}), 400
        success = _radio.yt_player.play_track(video_id, title, artist=artist, thumbnail=thumbnail)
        return jsonify({"ok": success})
    except Exception as e:
        logger.error("검색 재생 오류: %s", e)
        return jsonify({"error": str(e)}), 500


# ─────────── 알람 API ───────────

@app.route("/api/alarms")
def api_alarms():
    """알람 목록."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    try:
        return jsonify({
            "alarms": _radio.alarm.get_alarms(),
            "next": _radio.alarm.get_next_alarm_str(),
        })
    except Exception as e:
        logger.error("알람 목록 오류: %s", e)
        return jsonify({"error": str(e)}), 500


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


@app.route("/api/youtube/library")
def api_youtube_library():
    """사용자의 YouTube Music 라이브러리 플레이리스트 가져오기."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    
    try:
        if not _radio.yt_player.is_authenticated():
            return jsonify({
                "error": "YouTube 로그인 필요",
                "playlists": []
            }), 401
        
        # ytmusicapi 인스턴스 가져오기
        yt = _radio.yt_player._get_ytmusic()
        
        # 사용자의 라이브러리 플레이리스트 가져오기
        try:
            playlists = yt.get_library_playlists(limit=50)
        except Exception as e:
            logger.warning("라이브러리 플레이리스트 로드 실패: %s", e)
            playlists = []
        
        # 좋아하는 곡 플레이리스트도 추가
        special_playlists = []
        try:
            liked_songs = yt.get_liked_songs(limit=1)
            if liked_songs.get("tracks") or liked_songs.get("browseId"):
                special_playlists.append({
                    "id": liked_songs.get("browseId", "LM"),
                    "title": "👍 좋아하는 곡",
                    "description": "저장된 좋아하는 곡 모음",
                    "type": "playlist"
                })
        except Exception as e:
            logger.debug("좋아하는 곡 로드 실패: %s", e)
        
        # 결과 포맷팅
        result = []
        
        # 특수 플레이리스트
        for p in special_playlists:
            result.append({
                "id": p["id"],
                "title": p["title"],
                "description": p.get("description", ""),
                "type": "playlist"
            })
        
        # 일반 플레이리스트
        for p in (playlists or []):
            result.append({
                "id": p.get("playlistId", p.get("browseId", "")),
                "title": p.get("title", ""),
                "description": p.get("description", ""),
                "type": "playlist"
            })
        
        return jsonify({
            "ok": True,
            "playlists": result,
            "count": len(result)
        })
    
    except Exception as e:
        logger.error("라이브러리 로드 오류: %s", e)
        return jsonify({"error": str(e), "playlists": []}), 500


@app.route("/api/youtube/liked-songs")
def api_youtube_liked_songs():
    """사용자의 좋아하는 곡 가져오기."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    
    try:
        if not _radio.yt_player.is_authenticated():
            return jsonify({
                "error": "YouTube 로그인 필요",
                "tracks": []
            }), 401
        
        yt = _radio.yt_player._get_ytmusic()
        liked_tracks = yt.get_liked_songs(limit=100)
        
        tracks = []
        for item in liked_tracks.get("tracks", []):
            video_id = item.get("videoId")
            if not video_id:
                continue
            
            track = {
                "id": video_id,
                "title": item.get("title", ""),
                "artist": "",
                "duration": item.get("duration", ""),
                "type": "track"
            }
            
            artists = item.get("artists", [])
            if artists:
                track["artist"] = ", ".join(a.get("name", "") for a in artists if a)
            
            thumbnail = item.get("thumbnails", [{}])
            track["thumbnail"] = thumbnail[-1].get("url", "") if thumbnail else ""
            
            tracks.append(track)
        
        return jsonify({
            "ok": True,
            "tracks": tracks,
            "count": len(tracks)
        })
    
    except Exception as e:
        logger.error("좋아하는 곡 로드 오류: %s", e)
        return jsonify({"error": str(e), "tracks": []}), 500
@app.route("/api/youtube/auth", methods=["POST"])
def api_youtube_auth():
    """YouTube 인증 처리."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    try:
        data = request.get_json(silent=True) or {}
        action = data.get("action", "")
        
        if action == "login":
            # 로컬 PC에서 생성한 headers JSON 입력
            headers_json = data.get("headers", "")
            if not headers_json:
                return jsonify({
                    "ok": False,
                    "message": "❌ headers JSON이 필요합니다\n\n설정 방법:\n1. 로컬 PC에서 python3 get_youtube_headers.py 실행\n2. 나오는 JSON 전체를 복사\n3. 웹 UI 텍스트박스에 붙여넣기"
                }), 400
            
            success, message = _radio.yt_player.set_headers_from_json(headers_json)
            if success:
                return jsonify({
                    "ok": True,
                    "message": message,
                    "authenticated": True
                })
            else:
                return jsonify({
                    "ok": False,
                    "message": message,
                    "authenticated": False
                }), 400
        
        elif action == "check":
            # 인증 상태 확인
            is_auth = _radio.yt_player.is_authenticated()
            return jsonify({
                "authenticated": is_auth,
                "message": "로그인됨" if is_auth else "로그인 필요"
            })
        
        else:
            return jsonify({"error": "알 수 없는 action"}), 400
    
    except Exception as e:
        logger.error("YouTube 인증 오류: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/play-url", methods=["POST"])
def api_play_url():
    """YouTube 플레이리스트 또는 곡 URL 직접 재생."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    
    try:
        data = request.get_json(silent=True) or {}
        url = data.get("url", "").strip()
        
        if not url:
            return jsonify({"error": "URL이 필요합니다"}), 400
        
        # URL에서 트랙 추출 및 재생
        success = _radio.yt_player.play_url(url)
        
        if success:
            return jsonify({
                "ok": True,
                "message": "재생 시작"
            })
        else:
            return jsonify({
                "ok": False,
                "message": "URL에서 트랙을 추출할 수 없습니다"
            }), 400
    
    except Exception as e:
        logger.error("URL 재생 오류: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/buttons/diagnose")
def api_buttons_diagnose():
    """버튼 진단 정보 반환."""
    if not _radio or not _radio.buttons:
        return jsonify({"error": "버튼 미초기화"}), 503
    try:
        diagnosis = _radio.buttons.diagnose()
        return jsonify(diagnosis)
    except Exception as e:
        logger.error("버튼 진단 오류: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/buttons/test", methods=["POST"])
def api_buttons_test():
    """버튼 테스트 (웹 콘솔용)."""
    if not _radio or not _radio.buttons:
        return jsonify({"error": "버튼 미초기화"}), 503
    try:
        data = request.get_json(silent=True) or {}
        button = data.get("button", "").lower()
        long_press = data.get("long", False)
        
        if button not in ["a", "b", "x", "y"]:
            return jsonify({"error": "잘못된 버튼"}), 400
        
        _radio.buttons.simulate_press(button, long=long_press)
        return jsonify({
            "ok": True,
            "button": button,
            "long": long_press,
            "message": f"버튼 {button.upper()} ({'길게' if long_press else '짧게'}) 테스트 완료"
        })
    except Exception as e:
        logger.error("버튼 테스트 오류: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/sleep", methods=["POST"])
def api_sleep_timer():
    """슬립 타이머 설정."""
    if not _radio:
        return jsonify({"error": "초기화 중"}), 503
    try:
        data = request.get_json(silent=True) or {}
        minutes = data.get("minutes", 30)
        if minutes <= 0:
            _radio.alarm.cancel_sleep_timer()
        else:
            _radio.alarm.start_sleep_timer(minutes, on_sleep=_radio.mpd.stop)
        return jsonify({"ok": True, "minutes": minutes})
    except Exception as e:
        logger.error("슬립 타이머 오류: %s", e)
        return jsonify({"error": str(e)}), 500


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
