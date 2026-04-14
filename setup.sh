#!/bin/bash
# PiRadio 설치 스크립트 - Raspberry Pi Zero 2 W + Pirate Audio Speaker
# 사용법: chmod +x setup.sh && ./setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$HOME/.virtualenvs/piradio"
CURRENT_USER="$(whoami)"

echo "╔══════════════════════════════════════╗"
echo "║     📻 PiRadio 설치 스크립트        ║"
echo "║   Raspberry Pi Zero 2 W Edition     ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "  사용자: $CURRENT_USER"
echo "  경로:   $SCRIPT_DIR"
echo ""

# ─── 1. 시스템 패키지 ───
echo "▶ [1/7] 시스템 패키지 업데이트 및 설치..."

# apt 캐시 정리 후 업데이트 (미러 오류 대비)
sudo rm -rf /var/lib/apt/lists/*
sudo apt update || {
    echo "⚠ apt update 일부 실패 — 기존 캐시로 계속 진행합니다."
}

# 필수 패키지 (개별 설치로 하나 실패해도 계속 진행)
PACKAGES=(
    mpd mpc
    python3-venv python3-pip python3-dev
    python3-spidev python3-pil python3-numpy python3-lgpio
    libopenjp2-7
    fonts-nanum fonts-nanum-coding
    git
)

for pkg in "${PACKAGES[@]}"; do
    sudo apt install -y "$pkg" 2>/dev/null || echo "⚠ $pkg 설치 건너뜀 (이미 있거나 사용 불가)"
done

# yt-dlp는 pip으로 최신 버전 설치 (apt 버전이 오래됨)
echo "  yt-dlp는 pip으로 설치합니다."

# ─── 2. 부트 설정 ───
echo ""
echo "▶ [2/7] 부트 설정 확인..."

BOOT_CONFIG="/boot/firmware/config.txt"
if [ ! -f "$BOOT_CONFIG" ]; then
    BOOT_CONFIG="/boot/config.txt"
fi

add_boot_config() {
    if ! grep -q "$1" "$BOOT_CONFIG"; then
        echo "$1" | sudo tee -a "$BOOT_CONFIG" > /dev/null
        echo "  추가됨: $1"
    else
        echo "  이미 있음: $1"
    fi
}

add_boot_config "dtoverlay=hifiberry-dac"
add_boot_config "gpio=25=op,dh"
add_boot_config "dtparam=spi=on"

# ─── 3. ALSA 설정 ───
echo ""
echo "▶ [3/7] ALSA 오디오 설정..."
sudo cp "$SCRIPT_DIR/config/asound.conf" /etc/asound.conf
echo "  /etc/asound.conf 설치 완료"

# ─── 4. MPD 설정 ───
echo ""
echo "▶ [4/7] MPD 설정..."
sudo cp "$SCRIPT_DIR/config/mpd.conf" /etc/mpd.conf
sudo systemctl enable mpd
sudo systemctl restart mpd
echo "  MPD 설정 및 시작 완료"

# ─── 5. Python 가상환경 ───
echo ""
echo "▶ [5/7] Python 가상환경 설정..."

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv --system-site-packages "$VENV_DIR"
    echo "  가상환경 생성 완료: $VENV_DIR"
else
    echo "  가상환경 이미 존재: $VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

pip install --upgrade pip

# spidev는 python3-dev가 필요하므로, 시스템 python3-spidev 사용
# (--system-site-packages로 가상환경에서 접근 가능)
pip install \
    python-mpd2 \
    yt-dlp \
    ytmusicapi \
    flask \
    flask-socketio \
    pyyaml \
    Pillow \
    requests \
    schedule \
    gevent \
    st7789 \
    gpiozero

# spidev: python3-dev 있으면 pip으로, 없으면 시스템 패키지 사용
pip install spidev 2>/dev/null || echo "  ⚠ spidev pip 설치 실패 — 시스템 python3-spidev 사용"

# 설치 확인
python -c "import flask; import mpd; print('  핵심 패키지 확인 OK')"

echo "  Python 패키지 설치 완료"

# ─── 6. 데이터 디렉토리 ───
echo ""
echo "▶ [6/7] 디렉토리 생성..."
mkdir -p "$SCRIPT_DIR/data"
mkdir -p "$SCRIPT_DIR/logs"
echo "  data/ 및 logs/ 생성 완료"

# ─── 7. systemd 서비스 ───
echo ""
echo "▶ [7/7] systemd 서비스 설정..."

# 템플릿에서 실제 경로로 서비스 파일 생성
cat > /tmp/piradio.service << EOF
[Unit]
Description=PiRadio - 네트워크 라디오
After=network-online.target mpd.service
Wants=network-online.target

[Service]
Type=simple
User=$CURRENT_USER
Group=$CURRENT_USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$VENV_DIR/bin/python -m app.main
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

Environment=PYTHONUNBUFFERED=1

ProtectSystem=strict
ReadWritePaths=$SCRIPT_DIR/data $SCRIPT_DIR/logs
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF

sudo cp /tmp/piradio.service /etc/systemd/system/piradio.service
rm /tmp/piradio.service
sudo systemctl daemon-reload
sudo systemctl enable piradio
echo "  piradio.service 설치 완료"

# ─── 완료 ───
echo ""
echo "╔══════════════════════════════════════╗"
echo "║        ✅ 설치 완료!                ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "📌 다음 단계:"
echo "  1. config.yaml 수정 (날씨 API 키 등)"
echo "  2. 재부팅: sudo reboot"
echo "  3. 서비스 시작: sudo systemctl start piradio"
echo "  4. 웹 UI 접속: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo '<라즈베리파이IP>'):8080"
echo ""
echo "📌 수동 실행:"
echo "  source $VENV_DIR/bin/activate"
echo "  cd $SCRIPT_DIR"
echo "  python -m app.main"
echo ""
echo "📌 로그 확인:"
echo "  journalctl -u piradio -f"
echo "  tail -f $SCRIPT_DIR/logs/piradio.log"
