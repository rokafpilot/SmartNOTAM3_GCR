#!/usr/bin/env python3
"""
간단한 다각형 판별 테스트
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.fir_boundaries import PointInPolygonChecker, FIRBoundaryDatabase

def test_simple_polygon():
    """간단한 다각형 판별 테스트"""
    print("=== 간단한 다각형 판별 테스트 ===")
    
    # FIR 경계 데이터베이스 로드
    boundary_db = FIRBoundaryDatabase()
    polygon_checker = PointInPolygonChecker()
    
    # 테스트 좌표들
    test_coordinates = [
        (44.0, 160.0),  # N44E160
        (46.0, 170.0),  # N46E170
        (49.0, 180.0),  # N49E180
    ]
    
    print("KZAK FIR 경계 좌표:")
    kzak_boundary = boundary_db.fir_boundaries['KZAK']
    for i, coord in enumerate(kzak_boundary):
        print(f"  {i+1}: {coord}")
    
    print()
    print("경계 박스 정보:")
    min_x = min(p[0] for p in kzak_boundary)
    max_x = max(p[0] for p in kzak_boundary)
    min_y = min(p[1] for p in kzak_boundary)
    max_y = max(p[1] for p in kzak_boundary)
    print(f"  X 범위: {min_x:.1f} ~ {max_x:.1f}")
    print(f"  Y 범위: {min_y:.1f} ~ {max_y:.1f}")
    
    print()
    print("좌표별 판별:")
    for lat, lon in test_coordinates:
        print(f"\n좌표 ({lat:.1f}, {lon:.1f}):")
        
        # 경계 박스 검사
        in_bbox = min_x <= lat <= max_x and min_y <= lon <= max_y
        print(f"  경계 박스: {'✅ 내부' if in_bbox else '❌ 외부'}")
        
        # Ray Casting 알고리즘
        in_polygon = polygon_checker.is_point_in_polygon((lat, lon), kzak_boundary)
        print(f"  Ray Casting: {'✅ 내부' if in_polygon else '❌ 외부'}")
        
        # 간단한 알고리즘
        in_simple = polygon_checker.is_point_in_polygon_simple((lat, lon), kzak_boundary)
        print(f"  Simple: {'✅ 내부' if in_simple else '❌ 외부'}")

if __name__ == "__main__":
    test_simple_polygon()
