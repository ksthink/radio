#!/usr/bin/env python3
"""GPIO 버튼 진단 및 테스트 도구"""

import sys
import os
import json
import time
import logging
from pathlib import Path

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(__file__))

from app.config import load_config
from app.buttons import ButtonHandler

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

def diagnose_buttons():
    """GPIO 버튼 진단."""
    print("\n" + "="*70)
    print("🔍 GPIO 버튼 진단")
    print("="*70)
    
    config = load_config()
    button_cfg = config.get("buttons", {})
    
    print("\n📋 설정 정보:")
    print(f"  A (BCM {button_cfg.get('a', 5)}):  재생/일시정지")
    print(f"  B (BCM {button_cfg.get('b', 6)}):  볼륨 다운")
    print(f"  X (BCM {button_cfg.get('x', 16)}): 다음 채널")
    print(f"  Y (BCM {button_cfg.get('y', 24)}): 볼륨 업")
    print(f"\n  길게누르기: {button_cfg.get('long_press_ms', 800)}ms")
    print(f"  디바운싱: {button_cfg.get('debounce_ms', 250)}ms")
    
    # 버튼 핸들러 초기화
    handlers = {}
    for btn_name in ['a', 'b', 'x', 'y']:
        def make_callback(name):
            return lambda: logger.info(f"📢 콜백 실행: {name.upper()}")
        handlers[f'on_{btn_name}'] = make_callback(btn_name)
    
    handler = ButtonHandler(button_cfg, callbacks=handlers)
    
    # 진단 정보 출력
    print("\n🔧 진단 결과:")
    diagnosis = handler.diagnose()
    
    print(f"  GPIO 사용 가능: {'✅ 예' if diagnosis['gpio_available'] else '❌ 아니오'}")
    print(f"  버튼 초기화됨: {diagnosis['buttons_initialized']}/4")
    
    print("\n  개별 버튼 상태:")
    for btn_name, btn_info in diagnosis['buttons'].items():
        status = "✅ OK" if btn_info['initialized'] else "❌ 실패"
        state = f"({btn_info['state']})"
        print(f"    {btn_name.upper()}: BCM {btn_info['pin']} {status} {state}")
    
    handler.cleanup()
    return diagnosis['gpio_available']


def test_buttons_interactive():
    """대화형 버튼 테스트."""
    print("\n" + "="*70)
    print("🎮 버튼 테스트 (대화형)")
    print("="*70)
    print("\n버튼을 눌러 보세요. Ctrl+C로 종료\n")
    
    config = load_config()
    button_cfg = config.get("buttons", {})
    
    press_count = {'a': 0, 'b': 0, 'x': 0, 'y': 0}
    
    def make_callback(name):
        def callback():
            press_count[name] += 1
            print(f"\n🔔 {name.upper()} 버튼 누름! (총 {press_count[name]}회)")
        return callback
    
    callbacks = {
        'on_a': make_callback('a'),
        'on_b': make_callback('b'),
        'on_x': make_callback('x'),
        'on_y': make_callback('y'),
    }
    
    handler = ButtonHandler(button_cfg, callbacks=callbacks)
    
    try:
        print("버튼 대기 중...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n✅ 테스트 종료")
        print("\n📊 결과:")
        for btn, count in press_count.items():
            print(f"  {btn.upper()}: {count}회")
    finally:
        handler.cleanup()


def test_buttons_simulated(buttons: str = "abxy", long_press: bool = False):
    """시뮬레이션 버튼 테스트."""
    print("\n" + "="*70)
    print("🎮 버튼 시뮬레이션 테스트")
    print("="*70)
    
    config = load_config()
    button_cfg = config.get("buttons", {})
    
    press_log = []
    
    def make_callback(name):
        def callback():
            press_type = "길게" if long_press else "짧게"
            msg = f"  {name.upper()} {press_type} 누름 ✓"
            print(msg)
            press_log.append((name, long_press))
        return callback
    
    callbacks = {
        'on_a': make_callback('a'),
        'on_b': make_callback('b'),
        'on_x': make_callback('x'),
        'on_y': make_callback('y'),
    }
    
    handler = ButtonHandler(button_cfg, callbacks=callbacks)
    
    print(f"\n테스트 모드: {'길게 누르기' if long_press else '짧게 누르기'}")
    print(f"테스트 버튼: {buttons.upper()}\n")
    
    for btn in buttons.lower():
        if btn in 'abxy':
            handler.simulate_press(btn, long=long_press)
            time.sleep(0.5)
    
    print(f"\n✅ 테스트 완료 ({len(press_log)}개 이벤트)")
    handler.cleanup()


def main():
    """메인 함수."""
    if len(sys.argv) < 2:
        command = "diagnose"
    else:
        command = sys.argv[1].lower()
    
    if command == "diagnose" or command == "-d":
        diagnose_buttons()
    
    elif command == "interactive" or command == "-i":
        test_buttons_interactive()
    
    elif command == "simulate" or command == "-s":
        if len(sys.argv) > 2:
            buttons = sys.argv[2]
        else:
            buttons = "abxy"
        
        long_press = "--long" in sys.argv or "-l" in sys.argv
        test_buttons_simulated(buttons, long_press)
    
    else:
        print("""
🎮 GPIO 버튼 진단 및 테스트 도구

사용법: python3 test_buttons.py [command] [options]

명령어:
  diagnose [-d]              버튼 설정 및 상태 진단
  interactive [-i]           대화형 버튼 테스트 (실제 버튼 누르기)
  simulate [-s] [buttons]    버튼 시뮬레이션 (a, b, x, y)

예시:
  python3 test_buttons.py diagnose
  python3 test_buttons.py interactive
  python3 test_buttons.py simulate
  python3 test_buttons.py simulate a               # A 버튼만 테스트
  python3 test_buttons.py simulate abx --long     # A, B, X 길게 누르기
  
기타:
  --long, -l    길게 누르기 (기본: 짧게 누르기)
        """)
        sys.exit(1)


if __name__ == "__main__":
    main()
