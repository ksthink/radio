"""알람/타이머 관리 모듈"""

import json
import logging
import os
import threading
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AlarmManager:
    """알람과 슬립 타이머를 관리하는 클래스."""

    def __init__(self, data_file="data/alarms.json", on_alarm=None):
        self.data_file = data_file
        self.on_alarm = on_alarm  # 알람 발동 시 콜백
        self.alarms = []
        self._sleep_timer = None
        self._sleep_end = None
        self._check_thread = None
        self._running = False
        self._load()

    def _ensure_dir(self):
        """데이터 디렉토리 생성."""
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)

    def _load(self):
        """저장된 알람을 로드한다."""
        self._ensure_dir()
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    self.alarms = json.load(f)
                logger.info("알람 %d개 로드됨", len(self.alarms))
            except (json.JSONDecodeError, IOError) as e:
                logger.error("알람 로드 실패: %s", e)
                self.alarms = []

    def _save(self):
        """알람을 파일에 저장한다."""
        self._ensure_dir()
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.alarms, f, ensure_ascii=False, indent=2)

    def add_alarm(self, hour, minute, days=None, channel_id=None, label=""):
        """알람을 추가한다.

        Args:
            hour: 시 (0-23)
            minute: 분 (0-59)
            days: 요일 리스트 (0=월 ~ 6=일), None이면 매일
            channel_id: 알람 시 재생할 채널 ID
            label: 알람 이름
        """
        alarm = {
            "id": len(self.alarms) + 1,
            "hour": hour,
            "minute": minute,
            "days": days,  # None = 매일, [0,1,2,3,4] = 평일
            "channel_id": channel_id,
            "label": label,
            "enabled": True,
        }
        self.alarms.append(alarm)
        self._save()
        logger.info("알람 추가: %02d:%02d %s", hour, minute, label)
        return alarm

    def remove_alarm(self, alarm_id):
        """알람을 삭제한다."""
        self.alarms = [a for a in self.alarms if a["id"] != alarm_id]
        self._save()

    def toggle_alarm(self, alarm_id):
        """알람 활성/비활성 토글."""
        for alarm in self.alarms:
            if alarm["id"] == alarm_id:
                alarm["enabled"] = not alarm["enabled"]
                self._save()
                return alarm["enabled"]
        return None

    def get_alarms(self):
        """모든 알람 반환."""
        return self.alarms

    def get_next_alarm(self):
        """다음 울릴 알람 정보 반환."""
        now = datetime.now()
        enabled = [a for a in self.alarms if a.get("enabled", True)]
        if not enabled:
            return None

        next_alarm = None
        min_delta = timedelta(days=8)

        for alarm in enabled:
            # 오늘 해당 시간
            alarm_time = now.replace(
                hour=alarm["hour"],
                minute=alarm["minute"],
                second=0,
                microsecond=0,
            )

            days = alarm.get("days")
            if days is None:
                # 매일
                if alarm_time <= now:
                    alarm_time += timedelta(days=1)
                delta = alarm_time - now
            else:
                # 특정 요일
                delta = timedelta(days=8)
                for d in days:
                    test_time = alarm_time + timedelta(days=(d - now.weekday()) % 7)
                    if test_time <= now:
                        test_time += timedelta(days=7)
                    test_delta = test_time - now
                    if test_delta < delta:
                        delta = test_delta

            if delta < min_delta:
                min_delta = delta
                next_alarm = alarm

        return next_alarm

    def get_next_alarm_str(self):
        """다음 알람 시간 문자열 (예: '07:30')."""
        alarm = self.get_next_alarm()
        if alarm:
            return f"{alarm['hour']:02d}:{alarm['minute']:02d}"
        return None

    def start_sleep_timer(self, minutes, on_sleep=None):
        """슬립 타이머 시작."""
        self._sleep_end = datetime.now() + timedelta(minutes=minutes)
        self._sleep_callback = on_sleep
        logger.info("슬립 타이머: %d분 후 정지", minutes)

    def cancel_sleep_timer(self):
        """슬립 타이머 취소."""
        self._sleep_end = None
        self._sleep_callback = None

    def get_sleep_remaining(self):
        """슬립 타이머 남은 시간 (초). None이면 타이머 없음."""
        if self._sleep_end is None:
            return None
        remaining = (self._sleep_end - datetime.now()).total_seconds()
        if remaining <= 0:
            return 0
        return int(remaining)

    def start_monitoring(self):
        """알람 모니터링 시작."""
        self._running = True
        self._check_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._check_thread.start()

    def stop_monitoring(self):
        """알람 모니터링 중지."""
        self._running = False

    def _monitor_loop(self):
        """알람/슬립 타이머 체크 루프."""
        import time as _time
        last_triggered = set()

        while self._running:
            now = datetime.now()

            # 알람 체크
            for alarm in self.alarms:
                if not alarm.get("enabled", True):
                    continue

                # 요일 체크
                days = alarm.get("days")
                if days is not None and now.weekday() not in days:
                    continue

                if now.hour == alarm["hour"] and now.minute == alarm["minute"]:
                    key = f"{alarm['id']}_{now.date()}_{now.hour}_{now.minute}"
                    if key not in last_triggered:
                        last_triggered.add(key)
                        logger.info("알람 발동: %s", alarm.get("label", ""))
                        if self.on_alarm:
                            try:
                                self.on_alarm(alarm)
                            except Exception as e:
                                logger.error("알람 콜백 오류: %s", e)

            # 오래된 트리거 기록 정리
            if len(last_triggered) > 100:
                last_triggered.clear()

            # 슬립 타이머 체크
            if self._sleep_end and now >= self._sleep_end:
                logger.info("슬립 타이머 발동")
                self._sleep_end = None
                if self._sleep_callback:
                    try:
                        self._sleep_callback()
                    except Exception as e:
                        logger.error("슬립 콜백 오류: %s", e)
                    self._sleep_callback = None

            _time.sleep(10)  # 10초마다 체크
