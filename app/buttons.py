"""GPIO 버튼 핸들러 - 4개 물리 버튼 처리 (안정성 개선, 디버깅 기능 추가)"""

import logging
import time
import threading

logger = logging.getLogger(__name__)

# 라즈베리파이가 아닌 환경에서는 시뮬레이션
try:
    from gpiozero import Button, GPIOPinMissing
    from gpiozero.exc import GPIOError
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    logger.warning("gpiozero 라이브러리 없음 - 버튼 시뮬레이션 모드")


class ButtonHandler:
    """4개의 물리 버튼 이벤트를 관리하는 클래스 (개선된 버전).

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
        self._button_states = {}  # 디버깅용 상태 추적
        self._press_lock = threading.Lock()

        if GPIO_AVAILABLE:
            self._setup_buttons()
        else:
            logger.info("GPIO 미사용 - 웹 인터페이스로만 제어 가능")

    def _setup_buttons(self):
        """GPIO 버튼을 초기화한다 (개선된 에러 핸들링)."""
        pin_map = {
            "a": self.config.get("a", 5),
            "b": self.config.get("b", 6),
            "x": self.config.get("x", 16),
            "y": self.config.get("y", 24),
        }

        for name, pin in pin_map.items():
            try:
                # pull_up=True: 버튼이 눌렸을 때 LOW, 안 눌렸을 때 HIGH
                btn = Button(
                    pin,
                    pull_up=True,
                    bounce_time=self.debounce_ms,
                    hold_time=self.long_press_ms / 1000.0,
                )
                
                # 이벤트 핸들러등록 (미리 정의한 메서드 참조)
                def make_press_handler(button_name):
                    return lambda: self._on_press(button_name)
                
                def make_release_handler(button_name):
                    return lambda: self._on_release(button_name)
                
                btn.when_pressed = make_press_handler(name)
                btn.when_released = make_release_handler(name)
                
                self._buttons[name] = btn
                self._button_states[name] = "released"
                logger.info("✓ 버튼 %s (BCM %d) 초기화 성공", name.upper(), pin)
                
            except (GPIOPinMissing, GPIOError) as e:
                logger.error("✗ 버튼 %s (BCM %d) 초기화 실패: %s", name.upper(), pin, e)
            except Exception as e:
                logger.error("✗ 예상치 못한 오류 - 버튼 %s (BCM %d): %s", name.upper(), pin, e)

    def _on_press(self, name):
        """버튼 눌림 이벤트."""
        with self._press_lock:
            self._press_times[name] = time.time()
            self._button_states[name] = "pressed"
            logger.debug("버튼 %s 눌림", name.upper())

    def _on_release(self, name):
        """버튼 놓음 이벤트 - 누른 시간에 따라 동작 결정."""
        with self._press_lock:
            press_time = self._press_times.get(name)
            if press_time is None:
                logger.warning("버튼 %s: press_time이 없음 (이벤트 타이밍 문제)", name)
                return
            
            duration_ms = (time.time() - press_time) * 1000
            is_long = duration_ms >= self.long_press_ms
            
            self._button_states[name] = "released"
            logger.info("버튼 %s: %s (%.0fms)", 
                       name.upper(), 
                       "길게 누름" if is_long else "짧게 누름",
                       duration_ms)

        # 콜백 호출 (lock 밖에서)
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
                logger.debug("✓ 콜백 실행: %s", callback_name)
            except Exception as e:
                logger.error("✗ 콜백 실행 오류 - %s: %s", callback_name, e)
        else:
            logger.debug("⚠ 등록되지 않은 콜백: %s", callback_name)

    def get_button_states(self) -> dict:
        """모든 버튼의 현재 상태 반환 (테스트용)."""
        with self._press_lock:
            return self._button_states.copy()

    def simulate_press(self, button_name, long=False):
        """테스트/웹 인터페이스용 버튼 시뮬레이션."""
        if button_name.lower() not in ["a", "b", "x", "y"]:
            logger.warning("잘못된 버튼 이름: %s", button_name)
            return
        
        button_name = button_name.lower()
        
        if long:
            duration_ms = self.long_press_ms + 100
        else:
            duration_ms = 100

        logger.info("🎮 버튼 시뮬레이션: %s (%s)", 
                   button_name.upper(),
                   "길게" if long else "짧게")
        
        with self._press_lock:
            self._press_times[button_name] = time.time() - duration_ms / 1000.0
        self._on_release(button_name)

    def diagnose(self) -> dict:
        """버튼 설정 진단 정보 반환."""
        diagnosis = {
            "gpio_available": GPIO_AVAILABLE,
            "buttons_initialized": len(self._buttons),
            "long_press_ms": self.long_press_ms,
            "debounce_ms": self.debounce_ms * 1000,
            "button_states": self.get_button_states(),
            "buttons": {}
        }
        
        pin_map = {
            "a": self.config.get("a", 5),
            "b": self.config.get("b", 6),
            "x": self.config.get("x", 16),
            "y": self.config.get("y", 24),
        }
        
        for name, pin in pin_map.items():
            diagnosis["buttons"][name] = {
                "pin": pin,
                "initialized": name in self._buttons,
                "state": self._button_states.get(name, "unknown")
            }
        
        return diagnosis

    def cleanup(self):
        """GPIO 정리."""
        for btn in self._buttons.values():
            try:
                btn.close()
            except Exception as e:
                logger.warning("GPIO 정리 오류: %s", e)
        logger.info("GPIO 정리 완료")
