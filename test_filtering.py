#!/usr/bin/env python3
"""
NOTAM 필터링 테스트 스크립트
기술정보 섹션이 제대로 제외되는지 확인
"""
import sys
import os
sys.path.append('src')

# 직접 import 방식으로 변경
from src.notam_filter import NOTAMFilter

# 테스트용 NOTAM 텍스트 (기술정보 포함)
test_text = """
â—C¼O MPANY MINIMA FOR CAT II/III
RWY 15L/15R CAT II : DH 100FT, RVR 300M / 175M / 75M OR DH 100FT,
RVR 450M / 150M / 75M CAT III (Fail-Passive) : DH 50FT, RVR 175M / 175M / 75M
CAT III (Fail-Operational) : AH 100FT, RVR 75M / 75M / 75M

â—D¼E PARTURE AIRPORT TECHNICAL INFORMATION
TAKEOFF PERFORMANCE INFORMATION
// REFER TO THE FOLLOWING INTX TAKEOFF INFO //
IF THE INTX INFORMATION BELOW IS NOT VISIBLE IN THE LIST, ENTER THE
REDUCED LENGTH AS SHOWN BELOW.
15L-D4/C8 TAKEOFF
- EFB: INPUT 3937 (TAKEOFF SHORTENING FROM RWY START)

â—C¼O MPANY ADVISORY
1. 20FEB25 00:00 - UFN RKSI COAD01/25
// ICN EXTERNAL ELECTRICAL POWER DISCONNECTION CONFIRMATION //
BEFORE DOOR CLOSE & PBB DISCONNECTION,
CHECK THE OVERHEAD ELEC PANEL TO CONFIRM EXTERNAL ELECTRICAL
-- BY SELOQ--

â—R¼U NWAY
09JUL25 16:00 - 25SEP25 09:00 RKSI Z0582/25
E) TRIGGER NOTAM - AIRAC AIP SUP 52/25
WEF 1600 UTC 9 JUL 2025 TIL 0900 UTC 1 AUG 2025
- RWY 15L/33R WILL BE CLOSED DUE TO PAVEMENT CONSTRUCTION.

â—T¼A XIWAY
08SEP25 06:45 - 22OCT25 23:00 KSEA A2380/25
E) SEA TWY A BTN AIR CARGO 5 RAMP AND AIR CARGO 4 RAMP CLSD
"""

def test_filtering():
    """필터링 테스트 실행"""
    print("NOTAM 필터링 테스트 시작...")
    
    filter_obj = NOTAMFilter()
    
    # 섹션 분할 테스트
    sections = filter_obj._split_notams(test_text)
    print(f"\n총 {len(sections)}개 섹션 발견:")
    
    for i, section in enumerate(sections):
        print(f"\n--- 섹션 {i+1} ---")
        print(f"첫 줄: {section.split(chr(10))[0][:80]}...")
        
        # 제외 여부 확인
        should_exclude = filter_obj._should_exclude_section(section)
        print(f"제외 여부: {should_exclude}")
        
        if should_exclude:
            print("→ 기술정보 섹션으로 제외됨")
        else:
            print("→ 유효한 NOTAM으로 포함됨")
    
    # 전체 필터링 테스트
    print("\n\n=== 전체 필터링 결과 ===")
    filtered_notams = filter_obj.filter_korean_air_notams(test_text)
    print(f"필터링된 NOTAM 개수: {len(filtered_notams)}")
    
    for i, notam in enumerate(filtered_notams):
        print(f"\nNOTAM {i+1}:")
        print(f"  ID: {notam.get('id', 'N/A')}")
        print(f"  설명: {notam.get('description', 'N/A')[:100]}...")

if __name__ == "__main__":
    test_filtering()