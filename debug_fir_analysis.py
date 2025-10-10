#!/usr/bin/env python3
"""
FIR 분석 디버깅 스크립트
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.fir_notam_filter import analyze_route_with_fir_notams
from src.fir_boundaries import identify_fir_by_coordinate, analyze_upr_route
from src.upr_parser import parse_route_with_waypoints
from src.nav_data_loader import get_waypoint_coordinates, estimate_waypoint_fir

def debug_fir_analysis():
    """FIR 분석 디버깅"""
    print("=== FIR 분석 디버깅 ===")
    
    # 테스트 경로
    route = "RKSI..EGOBA Y697 LANAT Y51 SAMON Y142 GTC Y512 ADNAP R591 ADGOR..N44E160..N46E170..N49E180..N50W170..N52W160..N53W150..N52W140..ORNAI..TOU MARNR8 KSEA"
    
    print(f"분석할 경로: {route}")
    
    # 1. 경로 파싱 테스트
    print("\n1. 경로 파싱 테스트:")
    try:
        parsed_route = parse_route_with_waypoints(route)
        print(f"Waypoints: {parsed_route.get('waypoints', [])}")
        print(f"Coordinates: {len(parsed_route.get('coordinates', []))}개")
        print(f"Route codes: {parsed_route.get('route_codes', [])}")
        
        # 좌표 출력
        coordinates = parsed_route.get('coordinates', [])
        for i, coord in enumerate(coordinates):
            print(f"  좌표 {i+1}: {coord}")
            
    except Exception as e:
        print(f"경로 파싱 오류: {e}")
        return
    
    # 2. 좌표 기반 FIR 분석
    print("\n2. 좌표 기반 FIR 분석:")
    try:
        if coordinates:
            fir_analysis = analyze_upr_route(coordinates)
            print(f"통과하는 FIR: {fir_analysis.get('traversed_firs', [])}")
            print(f"FIR 세그먼트: {fir_analysis.get('fir_segments', {})}")
            
            # 각 좌표별 FIR 식별
            for coord_info in fir_analysis.get('coordinates', []):
                lat, lon = coord_info['lat'], coord_info['lon']
                fir = coord_info['fir']
                print(f"  ({lat:.1f}, {lon:.1f}) -> {fir or 'FIR 없음'}")
        else:
            print("좌표가 없습니다.")
            
    except Exception as e:
        print(f"좌표 기반 FIR 분석 오류: {e}")
    
    # 3. Waypoint FIR 분석
    print("\n3. Waypoint FIR 분석:")
    try:
        waypoints = parsed_route.get('waypoints', [])
        for waypoint in waypoints:
            coords = get_waypoint_coordinates(waypoint)
            estimated_fir = estimate_waypoint_fir(waypoint)
            
            if coords:
                lat, lon = coords
                fir = identify_fir_by_coordinate(lat, lon)
                print(f"  {waypoint} ({lat:.1f}, {lon:.1f}) -> {fir or 'FIR 없음'}")
            else:
                print(f"  {waypoint} (좌표 없음) -> {estimated_fir or 'FIR 없음'} (추정)")
                
    except Exception as e:
        print(f"Waypoint FIR 분석 오류: {e}")
    
    # 4. 전체 FIR 분석
    print("\n4. 전체 FIR 분석:")
    try:
        # 더미 NOTAM 데이터
        dummy_notams = [
            {'notam_number': 'A1234', 'airport_code': 'RKSI', 'description': 'Test NOTAM for Incheon'},
            {'notam_number': 'B5678', 'airport_code': 'KSEA', 'description': 'Test NOTAM for Seattle'},
            {'notam_number': 'C9012', 'airport_code': 'RJTT', 'description': 'Test NOTAM for Tokyo'},
        ]
        
        result = analyze_route_with_fir_notams(route, dummy_notams)
        
        print(f"통과하는 FIR: {result.get('traversed_firs', [])}")
        print(f"FIR별 NOTAM 수: {[(fir, len(notams)) for fir, notams in result.get('fir_notams', {}).items()]}")
        
        waypoint_fir_analysis = result.get('waypoint_fir_analysis', {})
        print(f"Waypoint FIR 분석: {waypoint_fir_analysis}")
        
    except Exception as e:
        print(f"전체 FIR 분석 오류: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_fir_analysis()
