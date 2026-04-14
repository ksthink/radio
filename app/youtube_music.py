"""YouTube Music 통합 모듈 - yt-dlp + ytmusicapi (로그인 지원, 캐싱, 병렬 처리 최적화)"""

import logging
import os
import subprocess
import sys
import json
import threading
import time
import hashlib
from typing import Optional, Dict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

logger = logging.getLogger(__name__)

# virtualenv 내 yt-dlp 절대경로 (systemd에서 PATH 문제 방지)
YT_DLP_BIN = os.path.join(os.path.dirname(sys.executable), "yt-dlp")
if not os.path.exists(YT_DLP_BIN):
    YT_DLP_BIN = "yt-dlp"


class URLCache:
    """스트림 URL 캐시 (시간 기반, 30분 TTL)."""
    def __init__(self, cache_dir: str = "data", ttl_seconds: int = 1800):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.ttl = ttl_seconds
        self.memory_cache = {}  # 빠른 접근용 메모리 캐시
        
    def _get_cache_key(self, video_id: str) -> str:
        return hashlib.md5(video_id.encode()).hexdigest()[:8]
    
    def get(self, video_id: str) -> Optional[str]:
        """캐시에서 URL 가져오기."""
        # 메모리 캐시 확인
        if video_id in self.memory_cache:
            url, timestamp = self.memory_cache[video_id]
            if time.time() - timestamp < self.ttl:
                return url
            del self.memory_cache[video_id]
        
        # 파일 캐시 확인
        cache_key = self._get_cache_key(video_id)
        cache_file = self.cache_dir / f"url_{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    if time.time() - data.get('timestamp', 0) < self.ttl:
                        # 메모리 캐시에도 저장
                        self.memory_cache[video_id] = (data['url'], data['timestamp'])
                        return data['url']
                    cache_file.unlink()  # 만료된 캐시 삭제
            except Exception as e:
                logger.warning(f"캐시 로드 실패: {e}")
        return None
    
    def set(self, video_id: str, url: str):
        """캐시에 URL 저장."""
        timestamp = time.time()
        self.memory_cache[video_id] = (url, timestamp)
        
        cache_key = self._get_cache_key(video_id)
        cache_file = self.cache_dir / f"url_{cache_key}.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump({'url': url, 'timestamp': timestamp}, f)
        except Exception as e:
            logger.warning(f"캐시 저장 실패: {e}")
    
    def clear_expired(self):
        """만료된 캐시 정리."""
        current_time = time.time()
        for cache_file in self.cache_dir.glob("url_*.json"):
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    if current_time - data.get('timestamp', 0) >= self.ttl:
                        cache_file.unlink()
            except Exception:
                pass


class YouTubeMusicPlayer:
    """YouTube Music에서 음악을 검색하고 스트림 URL을 추출하는 클래스 (로그인 지원)."""

    def __init__(self, mpd_controller, quality="bestaudio", buffer_tracks=3, auth_file: str = "data/yt_auth.json"):
        self.mpd = mpd_controller
        self.quality = quality
        self.buffer_tracks = buffer_tracks
        self.auth_file = Path(auth_file)
        self._ytmusic = None
        self._current_queue = []
        self._current_index = 0
        self._current_channel = None
        self._current_track = None
        self._lock = threading.Lock()
        self._radio_fail_ids = set()
        self._url_cache = URLCache()
        self._executor = ThreadPoolExecutor(max_workers=3)  # 병렬 처리용
        self.auth_file.parent.mkdir(exist_ok=True)
        logger.info("YouTubeMusicPlayer 초기화 완료 (캐싱, 병렬 처리 활성화)")

    def authenticate_browser(self):
        """브라우저를 통한 인증 (사용자 상호작용 필요).
        
        라즈베리파이 환경에서는 직접 실행 불가능.
        로컬 PC에서 다음을 실행:
        python3 -c "from ytmusicapi import YTMusic; YTMusic.auth.get_headers_from_browser()"
        
        생성된 ~/.config/ytmusicapi/headers_auth.json을 복사해서 사용.
        """
        try:
            from ytmusicapi import YTMusic
            logger.info("⚠️ 라즈베리파이 환경: 브라우저 기반 인증 직접 지원 불가")
            logger.info("📝 다음 중 하나를 선택하세요:")
            logger.info("   1. 로컬 PC에서 다음 실행: python3 -c \"from ytmusicapi import YTMusic; YTMusic.auth.get_headers_from_browser()\"")
            logger.info("   2. 생성된 ~/.config/ytmusicapi/headers_auth.json을 data/yt_auth.json으로 복사")
            logger.info("   3. 또는 웹 UI의 설정에서 headers JSON을 직접 붙여넣기")
            
            return False
        except Exception as e:
            logger.error(f"브라우저 인증 실패: {e}")
            return False

    def set_headers_from_json(self, headers_json: str) -> bool:
        """headers JSON 문자열로 직접 인증 (웹 UI에서 사용).
        
        로컬 PC에서 생성한 headers.json 내용을 직접 입력.
        """
        try:
            import json
            headers = json.loads(headers_json)
            self.auth_file.write_text(json.dumps(headers, indent=2))
            self._ytmusic = None  # 캐시 초기화
            
            # 인증 테스트
            yt = self._get_ytmusic()
            logger.info("✓ 인증 테스트 성공")
            return True
        except json.JSONDecodeError:
            logger.error("JSON 형식이 올바르지 않음")
            return False
        except Exception as e:
            logger.error(f"인증 설정 실패: {e}")
            return False

    def set_api_key(self, api_key: str):
        """API 키로 인증 (옵션)."""
        try:
            auth_data = {"api_key": api_key}
            self.auth_file.write_text(json.dumps(auth_data))
            logger.info("API 키 저장 완료")
            self._ytmusic = None  # 캐시 초기화
            return True
        except Exception as e:
            logger.error(f"API 키 설정 실패: {e}")
            return False

    def is_authenticated(self) -> bool:
        """인증 상태 확인."""
        return self.auth_file.exists()

    def _get_ytmusic(self):
        """ytmusicapi 인스턴스를 반환 (지연 로딩)."""
        if self._ytmusic is None:
            try:
                from ytmusicapi import YTMusic
                
                # 저장된 인증 정보로 로그인
                if self.auth_file.exists():
                    try:
                        self._ytmusic = YTMusic(auth=str(self.auth_file))
                        logger.info("저장된 인증으로 YTMusic API 초기화")
                    except Exception as e:
                        logger.warning(f"저장된 인증 실패, 익명 모드로 전환: {e}")
                        self._ytmusic = YTMusic()
                else:
                    # 비로그인 (제한적 기능)
                    self._ytmusic = YTMusic()
                    logger.info("YTMusic API 초기화 (비로그인)")
            except ImportError:
                logger.error("ytmusicapi 설치 필요: pip install ytmusicapi")
                raise
        return self._ytmusic

    def extract_stream_url(self, video_id: str, use_cache: bool = True) -> Optional[str]:
        """yt-dlp로 YouTube 영상의 오디오 스트림 URL을 추출한다 (캐싱 적용)."""
        # 캐시 확인
        if use_cache:
            cached_url = self._url_cache.get(video_id)
            if cached_url:
                logger.debug(f"캐시된 URL 사용: {video_id}")
                return cached_url
        
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
                    "--socket-timeout", "15",  # 타임아웃 15초로 단축
                    url,
                ],
                capture_output=True,
                text=True,
                timeout=20,
            )
            if result.returncode == 0 and result.stdout.strip():
                stream_url = result.stdout.strip().split("\n")[0]
                self._url_cache.set(video_id, stream_url)  # 캐시 저장
                logger.debug(f"스트림 URL 추출 성공 (캐쉬 저장): {video_id}")
                return stream_url
            else:
                logger.warning(f"yt-dlp 추출 실패: {result.stderr[:100]}")
                return None
        except subprocess.TimeoutExpired:
            logger.error(f"yt-dlp 타임아웃: {video_id}")
            return None
        except FileNotFoundError:
            logger.error("yt-dlp이 설치되지 않음")
            return None
        except Exception as e:
            logger.error(f"URL 추출 오류: {e}")
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
        """현재 큐의 트랙을 MPD에 추가하고 재생한다 (병렬 처리)."""
        self.mpd.clear_playlist()
        end = min(self._current_index + self.buffer_tracks, len(self._current_queue))
        
        # 병렬로 URL 추출
        tracks_to_add = self._current_queue[self._current_index:end]
        futures = {
            self._executor.submit(self.extract_stream_url, track["id"]): track 
            for track in tracks_to_add
        }
        
        added_count = 0
        for future in futures:
            try:
                stream_url = future.result(timeout=25)  # 개별 타임아웃
                if stream_url:
                    track = futures[future]
                    self.mpd.add_track(stream_url)
                    added_count += 1
            except Exception as e:
                logger.warning(f"트랙 추가 실패: {e}")

        if added_count > 0:
            self.mpd.play(0)
            logger.info(f"재생 시작 ({added_count}개 트랙 추가)")
            return True
        return False

    def queue_next_tracks(self):
        """재생 중 다음 트랙들을 미리 큐에 추가한다 (병렬 처리)."""
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

                # 병렬로 다음 트랙들 추가
                end = min(
                    self._current_index + self.buffer_tracks,
                    len(self._current_queue),
                )
                tracks_to_add = self._current_queue[self._current_index:end]
                futures = {
                    self._executor.submit(self.extract_stream_url, track["id"]): track
                    for track in tracks_to_add
                }
                
                for future in futures:
                    try:
                        stream_url = future.result(timeout=25)
                        if stream_url:
                            self.mpd.add_track(stream_url)
                    except Exception as e:
                        logger.warning(f"트랙 추가 실패: {e}")

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
