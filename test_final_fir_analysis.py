#!/usr/bin/env python3
"""
최종 FIR 분석 테스트 - 실제 NOTAM 데이터 구조
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.fir_notam_filter import analyze_route_with_fir_notams

def test_final_fir_analysis():
    """최종 FIR 분석 테스트"""
    print("=== 최종 FIR 분석 테스트 ===")
    
    # 테스트 경로
    route = "RKSI..EGOBA Y697 LANAT Y51 SAMON Y142 GTC Y512 ADNAP R591 ADGOR..N44E160..N46E170..N49E180..N50W170..N52W160..N53W150..N52W140..ORNAI..TOU MARNR8 KSEA"
    
    # 실제 NOTAM 데이터 (사용자 분석 결과 기반)
    actual_notams = [
        # RKSI 관련 NOTAM
        {
            'index': 1,
            'notam_number': 'A1234',
            'airports': ['RKSI'],
            'text': 'GPWS 오작동 경고 주의. GPS 신호 간섭 시 EGPWS TERR 경고 무시 절차',
            'effective_time': '2024-01-01T00:00:00Z',
            'expiry_time': '2024-12-31T23:59:59Z'
        },
        {
            'index': 2,
            'notam_number': 'A1235',
            'airports': ['RKSI'],
            'text': 'RWY 15L/33R 폐쇄, 활주로 정비 예정 시간 변경',
            'effective_time': '2024-01-01T00:00:00Z',
            'expiry_time': '2024-12-31T23:59:59Z'
        },
        
        # KSEA 관련 NOTAM
        {
            'index': 3,
            'notam_number': 'B1234',
            'airports': ['KSEA'],
            'text': 'BANGR NINE 출발 절차 시 GPS 필수, HQM VORTAC 운영 중단',
            'effective_time': '2024-01-01T00:00:00Z',
            'expiry_time': '2024-12-31T23:59:59Z'
        },
        {
            'index': 4,
            'notam_number': 'B1235',
            'airports': ['KSEA'],
            'text': 'ELMAA FIVE 출발 절차 HOQUIAM Transition 사용 불가',
            'effective_time': '2024-01-01T00:00:00Z',
            'expiry_time': '2024-12-31T23:59:59Z'
        },
        
        # KPDX 관련 NOTAM
        {
            'index': 5,
            'notam_number': 'C1234',
            'airports': ['KPDX'],
            'text': 'RWY 10R/28L 폐쇄',
            'effective_time': '2024-01-01T00:00:00Z',
            'expiry_time': '2024-12-31T23:59:59Z'
        },
        {
            'index': 6,
            'notam_number': 'C1235',
            'airports': ['KPDX'],
            'text': 'ILS RWY 10L 사용 불가',
            'effective_time': '2024-01-01T00:00:00Z',
            'expiry_time': '2024-12-31T23:59:59Z'
        },
    ]
    
    print(f"테스트 NOTAM 데이터:")
    for notam in actual_notams:
        print(f"  {notam['airports']} {notam['notam_number']}: {notam['text'][:50]}...")
    
    print()
    
    try:
        # FIR 분석 실행
        result = analyze_route_with_fir_notams(route, actual_notams)
        
        print("=== FIR 분석 결과 ===")
        
        # 1. 통과하는 FIR
        traversed_firs = result.get('traversed_firs', [])
        print(f"통과하는 FIR: {traversed_firs}")
        
        # 2. FIR별 NOTAM 분석
        fir_notams = result.get('fir_notams', {})
        print(f"\nFIR별 관련 NOTAM:")
        for fir, notams in fir_notams.items():
            print(f"  {fir} FIR: {len(notams)}개 NOTAM")
            for notam in notams:
                airports = notam.get('airports', [])
                notam_num = notam.get('notam_number', 'N/A')
                print(f"    - {airports} {notam_num}")
        
        # 3. 전체 관련 NOTAM 수
        total_notams = result.get('total_relevant_notams', 0)
        print(f"\n전체 관련 NOTAM 수: {total_notams}개")
        
        # 4. 최종 결과 확인
        print(f"\n=== 최종 결과 확인 ===")
        rjjj_count = len(fir_notams.get('RJJJ', []))
        paza_count = len(fir_notams.get('PAZA', []))
        
        print(f"✅ RJJJ FIR: {rjjj_count}개 NOTAM")
        print(f"✅ PAZA FIR: {paza_count}개 NOTAM")
        
        if rjjj_count > 0 and paza_count > 0:
            print("🎉 성공! RJJJ, PAZA FIR 관련 NOTAM이 올바르게 식별되었습니다!")
        elif rjjj_count > 0 or paza_count > 0:
            print("⚠️ 부분 성공: 일부 FIR만 NOTAM이 식별되었습니다.")
        else:
            print("❌ 실패: FIR별 NOTAM이 식별되지 않았습니다.")
            
    except Exception as e:
        print(f"❌ 분석 중 오류: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_final_fir_analysis()
