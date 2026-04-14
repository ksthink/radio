"""MPD 클라이언트 래퍼 - MPD와의 통신을 관리"""

import logging
import threading
from mpd import MPDClient, ConnectionError as MPDConnectionError

logger = logging.getLogger(__name__)


class MPDController:
    """MPD 서버와 통신하는 컨트롤러."""

    def __init__(self, host="localhost", port=6600):
        self.host = host
        self.port = port
        self.client = MPDClient()
        self.client.timeout = 10
        self._lock = threading.Lock()

    def connect(self):
        """MPD에 연결한다."""
        with self._lock:
            try:
                self.client.connect(self.host, self.port)
                logger.info("MPD 연결 성공: %s:%s", self.host, self.port)
            except MPDConnectionError:
                logger.warning("MPD 이미 연결됨, 재연결 시도")
                self._reconnect_unlocked()

    def _reconnect_unlocked(self):
        """내부용 재연결 (lock 없이)."""
        try:
            self.client.disconnect()
        except Exception:
            pass
        self.client = MPDClient()
        self.client.timeout = 10
        self.client.connect(self.host, self.port)

    def reconnect(self):
        """MPD에 재연결한다."""
        with self._lock:
            self._reconnect_unlocked()

    def _ensure_connected(self):
        """연결 상태를 확인하고 필요시 재연결 (lock 없이)."""
        try:
            self.client.ping()
        except Exception:
            self._reconnect_unlocked()

    def play(self, pos=None):
        with self._lock:
            self._ensure_connected()
            if pos is not None:
                self.client.play(pos)
            else:
                self.client.play()

    def pause(self):
        with self._lock:
            self._ensure_connected()
            self.client.pause()

    def stop(self):
        with self._lock:
            self._ensure_connected()
            self.client.stop()

    def next(self):
        with self._lock:
            self._ensure_connected()
            self.client.next()

    def previous(self):
        with self._lock:
            self._ensure_connected()
            self.client.previous()

    def set_volume(self, volume):
        with self._lock:
            self._ensure_connected()
            volume = max(0, min(100, volume))
            self.client.setvol(volume)

    def get_volume(self):
        with self._lock:
            self._ensure_connected()
            status = self.client.status()
            return int(status.get("volume", 50))

    def volume_up(self, step=5):
        with self._lock:
            self._ensure_connected()
            status = self.client.status()
            current = int(status.get("volume", 50))
            new_vol = min(current + step, 100)
            self.client.setvol(new_vol)
            return new_vol

    def volume_down(self, step=5):
        with self._lock:
            self._ensure_connected()
            status = self.client.status()
            current = int(status.get("volume", 50))
            new_vol = max(current - step, 0)
            self.client.setvol(new_vol)
            return new_vol

    def get_status(self):
        with self._lock:
            self._ensure_connected()
            return self.client.status()

    def get_current_song(self):
        with self._lock:
            self._ensure_connected()
            return self.client.currentsong()

    def is_playing(self):
        status = self.get_status()
        return status.get("state") == "play"

    def clear_playlist(self):
        with self._lock:
            self._ensure_connected()
            self.client.clear()

    def add_track(self, uri):
        with self._lock:
            self._ensure_connected()
            self.client.add(uri)
            logger.debug("트랙 추가: %s", uri[:80])

    def add_and_play(self, uri):
        with self._lock:
            self._ensure_connected()
            self.client.clear()
            self.client.add(uri)
            self.client.play(0)

    def get_playlist(self):
        with self._lock:
            self._ensure_connected()
            return self.client.playlistinfo()

    def playlist_length(self):
        with self._lock:
            self._ensure_connected()
            status = self.client.status()
            return int(status.get("playlistlength", 0))

    def set_repeat(self, state):
        with self._lock:
            self._ensure_connected()
            self.client.repeat(1 if state else 0)

    def set_random(self, state):
        with self._lock:
            self._ensure_connected()
            self.client.random(1 if state else 0)

    def get_elapsed(self):
        status = self.get_status()
        return float(status.get("elapsed", 0))

    def get_duration(self):
        status = self.get_status()
        return float(status.get("duration", 0))

    def close(self):
        """연결 종료."""
        try:
            self.client.close()
            self.client.disconnect()
        except Exception:
            pass
