#!/bin/bash
# PiRadio 설치 스크립트 - Raspberry Pi Zero 2 W + Pirate Audio Speaker
# 사용법: chmod +x setup.sh && ./setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$HOME/.virtualenvs/piradio"

echo "╔══════════════════════════════════════╗"
echo "║     📻 PiRadio 설치 스크립트        ║"
echo "║   Raspberry Pi Zero 2 W Edition     ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ─── 1. 시스템 패키지 ───
echo "▶ [1/7] 시스템 패키지 업데이트 및 설치..."
sudo apt update
sudo apt install -y \
    mpd mpc \
    python3-venv python3-pip python3-dev \
    python3-spidev python3-pil python3-numpy python3-lgpio \
    libopenjp2-7 \
    fonts-nanum fonts-nanum-coding \
    yt-dlp \
    git

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
python3 -m venv --system-site-packages "$VENV_DIR"
source "$VENV_DIR/bin/activate"

pip install --upgrade pip
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
SERVICE_FILE="$SCRIPT_DIR/systemd/piradio.service"

# 실제 경로로 업데이트
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$SCRIPT_DIR|" "$SERVICE_FILE"
sed -i "s|ExecStart=.*|ExecStart=$VENV_DIR/bin/python -m app.main|" "$SERVICE_FILE"
sed -i "s|User=.*|User=$(whoami)|" "$SERVICE_FILE"
sed -i "s|Group=.*|Group=$(whoami)|" "$SERVICE_FILE"
sed -i "s|ReadWritePaths=.*|ReadWritePaths=$SCRIPT_DIR/data $SCRIPT_DIR/logs|" "$SERVICE_FILE"

sudo cp "$SERVICE_FILE" /etc/systemd/system/piradio.service
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
echo "  4. 웹 UI 접속: http://$(hostname -I | awk '{print $1}'):8080"
echo ""
echo "📌 수동 실행:"
echo "  source $VENV_DIR/bin/activate"
echo "  cd $SCRIPT_DIR"
echo "  python -m app.main"
echo ""
echo "📌 로그 확인:"
echo "  journalctl -u piradio -f"
echo "  tail -f logs/piradio.log"
