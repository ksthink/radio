"""YouTube Music 통합 모듈 - yt-dlp + ytmusicapi"""

import logging
import os
import subprocess
import sys
import json
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# virtualenv 내 yt-dlp 절대경로 (systemd에서 PATH 문제 방지)
YT_DLP_BIN = os.path.join(os.path.dirname(sys.executable), "yt-dlp")
if not os.path.exists(YT_DLP_BIN):
    YT_DLP_BIN = "yt-dlp"


class YouTubeMusicPlayer:
    """YouTube Music에서 음악을 검색하고 스트림 URL을 추출하는 클래스."""

    def __init__(self, mpd_controller, quality="bestaudio", buffer_tracks=3):
        self.mpd = mpd_controller
        self.quality = quality
        self.buffer_tracks = buffer_tracks
        self._ytmusic = None
        self._current_queue = []
        self._current_index = 0
        self._current_channel = None
        self._current_track = None  # 현재 재생 중인 트랙 정보
        self._lock = threading.Lock()
        self._radio_fail_ids = set()  # 라디오 트랙 가져오기 실패한 ID 캐시

    def _get_ytmusic(self):
        """ytmusicapi 인스턴스를 반환 (지연 로딩)."""
        if self._ytmusic is None:
            try:
                from ytmusicapi import YTMusic
                self._ytmusic = YTMusic()
                logger.info("YTMusic API 초기화 완료")
            except ImportError:
                logger.error("ytmusicapi가 설치되지 않음: pip install ytmusicapi")
                raise
        return self._ytmusic

    def extract_stream_url(self, video_id: str) -> Optional[str]:
        """yt-dlp로 YouTube 영상의 오디오 스트림 URL을 추출한다."""
        url = f"https://music.youtube.com/watch?v={video_id}"
        try:
            result = subprocess.run(
                [
                    YT_DLP_BIN,
                    "--no-playlist",
                    "-f", self.quality,
                    "--get-url",
                    "--no-warnings",
                    "--no-check-certificates",
                    url,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                stream_url = result.stdout.strip().split("\n")[0]
                logger.debug("스트림 URL 추출 성공: %s", video_id)
                return stream_url
            else:
                logger.error("yt-dlp 실패: %s", result.stderr[:200])
                return None
        except subprocess.TimeoutExpired:
            logger.error("yt-dlp 타임아웃: %s", video_id)
            return None
        except FileNotFoundError:
            logger.error("yt-dlp가 설치되지 않음")
            return None

    def get_video_info(self, video_id: str) -> Optional[dict]:
        """yt-dlp로 영상 메타정보를 가져온다."""
        url = f"https://music.youtube.com/watch?v={video_id}"
        try:
            result = subprocess.run(
                [
                    YT_DLP_BIN,
                    "--no-playlist",
                    "-j",
                    "--no-warnings",
                    "--no-check-certificates",
                    url,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
            return None
        except Exception as e:
            logger.error("영상 정보 가져오기 실패: %s", e)
            return None

    def search(self, query: str, limit: int = 10, filter_type: str = "songs"):
        """YouTube Music에서 검색한다.

        filter_type: "songs", "videos", "albums", "artists", "playlists", "podcasts"
        """
        yt = self._get_ytmusic()
        # filter 검색 시도, 결과 없으면 필터 없이 재시도
        try:
            results = yt.search(query, filter=filter_type, limit=limit)
        except Exception:
            results = []
        if not results:
            try:
                results = yt.search(query, limit=limit)
            except Exception as e:
                logger.error("검색 실패: %s", e)
                results = []
        tracks = []
        for item in results:
            video_id = item.get("videoId")
            if not video_id:
                continue  # videoId 없는 결과 건너뛰기 (앨범, 아티스트 등)
            track = {
                "id": video_id,
                "title": item.get("title", "알 수 없음"),
                "artist": "",
                "duration": item.get("duration", ""),
                "type": filter_type,
            }
            artists = item.get("artists", [])
            if artists:
                track["artist"] = ", ".join(a.get("name", "") for a in artists if a)
            thumbnail = item.get("thumbnails", [{}])
            track["thumbnail"] = thumbnail[-1].get("url", "") if thumbnail else ""
            tracks.append(track)
        return tracks

    def search_podcasts(self, query: str, limit: int = 10):
        """YouTube 팟캐스트를 검색한다."""
        yt = self._get_ytmusic()
        results = yt.search(query, filter="podcasts", limit=limit)
        podcasts = []
        for item in results:
            podcast = {
                "id": item.get("browseId", ""),
                "title": item.get("title", "알 수 없음"),
                "author": "",
                "type": "podcast",
            }
            author = item.get("author")
            if author:
                podcast["author"] = author.get("name", "") if isinstance(author, dict) else str(author)
            thumbnail = item.get("thumbnails", [{}])
            podcast["thumbnail"] = thumbnail[-1].get("url", "") if thumbnail else ""
            podcasts.append(podcast)
        return podcasts

    def get_playlist_tracks(self, playlist_id: str):
        """YouTube Music 플레이리스트의 트랙 목록을 가져온다."""
        yt = self._get_ytmusic()
        playlist = yt.get_playlist(playlist_id, limit=100)
        tracks = []
        for item in playlist.get("tracks", []):
            video_id = item.get("videoId")
            if not video_id:
                continue
            track = {
                "id": video_id,
                "title": item.get("title", "알 수 없음"),
                "artist": "",
                "duration": item.get("duration", ""),
            }
            artists = item.get("artists", [])
            if artists:
                track["artist"] = ", ".join(a.get("name", "") for a in artists if a)
            thumbnail = item.get("thumbnails", [{}])
            track["thumbnail"] = thumbnail[-1].get("url", "") if thumbnail else ""
            tracks.append(track)
        return tracks

    def get_radio_tracks(self, video_id: str):
        """특정 곡 기반으로 라디오(자동 재생) 트랙을 가져온다."""
        yt = self._get_ytmusic()
        try:
            watch = yt.get_watch_playlist(videoId=video_id, limit=25)
            tracks = []
            for item in watch.get("tracks", []):
                vid = item.get("videoId")
                if not vid:
                    continue
                track = {
                    "id": vid,
                    "title": item.get("title", "알 수 없음"),
                    "artist": "",
                    "duration": item.get("length", ""),
                }
                artists = item.get("artists", [])
                if artists:
                    track["artist"] = ", ".join(a.get("name", "") for a in artists if a)
                thumbnail = item.get("thumbnail", [{}])
                if isinstance(thumbnail, list):
                    track["thumbnail"] = thumbnail[-1].get("url", "") if thumbnail else ""
                else:
                    track["thumbnail"] = ""
                tracks.append(track)
            return tracks
        except Exception as e:
            logger.error("라디오 트랙 가져오기 실패: %s", e)
            return []

    def play_track(self, video_id: str, title: str = "", artist: str = "", thumbnail: str = ""):
        """단일 트랙을 재생한다."""
        stream_url = self.extract_stream_url(video_id)
        if stream_url:
            track_info = {
                "id": video_id,
                "title": title,
                "artist": artist,
                "thumbnail": thumbnail,
            }
            self.mpd.add_and_play(stream_url)
            with self._lock:
                self._current_queue = [track_info]
                self._current_index = 0
                self._current_channel = None
                self._current_track = track_info
            logger.info("재생 시작: %s (%s)", title, video_id)
            return True
        logger.error("재생 실패: %s", video_id)
        return False

    def play_channel(self, channel: dict):
        """채널(즐겨찾기)을 재생한다. 채널 타입에 따라 동작이 다르다."""
        with self._lock:
            self._current_channel = channel
            ch_type = channel.get("type", "track")
            ch_id = channel.get("id", "")

            if ch_type == "playlist":
                tracks = self.get_playlist_tracks(ch_id)
            elif ch_type == "radio":
                tracks = self.get_radio_tracks(ch_id)
            elif ch_type == "track":
                tracks = [channel]
            else:
                tracks = [channel]

            if not tracks:
                logger.error("채널에서 트랙을 가져올 수 없음: %s", channel.get("name"))
                return False

            self._current_queue = tracks
            self._current_index = 0
            self._current_track = tracks[0] if tracks else None
            return self._queue_and_play()

    def _queue_and_play(self):
        """현재 큐의 트랙을 MPD에 추가하고 재생한다."""
        self.mpd.clear_playlist()
        end = min(self._current_index + self.buffer_tracks, len(self._current_queue))

        for i in range(self._current_index, end):
            track = self._current_queue[i]
            stream_url = self.extract_stream_url(track["id"])
            if stream_url:
                self.mpd.add_track(stream_url)

        if self.mpd.playlist_length() > 0:
            self.mpd.play(0)
            return True
        return False

    def queue_next_tracks(self):
        """재생 중 다음 트랙들을 미리 큐에 추가한다."""
        with self._lock:
            if not self._current_queue:
                return

            playlist_len = self.mpd.playlist_length()
            status = self.mpd.get_status()
            current_pos = int(status.get("song", 0))

            remaining = playlist_len - current_pos - 1
            if remaining < 2:
                self._current_index += self.buffer_tracks
                if self._current_index >= len(self._current_queue):
                    # 큐 끝에 도달: 라디오 모드면 새 트랙 가져오기
                    if self._current_channel and self._current_queue:
                        last_id = self._current_queue[-1]["id"]
                        if last_id in self._radio_fail_ids:
                            return  # 이미 실패한 ID는 재시도하지 않음
                        new_tracks = self.get_radio_tracks(last_id)
                        if new_tracks:
                            self._current_queue.extend(new_tracks[1:])
                        else:
                            self._radio_fail_ids.add(last_id)
                            logger.warning("라디오 트랙 가져오기 실패, 재시도 안 함: %s", last_id)
                            return

                end = min(
                    self._current_index + self.buffer_tracks,
                    len(self._current_queue),
                )
                for i in range(self._current_index, end):
                    track = self._current_queue[i]
                    stream_url = self.extract_stream_url(track["id"])
                    if stream_url:
                        self.mpd.add_track(stream_url)

    def get_current_track_info(self):
        """현재 재생 중인 트랙의 메타정보."""
        return self._current_track

    def next_track(self):
        """다음 트랙으로 이동."""
        self.mpd.next()
        # 버퍼 체크를 별도 스레드로
        threading.Thread(target=self.queue_next_tracks, daemon=True).start()

    def previous_track(self):
        """이전 트랙으로 이동."""
        self.mpd.previous()
