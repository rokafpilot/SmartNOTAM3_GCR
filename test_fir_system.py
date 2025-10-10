#!/usr/bin/env python3
"""
FIR 분석 시스템 테스트 스크립트
UPR 좌표 구간이 올바른 FIR을 식별하는지 검증
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.fir_boundaries import identify_fir_by_coordinate, analyze_upr_route
from src.upr_parser import parse_upr_route, parse_route_with_waypoints
from src.fir_notam_filter import analyze_route_with_fir_notams

def test_coordinate_parsing():
    """좌표 파싱 테스트"""
    print("=== 좌표 파싱 테스트 ===")
    
    test_coordinates = [
        "N44E160",
        "N46E170", 
        "N49E180",
        "N50W170",
        "N52W160",
        "N53W150",
        "N52W140"
    ]
    
    for coord_str in test_coordinates:
        try:
            coords = parse_upr_route(coord_str)
            if coords:
                lat, lon = coords[0]
                print(f"✅ {coord_str} -> ({lat:.1f}, {lon:.1f})")
            else:
                print(f"❌ {coord_str} -> 파싱 실패")
        except Exception as e:
            print(f"❌ {coord_str} -> 오류: {e}")

def test_fir_identification():
    """FIR 식별 테스트"""
    print("\n=== FIR 식별 테스트 ===")
    
    test_points = [
        (44.0, 160.0),  # N44E160
        (46.0, 170.0),  # N46E170
        (49.0, 180.0),  # N49E180
        (50.0, -170.0), # N50W170
        (52.0, -160.0), # N52W160
        (53.0, -150.0), # N53W150
        (52.0, -140.0)  # N52W140
    ]
    
    for lat, lon in test_points:
        fir = identify_fir_by_coordinate(lat, lon)
        print(f"✅ ({lat:.1f}, {lon:.1f}) -> {fir or 'FIR 없음'}")

def test_upr_route_analysis():
    """UPR 경로 분석 테스트"""
    print("\n=== UPR 경로 분석 테스트 ===")
    
    upr_route = "N44E160..N46E170..N49E180..N50W170..N52W160..N53W150..N52W140"
    
    try:
        # 1. 좌표 파싱
        coordinates = parse_upr_route(upr_route)
        print(f"파싱된 좌표 수: {len(coordinates)}")
        
        # 2. FIR 분석
        analysis = analyze_upr_route(coordinates)
        
        print(f"통과하는 FIR: {analysis.get('traversed_firs', [])}")
        print(f"FIR 세그먼트: {analysis.get('fir_segments', {})}")
        
        # 3. 각 좌표별 FIR 식별
        print("\n좌표별 FIR 식별:")
        for coord_info in analysis.get('coordinates', []):
            lat, lon = coord_info['lat'], coord_info['lon']
            fir = coord_info['fir']
            print(f"  ({lat:.1f}, {lon:.1f}) -> {fir or 'FIR 없음'}")
            
    except Exception as e:
        print(f"❌ UPR 경로 분석 오류: {e}")

def test_full_route_analysis():
    """전체 경로 분석 테스트"""
    print("\n=== 전체 경로 분석 테스트 ===")
    
    full_route = "RKSI..EGOBA Y697 LANAT Y51 SAMON Y142 GTC Y512 ADNAP R591 ADGOR..N44E160..N46E170..N49E180..N50W170..N52W160..N53W150..N52W140..ORNAI..TOU MARNR8 KSEA"
    
    try:
        # 1. 경로 파싱
        parsed_route = parse_route_with_waypoints(full_route)
        
        print(f"Waypoints: {parsed_route.get('waypoints', [])}")
        print(f"Coordinates: {len(parsed_route.get('coordinates', []))}개")
        print(f"Route codes: {parsed_route.get('route_codes', [])}")
        
        # 2. FIR 분석 (더미 NOTAM 데이터로)
        dummy_notams = [
            {'notam_number': 'A1234', 'airport_code': 'KSEA', 'description': 'Test NOTAM for Seattle'},
            {'notam_number': 'B5678', 'airport_code': 'RJTT', 'description': 'Test NOTAM for Tokyo'},
            {'notam_number': 'C9012', 'airport_code': 'PAZA', 'description': 'Test NOTAM for Anchorage'}
        ]
        
        analysis_result = analyze_route_with_fir_notams(full_route, dummy_notams)
        
        print(f"\nFIR 분석 결과:")
        print(f"통과하는 FIR: {analysis_result.get('traversed_firs', [])}")
        print(f"FIR별 NOTAM 수: {[(fir, len(notams)) for fir, notams in analysis_result.get('fir_notams', {}).items()]}")
        print(f"전체 관련 NOTAM 수: {analysis_result.get('total_relevant_notams', 0)}")
        
    except Exception as e:
        print(f"❌ 전체 경로 분석 오류: {e}")

def main():
    """메인 테스트 함수"""
    print("🚀 FIR 분석 시스템 테스트 시작\n")
    
    try:
        test_coordinate_parsing()
        test_fir_identification()
        test_upr_route_analysis()
        test_full_route_analysis()
        
        print("\n✅ 모든 테스트 완료!")
        
    except Exception as e:
        print(f"\n❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
