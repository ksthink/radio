#!/usr/bin/env python3
"""YouTube Music 로그인 도구 - 명령줄에서 인증 토큰 생성"""

import sys
import os
import json
import logging
from pathlib import Path

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(__file__))

from app.config import load_config
from app.youtube_music import YouTubeMusicPlayer
from app.mpd_client import MPDController

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

def login_youtube(auth_file: str = "data/yt_auth.json"):
    """YouTube Music 인증을 진행합니다."""
    
    try:
        from ytmusicapi import YTMusic
    except ImportError:
        logger.error("❌ ytmusicapi 설치 필요: pip install ytmusicapi")
        return False
    
    auth_path = Path(auth_file)
    auth_path.parent.mkdir(exist_ok=True)
    
    print("\n" + "="*60)
    print("🔐 YouTube Music 로그인")
    print("="*60)
    print("\n⚠️  중요: 다음 단계를 따르세요:\n")
    print("1. 브라우저 인증 페이지가 열립니다")
    print("2. Google 계정으로 로그인하세요")
    print("3. YouTube Music 접근 권한을 허용하세요")
    print("4. 인증 완료 후 이 프로그램이 자동으로 구성됩니다\n")
    
    try:
        logger.info("브라우저 기반 인증 시작...")
        print("🚀 브라우저를 여는 중... (잠시만 기다려주세요)")
        
        headers = YTMusic.auth.get_headers_from_browser()
        
        # 인증 정보 저장
        auth_path.write_text(json.dumps(headers, indent=2, ensure_ascii=False))
        logger.info(f"✓ 인증 정보 저장: {auth_path}")
        
        # 인증 테스트
        yt = YTMusic(auth=str(auth_path))
        logger.info("✓ 인증 테스트 성공")
        
        print("\n✅ YouTube Music 로그인 완료!")
        print(f"📁 인증 정보 저장 위치: {auth_path}")
        print("\n🎉 이제 YouTube Music의 모든 기능을 사용할 수 있습니다!\n")
        
        return True
    
    except Exception as e:
        logger.error(f"❌ 로그인 실패: {e}")
        print(f"\n❌ 오류: {e}\n")
        return False


def check_auth(auth_file: str = "data/yt_auth.json"):
    """인증 상태 확인."""
    auth_path = Path(auth_file)
    
    print("\n" + "="*60)
    print("🔍 YouTube Music 인증 상태 확인")
    print("="*60 + "\n")
    
    if not auth_path.exists():
        print("❌ 인증되지 않음")
        print(f"   인증 파일이 없습니다: {auth_path}")
        print("\n📝 로그인하려면: python3 authenticate_youtube.py login\n")
        return False
    
    try:
        from ytmusicapi import YTMusic
        yt = YTMusic(auth=str(auth_path))
        
        print("✅ 인증됨 (로그인 상태)")
        
        # 사용자 정보 표시 (선택)
        try:
            # YTMusic 객체가 사용자 정보를 반환하면 표시
            print(f"   파일: {auth_path}")
            print(f"   파일 크기: {auth_path.stat().st_size} bytes")
            print(f"   마지막 수정: {auth_path.stat().st_mtime}")
        except:
            pass
        
        print()
        return True
    
    except Exception as e:
        logger.error(f"인증 검사 실패: {e}")
        print(f"❌ 인증 오류: {e}\n")
        return False


def main():
    """메인 함수."""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
    else:
        command = "check"
    
    config = load_config()
    auth_file = config.get("youtube", {}).get("auth_file", "data/yt_auth.json")
    
    if command == "login":
        success = login_youtube(auth_file)
        sys.exit(0 if success else 1)
    
    elif command == "check":
        success = check_auth(auth_file)
        sys.exit(0 if success else 1)
    
    elif command == "logout":
        print("\n" + "="*60)
        print("🔓 YouTube Music 로그아웃")
        print("="*60 + "\n")
        
        auth_path = Path(auth_file)
        if auth_path.exists():
            auth_path.unlink()
            print("✅ 로그아웃 완료 - 인증 파일 삭제됨\n")
        else:
            print("⚠️  이미 로그아웃 상태입니다\n")
        
        sys.exit(0)
    
    else:
        print("""
사용법: python3 authenticate_youtube.py [command]

명령어:
  login   - YouTube Music 로그인 (브라우저 기반)
  check   - 인증 상태 확인 (기본값)
  logout  - 로그아웃

예시:
  python3 authenticate_youtube.py login
  python3 authenticate_youtube.py check
  python3 authenticate_youtube.py logout
        """)
        sys.exit(1)


if __name__ == "__main__":
    main()
