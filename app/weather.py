"""날씨 정보 모듈 - OpenWeatherMap API"""

import logging
import threading
import time

import requests

logger = logging.getLogger(__name__)


class WeatherClient:
    """OpenWeatherMap API를 사용한 날씨 정보 클래스."""

    API_URL = "https://api.openweathermap.org/data/2.5/weather"

    def __init__(self, api_key="", city="Seoul", units="metric", update_interval=1800):
        self.api_key = api_key
        self.city = city
        self.units = units
        self.update_interval = update_interval
        self._data = None
        self._running = False
        self._thread = None

    def fetch(self):
        """날씨 정보를 가져온다."""
        if not self.api_key:
            logger.debug("날씨 API 키 미설정")
            return None

        try:
            resp = requests.get(
                self.API_URL,
                params={
                    "q": self.city,
                    "appid": self.api_key,
                    "units": self.units,
                    "lang": "kr",
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            self._data = {
                "city": data.get("name", self.city),
                "temp": round(data["main"]["temp"]),
                "feels_like": round(data["main"]["feels_like"]),
                "humidity": data["main"]["humidity"],
                "description": data["weather"][0]["description"],
                "icon": data["weather"][0]["icon"],
                "wind_speed": data.get("wind", {}).get("speed", 0),
            }
            logger.info("날씨 업데이트: %s %d°C %s",
                        self._data["city"], self._data["temp"], self._data["description"])
            return self._data

        except requests.RequestException as e:
            logger.error("날씨 정보 가져오기 실패: %s", e)
            return self._data  # 이전 데이터 반환

    def get_weather(self):
        """캐시된 날씨 정보 반환."""
        return self._data

    def start_updates(self):
        """주기적 날씨 업데이트 시작."""
        self._running = True
        self._thread = threading.Thread(target=self._update_loop, daemon=True)
        self._thread.start()
        # 처음 한번 즉시 호출
        threading.Thread(target=self.fetch, daemon=True).start()

    def stop_updates(self):
        """업데이트 중지."""
        self._running = False

    def _update_loop(self):
        """주기적 업데이트 루프."""
        while self._running:
            time.sleep(self.update_interval)
            if self._running:
                self.fetch()
