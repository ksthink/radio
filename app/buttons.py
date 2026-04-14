"""GPIO 버튼 핸들러 - 4개 물리 버튼 처리"""

import logging
import time
import threading

logger = logging.getLogger(__name__)

# 라즈베리파이가 아닌 환경에서는 시뮬레이션
try:
    from gpiozero import Button
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    logger.warning("gpiozero 라이브러리 없음 - 버튼 시뮬레이션 모드")


class ButtonHandler:
    """4개의 물리 버튼 이벤트를 관리하는 클래스.

    Pirate Audio Speaker 버튼 매핑:
    - A (BCM 5):  재생/일시정지 | 길게: 시계 화면
    - B (BCM 6):  볼륨 다운    | 길게: 이전 채널
    - X (BCM 16): 다음 채널    | 길게: 채널 목록
    - Y (BCM 24): 볼륨 업      | 길게: 메뉴
    """

    def __init__(self, config, callbacks=None):
        """
        callbacks: dict of callback functions
            - on_play_pause()
            - on_volume_up()
            - on_volume_down()
            - on_next()
            - on_previous()
            - on_menu()
            - on_station_list()
            - on_clock()
        """
        self.config = config
        self.callbacks = callbacks or {}
        self.long_press_ms = config.get("long_press_ms", 800)
        self.debounce_ms = config.get("debounce_ms", 250) / 1000.0
        self._buttons = {}
        self._press_times = {}

        if GPIO_AVAILABLE:
            self._setup_buttons()
        else:
            logger.info("GPIO 미사용 - 웹 인터페이스로만 제어 가능")

    def _setup_buttons(self):
        """GPIO 버튼을 초기화한다."""
        pin_map = {
            "a": self.config.get("a", 5),
            "b": self.config.get("b", 6),
            "x": self.config.get("x", 16),
            "y": self.config.get("y", 24),
        }

        for name, pin in pin_map.items():
            try:
                btn = Button(
                    pin,
                    pull_up=True,
                    bounce_time=self.debounce_ms,
                )
                btn.when_pressed = lambda n=name: self._on_press(n)
                btn.when_released = lambda n=name: self._on_release(n)
                self._buttons[name] = btn
                logger.info("버튼 설정: %s -> BCM %d", name, pin)
            except Exception as e:
                logger.error("버튼 %s (BCM %d) 설정 실패: %s", name, pin, e)

    def _on_press(self, name):
        """버튼 눌림 이벤트."""
        self._press_times[name] = time.time()

    def _on_release(self, name):
        """버튼 놓음 이벤트 - 누른 시간에 따라 동작 결정."""
        press_time = self._press_times.get(name, time.time())
        duration_ms = (time.time() - press_time) * 1000
        is_long = duration_ms >= self.long_press_ms

        logger.debug("버튼 %s: %s (%dms)", name, "길게" if is_long else "짧게", duration_ms)

        if name == "a":
            if is_long:
                self._call("on_clock")
            else:
                self._call("on_play_pause")
        elif name == "b":
            if is_long:
                self._call("on_previous")
            else:
                self._call("on_volume_down")
        elif name == "x":
            if is_long:
                self._call("on_station_list")
            else:
                self._call("on_next")
        elif name == "y":
            if is_long:
                self._call("on_menu")
            else:
                self._call("on_volume_up")

    def _call(self, callback_name):
        """콜백 안전 실행."""
        cb = self.callbacks.get(callback_name)
        if cb:
            try:
                cb()
            except Exception as e:
                logger.error("콜백 %s 실행 오류: %s", callback_name, e)
        else:
            logger.debug("미등록 콜백: %s", callback_name)

    def simulate_press(self, button_name, long=False):
        """테스트/웹 인터페이스용 버튼 시뮬레이션."""
        if long:
            duration_ms = self.long_press_ms + 100
        else:
            duration_ms = 100

        self._press_times[button_name] = time.time() - duration_ms / 1000.0
        self._on_release(button_name)

    def cleanup(self):
        """GPIO 정리."""
        for btn in self._buttons.values():
            btn.close()
