"""GPIO 버튼 핸들러

키 매핑:
  A 짧게   → 이전 곡 / 재생목록에서 위로
  A 길게   → -5초 seek (계속 반복)
  X 짧게   → 다음 곡 / 재생목록에서 아래로
  X 더블탭 → 재생목록 화면으로 이동 / 재생목록에서 선택 후 재생
  X 길게   → +5초 seek (계속 반복)
  B 길게   → 볼륨 업 (계속 반복)
  Y 길게   → 볼륨 다운 (계속 반복)
  B/Y 짧게 → 없음
"""

import logging
import time
import threading

logger = logging.getLogger(__name__)

DOUBLE_TAP_MS = 400   # 더블탭 인식 시간 창 (ms)
REPEAT_INTERVAL = 0.4 # 길게 누름 반복 간격 (초)

try:
    from gpiozero import Button
    try:
        from gpiozero import GPIOPinMissing
    except ImportError:
        GPIOPinMissing = Exception
    try:
        from gpiozero.exc import GPIOError
    except ImportError:
        GPIOError = Exception
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    logger.warning("gpiozero 라이브러리 없음 - 버튼 시뮬레이션 모드")


class ButtonHandler:
    def __init__(self, config, callbacks=None):
        self.config = config
        self.callbacks = callbacks or {}
        self.long_press_ms = config.get("long_press_ms", 800)
        self.debounce_ms = config.get("debounce_ms", 250) / 1000.0

        self._buttons = {}
        self._press_times = {}
        self._is_long = {}          # 길게 누름으로 처리됐는지
        self._button_states = {}
        self._last_release_time = {}  # 더블탭 감지용
        self._pending_timers = {}     # X 싱글탭 지연 타이머
        self._repeat_stop_events = {} # 반복 스레드 중지 이벤트
        self._press_lock = threading.Lock()

        if GPIO_AVAILABLE:
            self._setup_buttons()
        else:
            logger.info("GPIO 미사용 - 웹 인터페이스로만 제어 가능")

    def _setup_buttons(self):
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
                    hold_time=self.long_press_ms / 1000.0,
                    hold_repeat=False,
                )

                def make_press(n):
                    return lambda: self._on_press(n)

                def make_held(n):
                    return lambda: self._on_held(n)

                def make_release(n):
                    return lambda: self._on_release(n)

                btn.when_pressed = make_press(name)
                btn.when_held = make_held(name)
                btn.when_released = make_release(name)

                self._buttons[name] = btn
                self._button_states[name] = "released"
                self._is_long[name] = False
                logger.info("✓ 버튼 %s (BCM %d) 초기화 완료", name.upper(), pin)

            except (GPIOPinMissing, GPIOError) as e:
                logger.error("✗ 버튼 %s (BCM %d) 초기화 실패: %s", name.upper(), pin, e)
            except Exception as e:
                logger.error("✗ 버튼 %s 예외: %s", name.upper(), e)

    def _on_press(self, name):
        with self._press_lock:
            self._press_times[name] = time.time()
            self._button_states[name] = "pressed"
            self._is_long[name] = False

    def _on_held(self, name):
        """hold_time 이상 눌림 → 길게 누름 처리."""
        with self._press_lock:
            self._is_long[name] = True
        # 대기 중인 싱글탭 타이머 취소
        self._cancel_pending(name)
        # 반복 동작 시작
        self._start_repeat(name)
        logger.debug("버튼 %s 길게 누름 시작", name.upper())

    def _on_release(self, name):
        """버튼 놓임 → 반복 중지 및 단/더블 탭 처리."""
        self._stop_repeat(name)

        with self._press_lock:
            is_long = self._is_long.get(name, False)
            self._is_long[name] = False
            self._button_states[name] = "released"

        if is_long:
            logger.debug("버튼 %s 길게 누름 종료", name.upper())
            return  # 길게 누름은 _on_held에서 이미 처리됨

        # 짧게 누름
        now = time.time()
        logger.info("버튼 %s 짧게 누름", name.upper())

        if name == "x":
            # 더블탭 감지
            last = self._last_release_time.get("x", 0)
            dt_ms = (now - last) * 1000
            self._cancel_pending("x")

            if last > 0 and dt_ms < DOUBLE_TAP_MS:
                # 더블탭 확정
                self._last_release_time["x"] = 0
                logger.info("버튼 X 더블탭")
                self._call("on_x_double")
            else:
                # 싱글탭 - DOUBLE_TAP_MS 후 실행 (더블탭 여부 대기)
                self._last_release_time["x"] = now

                def do_single():
                    self._pending_timers.pop("x", None)
                    self._call("on_x_single")

                t = threading.Timer(DOUBLE_TAP_MS / 1000.0, do_single)
                self._pending_timers["x"] = t
                t.start()

        elif name == "a":
            self._call("on_a_short")

        # B/Y 짧게 누름 → 동작 없음

    def _start_repeat(self, name):
        """길게 누름 반복 스레드 시작."""
        if name in self._repeat_stop_events:
            return
        stop = threading.Event()
        self._repeat_stop_events[name] = stop

        cb_map = {
            "a": "on_seek_back",
            "x": "on_seek_forward",
            "b": "on_volume_up",
            "y": "on_volume_down",
        }
        cb_name = cb_map.get(name)
        if not cb_name:
            return

        def loop():
            # 첫 번째 즉시 실행
            self._call(cb_name)
            while not stop.wait(REPEAT_INTERVAL):
                self._call(cb_name)

        threading.Thread(target=loop, daemon=True).start()

    def _stop_repeat(self, name):
        stop = self._repeat_stop_events.pop(name, None)
        if stop:
            stop.set()

    def _cancel_pending(self, name):
        t = self._pending_timers.pop(name, None)
        if t:
            t.cancel()

    def _call(self, cb_name):
        cb = self.callbacks.get(cb_name)
        if cb:
            try:
                cb()
            except Exception as e:
                logger.error("콜백 오류 - %s: %s", cb_name, e)
        else:
            logger.debug("콜백 없음: %s", cb_name)

    def get_button_states(self) -> dict:
        with self._press_lock:
            return self._button_states.copy()

    def simulate_press(self, button_name, long=False):
        name = button_name.lower()
        if name not in ["a", "b", "x", "y"]:
            return
        if long:
            self._on_press(name)
            self._on_held(name)
            time.sleep(0.1)
            self._on_release(name)
        else:
            self._on_press(name)
            self._on_release(name)

    def diagnose(self) -> dict:
        pin_map = {"a": self.config.get("a", 5), "b": self.config.get("b", 6),
                   "x": self.config.get("x", 16), "y": self.config.get("y", 24)}
        return {
            "gpio_available": GPIO_AVAILABLE,
            "buttons_initialized": len(self._buttons),
            "long_press_ms": self.long_press_ms,
            "debounce_ms": self.debounce_ms * 1000,
            "button_states": self.get_button_states(),
            "buttons": {n: {"pin": p, "initialized": n in self._buttons,
                            "state": self._button_states.get(n, "unknown")}
                        for n, p in pin_map.items()},
        }

    def cleanup(self):
        for name in list(self._repeat_stop_events.keys()):
            self._stop_repeat(name)
        for t in list(self._pending_timers.values()):
            t.cancel()
        self._pending_timers.clear()
        for btn in self._buttons.values():
            try:
                btn.close()
            except Exception:
                pass
        logger.info("GPIO 정리 완료")


logger = logging.getLogger(__name__)

# 라즈베리파이가 아닌 환경에서는 시뮬레이션
try:
    from gpiozero import Button
    try:
        from gpiozero import GPIOPinMissing
    except ImportError:
        GPIOPinMissing = Exception
    try:
        from gpiozero.exc import GPIOError
    except ImportError:
        GPIOError = Exception
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
