#!/usr/bin/env python3
"""
점-다각형 내부 판별 테스트
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.fir_boundaries import PointInPolygonChecker, FIRBoundaryDatabase

def test_point_in_polygon():
    """점-다각형 내부 판별 테스트"""
    print("=== 점-다각형 내부 판별 테스트 ===")
    
    # FIR 경계 데이터베이스 로드
    boundary_db = FIRBoundaryDatabase()
    polygon_checker = PointInPolygonChecker()
    
    # 테스트 좌표들
    test_coordinates = [
        (44.0, 160.0),  # N44E160
        (46.0, 170.0),  # N46E170
        (49.0, 180.0),  # N49E180
        (50.0, -170.0), # N50W170
        (52.0, -160.0), # N52W160
        (53.0, -150.0), # N53W150
        (52.0, -140.0)  # N52W140
    ]
    
    print("FIR 경계 정보:")
    for fir_code, boundary in boundary_db.fir_boundaries.items():
        print(f"  {fir_code}: {len(boundary)}개 좌표")
        if boundary:
            print(f"    첫 번째 좌표: {boundary[0]}")
            print(f"    마지막 좌표: {boundary[-1]}")
    
    print()
    print("좌표별 FIR 판별:")
    for lat, lon in test_coordinates:
        print(f"\n좌표 ({lat:.1f}, {lon:.1f}):")
        
        for fir_code, boundary in boundary_db.fir_boundaries.items():
            is_inside = polygon_checker.is_point_in_polygon((lat, lon), boundary)
            print(f"  {fir_code}: {'✅ 내부' if is_inside else '❌ 외부'}")
    
    print()
    print("=== 문제 진단 ===")
    print("N44E160~N49E180 구간이 KZAK FIR에 속해야 하는데 현재는 'FIR 없음'으로 나오고 있습니다.")
    print("이는 KZAK FIR 경계 좌표가 잘못 설정되었거나, 점-다각형 판별 알고리즘에 문제가 있을 수 있습니다.")

if __name__ == "__main__":
    test_point_in_polygon()
