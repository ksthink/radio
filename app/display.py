"""ST7789 디스플레이 매니저 - 240x240 LCD 제어"""

import logging
import os
import time
import threading
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# 라즈베리파이가 아닌 환경에서는 시뮬레이션 모드
try:
    import st7789
    DISPLAY_AVAILABLE = True
except ImportError:
    DISPLAY_AVAILABLE = False
    logger.warning("st7789 라이브러리 없음 - 시뮬레이션 모드")


# 색상 상수
COLOR_BG = (0, 0, 0)           # 배경 - 검정
COLOR_TEXT = (255, 255, 255)    # 기본 텍스트 - 흰색
COLOR_ACCENT = (0, 200, 255)   # 강조 - 시안
COLOR_DIM = (128, 128, 128)    # 어두운 텍스트
COLOR_VOLUME = (0, 255, 100)   # 볼륨 바
COLOR_PROGRESS = (255, 100, 0) # 프로그레스 바
COLOR_ALARM = (255, 50, 50)    # 알람 아이콘


class DisplayManager:
    """ST7789 240x240 디스플레이를 관리하는 클래스."""

    WIDTH = 240
    HEIGHT = 240

    # 화면 모드
    MODE_NOW_PLAYING = "now_playing"
    MODE_STATION_LIST = "station_list"
    MODE_CLOCK = "clock"
    MODE_MENU = "menu"
    MODE_ALARM = "alarm"

    def __init__(self, config):
        self.config = config
        self.mode = self.MODE_CLOCK
        self._lock = threading.Lock()
        self._screen_on = True
        self._last_activity = time.time()
        self._screen_timeout = config.get("screen_timeout", 300)

        # 폰트 로딩
        self._load_fonts(config)

        # 디스플레이 초기화
        if DISPLAY_AVAILABLE:
            self.display = st7789.ST7789(
                port=config.get("spi_port", 0),
                cs=config.get("spi_cs", 1),
                dc=config.get("spi_dc", 9),
                backlight=config.get("backlight", 13),
                rotation=config.get("rotation", 90),
                width=self.WIDTH,
                height=self.HEIGHT,
                spi_speed_hz=60_000_000,
            )
            self.display.begin()
        else:
            self.display = None

        # 이미지 버퍼
        self.buffer = Image.new("RGB", (self.WIDTH, self.HEIGHT), COLOR_BG)
        self.draw = ImageDraw.Draw(self.buffer)

        # 메뉴/리스트 상태
        self._list_offset = 0
        self._list_selected = 0
        self._menu_items = []

    def _load_fonts(self, config):
        """폰트를 로드한다."""
        font_path = config.get("font_path", "")
        fallback = config.get("font_fallback", "")

        actual_path = font_path if os.path.exists(font_path) else fallback

        try:
            self.font_large = ImageFont.truetype(actual_path, 24)
            self.font_medium = ImageFont.truetype(actual_path, 18)
            self.font_small = ImageFont.truetype(actual_path, 14)
            self.font_tiny = ImageFont.truetype(actual_path, 11)
            self.font_clock = ImageFont.truetype(actual_path, 56)
            logger.info("폰트 로드 완료: %s", actual_path)
        except Exception:
            logger.warning("TTF 폰트 로드 실패, 기본 폰트 사용")
            self.font_large = ImageFont.load_default()
            self.font_medium = ImageFont.load_default()
            self.font_small = ImageFont.load_default()
            self.font_tiny = ImageFont.load_default()
            self.font_clock = ImageFont.load_default()

    def wake(self):
        """화면 깨우기."""
        self._last_activity = time.time()
        if not self._screen_on:
            self._screen_on = True
            if self.display:
                self.display.set_backlight(True)

    def check_timeout(self):
        """화면 자동 꺼짐 확인."""
        if self._screen_timeout <= 0:
            return
        if self._screen_on and (time.time() - self._last_activity > self._screen_timeout):
            self._screen_on = False
            if self.display:
                self.display.set_backlight(False)

    def set_mode(self, mode):
        """화면 모드 변경."""
        self.mode = mode
        self._list_offset = 0
        self._list_selected = 0
        self.wake()

    def _clear(self):
        """화면 버퍼 초기화."""
        self.draw.rectangle([(0, 0), (self.WIDTH, self.HEIGHT)], fill=COLOR_BG)

    def _flush(self):
        """버퍼를 디스플레이에 전송."""
        if self.display:
            self.display.display(self.buffer)

    def _truncate_text(self, text, font, max_width):
        """텍스트가 너무 길면 말줄임표로 자른다."""
        bbox = font.getbbox(text)
        text_width = bbox[2] - bbox[0]
        if text_width <= max_width:
            return text
        while text and (font.getbbox(text + "…")[2] - font.getbbox(text + "…")[0]) > max_width:
            text = text[:-1]
        return text + "…"

    def _draw_progress_bar(self, x, y, width, height, ratio, color=COLOR_PROGRESS):
        """프로그레스 바를 그린다."""
        ratio = max(0.0, min(1.0, ratio))
        # 배경
        self.draw.rectangle([(x, y), (x + width, y + height)], fill=(40, 40, 40))
        # 채움
        fill_w = int(width * ratio)
        if fill_w > 0:
            self.draw.rectangle([(x, y), (x + fill_w, y + height)], fill=color)

    def _draw_volume_indicator(self, volume, y=220):
        """볼륨 표시기를 그린다."""
        bar_width = 160
        bar_x = (self.WIDTH - bar_width) // 2
        self.draw.text((bar_x - 25, y - 2), "♪", fill=COLOR_VOLUME, font=self.font_small)
        self._draw_progress_bar(bar_x, y, bar_width, 6, volume / 100.0, COLOR_VOLUME)
        vol_text = f"{volume}%"
        self.draw.text((bar_x + bar_width + 5, y - 2), vol_text, fill=COLOR_DIM, font=self.font_tiny)

    def render_now_playing(self, track_info=None, status=None, volume=50):
        """현재 재생 중인 곡 화면."""
        with self._lock:
            self._clear()

            if not track_info:
                self.draw.text(
                    (60, 100), "재생 중인 곡 없음",
                    fill=COLOR_DIM, font=self.font_medium
                )
                self._flush()
                return

            # 상단: 상태 표시
            state_icon = "▶" if status == "play" else "⏸" if status == "pause" else "⏹"
            now = datetime.now().strftime("%H:%M")
            self.draw.text((8, 6), state_icon, fill=COLOR_ACCENT, font=self.font_medium)
            self.draw.text((195, 6), now, fill=COLOR_DIM, font=self.font_small)

            # 구분선
            self.draw.line([(10, 30), (230, 30)], fill=(40, 40, 40), width=1)

            # 앨범아트 영역 (썸네일이 있으면 표시)
            art_size = 100
            art_x = (self.WIDTH - art_size) // 2
            art_y = 40
            self.draw.rectangle(
                [(art_x, art_y), (art_x + art_size, art_y + art_size)],
                fill=(30, 30, 40)
            )
            self.draw.text(
                (art_x + 35, art_y + 35), "♫",
                fill=COLOR_ACCENT, font=self.font_large
            )

            # 곡 제목
            title = track_info.get("title", "알 수 없음")
            title = self._truncate_text(title, self.font_medium, 220)
            title_bbox = self.font_medium.getbbox(title)
            title_w = title_bbox[2] - title_bbox[0]
            self.draw.text(
                ((self.WIDTH - title_w) // 2, 150),
                title, fill=COLOR_TEXT, font=self.font_medium
            )

            # 아티스트
            artist = track_info.get("artist", "")
            if artist:
                artist = self._truncate_text(artist, self.font_small, 220)
                artist_bbox = self.font_small.getbbox(artist)
                artist_w = artist_bbox[2] - artist_bbox[0]
                self.draw.text(
                    ((self.WIDTH - artist_w) // 2, 175),
                    artist, fill=COLOR_DIM, font=self.font_small
                )

            # 프로그레스 바
            elapsed = track_info.get("elapsed", 0)
            duration = track_info.get("duration", 0)
            if duration > 0:
                self._draw_progress_bar(20, 200, 200, 4, elapsed / duration)
                elapsed_str = f"{int(elapsed)//60}:{int(elapsed)%60:02d}"
                dur_str = f"{int(duration)//60}:{int(duration)%60:02d}"
                self.draw.text((20, 206), elapsed_str, fill=COLOR_DIM, font=self.font_tiny)
                self.draw.text((190, 206), dur_str, fill=COLOR_DIM, font=self.font_tiny)

            # 볼륨
            self._draw_volume_indicator(volume, y=228)

            self._flush()

    def render_station_list(self, stations, selected_index=0):
        """채널/스테이션 목록 화면."""
        with self._lock:
            self._clear()
            self._list_selected = selected_index

            # 헤더
            self.draw.text((10, 6), "♪ 채널 목록", fill=COLOR_ACCENT, font=self.font_medium)
            self.draw.line([(10, 30), (230, 30)], fill=(40, 40, 40), width=1)

            if not stations:
                self.draw.text(
                    (40, 100), "채널이 없습니다",
                    fill=COLOR_DIM, font=self.font_medium
                )
                self._flush()
                return

            # 리스트 아이템 (최대 5개 표시)
            visible = 5
            start = max(0, selected_index - visible // 2)
            start = min(start, max(0, len(stations) - visible))

            for i in range(start, min(start + visible, len(stations))):
                y = 38 + (i - start) * 40
                is_selected = (i == selected_index)

                if is_selected:
                    self.draw.rectangle(
                        [(5, y), (235, y + 36)],
                        fill=(30, 60, 80)
                    )

                station = stations[i]
                name = self._truncate_text(station.get("name", ""), self.font_medium, 200)
                desc = station.get("artist", station.get("description", ""))
                desc = self._truncate_text(desc, self.font_tiny, 200)

                color = COLOR_TEXT if is_selected else COLOR_DIM
                self.draw.text((15, y + 2), name, fill=color, font=self.font_medium)
                if desc:
                    self.draw.text((15, y + 22), desc, fill=COLOR_DIM, font=self.font_tiny)

            # 스크롤 인디케이터
            if len(stations) > visible:
                ratio = selected_index / max(1, len(stations) - 1)
                indicator_y = 38 + int(ratio * (visible * 40 - 20))
                self.draw.rectangle(
                    [(233, indicator_y), (237, indicator_y + 20)],
                    fill=COLOR_ACCENT
                )

            self._flush()

    def render_clock(self, weather_info=None, alarm_time=None):
        """시계/날씨 화면 (유휴 모드)."""
        with self._lock:
            self._clear()
            now = datetime.now()

            # 시간
            time_str = now.strftime("%H:%M")
            time_bbox = self.font_clock.getbbox(time_str)
            time_w = time_bbox[2] - time_bbox[0]
            self.draw.text(
                ((self.WIDTH - time_w) // 2, 30),
                time_str, fill=COLOR_TEXT, font=self.font_clock
            )

            # 초 (작은 글씨)
            sec_str = now.strftime(":%S")
            self.draw.text((175, 55), sec_str, fill=COLOR_DIM, font=self.font_small)

            # 날짜
            date_str = now.strftime("%Y년 %m월 %d일")
            weekdays = ["월", "화", "수", "목", "금", "토", "일"]
            date_str += f" ({weekdays[now.weekday()]})"
            date_bbox = self.font_medium.getbbox(date_str)
            date_w = date_bbox[2] - date_bbox[0]
            self.draw.text(
                ((self.WIDTH - date_w) // 2, 100),
                date_str, fill=COLOR_DIM, font=self.font_medium
            )

            # 구분선
            self.draw.line([(30, 130), (210, 130)], fill=(40, 40, 40), width=1)

            # 날씨 정보
            if weather_info:
                temp = weather_info.get("temp", "--")
                desc = weather_info.get("description", "")
                humidity = weather_info.get("humidity", "--")
                city = weather_info.get("city", "")

                weather_line1 = f"{city}  {temp}°C"
                weather_line2 = f"{desc}  습도 {humidity}%"

                w1_bbox = self.font_medium.getbbox(weather_line1)
                w1_w = w1_bbox[2] - w1_bbox[0]
                self.draw.text(
                    ((self.WIDTH - w1_w) // 2, 142),
                    weather_line1, fill=COLOR_TEXT, font=self.font_medium
                )
                w2_bbox = self.font_small.getbbox(weather_line2)
                w2_w = w2_bbox[2] - w2_bbox[0]
                self.draw.text(
                    ((self.WIDTH - w2_w) // 2, 168),
                    weather_line2, fill=COLOR_DIM, font=self.font_small
                )
            else:
                self.draw.text(
                    (60, 145), "날씨 정보 없음",
                    fill=COLOR_DIM, font=self.font_small
                )

            # 알람 표시
            if alarm_time:
                alarm_str = f"⏰ {alarm_time}"
                self.draw.text((80, 205), alarm_str, fill=COLOR_ALARM, font=self.font_medium)

            # 하단 안내
            self.draw.text(
                (45, 225), "A: 재생  X: 채널목록",
                fill=(60, 60, 60), font=self.font_tiny
            )

            self._flush()

    def render_menu(self, items, selected_index=0):
        """설정 메뉴 화면."""
        with self._lock:
            self._clear()

            self.draw.text((10, 6), "⚙ 설정", fill=COLOR_ACCENT, font=self.font_medium)
            self.draw.line([(10, 30), (230, 30)], fill=(40, 40, 40), width=1)

            for i, item in enumerate(items):
                y = 38 + i * 35
                is_selected = (i == selected_index)

                if is_selected:
                    self.draw.rectangle(
                        [(5, y), (235, y + 30)],
                        fill=(30, 60, 80)
                    )

                label = item.get("label", "")
                value = item.get("value", "")
                color = COLOR_TEXT if is_selected else COLOR_DIM

                self.draw.text((15, y + 4), label, fill=color, font=self.font_medium)
                if value:
                    self.draw.text((180, y + 6), value, fill=COLOR_ACCENT, font=self.font_small)

            self._flush()

    def render_volume_popup(self, volume):
        """볼륨 변경 시 팝업 오버레이."""
        with self._lock:
            # 반투명 배경 효과 (중앙 영역만)
            overlay = self.buffer.copy()
            draw = ImageDraw.Draw(overlay)

            # 박스
            draw.rectangle([(40, 90), (200, 150)], fill=(20, 20, 30))
            draw.rectangle([(40, 90), (200, 150)], outline=COLOR_ACCENT, width=1)

            # 볼륨 텍스트
            vol_text = f"볼륨: {volume}%"
            vol_bbox = self.font_large.getbbox(vol_text)
            vol_w = vol_bbox[2] - vol_bbox[0]
            draw.text(
                ((self.WIDTH - vol_w) // 2, 95),
                vol_text, fill=COLOR_TEXT, font=self.font_large
            )

            # 볼륨 바
            bar_x = 55
            bar_w = 130
            draw.rectangle(
                [(bar_x, 128), (bar_x + bar_w, 140)],
                fill=(40, 40, 40)
            )
            fill_w = int(bar_w * volume / 100)
            if fill_w > 0:
                draw.rectangle(
                    [(bar_x, 128), (bar_x + fill_w, 140)],
                    fill=COLOR_VOLUME
                )

            self.buffer = overlay
            self.draw = ImageDraw.Draw(self.buffer)
            self._flush()

    def show_message(self, title, message, duration=2):
        """일시적 메시지를 표시한다."""
        with self._lock:
            self._clear()
            title_bbox = self.font_large.getbbox(title)
            title_w = title_bbox[2] - title_bbox[0]
            self.draw.text(
                ((self.WIDTH - title_w) // 2, 80),
                title, fill=COLOR_ACCENT, font=self.font_large
            )
            msg_bbox = self.font_medium.getbbox(message)
            msg_w = msg_bbox[2] - msg_bbox[0]
            self.draw.text(
                ((self.WIDTH - msg_w) // 2, 130),
                message, fill=COLOR_TEXT, font=self.font_medium
            )
            self._flush()

    def cleanup(self):
        """디스플레이 정리."""
        if self.display:
            self._clear()
            self._flush()
            self.display.set_backlight(False)
