import requests
import json
from datetime import datetime
import logging

# 로깅 설정
logger = logging.getLogger(__name__)

class TimezoneAPI:
    """
    API 기반 시간대 계산 시스템
    ICAO 코드 -> 좌표 -> 실시간 시간대 정보 (DST 자동 적용)
    """
    
    def __init__(self):
        self.cache = {}  # 캐시로 API 호출 최적화
        self.timeout = 10  # API 타임아웃
        
    def get_timezone_by_icao(self, icao_code):
        """
        ICAO 코드로 실시간 시간대 정보 조회
        
        Args:
            icao_code (str): ICAO 공항 코드
            
        Returns:
            dict: {
                'timezone_id': 'America/New_York',
                'utc_offset': '-04:00',
                'utc_offset_seconds': -14400,
                'dst_active': True,
                'current_time': '2024-09-23T12:00:00'
            }
        """
        if not icao_code or len(icao_code) != 4:
            return self._get_default_timezone()
            
        icao_upper = icao_code.upper()
        
        # 캐시 확인
        if icao_upper in self.cache:
            cached_data = self.cache[icao_upper]
            # 캐시가 1시간 이내라면 재사용
            if datetime.now().timestamp() - cached_data['timestamp'] < 3600:
                logger.info(f"캐시에서 {icao_upper} 시간대 정보 조회")
                return cached_data['data']
        
        try:
            # 1단계: ICAO 코드 -> 좌표 변환
            coordinates = self._get_coordinates_by_icao(icao_upper)
            if not coordinates:
                logger.warning(f"{icao_upper} 좌표 조회 실패, 기본값 사용")
                return self._get_default_timezone()
            
            # 2단계: 좌표 -> 시간대 정보 조회
            timezone_info = self._get_timezone_by_coordinates(coordinates['lat'], coordinates['lon'])
            if not timezone_info:
                logger.warning(f"{icao_upper} 시간대 조회 실패, 기본값 사용")
                return self._get_default_timezone()
            
            # 캐시 저장
            self.cache[icao_upper] = {
                'data': timezone_info,
                'timestamp': datetime.now().timestamp()
            }
            
            logger.info(f"{icao_upper} 시간대 정보 조회 성공: {timezone_info['timezone_id']}")
            return timezone_info
            
        except Exception as e:
            logger.error(f"{icao_upper} API 조회 중 오류: {e}")
            return self._get_default_timezone()
    
    def _get_coordinates_by_icao(self, icao_code):
        """
        Nominatim API로 ICAO 코드의 좌표 조회
        """
        try:
            url = f'https://nominatim.openstreetmap.org/search'
            params = {
                'q': f'{icao_code} airport',
                'format': 'json',
                'limit': 1
            }
            headers = {'User-Agent': 'SmartNOTAM/1.0 (timezone lookup)'}
            
            response = requests.get(url, params=params, headers=headers, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                if data:
                    result = data[0]
                    return {
                        'lat': float(result['lat']),
                        'lon': float(result['lon']),
                        'display_name': result['display_name']
                    }
            return None
            
        except Exception as e:
            logger.error(f"좌표 조회 오류: {e}")
            return None
    
    def _get_timezone_by_coordinates(self, lat, lon):
        """
        TimeAPI.io로 좌표의 시간대 정보 조회
        """
        try:
            url = f'https://timeapi.io/api/TimeZone/coordinate'
            params = {
                'latitude': lat,
                'longitude': lon
            }
            
            response = requests.get(url, params=params, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                
                # UTC 오프셋 계산
                utc_offset_obj = data.get('currentUtcOffset', {})
                utc_offset_seconds = utc_offset_obj.get('seconds', 0)
                
                # 시간대 형식 변환
                hours = utc_offset_seconds // 3600
                minutes = abs(utc_offset_seconds % 3600) // 60
                utc_offset_str = f"UTC{hours:+d}" if minutes == 0 else f"UTC{hours:+d}:{minutes:02d}"
                
                # DST 활성 여부 판단 (표준시간과 현재시간 비교)
                standard_offset = data.get('standardUtcOffset', {}).get('seconds', 0)
                dst_active = utc_offset_seconds != standard_offset
                
                return {
                    'timezone_id': data.get('timeZone', 'UTC'),
                    'utc_offset': utc_offset_str,
                    'utc_offset_seconds': utc_offset_seconds,
                    'dst_active': dst_active,
                    'current_time': data.get('currentLocalTime', ''),
                    'coordinates': {'lat': lat, 'lon': lon}
                }
            return None
            
        except Exception as e:
            logger.error(f"시간대 조회 오류: {e}")
            return None
    
    def _get_default_timezone(self):
        """
        기본 시간대 정보 반환
        """
        return {
            'timezone_id': 'UTC',
            'utc_offset': 'UTC+0',
            'utc_offset_seconds': 0,
            'dst_active': False,
            'current_time': datetime.utcnow().isoformat(),
            'coordinates': None
        }
    
    def get_simple_utc_offset(self, icao_code):
        """
        기존 호환성을 위한 간단한 UTC 오프셋 반환
        
        Args:
            icao_code (str): ICAO 공항 코드
            
        Returns:
            str: UTC 오프셋 (예: "UTC-4", "UTC+9")
        """
        timezone_info = self.get_timezone_by_icao(icao_code)
        return timezone_info['utc_offset']

# 전역 인스턴스
_timezone_api = TimezoneAPI()

def get_utc_offset_api(icao_code):
    """
    API 기반 UTC 오프셋 조회 (기존 함수와 호환)
    
    Args:
        icao_code (str): ICAO 공항 코드
        
    Returns:
        str: UTC 오프셋 (예: "UTC-4", "UTC+9")
    """
    return _timezone_api.get_simple_utc_offset(icao_code)

def get_timezone_info_api(icao_code):
    """
    API 기반 상세 시간대 정보 조회
    
    Args:
        icao_code (str): ICAO 공항 코드
        
    Returns:
        dict: 상세 시간대 정보
    """
    return _timezone_api.get_timezone_by_icao(icao_code)