#!/usr/bin/env python3
"""
NOTAM 카운팅 디버깅
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.fir_notam_filter import FIRNotamFilter

def debug_notam_counting():
    """NOTAM 카운팅 디버깅"""
    print("=== NOTAM 카운팅 디버깅 ===")
    
    # FIR 필터링 인스턴스 생성
    filter_instance = FIRNotamFilter()
    
    # 실제 NOTAM 데이터 구조로 테스트
    test_notams = [
        {'index': 1, 'notam_number': 'A1234', 'airports': ['RKSI'], 'text': 'Test NOTAM 1'},
        {'index': 2, 'notam_number': 'A1235', 'airports': ['RKSI'], 'text': 'Test NOTAM 2'},
        {'index': 3, 'notam_number': 'B1234', 'airports': ['KSEA'], 'text': 'Test NOTAM 3'},
        {'index': 4, 'notam_number': 'B1235', 'airports': ['KSEA'], 'text': 'Test NOTAM 4'},
    ]
    
    print("테스트 NOTAM:")
    for notam in test_notams:
        print(f"  {notam['airports']} {notam['notam_number']}")
    
    print()
    print("RJJJ FIR 필터링:")
    rjjj_notams = filter_instance.filter_notams_by_fir(test_notams, ['RJJJ'])
    print(f"  RJJJ FIR: {len(rjjj_notams)}개 NOTAM")
    for notam in rjjj_notams:
        print(f"    - {notam['airports']} {notam['notam_number']}")
    
    print()
    print("PAZA FIR 필터링:")
    paza_notams = filter_instance.filter_notams_by_fir(test_notams, ['PAZA'])
    print(f"  PAZA FIR: {len(paza_notams)}개 NOTAM")
    for notam in paza_notams:
        print(f"    - {notam['airports']} {notam['notam_number']}")
    
    print()
    print("공항별 FIR 매핑:")
    for notam in test_notams:
        airports = notam['airports']
        for airport in airports:
            fir = filter_instance._get_fir_from_airport_code(airport)
            print(f"  {airport} -> {fir or 'FIR 없음'}")
    
    print()
    print("=== 문제 분석 ===")
    print("사용자 보고:")
    print("  - 실제 RJJJ NOTAM: 23개")
    print("  - 분석 결과 RJJJ: 81개 (잘못됨)")
    print("  - 분석 결과 PAZA: 190개 (의심스러움)")
    print()
    print("가능한 원인:")
    print("  1. NOTAM 데이터 중복 계산")
    print("  2. FIR 매핑 오류로 인한 잘못된 분류")
    print("  3. waypoint 기반 NOTAM과 FIR 기반 NOTAM 중복 계산")

if __name__ == "__main__":
    debug_notam_counting()
