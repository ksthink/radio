#!/usr/bin/env python3
"""YouTube Music 인증 헤더 생성 도구 (로컬 PC용)

브라우저의 cookies를 추출하여 headers JSON을 생성합니다.
"""

import sys
import json
from pathlib import Path

def create_headers_from_cookies():
    """브라우저의 cookies에서 headers 생성."""
    
    print("\n" + "="*70)
    print("🌐 YouTube Music 인증 헤더 생성 (Cookie 방식)")
    print("="*70)
    
    print("""
⚠️  중요: 다음 단계를 따르세요:

1️⃣  YouTube Music 웹사이트 접속:
   https://music.youtube.com/

2️⃣  Google 계정으로 로그인

3️⃣  브라우저 개발자 도구 열기:
   Windows/Linux: F12 또는 Ctrl+Shift+I
   Mac: Cmd+Option+I

4️⃣  'Storage' 또는 'Application' 탭 클릭

5️⃣  왼쪽 메뉴에서 'Cookies' → 'music.youtube.com' 선택

6️⃣  'SAPISID' 또는 'Cookie' 값 찾기

7️⃣  다음 중 하나를 선택:
""")
    
    print("\n   [방법 A] SAPISID 이용 (간단함)")
    print("   " + "-"*60)
    sapisid = input("\n   SAPISID 값을 붙여넣으세요 (없으면 Enter): ").strip()
    
    if sapisid:
        headers = {
            "Authorization": f"SAPISIDHASH {sapisid}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        headers_json = json.dumps(headers, indent=2, ensure_ascii=False)
        save_and_display_headers(headers_json)
        return True
    
    print("\n   [방법 B] 전체 Cookies 이용")
    print("   " + "-"*60)
    print("   'Cookies' 리스트에서 모든 항목 선택 (Ctrl+A)")
    print("   우측 클릭 → '복사' → 아래에 붙여넣기\n")
    
    cookies_text = input("   Cookie 값들을 붙여넣으세요: ").strip()
    
    if cookies_text:
        headers = {
            "Cookie": cookies_text,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        headers_json = json.dumps(headers, indent=2, ensure_ascii=False)
        save_and_display_headers(headers_json)
        return True
    
    print("\n❌ 입력값이 없습니다.")
    return False


def save_and_display_headers(headers_json):
    """headers를 저장하고 표시."""
    print("\n✅ 인증 성공!\n")
    print("="*70)
    print("📋 다음 JSON을 복사하세요:\n")
    print(headers_json)
    print("\n" + "="*70)
    
    print("\n📝 사용 방법:")
    print("1. 위 JSON을 전체 복사 (Ctrl+A)")
    print("2. 라즈베리파이 웹 UI 접속: http://라즈베리파이IP:8080")
    print("3. '설정' 탭 → 'YouTube Music 인증' 섹션")
    print("4. 텍스트박스에 붙여넣기")
    print("5. 'YouTube 로그인' 버튼 클릭\n")
    
    # 파일로도 저장
    config_dir = Path.home() / ".config" / "ytmusicapi"
    config_dir.mkdir(exist_ok=True, parents=True)
    auth_file = config_dir / "headers_auth.json"
    auth_file.write_text(headers_json)
    
    print(f"💾 저장 위치: {auth_file}")
    print(f"   (필요시 이 파일을 라즈베리파이의 data/yt_auth.json으로 복사 가능)\n")


def load_existing_headers():
    """기존 인증 파일에서 headers 로드."""
    config_dir = Path.home() / ".config" / "ytmusicapi"
    auth_file = config_dir / "headers_auth.json"
    
    if auth_file.exists():
        try:
            headers_json = auth_file.read_text()
            print(f"\n✅ 기존 인증 파일을 찾았습니다:\n")
            print("="*70)
            print(headers_json)
            print("="*70)
            print(f"\n위 JSON을 라즈베리파이 웹 UI에 붙여넣으세요.\n")
            return True
        except Exception as e:
            print(f"❌ 파일 로드 실패: {e}")
            return False
    else:
        print(f"❌ 인증 파일을 찾을 수 없습니다: {auth_file}")
        print("   먼저 'python3 get_youtube_headers.py new' 로 인증을 진행하세요.\n")
        return False


def main():
    """메인 함수."""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
    else:
        command = "new"
    
    if command == "new":
        success = create_headers_from_cookies()
        sys.exit(0 if success else 1)
    
    elif command == "show":
        success = load_existing_headers()
        sys.exit(0 if success else 1)
    
    else:
        print("""
🔐 YouTube Music 인증 헤더 생성 도구

사용법: python3 get_youtube_headers.py [command]

명령어:
  new     - 새로운 인증 진행 (브라우저 개발자 도구 사용) [기본값]
  show    - 기존 인증 파일의 headers 표시

예시:
  python3 get_youtube_headers.py new
  python3 get_youtube_headers.py show

설명:
  1. YouTube Music 웹사이트 방문
  2. 개발자 도구(F12) → Storage → Cookies에서 추출
  3. 생성된 headers를 라즈베리파이에 입력

생성된 headers는 다음 경로에 저장됩니다:
  ~/.config/ytmusicapi/headers_auth.json
        """)
        sys.exit(1)


if __name__ == "__main__":
    main()

