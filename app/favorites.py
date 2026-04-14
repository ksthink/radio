"""즐겨찾기 채널 관리 모듈"""

import json
import logging
import os

logger = logging.getLogger(__name__)

# 기본 채널 프리셋 (빈 상태로 시작, 웹 UI에서 검색 후 추가)
DEFAULT_CHANNELS = []


class FavoritesManager:
    """즐겨찾기 채널을 관리하는 클래스."""

    def __init__(self, data_file="data/favorites.json"):
        self.data_file = data_file
        self.channels = []
        self._current_index = 0
        self._load()

    def _ensure_dir(self):
        """데이터 디렉토리 생성."""
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)

    def _load(self):
        """저장된 채널을 로드한다."""
        self._ensure_dir()
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    self.channels = json.load(f)
                logger.info("즐겨찾기 %d개 로드됨", len(self.channels))
            except (json.JSONDecodeError, IOError):
                self.channels = list(DEFAULT_CHANNELS)
                self._save()
        else:
            self.channels = list(DEFAULT_CHANNELS)
            self._save()
            logger.info("기본 채널 %d개 생성됨", len(self.channels))

    def _save(self):
        """채널을 파일에 저장한다."""
        self._ensure_dir()
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.channels, f, ensure_ascii=False, indent=2)

    def get_channels(self):
        """모든 채널 반환."""
        return self.channels

    def get_channel(self, index):
        """인덱스로 채널 가져오기."""
        if 0 <= index < len(self.channels):
            return self.channels[index]
        return None

    def get_current(self):
        """현재 선택된 채널."""
        return self.get_channel(self._current_index)

    def get_current_index(self):
        """현재 인덱스."""
        return self._current_index

    def set_current_index(self, index):
        """현재 인덱스 설정."""
        if 0 <= index < len(self.channels):
            self._current_index = index

    def next_channel(self):
        """다음 채널로 이동."""
        if self.channels:
            self._current_index = (self._current_index + 1) % len(self.channels)
        return self.get_current()

    def previous_channel(self):
        """이전 채널로 이동."""
        if self.channels:
            self._current_index = (self._current_index - 1) % len(self.channels)
        return self.get_current()

    def add_channel(self, channel_id, name, ch_type="playlist", description="",
                    artist="", thumbnail=""):
        """채널을 추가한다."""
        channel = {
            "id": channel_id,
            "name": name,
            "type": ch_type,
            "description": description,
            "artist": artist,
            "thumbnail": thumbnail,
        }
        self.channels.append(channel)
        self._save()
        logger.info("채널 추가: %s", name)
        return channel

    def remove_channel(self, index):
        """채널을 삭제한다."""
        if 0 <= index < len(self.channels):
            removed = self.channels.pop(index)
            if self._current_index >= len(self.channels):
                self._current_index = max(0, len(self.channels) - 1)
            self._save()
            logger.info("채널 삭제: %s", removed.get("name"))
            return True
        return False

    def move_channel(self, from_index, to_index):
        """채널 순서를 변경한다."""
        if (0 <= from_index < len(self.channels) and
                0 <= to_index < len(self.channels)):
            channel = self.channels.pop(from_index)
            self.channels.insert(to_index, channel)
            self._save()
            return True
        return False

    def update_channel(self, index, **kwargs):
        """채널 정보를 업데이트한다."""
        if 0 <= index < len(self.channels):
            allowed_keys = {"name", "description", "artist", "thumbnail", "id", "type"}
            for key, value in kwargs.items():
                if key in allowed_keys:
                    self.channels[index][key] = value
            self._save()
            return True
        return False

    def find_by_id(self, channel_id):
        """ID로 채널 찾기."""
        for i, ch in enumerate(self.channels):
            if ch.get("id") == channel_id:
                return i, ch
        return -1, None

    def channel_count(self):
        """채널 수."""
        return len(self.channels)
