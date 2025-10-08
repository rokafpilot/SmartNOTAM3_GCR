import os
import csv
from datetime import datetime, timedelta
import requests
import logging

# 로깅 설정
logger = logging.getLogger(__name__)

# 전역 변수
_airport_timezones = {}
_csv_loaded = False
API_AVAILABLE = True

def _load_airport_timezones():
    """CSV 파일에서 공항 시간대 정보 로드"""
    global _airport_timezones, _csv_loaded
    
    if _csv_loaded:
        return
        
    try:
        csv_path = os.path.join(os.path.dirname(__file__), 'airports_timezones.csv')
        if os.path.exists(csv_path):
            with open(csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    icao_code = row.get('ident', '').strip()
                    timezone = row.get('time_zone', 'UTC+0').strip()
                    if icao_code and timezone:
                        _airport_timezones[icao_code] = timezone
            print(f"공항 시간대 CSV 로드 완료: {len(_airport_timezones)}개")
        else:
            print(f"공항 데이터 파일을 찾을 수 없습니다: {csv_path}")
            
    except Exception as e:
        print(f"공항 시간대 CSV 로드 오류: {e}")
        _csv_loaded = True  # 오류가 나도 다시 시도하지 않도록

def is_dst_active():
    """
    미국 DST 규칙에 따른 일광절약시간 활성 여부 판단
    2024년 기준: 3월 둘째 일요일 02:00 ~ 11월 첫째 일요일 02:00
    """
    current_date = datetime.now()
    current_year = current_date.year
    
    # 3월 둘째 일요일 계산
    march_first = datetime(current_year, 3, 1)
    march_first_weekday = march_first.weekday()  # 0=월요일, 6=일요일
    days_to_first_sunday = (6 - march_first_weekday) % 7
    first_sunday_march = march_first + timedelta(days=days_to_first_sunday)
    second_sunday_march = first_sunday_march + timedelta(days=7)
    
    # 11월 첫째 일요일 계산
    november_first = datetime(current_year, 11, 1)
    november_first_weekday = november_first.weekday()
    days_to_first_sunday_nov = (6 - november_first_weekday) % 7
    first_sunday_november = november_first + timedelta(days=days_to_first_sunday_nov)
    
    # DST 시작: 3월 둘째 일요일 02:00
    dst_start = second_sunday_march.replace(hour=2, minute=0, second=0, microsecond=0)
    
    # DST 종료: 11월 첫째 일요일 02:00
    dst_end = first_sunday_november.replace(hour=2, minute=0, second=0, microsecond=0)
    
    return dst_start <= current_date < dst_end

def get_utc_offset(icao_code, use_api=True):
    """
    ICAO 공항 코드의 UTC 시간대를 반환합니다.
    
    우선순위:
    1. API 기반 실시간 조회 (DST 자동 적용)
    2. FIR 패턴 기반 계산
    3. CSV 파일 조회
    4. 기본값 폴백
    
    Args:
        icao_code (str): ICAO 공항 코드 (예: KSEA, RJTT, RKSI)
        use_api (bool): API 사용 여부 (기본값: True)
        
    Returns:
        str: UTC 시간대 (예: UTC+9, UTC-4)
    """
    if not icao_code or len(icao_code) < 2:
        return "UTC+0"
    
    icao_upper = icao_code.upper()
    
    # 1단계: API 기반 실시간 조회 (최우선)
    if use_api and API_AVAILABLE:
        try:
            api_result = get_utc_offset_api(icao_upper)
            if api_result and api_result != "UTC+0":
                print(f"API로 {icao_upper} 시간대 계산: {api_result}")
                return api_result
        except Exception as e:
            print(f"API 조회 실패, 폴백 사용: {e}")
    
    # 2단계: FIR 패턴 기반 정확한 시간대 계산
    fir_timezone = get_timezone_by_fir_pattern(icao_upper)
    if fir_timezone != "UTC+0":  # 기본값이 아닌 경우
        print(f"FIR 패턴으로 {icao_upper} 시간대 계산: {fir_timezone}")
        return fir_timezone
    
    # 3단계: CSV 파일에서 정확한 매칭 시도
    _load_airport_timezones()
    if icao_upper in _airport_timezones:
        result = _airport_timezones[icao_upper]
        print(f"CSV에서 {icao_upper} 찾음: {result}")
        return result
    
    print(f"CSV에서 {icao_upper} 찾지 못함, 기본 로직 사용")
    
    # 4단계: 기존 ICAO 첫 글자 기반 매핑 (마지막 수단)
    first_letter = icao_upper[0]
    
    # ICAO 지역 코드별 UTC 시간대 매핑 (기본값)
    utc_offsets = {
        'A': 'UTC+2',  # 남서 아시아
        'B': 'UTC+3',  # 중동
        'C': 'UTC+4',  # 중동
        'D': 'UTC+5',  # 남아시아
        'E': 'UTC+6',  # 남아시아
        'F': 'UTC+7',  # 동남아시아
        'G': 'UTC+8',  # 동남아시아
        'H': 'UTC+9',  # 동아시아
        'I': 'UTC+10', # 오세아니아
        'J': 'UTC+11', # 오세아니아
        'K': 'UTC-5',  # 북미
        'L': 'UTC+1',  # 유럽
        'M': 'UTC+12', # 오세아니아
        'N': 'UTC+12', # 오세아니아
        'O': 'UTC+3',  # 중동
        'P': 'UTC-9',  # 알래스카
        'R': 'UTC+9',  # 동아시아 (한국)
        'S': 'UTC-3',  # 남미
        'T': 'UTC-4',  # 카리브해
        'U': 'UTC+3',  # 러시아
        'V': 'UTC+5',  # 남아시아
        'W': 'UTC+7',  # 동남아시아
        'Y': 'UTC+10', # 오스트레일리아
        'Z': 'UTC+8'   # 중국
    }
    
    return utc_offsets.get(first_letter, 'UTC+0')

def get_timezone_by_fir_pattern(icao_code):
    """
    ICAO 코드의 FIR 패턴으로 정확한 시간대 자동 계산 (일광절약시간 적용)
    
    Args:
        icao_code (str): ICAO 공항 코드 (4자리)
        
    Returns:
        str: UTC 시간대 (예: UTC+9, 일광절약시간 적용된 UTC-4)
    """
    if len(icao_code) < 2:
        return "UTC+0"
    
    # 첫 2글자로 FIR 지역 식별
    fir_prefix = icao_code[:2]
    
    # DST 활성 여부 확인
    dst_active = is_dst_active()
    
    # 동아시아 FIR 매핑 (R으로 시작) - DST 미적용 지역
    if fir_prefix == 'RK':      # 한국 FIR
        return "UTC+9"
    elif fir_prefix == 'RJ':    # 일본 FIR
        return "UTC+9"
    elif fir_prefix == 'RC':    # 대만 FIR
        return "UTC+8"
    elif fir_prefix == 'RP':    # 필리핀 FIR
        return "UTC+8"
    elif fir_prefix == 'RO':    # 오키나와 FIR
        return "UTC+9"
    
    # 중국 FIR 매핑 (Z로 시작)
    elif fir_prefix == 'ZB':    # 베이징 FIR
        return "UTC+8"
    elif fir_prefix == 'ZS':    # 상하이 FIR
        return "UTC+8"
    elif fir_prefix == 'ZG':    # 광저우 FIR
        return "UTC+8"
    elif fir_prefix == 'ZU':    # 우루무치 FIR
        return "UTC+8"
    elif fir_prefix == 'ZY':    # 선양 FIR
        return "UTC+8"
    elif fir_prefix == 'ZW':    # 우한 FIR
        return "UTC+8"
    elif fir_prefix == 'ZL':    # 란저우 FIR
        return "UTC+8"
    
    # 동남아시아 FIR 매핑 (V로 시작)
    elif fir_prefix == 'VH':    # 홍콩 FIR
        return "UTC+8"
    elif fir_prefix == 'VT':    # 태국 FIR
        return "UTC+7"
    elif fir_prefix == 'VV':    # 베트남 FIR
        return "UTC+7"
    elif fir_prefix == 'VM':    # 말레이시아 FIR
        return "UTC+8"
    elif fir_prefix == 'WI':    # 인도네시아 FIR (서부)
        return "UTC+7"
    elif fir_prefix == 'WA':    # 인도네시아 FIR (중부)
        return "UTC+8"
    elif fir_prefix == 'WB':    # 인도네시아 FIR (동부)
        return "UTC+9"
    elif fir_prefix == 'WS':    # 싱가포르 FIR
        return "UTC+8"
    
    # 미국 FIR 매핑 (K로 시작) - DST 적용
    elif fir_prefix == 'KS':    # 서부 (시애틀, 샌프란시스코)
        return "UTC-7" if dst_active else "UTC-8"  # PDT/PST
    elif fir_prefix == 'KL':    # 서부 (로스앤젤레스)
        return "UTC-7" if dst_active else "UTC-8"  # PDT/PST
    elif fir_prefix == 'KD':    # 중부 (덴버)
        return "UTC-6" if dst_active else "UTC-7"  # MDT/MST
    elif fir_prefix == 'KM':    # 중부 (시카고)
        return "UTC-5" if dst_active else "UTC-6"  # CDT/CST
    elif fir_prefix == 'KE':    # 동부 (뉴욕)
        return "UTC-4" if dst_active else "UTC-5"  # EDT/EST
    elif fir_prefix == 'KH':    # 하와이
        return "UTC-10"  # HST (DST 없음)
    elif fir_prefix == 'PA':    # 알래스카
        return "UTC-8" if dst_active else "UTC-9"  # AKDT/AKST
    
    # 캐나다 FIR 매핑 (C로 시작) - DST 적용
    elif fir_prefix == 'CY':    # 캐나다 동부
        return "UTC-4" if dst_active else "UTC-5"  # EDT/EST
    elif fir_prefix == 'CZ':    # 캐나다 서부
        return "UTC-7" if dst_active else "UTC-8"  # PDT/PST
    
    # 유럽 FIR 매핑 (L로 시작) - DST 적용
    elif fir_prefix == 'LF':    # 프랑스
        return "UTC+2" if dst_active else "UTC+1"  # CEST/CET
    elif fir_prefix == 'EG':    # 영국
        return "UTC+1" if dst_active else "UTC+0"  # BST/GMT
    elif fir_prefix == 'ED':    # 독일
        return "UTC+2" if dst_active else "UTC+1"  # CEST/CET
    
    # 오스트레일리아 FIR 매핑 (Y로 시작) - DST 적용
    elif fir_prefix == 'YB':    # 브리즈번 (DST 없음)
        return "UTC+10"
    elif fir_prefix == 'YS':    # 시드니
        return "UTC+11" if dst_active else "UTC+10"  # AEDT/AEST
    elif fir_prefix == 'YM':    # 멜버른
        return "UTC+11" if dst_active else "UTC+10"  # AEDT/AEST
    
    # 기본값
    return "UTC+0"

def get_utc_offset_api(icao_code):
    """
    API를 사용하여 ICAO 코드의 UTC 오프셋을 조회합니다.
    
    Args:
        icao_code (str): ICAO 공항 코드
        
    Returns:
        str: UTC 오프셋 (예: UTC-8, UTC+9)
    """
    try:
        # TimeAPI.io를 사용한 시간대 조회
        url = f'https://timeapi.io/api/TimeZone/coordinate'
        
        # ICAO 코드로 좌표 조회 (간단한 매핑)
        coordinates = get_coordinates_by_icao(icao_code)
        if not coordinates:
            return None
            
        params = {
            'latitude': coordinates['lat'],
            'longitude': coordinates['lon']
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            # UTC 오프셋 계산
            utc_offset_obj = data.get('currentUtcOffset', {})
            utc_offset_seconds = utc_offset_obj.get('seconds', 0)
            
            # 시간대 형식 변환
            hours = utc_offset_seconds // 3600
            minutes = abs(utc_offset_seconds % 3600) // 60
            utc_offset_str = f"UTC{hours:+d}" if minutes == 0 else f"UTC{hours:+d}:{minutes:02d}"
            
            return utc_offset_str
            
    except Exception as e:
        logger.error(f"API 시간대 조회 오류: {e}")
        
    return None

def get_coordinates_by_icao(icao_code):
    """
    ICAO 코드로 좌표를 조회합니다.
    
    Args:
        icao_code (str): ICAO 공항 코드
        
    Returns:
        dict: {'lat': float, 'lon': float} 또는 None
    """
    # 주요 공항의 좌표 매핑 (예시)
    airport_coordinates = {
        'KSEA': {'lat': 47.4475673, 'lon': -122.3080159},  # 시애틀
        'RKSI': {'lat': 37.4601919, 'lon': 126.4406952},   # 인천
        'RJTT': {'lat': 35.5493939, 'lon': 139.7798386},   # 하네다
        'VVDN': {'lat': 16.043917, 'lon': 108.19937},      # 다낭
        'VVCR': {'lat': 10.818139, 'lon': 106.652002},     # 호치민
    }
    
    return airport_coordinates.get(icao_code.upper())