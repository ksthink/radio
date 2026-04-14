"""PiRadio 메인 애플리케이션 - 모든 모듈을 통합하는 진입점"""

import logging
import os
import signal
import sys
import threading
import time

from app.config import load_config
from app.mpd_client import MPDController
from app.youtube_music import YouTubeMusicPlayer
from app.display import DisplayManager
from app.buttons import ButtonHandler
from app.alarm import AlarmManager
from app.weather import WeatherClient
from app.favorites import FavoritesManager
from app.playlists import PlaylistManager

logger = logging.getLogger("piradio")


class PiRadio:
    """메인 라디오 애플리케이션."""

    def __init__(self, config_path=None):
        self.config = load_config(config_path)
        self._running = False
        self._setup_logging()
        self._init_components()

    def _setup_logging(self):
        """로깅 설정."""
        log_cfg = self.config.get("logging", {})
        log_file = log_cfg.get("file", "logs/piradio.log")
        log_level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)

        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        logging.basicConfig(
            level=log_level,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            handlers=[
                logging.FileHandler(log_file, encoding="utf-8"),
                logging.StreamHandler(sys.stdout),
            ],
        )
        logger.info("PiRadio 시작")

    def _init_components(self):
        """모든 컴포넌트 초기화."""
        # MPD
        mpd_cfg = self.config.get("mpd", {})
        self.mpd = MPDController(
            host=mpd_cfg.get("host", "localhost"),
            port=mpd_cfg.get("port", 6600),
        )

        # YouTube Music Player (캐싱, 로그인 지원)
        yt_cfg = self.config.get("youtube", {})
        auth_file = yt_cfg.get("auth_file", "data/yt_auth.json")
        os.makedirs(os.path.dirname(auth_file), exist_ok=True)
        
        self.yt_player = YouTubeMusicPlayer(
            self.mpd,
            quality=yt_cfg.get("quality", "bestaudio"),
            buffer_tracks=yt_cfg.get("buffer_tracks", 3),
            auth_file=auth_file,
        )
        
        # YouTube 인증 상태 확인 및 로깅
        if self.yt_player.is_authenticated():
            logger.info("✓ YouTube 인증 토큰 발견 - 로그인 상태")
        else:
            logger.info("⚠️ YouTube 비로그인 - 웹 UI에서 '/api/youtube/auth' 호출로 로그인 가능")

        # 즐겨찾기
        fav_cfg = self.config.get("favorites", {})
        self.favorites = FavoritesManager(
            data_file=fav_cfg.get("data_file", "data/favorites.json"),
        )

        # 디스플레이
        disp_cfg = self.config.get("display", {})
        self.display = DisplayManager(disp_cfg)

        # 알람
        alarm_cfg = self.config.get("alarm", {})
        self.alarm = AlarmManager(
            data_file=alarm_cfg.get("data_file", "data/alarms.json"),
            on_alarm=self._on_alarm,
        )

        # 날씨
        weather_cfg = self.config.get("weather", {})
        self.weather = WeatherClient(
            api_key=weather_cfg.get("api_key", ""),
            city=weather_cfg.get("city", "Seoul"),
            units=weather_cfg.get("units", "metric"),
            update_interval=weather_cfg.get("update_interval", 1800),
        )

        # 저장된 재생목록 (버튼 네비게이션 공유)
        self.playlists = PlaylistManager(data_dir="data")
        self._playlist_index = 0

        # 버튼 (새 키 매핑)
        btn_cfg = self.config.get("buttons", {})
        self.buttons = ButtonHandler(btn_cfg, callbacks={
            "on_a_short":       self._btn_a_short,
            "on_x_single":      self._btn_x_single,
            "on_x_double":      self._btn_x_double,
            "on_seek_back":     self._btn_seek_back,
            "on_seek_forward":  self._btn_seek_forward,
            "on_volume_up":     self.volume_up,
            "on_volume_down":   self.volume_down,
        })

        logger.info("모든 컴포넌트 초기화 완료")

    # ─────────── 제어 메서드 ───────────

    def toggle_play_pause(self):
        """재생/일시정지 토글."""
        self.display.wake()
        if self.mpd.is_playing():
            self.mpd.pause()
            logger.info("일시정지")
        else:
            # 현재 플레이리스트가 비었으면 현재 채널 재생
            if self.mpd.playlist_length() == 0:
                channel = self.favorites.get_current()
                if channel:
                    try:
                        self.yt_player.play_channel(channel)
                    except Exception as e:
                        logger.error("채널 재생 실패: %s", e)
                        return
                else:
                    logger.info("재생할 채널 없음")
                    return
            else:
                self.mpd.play()
            self.display.set_mode(DisplayManager.MODE_NOW_PLAYING)
            logger.info("재생")

    def volume_up(self):
        """볼륨 올리기."""
        self.display.wake()
        step = self.config.get("volume", {}).get("step", 5)
        vol = self.mpd.volume_up(step)
        self.display.render_volume_popup(vol)
        logger.debug("볼륨: %d", vol)

    def volume_down(self):
        """볼륨 내리기."""
        self.display.wake()
        step = self.config.get("volume", {}).get("step", 5)
        vol = self.mpd.volume_down(step)
        self.display.render_volume_popup(vol)
        logger.debug("볼륨: %d", vol)

    # ─────────── 버튼 콜백 ───────────

    def _btn_a_short(self):
        """A 짧게: 이전 곡 / 재생목록에서 위로."""
        self.display.wake()
        if self.display.mode == DisplayManager.MODE_STATION_LIST:
            items = self.playlists.get_playlists()
            if items:
                self._playlist_index = max(0, self._playlist_index - 1)
                self._render_playlist_list()
        else:
            if self.yt_player._current_queue:
                self.yt_player.previous_track()
            else:
                ch = self.favorites.previous_channel()
                if ch:
                    threading.Thread(target=self.yt_player.play_channel,
                                     args=(ch,), daemon=True).start()
            self.display.set_mode(DisplayManager.MODE_NOW_PLAYING)
            logger.info("이전 트랙")

    def _btn_x_single(self):
        """X 싱글탭: 다음 곡 / 재생목록에서 아래로."""
        self.display.wake()
        if self.display.mode == DisplayManager.MODE_STATION_LIST:
            items = self.playlists.get_playlists()
            if items:
                self._playlist_index = min(len(items) - 1, self._playlist_index + 1)
                self._render_playlist_list()
        else:
            if self.yt_player._current_queue:
                self.yt_player.next_track()
            else:
                ch = self.favorites.next_channel()
                if ch:
                    threading.Thread(target=self.yt_player.play_channel,
                                     args=(ch,), daemon=True).start()
            self.display.set_mode(DisplayManager.MODE_NOW_PLAYING)
            logger.info("다음 트랙")

    def _btn_x_double(self):
        """X 더블탭: 재생목록 화면으로 / 재생목록에서 선택 재생."""
        self.display.wake()
        if self.display.mode == DisplayManager.MODE_STATION_LIST:
            items = self.playlists.get_playlists()
            if items and self._playlist_index < len(items):
                pl = items[self._playlist_index]
                logger.info("재생목록 선택: %s", pl['title'])
                self.display.set_mode(DisplayManager.MODE_NOW_PLAYING)
                threading.Thread(target=self.yt_player.play_url,
                                 args=(pl['url'],), daemon=True).start()
        else:
            self._playlist_index = 0
            self.display.set_mode(DisplayManager.MODE_STATION_LIST)
            self._render_playlist_list()
            logger.info("재생목록 화면 표시")

    def _btn_seek_back(self):
        """A 길게: -5초 seek."""
        self.display.wake()
        self.mpd.seek_relative(-5)

    def _btn_seek_forward(self):
        """X 길게: +5초 seek."""
        self.display.wake()
        self.mpd.seek_relative(5)

    def _render_playlist_list(self):
        """재생목록 화면 렌더링."""
        items = [{"name": p["title"], "description": p["url"]}
                 for p in self.playlists.get_playlists()]
        self.display.render_station_list(items, self._playlist_index)

    def next_channel(self):
        """웹 API용: 다음 트랙."""
        self._btn_x_single()

    def previous_channel(self):
        """웹 API용: 이전 트랙."""
        self._btn_a_short()

    def play_channel(self, index):
        """특정 인덱스의 채널 재생."""
        self.favorites.set_current_index(index)
        channel = self.favorites.get_current()
        if channel:
            threading.Thread(
                target=self.yt_player.play_channel, args=(channel,), daemon=True
            ).start()
            self.display.set_mode(DisplayManager.MODE_NOW_PLAYING)

    def show_station_list(self):
        """채널 목록 화면 표시."""
        self.display.wake()
        self.display.set_mode(DisplayManager.MODE_STATION_LIST)
        self.display.render_station_list(
            self.favorites.get_channels(),
            self.favorites.get_current_index(),
        )

    def show_clock(self):
        """시계/날씨 화면."""
        self.display.wake()
        self.display.set_mode(DisplayManager.MODE_CLOCK)

    def show_menu(self):
        """설정 메뉴 표시."""
        self.display.wake()
        vol = self.mpd.get_volume()
        menu_items = [
            {"label": "볼륨", "value": f"{vol}%"},
            {"label": "화면 밝기", "value": "80%"},
            {"label": "슬립 타이머", "value": "끄기"},
            {"label": "시스템 정보", "value": ""},
            {"label": "재시작", "value": ""},
        ]
        self.display.set_mode(DisplayManager.MODE_MENU)
        self.display.render_menu(menu_items, 0)

    def _on_alarm(self, alarm):
        """알람 발동 콜백."""
        logger.info("알람 발동: %s", alarm.get("label", ""))
        self.display.wake()
        self.display.show_message("⏰ 알람", alarm.get("label", "알람!"))

        # 알람 채널 재생
        channel_id = alarm.get("channel_id")
        if channel_id:
            idx, ch = self.favorites.find_by_id(channel_id)
            if ch:
                self.play_channel(idx)
                return

        # 기본: 현재 채널 재생
        channel = self.favorites.get_current()
        if channel:
            self.yt_player.play_channel(channel)

        # 볼륨을 적당히 올리기
        self.mpd.set_volume(self.config.get("volume", {}).get("default", 50))

    # ─────────── 디스플레이 업데이트 루프 ───────────

    def _display_loop(self):
        """디스플레이 주기적 업데이트."""
        while self._running:
            try:
                self.display.check_timeout()

                if self.display.mode == DisplayManager.MODE_NOW_PLAYING:
                    track_info = self.yt_player.get_current_track_info()
                    status = self.mpd.get_status()
                    state = status.get("state", "stop")
                    volume = int(status.get("volume", 50))

                    if track_info:
                        track_info["elapsed"] = float(status.get("elapsed", 0))
                        track_info["duration"] = float(status.get("duration", 0))
                    self.display.render_now_playing(track_info, state, volume)

                elif self.display.mode == DisplayManager.MODE_CLOCK:
                    weather = self.weather.get_weather()
                    alarm_time = self.alarm.get_next_alarm_str()
                    self.display.render_clock(weather, alarm_time)

                # 다음 트랙 버퍼링 체크
                if self.mpd.is_playing():
                    self.yt_player.queue_next_tracks()

            except Exception as e:
                logger.error("디스플레이 업데이트 오류: %s", e)

            time.sleep(1)

    # ─────────── 시작/종료 ───────────

    def start(self):
        """라디오 시작."""
        self._running = True

        # MPD 연결
        try:
            self.mpd.connect()
            vol = self.config.get("volume", {}).get("default", 50)
            self.mpd.set_volume(vol)
        except Exception as e:
            logger.error("MPD 연결 실패: %s", e)
            logger.info("MPD 없이 계속 진행 (웹 인터페이스만 사용 가능)")

        # 날씨 업데이트 시작
        if self.config.get("weather", {}).get("enabled"):
            self.weather.start_updates()

        # 알람 모니터링 시작
        if self.config.get("alarm", {}).get("enabled"):
            self.alarm.start_monitoring()

        # 디스플레이 루프
        self._display_thread = threading.Thread(target=self._display_loop, daemon=True)
        self._display_thread.start()

        # 시계 화면으로 시작
        self.display.set_mode(DisplayManager.MODE_CLOCK)

        # 웹 서버 시작
        from app.web.server import init_web, run_server
        init_web(self)
        web_cfg = self.config.get("web", {})
        logger.info("PiRadio 준비 완료")
        run_server(
            host=web_cfg.get("host", "0.0.0.0"),
            port=web_cfg.get("port", 8080),
        )

    def stop(self):
        """라디오 종료."""
        logger.info("PiRadio 종료 중...")
        self._running = False
        self.alarm.stop_monitoring()
        self.weather.stop_updates()
        self.display.cleanup()
        self.buttons.cleanup()
        self.mpd.close()
        logger.info("PiRadio 종료 완료")


def main():
    """메인 진입점."""
    config_path = None
    if len(sys.argv) > 1:
        config_path = sys.argv[1]

    radio = PiRadio(config_path)

    # 시그널 핸들러
    def signal_handler(sig, frame):
        radio.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    radio.start()


if __name__ == "__main__":
    main()
