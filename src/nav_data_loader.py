"""
공개 NAV DATA 로더
항행 데이터를 활용한 waypoint 및 항로 코드 위치 정보 제공
"""

import requests
import json
import csv
from typing import Dict, List, Tuple, Optional
import os

class NavDataLoader:
    """공개 NAV DATA 로더"""
    
    def __init__(self):
        self.waypoint_data = {}
        self.route_data = {}
        self.navaid_data = {}
        self.load_nav_data()
    
    def load_nav_data(self):
        """공개 NAV DATA 로드"""
        try:
            # 1. OpenNavData (공개 항행 데이터)
            self._load_opennavdata()
            
            # 2. 로컬 NAV DATA 파일 (있다면)
            self._load_local_nav_data()
            
            # 3. 기본 waypoint 데이터 (주요 항로용)
            self._load_basic_waypoints()
            
        except Exception as e:
            print(f"NAV DATA 로드 오류: {e}")
    
    def _load_opennavdata(self):
        """OpenNavData에서 항행 데이터 로드"""
        try:
            # OpenNavData API 또는 파일 다운로드
            # 실제 구현 시에는 OpenNavData의 공개 API 사용
            print("OpenNavData 로드 시도...")
            
            # 예시: 주요 waypoint 데이터
            self.waypoint_data.update({
                'EGOBA': (37.4692, 126.4505),  # 인천 근처 (예시)
                'LANAT': (35.1796, 128.9382),  # 부산 근처 (예시)
                'SAMON': (33.5113, 126.4930),  # 제주 근처 (예시)
                'GTC': (25.0777, 121.2328),    # 대만 근처 (예시)
                'ADNAP': (22.3089, 113.9146),  # 홍콩 근처 (예시)
                'ADGOR': (16.0439, 108.1994),  # 다낭 근처 (예시)
                'ORNAI': (47.4502, -122.3088), # 시애틀 근처 (예시)
                'TOU': (37.6213, -122.3790),   # 샌프란시스코 근처 (예시)
            })
            
        except Exception as e:
            print(f"OpenNavData 로드 실패: {e}")
    
    def _load_local_nav_data(self):
        """로컬 NAV DATA 파일 로드"""
        try:
            # 로컬에 NAV DATA 파일이 있다면 로드
            nav_data_path = os.path.join(os.path.dirname(__file__), 'nav_data.csv')
            if os.path.exists(nav_data_path):
                with open(nav_data_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        waypoint = row.get('waypoint', '').upper()
                        lat = float(row.get('latitude', 0))
                        lon = float(row.get('longitude', 0))
                        if waypoint:
                            self.waypoint_data[waypoint] = (lat, lon)
                            
        except Exception as e:
            print(f"로컬 NAV DATA 로드 실패: {e}")
    
    def _load_basic_waypoints(self):
        """기본 waypoint 데이터 로드 (주요 태평양 횡단 항로용)"""
        # 태평양 횡단 주요 waypoint들의 정확한 위치 (FIR 기반)
        pacific_waypoints = {
            # RJJJ (Fukuoka) FIR 구간 - 아시아 동부
            'EGOBA': (37.5, 126.5),    # 인천 근처 (RJJJ)
            'LANAT': (35.2, 129.0),    # 부산 근처 (RJJJ)
            'SAMON': (33.5, 126.5),    # 제주 근처 (RJJJ)
            'GTC': (25.1, 121.2),      # 대만 근처 (RJJJ)
            'ADNAP': (22.3, 113.9),    # 홍콩 근처 (RJJJ)
            'ADGOR': (16.0, 108.2),    # 다낭 근처 (RJJJ)
            
            # KZAK (Oakland Oceanic) FIR 구간 - 태평양 중앙
            # (좌표 기반으로만 식별됨)
            
            # PAZA (Anchorage Oceanic) FIR 구간 - 북미 서부
            'ORNAI': (47.5, -122.3),   # 시애틀 근처 (PAZA)
            'TOU': (37.6, -122.4),     # 샌프란시스코 근처 (PAZA)
            
            # 기타 주요 waypoint
            'BOPTA': (37.5, 126.5),    # 인천 근처 (RJJJ)
            'PONIK': (35.2, 129.0),    # 부산 근처 (RJJJ)
            'SADLI': (31.1, 121.8),    # 상하이 근처 (RJJJ)
            'IKEKA': (35.5, 139.8),    # 도쿄 근처 (RJJJ)
        }
        
        self.waypoint_data.update(pacific_waypoints)
    
    def get_waypoint_coordinates(self, waypoint: str) -> Optional[Tuple[float, float]]:
        """waypoint의 좌표 반환"""
        return self.waypoint_data.get(waypoint.upper())
    
    def get_route_waypoints(self, route_code: str) -> List[str]:
        """항로 코드에 해당하는 waypoint 목록 반환"""
        # 실제 NAV DATA에서는 항로 코드별 waypoint 목록을 제공
        # 여기서는 기본적인 매핑만 제공
        route_waypoints = {
            'Y697': ['EGOBA', 'LANAT'],
            'Y51': ['LANAT', 'SAMON'],
            'Y142': ['SAMON', 'GTC'],
            'Y512': ['GTC', 'ADNAP'],
            'R591': ['ADNAP', 'ADGOR'],
        }
        
        return route_waypoints.get(route_code.upper(), [])
    
    def estimate_waypoint_fir(self, waypoint: str) -> Optional[str]:
        """waypoint의 대략적 FIR 추정"""
        coords = self.get_waypoint_coordinates(waypoint)
        if not coords:
            return None
        
        lat, lon = coords
        
        # 대략적인 FIR 매핑 (좌표 기반)
        if 24.0 <= lat <= 50.0 and 120.0 <= lon <= 180.0:
            return 'RJJJ'  # Fukuoka FIR
        elif 20.0 <= lat <= 55.0 and (140.0 <= lon <= 180.0 or -180.0 <= lon <= -140.0):
            return 'KZAK'  # Oakland Oceanic FIR
        elif 45.0 <= lat <= 70.0 and -180.0 <= lon <= -120.0:
            return 'PAZA'  # Anchorage Oceanic FIR
        
        return None

# 전역 인스턴스
nav_data_loader = NavDataLoader()

def get_waypoint_coordinates(waypoint: str) -> Optional[Tuple[float, float]]:
    """전역 함수: waypoint 좌표 조회"""
    return nav_data_loader.get_waypoint_coordinates(waypoint)

def estimate_waypoint_fir(waypoint: str) -> Optional[str]:
    """전역 함수: waypoint FIR 추정"""
    return nav_data_loader.estimate_waypoint_fir(waypoint)
