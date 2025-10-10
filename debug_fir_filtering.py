#!/usr/bin/env python3
"""
FIR 필터링 디버깅 스크립트
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.fir_notam_filter import FIRNotamFilter

def debug_fir_filtering():
    """FIR 필터링 디버깅"""
    print("=== FIR 필터링 디버깅 ===")
    
    # FIR 필터링 인스턴스 생성
    filter_instance = FIRNotamFilter()
    
    # 테스트 NOTAM 데이터
    test_notams = [
        {'notam_number': 'A1234', 'airport_code': 'RKSI', 'description': 'Test NOTAM for Incheon'},
        {'notam_number': 'B1234', 'airport_code': 'RJTT', 'description': 'Test NOTAM for Tokyo'},
        {'notam_number': 'C1234', 'airport_code': 'KSEA', 'description': 'Test NOTAM for Seattle'},
        {'notam_number': 'D1234', 'airport_code': 'PANC', 'description': 'Test NOTAM for Anchorage'},
        {'notam_number': 'E1234', 'airport_code': 'RCTP', 'description': 'Test NOTAM for Taiwan'},
        {'notam_number': 'F1234', 'airport_code': 'VHHH', 'description': 'Test NOTAM for Hong Kong'},
    ]
    
    print("테스트 NOTAM:")
    for notam in test_notams:
        print(f"  {notam['airport_code']} {notam['notam_number']}")
    
    print()
    print("FIR 매핑 확인:")
    for notam in test_notams:
        airport_code = notam['airport_code']
        fir = filter_instance._get_fir_from_airport_code(airport_code)
        print(f"  {airport_code} -> {fir or 'FIR 없음'}")
    
    print()
    print("RJJJ FIR 필터링 결과:")
    rjjj_notams = filter_instance.filter_notams_by_fir(test_notams, ['RJJJ'])
    print(f"  RJJJ FIR: {len(rjjj_notams)}개 NOTAM")
    for notam in rjjj_notams:
        print(f"    - {notam['airport_code']} {notam['notam_number']}")
    
    print()
    print("PAZA FIR 필터링 결과:")
    paza_notams = filter_instance.filter_notams_by_fir(test_notams, ['PAZA'])
    print(f"  PAZA FIR: {len(paza_notams)}개 NOTAM")
    for notam in paza_notams:
        print(f"    - {notam['airport_code']} {notam['notam_number']}")
    
    print()
    print("KZAK FIR 필터링 결과:")
    kzak_notams = filter_instance.filter_notams_by_fir(test_notams, ['KZAK'])
    print(f"  KZAK FIR: {len(kzak_notams)}개 NOTAM")
    for notam in kzak_notams:
        print(f"    - {notam['airport_code']} {notam['notam_number']}")
    
    print()
    print("FIR 매핑 설정 확인:")
    fir_mapping = filter_instance.fir_airport_mapping
    for fir_code, prefixes in fir_mapping.items():
        print(f"  {fir_code}: {prefixes}")

if __name__ == "__main__":
    debug_fir_filtering()
