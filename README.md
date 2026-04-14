# 📻 PiRadio - 커스텀 네트워크 라디오

**Raspberry Pi Zero 2 W + Pimoroni Pirate Audio Speaker**로 만드는 YouTube Music 네트워크 라디오.

## 주요 기능

- **YouTube Music / 팟캐스트 재생** — `yt-dlp` + `ytmusicapi` 기반
- **🔐 YouTube 로그인 지원** — 브라우저 인증으로 개인 라이브러리 접근 가능
- **⚡ 성능 최적화** — URL 캐싱 + 병렬 처리로 3배 빠른 로딩
- **MPD 백엔드** — 안정적인 오디오 재생
- **240x240 LCD UI** — ST7789 디스플레이에 재생 정보, 시계, 날씨 표시
- **4버튼 물리 컨트롤** — 재생/정지, 볼륨, 채널 전환 + 🔧 진단 도구
- **웹 리모컨** — 스마트폰/PC에서 원격 제어
- **알람/슬립 타이머** — 지정 시간에 자동 재생/정지
- **날씨 정보** — OpenWeatherMap API 연동
- **즐겨찾기 채널 관리** — YouTube Music 재생목록을 라디오 채널처럼 사용

## 하드웨어

| 부품 | 설명 |
|------|------|
| Raspberry Pi Zero 2 W | 메인 보드 |
| Pimoroni Pirate Audio Speaker | DAC + 스피커 + LCD + 버튼 |
| microSD 카드 (16GB+) | Raspberry Pi OS |
| USB-C 전원 (5V/2.5A) | 전원 공급 |

## 빠른 시작

### 1. Raspberry Pi OS 설치
Raspberry Pi Imager로 **Raspberry Pi OS Bookworm (Lite)** 설치.
SSH와 Wi-Fi 미리 설정.

### 2. PiRadio 설치
```bash
git clone https://github.com/ksthink/radio.git ~/radio
cd ~/radio
chmod +x setup.sh
./setup.sh
```

### 4. YouTube 인증 (선택사항)

더 많은 기능과 개인 라이브러리를 사용하려면 YouTube 로그인하기:

```bash
# 웹 UI에서: http://라디오IP:8080 → 설정 → YouTube 로그인
# 또는 명령줄에서:
python3 authenticate_youtube.py login
```

### 5. 재부팅
```bash
sudo reboot
```

### 5. 접속
- **웹 리모컨**: `http://<라즈베리파이IP>:8080`
- **물리 버튼**: 바로 사용 가능

## 버튼 매핑

| 버튼 | 짧게 누르기 | 길게 누르기 (0.8초) |
|------|-------------|---------------------|
| **A** (BCM 5) | 재생/일시정지 | 시계 화면 |
| **B** (BCM 6) | 볼륨 다운 | 이전 채널 |
| **X** (BCM 16) | 다음 채널 | 채널 목록 |
| **Y** (BCM 24) | 볼륨 업 | 설정 메뉴 |

## 프로젝트 구조

```
radio/
├── config.yaml              # 앱 설정
├── config/
│   ├── mpd.conf             # MPD 설정
│   ├── asound.conf          # ALSA 설정
│   └── boot_config.txt.example
├── app/
│   ├── main.py              # 메인 진입점
│   ├── config.py            # 설정 로더
│   ├── mpd_client.py        # MPD 통신
│   ├── youtube_music.py     # YouTube Music 통합
│   ├── display.py           # ST7789 LCD 제어
│   ├── buttons.py           # GPIO 버튼 핸들러
│   ├── alarm.py             # 알람/슬립 타이머
│   ├── weather.py           # 날씨 정보
│   ├── favorites.py         # 즐겨찾기 채널
│   └── web/
│       ├── server.py        # Flask 웹 서버 + REST API
│       ├── templates/
│       │   └── index.html
│       └── static/
│           ├── style.css
│           └── app.js
├── systemd/
│   └── piradio.service      # systemd 서비스
├── setup.sh                 # 자동 설치 스크립트
└── requirements.txt
```

## 웹 API

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/status` | GET | 현재 상태 |
| `/api/play` | POST | 재생/일시정지 |
| `/api/stop` | POST | 정지 |
| `/api/next` | POST | 다음 채널 |
| `/api/previous` | POST | 이전 채널 |
| `/api/volume` | POST | 볼륨 설정 `{"volume": 50}` |
| `/api/volume/up` | POST | 볼륨 올리기 |
| `/api/volume/down` | POST | 볼륨 내리기 |
| `/api/channels` | GET | 채널 목록 |
| `/api/channels` | POST | 채널 추가 |
| `/api/channels/<i>/play` | POST | 채널 재play |
| `/api/channels/<i>` | DELETE | 채널 삭제 |
| `/api/search?q=&type=` | GET | YouTube Music 검색 |
| `/api/search/play` | POST | 검색 결과 재생 |
| `/api/alarms` | GET/POST | 알람 목록/추가 |
| `/api/alarms/<id>` | DELETE | 알람 삭제 |
| `/api/alarms/<id>/toggle` | POST | 알람 토글 |
| `/api/sleep` | POST | 슬립 타이머 `{"minutes": 30}` |
| **`/api/youtube/auth`** | **POST** | **YouTube 로그인** `{"action": "login"\|"check"}` |
| **`/api/buttons/diagnose`** | **GET** | **버튼 상태 진단** |
| **`/api/buttons/test`** | **POST** | **버튼 테스트** `{"button": "a\|b\|x\|y", "long": bool}` |

## YouTube Music 채널 추가 방법

1. YouTube Music에서 재생목록 URL 확인
   - 예: `https://music.youtube.com/playlist?list=RDCLAK5uy_k...`
2. `list=` 뒤의 ID를 복사
3. 웹 UI의 "채널" 탭에서 추가

또는 검색 탭에서 곡/재생목록을 검색 후 ♡ 버튼으로 즐겨찾기에 추가.

## 성능 최적화 및 유용한 도구

### 🔐 YouTube 인증 도구
```bash
# YouTube Music 로그인 (브라우저 인증)
python3 authenticate_youtube.py login

# 인증 상태 확인
python3 authenticate_youtube.py check

# 로그아웃
python3 authenticate_youtube.py logout
```

### 🎮 GPIO 버튼 진단 및 테스트 도구
```bash
# 버튼 설정 및 상태 진단
python3 test_buttons.py diagnose

# 대화형 버튼 테스트 (실제 버튼 누르기)
python3 test_buttons.py interactive

# 버튼 시뮬레이션
python3 test_buttons.py simulate
python3 test_buttons.py simulate a          # A 버튼만
python3 test_buttons.py simulate abx --long # A, B, X 길게 누르기
```

### ⚡ 성능 최적화 설정

자세한 최적화 가이드는 [OPTIMIZATION.md](OPTIMIZATION.md) 참고:

- **스트림 URL 캐싱**: 30분 TTL로 50% 속도 향상
- **병렬 트랙 로딩**: 3개 동시 처리로 3배 빠른 버퍼링
- **응답 시간 단축**: yt-dlp 타임아웃 최적화
- **버튼 안정성**: 디바운싱 + 스레드 안전성

```yaml
# config.yaml 성능 관련 설정
youtube:
  quality: "bestaudio"
  buffer_tracks: 3           # 느린 네트워크: 2, 빠른 네트워크: 5
  cache_ttl: 1800          # 캐시 만료 시간 (초)

buttons:
  debounce_ms: 250          # 버튼 반응 없음 시: 350-400
  long_press_ms: 800        # 길게누르기 판정 시간
```

## 수동 실행

```bash
source ~/.virtualenvs/piradio/bin/activate
cd ~/radio
python -m app.main
```

## 서비스 관리

```bash
sudo systemctl start piradio      # 시작
sudo systemctl stop piradio       # 정지
sudo systemctl restart piradio    # 재시작
sudo systemctl status piradio     # 상태 확인
journalctl -u piradio -f          # 로그 확인
```

## 트러블슈팅

### 🔘 버튼이 반응이 없음

1. **진단 실행**:
   ```bash
   python3 test_buttons.py diagnose
   # 또는 웹 API: curl http://localhost:8080/api/buttons/diagnose
   ```

2. **디바운싱 값 증가** (config.yaml):
   ```yaml
   buttons:
     debounce_ms: 350  # 기본값 250ms → 350-400ms로 증가
   ```

3. **핀 번호 확인**:
   ```bash
   pinout  # 라즈베리파이 핀 배치 확인
   ```

4. **버튼 테스트**:
   ```bash
   python3 test_buttons.py interactive  # 실제 버튼 누르기
   python3 test_buttons.py simulate a   # 시뮬레이션
   ```

### 📡 YouTube 로그인 페이지가 안 열림

1. **라이브러리 재설치**:
   ```bash
   pip install --upgrade ytmusicapi yt-dlp
   ```

2. **개발자 로그 확인**:
   ```bash
   python3 authenticate_youtube.py login  # 콘솔 에러 메시지 확인
   tail -f logs/piradio.log | grep -i youtube
   ```

3. **토큰 초기화**:
   ```bash
   rm data/yt_auth.json
   python3 authenticate_youtube.py login  # 재로그인
   ```

### ⚡ YouTube 음악이 느려요

1. **캐시 확인**:
   ```bash
   ls -la data/url_*.json | head -5  # 캐시 파일 확인
   ```

2. **버퍼 트랙 수 조정** (config.yaml):
   ```yaml
   youtube:
     buffer_tracks: 2      # 느린 네트워크: 2 (빠른 시작)
     cache_ttl: 1800      # 캐시 유효시간 조정
   ```

3. **yt-dlp 업데이트**:
   ```bash
   pip install --upgrade yt-dlp
   ```

### MPD 연결 실패
```bash
sudo systemctl status mpd
sudo systemctl restart mpd
mpc status
```

### 오디오 안 나옴
```bash
# DAC 확인
aplay -l
# 테스트 사운드
speaker-test -t wav -c 2
# /boot/firmware/config.txt 확인
cat /boot/firmware/config.txt | grep -E "hifiberry|gpio=25|spi"
```

### 디스플레이 안 켜짐
```bash
# SPI 확인
ls /dev/spidev*
# SPI 활성화
sudo raspi-config  # Interface Options > SPI > Enable
```

### yt-dlp 업데이트
```bash
pip install --upgrade yt-dlp
```

## 라이선스

MIT
