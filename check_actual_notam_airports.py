#!/usr/bin/env python3
"""
실제 NOTAM 데이터의 공항 코드 확인
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.fir_notam_filter import FIRNotamFilter

def check_actual_notam_airports():
    """실제 NOTAM 데이터의 공항 코드 확인"""
    print("=== 실제 NOTAM 데이터 공항 코드 확인 ===")
    
    # FIR 필터링 인스턴스
    filter_instance = FIRNotamFilter()
    
    # 사용자가 제공한 분석 결과에서 추출한 공항 코드들
    actual_airports = [
        'RKSI',  # 인천 (한국)
        'KSEA',  # 시애틀 (미국)
        'KPDX',  # 포틀랜드 (미국)
    ]
    
    print("실제 NOTAM 데이터의 공항 코드들:")
    for airport in actual_airports:
        fir = filter_instance._get_fir_from_airport_code(airport)
        print(f"  {airport} -> {fir or 'FIR 없음'}")
    
    print()
    print("FIR 매핑 설정:")
    fir_mapping = filter_instance.fir_airport_mapping
    for fir_code, prefixes in fir_mapping.items():
        print(f"  {fir_code}: {prefixes}")
    
    print()
    print("=== 문제 분석 ===")
    print("실제 NOTAM 데이터에는 다음 공항들만 있습니다:")
    print("  - RKSI (인천) -> FIR 없음")
    print("  - KSEA (시애틀) -> FIR 없음") 
    print("  - KPDX (포틀랜드) -> FIR 없음")
    print()
    print("RJJJ, PAZA FIR에 해당하는 공항 코드가 없습니다!")
    print("따라서 RJJJ: 0개, PAZA: 0개 NOTAM이 정확한 결과입니다.")
    
    print()
    print("=== 해결 방안 ===")
    print("1. FIR 매핑 확장:")
    print("   - RKSI -> RJJJ FIR (한국)")
    print("   - KSEA -> PAZA FIR (미국 서부)")
    print("   - KPDX -> PAZA FIR (미국 서부)")
    
    print()
    print("2. 또는 실제 NOTAM 데이터에 RJJJ, PAZA FIR 공항 추가:")
    print("   - RJTT (도쿄) -> RJJJ FIR")
    print("   - PANC (앵커리지) -> PAZA FIR")

if __name__ == "__main__":
    check_actual_notam_airports()
