#!/usr/bin/env python3
"""
Waypoint FIR 분석 시스템 테스트
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.nav_data_loader import get_waypoint_coordinates, estimate_waypoint_fir
from src.fir_notam_filter import analyze_route_with_fir_notams

def test_waypoint_coordinates():
    """Waypoint 좌표 조회 테스트"""
    print("=== Waypoint 좌표 조회 테스트 ===")
    
    test_waypoints = [
        'EGOBA', 'LANAT', 'SAMON', 'GTC', 'ADNAP', 'ADGOR', 'ORNAI', 'TOU'
    ]
    
    for waypoint in test_waypoints:
        coords = get_waypoint_coordinates(waypoint)
        if coords:
            lat, lon = coords
            print(f"✅ {waypoint} -> ({lat:.1f}, {lon:.1f})")
        else:
            print(f"❌ {waypoint} -> 좌표 없음")

def test_waypoint_fir_estimation():
    """Waypoint FIR 추정 테스트"""
    print("\n=== Waypoint FIR 추정 테스트 ===")
    
    test_waypoints = [
        'EGOBA', 'LANAT', 'SAMON', 'GTC', 'ADNAP', 'ADGOR', 'ORNAI', 'TOU'
    ]
    
    for waypoint in test_waypoints:
        fir = estimate_waypoint_fir(waypoint)
        coords = get_waypoint_coordinates(waypoint)
        if coords:
            lat, lon = coords
            print(f"✅ {waypoint} ({lat:.1f}, {lon:.1f}) -> {fir or 'FIR 없음'}")
        else:
            print(f"✅ {waypoint} (좌표 없음) -> {fir or 'FIR 없음'}")

def test_full_route_analysis():
    """전체 경로 분석 테스트 (Waypoint FIR 포함)"""
    print("\n=== 전체 경로 분석 테스트 (Waypoint FIR 포함) ===")
    
    full_route = "RKSI..EGOBA Y697 LANAT Y51 SAMON Y142 GTC Y512 ADNAP R591 ADGOR..N44E160..N46E170..N49E180..N50W170..N52W160..N53W150..N52W140..ORNAI..TOU MARNR8 KSEA"
    
    try:
        # 더미 NOTAM 데이터
        dummy_notams = [
            {'notam_number': 'A1234', 'airport_code': 'KSEA', 'description': 'Test NOTAM for Seattle'},
            {'notam_number': 'B5678', 'airport_code': 'RJTT', 'description': 'Test NOTAM for Tokyo'},
            {'notam_number': 'C9012', 'airport_code': 'RKSI', 'description': 'Test NOTAM for Incheon'},
            {'notam_number': 'D3456', 'airport_code': 'VVDN', 'description': 'Test NOTAM for Da Nang'},
        ]
        
        analysis_result = analyze_route_with_fir_notams(full_route, dummy_notams)
        
        print(f"Waypoint FIR 분석 결과:")
        waypoint_fir_analysis = analysis_result.get('waypoint_fir_analysis', {})
        
        # Waypoint별 FIR 정보
        waypoint_firs = waypoint_fir_analysis.get('waypoint_firs', {})
        print(f"\nWaypoint별 FIR:")
        for waypoint, info in waypoint_firs.items():
            fir = info.get('fir', 'Unknown')
            coords = info.get('coordinates')
            estimated = info.get('estimated', False)
            if coords:
                lat, lon = coords
                print(f"  {waypoint} -> {fir} ({lat:.1f}, {lon:.1f})")
            else:
                status = "추정" if estimated else "알 수 없음"
                print(f"  {waypoint} -> {fir} ({status})")
        
        # FIR별 Waypoint 그룹화
        fir_waypoints = waypoint_fir_analysis.get('fir_waypoints', {})
        print(f"\nFIR별 Waypoint:")
        for fir, waypoints in fir_waypoints.items():
            print(f"  {fir}: {', '.join(waypoints)}")
        
        # 알 수 없는 Waypoint
        unknown_waypoints = waypoint_fir_analysis.get('unknown_waypoints', [])
        if unknown_waypoints:
            print(f"\n알 수 없는 Waypoint: {', '.join(unknown_waypoints)}")
        
        print(f"\n전체 관련 NOTAM 수: {analysis_result.get('total_relevant_notams', 0)}")
        
    except Exception as e:
        print(f"❌ 전체 경로 분석 오류: {e}")
        import traceback
        traceback.print_exc()

def main():
    """메인 테스트 함수"""
    print("🚀 Waypoint FIR 분석 시스템 테스트 시작\n")
    
    try:
        test_waypoint_coordinates()
        test_waypoint_fir_estimation()
        test_full_route_analysis()
        
        print("\n✅ 모든 테스트 완료!")
        
    except Exception as e:
        print(f"\n❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
