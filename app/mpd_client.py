"""MPD 클라이언트 래퍼 - MPD와의 통신을 관리"""

import logging
from mpd import MPDClient, ConnectionError as MPDConnectionError

logger = logging.getLogger(__name__)


class MPDController:
    """MPD 서버와 통신하는 컨트롤러."""

    def __init__(self, host="localhost", port=6600):
        self.host = host
        self.port = port
        self.client = MPDClient()
        self.client.timeout = 10

    def connect(self):
        """MPD에 연결한다."""
        try:
            self.client.connect(self.host, self.port)
            logger.info("MPD 연결 성공: %s:%s", self.host, self.port)
        except MPDConnectionError:
            logger.warning("MPD 이미 연결됨, 재연결 시도")
            self.reconnect()

    def reconnect(self):
        """MPD에 재연결한다."""
        try:
            self.client.disconnect()
        except Exception:
            pass
        self.client = MPDClient()
        self.client.timeout = 10
        self.client.connect(self.host, self.port)

    def _ensure_connected(self):
        """연결 상태를 확인하고 필요시 재연결."""
        try:
            self.client.ping()
        except Exception:
            self.reconnect()

    def play(self, pos=None):
        """재생 시작."""
        self._ensure_connected()
        if pos is not None:
            self.client.play(pos)
        else:
            self.client.play()

    def pause(self):
        """일시정지 토글."""
        self._ensure_connected()
        self.client.pause()

    def stop(self):
        """재생 정지."""
        self._ensure_connected()
        self.client.stop()

    def next(self):
        """다음 트랙."""
        self._ensure_connected()
        self.client.next()

    def previous(self):
        """이전 트랙."""
        self._ensure_connected()
        self.client.previous()

    def set_volume(self, volume):
        """볼륨 설정 (0-100)."""
        self._ensure_connected()
        volume = max(0, min(100, volume))
        self.client.setvol(volume)

    def get_volume(self):
        """현재 볼륨 반환."""
        self._ensure_connected()
        status = self.client.status()
        return int(status.get("volume", 50))

    def volume_up(self, step=5):
        """볼륨 올리기."""
        current = self.get_volume()
        self.set_volume(current + step)
        return min(current + step, 100)

    def volume_down(self, step=5):
        """볼륨 내리기."""
        current = self.get_volume()
        self.set_volume(current - step)
        return max(current - step, 0)

    def get_status(self):
        """MPD 상태 정보 반환."""
        self._ensure_connected()
        return self.client.status()

    def get_current_song(self):
        """현재 재생 중인 곡 정보 반환."""
        self._ensure_connected()
        return self.client.currentsong()

    def is_playing(self):
        """재생 중인지 확인."""
        status = self.get_status()
        return status.get("state") == "play"

    def clear_playlist(self):
        """플레이리스트 초기화."""
        self._ensure_connected()
        self.client.clear()

    def add_track(self, uri):
        """트랙 URI를 플레이리스트에 추가."""
        self._ensure_connected()
        self.client.add(uri)
        logger.debug("트랙 추가: %s", uri[:80])

    def add_and_play(self, uri):
        """트랙을 추가하고 바로 재생."""
        self._ensure_connected()
        self.client.clear()
        self.client.add(uri)
        self.client.play(0)

    def get_playlist(self):
        """현재 플레이리스트 반환."""
        self._ensure_connected()
        return self.client.playlistinfo()

    def playlist_length(self):
        """플레이리스트 길이."""
        self._ensure_connected()
        status = self.client.status()
        return int(status.get("playlistlength", 0))

    def set_repeat(self, state):
        """반복 재생 설정."""
        self._ensure_connected()
        self.client.repeat(1 if state else 0)

    def set_random(self, state):
        """랜덤 재생 설정."""
        self._ensure_connected()
        self.client.random(1 if state else 0)

    def get_elapsed(self):
        """현재 재생 경과 시간 (초)."""
        status = self.get_status()
        return float(status.get("elapsed", 0))

    def get_duration(self):
        """현재 트랙 길이 (초)."""
        status = self.get_status()
        return float(status.get("duration", 0))

    def close(self):
        """연결 종료."""
        try:
            self.client.close()
            self.client.disconnect()
        except Exception:
            pass
