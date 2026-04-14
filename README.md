# 📻 PiRadio - 커스텀 네트워크 라디오

**Raspberry Pi Zero 2 W + Pimoroni Pirate Audio Speaker**로 만드는 YouTube Music 네트워크 라디오.

## 기능

- **YouTube Music / 팟캐스트 재생** — `yt-dlp` + `ytmusicapi` 기반
- **MPD 백엔드** — 안정적인 오디오 재생
- **240x240 LCD UI** — ST7789 디스플레이에 재생 정보, 시계, 날씨 표시
- **4버튼 물리 컨트롤** — 재생/정지, 볼륨, 채널 전환
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
git clone <이 저장소> ~/radio
cd ~/radio
chmod +x setup.sh
./setup.sh
```

### 3. 설정
```bash
nano config.yaml
```
- `weather.api_key`: [OpenWeatherMap](https://openweathermap.org/api)에서 무료 API 키 발급
- `weather.city`: 도시 이름
- 즐겨찾기 채널은 웹 UI에서 관리 가능

### 4. 재부팅
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
| `/api/channels/<i>/play` | POST | 채널 재생 |
| `/api/channels/<i>` | DELETE | 채널 삭제 |
| `/api/search?q=&type=` | GET | YouTube Music 검색 |
| `/api/search/play` | POST | 검색 결과 재생 |
| `/api/alarms` | GET/POST | 알람 목록/추가 |
| `/api/alarms/<id>` | DELETE | 알람 삭제 |
| `/api/alarms/<id>/toggle` | POST | 알람 토글 |
| `/api/sleep` | POST | 슬립 타이머 `{"minutes": 30}` |

## YouTube Music 채널 추가 방법

1. YouTube Music에서 재생목록 URL 확인
   - 예: `https://music.youtube.com/playlist?list=RDCLAK5uy_k...`
2. `list=` 뒤의 ID를 복사
3. 웹 UI의 "채널" 탭에서 추가

또는 검색 탭에서 곡/재생목록을 검색 후 ♡ 버튼으로 즐겨찾기에 추가.

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
