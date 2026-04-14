#!/usr/bin/env python3
"""YouTube Music 인증 헤더 생성 도구 (로컬 PC용)

라즈베리파이의 웹 UI에 붙여넣을 headers JSON을 생성합니다.
"""

import sys
import json
from pathlib import Path

def get_headers_from_browser():
    """브라우저 기반 인증으로 headers 생성."""
    try:
        from ytmusicapi import YTMusic
        
        print("\n" + "="*70)
        print("🌐 YouTube Music 인증 헤더 생성")
        print("="*70)
        print("\n⚠️  중요: 다음 단계를 따르세요:\n")
        print("1. 브라우저 인증 페이지가 열립니다")
        print("2. Google 계정으로 로그인하세요")
        print("3. YouTube Music 접근 권한을 허용하세요")
        print("4. 인증 완료 후 자동으로 headers가 생성됩니다\n")
        
        input("엔터를 눌러 시작하세요...")
        
        print("\n🚀 브라우저를 여는 중...\n")
        headers = YTMusic.auth.get_headers_from_browser()
        
        # headers를 JSON으로 포맷팅
        headers_json = json.dumps(headers, indent=2, ensure_ascii=False)
        
        print("\n✅ 인증 성공!\n")
        print("="*70)
        print("📋 다음 JSON을 복사하세요:\n")
        print(headers_json)
        print("\n" + "="*70)
        
        print("\n📝 사용 방법:")
        print("1. 위 JSON을 전체 복사 (Ctrl+A 또는 Cmd+A)")
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
        
        return True
    
    except ImportError:
        print("❌ ytmusicapi 설치 필요: pip install ytmusicapi")
        return False
    except Exception as e:
        print(f"❌ 오류: {e}")
        return False


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
        success = get_headers_from_browser()
        sys.exit(0 if success else 1)
    
    elif command == "show":
        success = load_existing_headers()
        sys.exit(0 if success else 1)
    
    else:
        print("""
🔐 YouTube Music 인증 헤더 생성 도구

사용법: python3 get_youtube_headers.py [command]

명령어:
  new     - 새로운 인증 진행 (브라우저 사용) [기본값]
  show    - 기존 인증 파일의 headers 표시

예시:
  python3 get_youtube_headers.py new
  python3 get_youtube_headers.py show

생성된 headers는 다음 경로에 저장됩니다:
  ~/.config/ytmusicapi/headers_auth.json
        """)
        sys.exit(1)


if __name__ == "__main__":
    main()
