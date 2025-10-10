#!/usr/bin/env python3
"""
웹 인터페이스 NOTAM 데이터 구조 테스트
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.fir_notam_filter import analyze_route_with_fir_notams

def test_web_notam_structure():
    """웹 인터페이스 NOTAM 데이터 구조 테스트"""
    print("=== 웹 인터페이스 NOTAM 데이터 구조 테스트 ===")
    
    # 테스트 경로
    route = "RKSI..EGOBA Y697 LANAT Y51 SAMON Y142 GTC Y512 ADNAP R591 ADGOR..N44E160..N46E170..N49E180..N50W170..N52W160..N53W150..N52W140..ORNAI..TOU MARNR8 KSEA"
    
    # 웹 인터페이스 데이터 구조로 NOTAM 생성
    web_notams = [
        # RKSI 관련 NOTAM (웹 인터페이스 구조)
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
        
        # RJJJ FIR 관련 NOTAM
        {
            'index': 3,
            'notam_number': 'B1234',
            'airports': ['RJTT'],
            'text': 'Tokyo FIR 관련 NOTAM - GPS RAIM 예측 정보',
            'effective_time': '2024-01-01T00:00:00Z',
            'expiry_time': '2024-12-31T23:59:59Z'
        },
        {
            'index': 4,
            'notam_number': 'B1235',
            'airports': ['RCTP'],
            'text': 'Taiwan FIR 관련 NOTAM - VOR DME 운영 중단',
            'effective_time': '2024-01-01T00:00:00Z',
            'expiry_time': '2024-12-31T23:59:59Z'
        },
        
        # KSEA 관련 NOTAM
        {
            'index': 5,
            'notam_number': 'C1234',
            'airports': ['KSEA'],
            'text': 'BANGR NINE 출발 절차 시 GPS 필수, HQM VORTAC 운영 중단',
            'effective_time': '2024-01-01T00:00:00Z',
            'expiry_time': '2024-12-31T23:59:59Z'
        },
        
        # PAZA FIR 관련 NOTAM
        {
            'index': 6,
            'notam_number': 'D1234',
            'airports': ['PANC'],
            'text': 'Anchorage FIR 관련 NOTAM - 항로 변경 정보',
            'effective_time': '2024-01-01T00:00:00Z',
            'expiry_time': '2024-12-31T23:59:59Z'
        },
        {
            'index': 7,
            'notam_number': 'D1235',
            'airports': ['PAFA'],
            'text': 'Fairbanks FIR 관련 NOTAM - 기상 정보',
            'effective_time': '2024-01-01T00:00:00Z',
            'expiry_time': '2024-12-31T23:59:59Z'
        },
    ]
    
    print(f"테스트 NOTAM 데이터 (웹 인터페이스 구조):")
    for notam in web_notams:
        print(f"  {notam['airports']} {notam['notam_number']}: {notam['text'][:50]}...")
    
    print()
    
    try:
        # FIR 분석 실행
        result = analyze_route_with_fir_notams(route, web_notams)
        
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
        
        # 3. Waypoint FIR 분석
        waypoint_fir_analysis = result.get('waypoint_fir_analysis', {})
        fir_waypoints = waypoint_fir_analysis.get('fir_waypoints', {})
        print(f"\nWaypoint FIR 분석:")
        for fir, waypoints in fir_waypoints.items():
            print(f"  {fir} FIR: {', '.join(waypoints)}")
        
        # 4. 전체 관련 NOTAM 수
        total_notams = result.get('total_relevant_notams', 0)
        print(f"\n전체 관련 NOTAM 수: {total_notams}개")
        
        # 5. 분석 결과 요약
        print(f"\n=== 분석 결과 요약 ===")
        print(f"✅ RJJJ FIR: {'식별됨' if 'RJJJ' in traversed_firs else '식별 안됨'} ({len(fir_notams.get('RJJJ', []))}개 NOTAM)")
        print(f"✅ KZAK FIR: {'식별됨' if 'KZAK' in traversed_firs else '식별 안됨'} ({len(fir_notams.get('KZAK', []))}개 NOTAM)")
        print(f"✅ PAZA FIR: {'식별됨' if 'PAZA' in traversed_firs else '식별 안됨'} ({len(fir_notams.get('PAZA', []))}개 NOTAM)")
        
        if len(fir_notams.get('RJJJ', [])) > 0 or len(fir_notams.get('PAZA', [])) > 0:
            print("🎉 FIR별 NOTAM이 올바르게 식별되었습니다!")
        else:
            print("⚠️ FIR별 NOTAM이 식별되지 않았습니다.")
            
    except Exception as e:
        print(f"❌ 분석 중 오류: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_web_notam_structure()
