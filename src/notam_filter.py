import os
import google.generativeai as genai
from dotenv import load_dotenv
import re
from datetime import datetime, timedelta
import json
import csv
from constants import NO_TRANSLATE_TERMS, DEFAULT_ABBR_DICT
from typing import Dict, List, Optional

# 환경 변수 로드
load_dotenv()

# Google API 키 설정
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다.")

# Gemini 모델 설정
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash-lite')

# 색상 패턴 정의
RED_STYLE_TERMS = [
    'closed', 'close', 'closing','obstacle','obstacles','obstacle area','obstruction','obstructions',
    'restricted','prohibited','severe','severe weather','volcanic ash','volcanic ash cloud',
    'out of service', 'unserviceable', 'not available','not authorized',
    'caution','cautious',
    'hazard','hazardous','hazardous weather','hazardous materials',
    'emergency','emergency landing','emergency landing procedure',
    '장애물', '장애물 구역', '장애물 설치', '장애물 설치됨',
    '사용 불가', '운용 중단', '제한됨', '폐쇄됨',
    '제한', '폐쇄', '중단', '불가능', '불가',
    '긴급', '긴급 착륙', '긴급 착륙 절차',
    '경보', '경보 발생', '경보 해제',
    '주의', '주의 요구', '주의 요구 사항',
    '크레인', 'crane', 'cranes',
    'GPS RAIM',  # GPS RAIM을 하나의 단어로 처리
    'Non-Precision Approach', 'non-precision approach',
    '포장 공사', 'pavement construction',
 ]

BLUE_STYLE_PATTERNS = [
    r'\bDVOR\b',  # DVOR
    r'\bAPRON\b',  # APRON
    r'\bANTI-ICING\b',  # ANTI-ICING
    r'\bDE-ICING\b',  # DE-ICING
    r'\bSTAND\s+NUMBER\s+\d+\b',  # STAND NUMBER + 숫자 (예: STAND NUMBER 711)
    r'\bSTAND\s+\d+\b',  # STAND + 숫자 (예: STAND 711)
    r'\bSTAND\b',  # STAND
    r'\bILS\b',  # ILS
    r'\bLOC\b',  # LOC
    r'\bS-LOC\b',  # S-LOC
    r'\bMDA\b',  # MDA
    r'\bCAT\b',  # CAT
    r'\bVIS\b',  # VIS
    r'\bRVR\b',  # RVR
    r'\bHAT\b',  # HAT
    r'\bRWY\s+(?:\d{2}[LRC]?(?:/\d{2}[LRC]?)?)\b',  # RWY + 숫자 + 선택적 L/R/C (예: RWY 15L/33R)
    r'\bTWY\s+(?:[A-Z]|[A-Z]{2}|[A-Z]\d{1,2})\b',  # TWY + 알파벳(1-2자리) 또는 알파벳+숫자(1-2자리)
    r'\bTWY\s+[A-Z]\b',  # TWY + 한 자리 알파벳 (예: TWY D)
    r'\bTWY\s+[A-Z]{2}\b',  # TWY + 두 자리 알파벳 (예: TWY DD)
    r'\bTWY\s+[A-Z]\d{1,2}\b',  # TWY + 알파벳+숫자(1-2자리) (예: TWY D1, TWY D12)
    r'\bVOR\b',  # VOR
    r'\bDME\b',  # DME
    r'\bTWR\b',  # TWR
    r'\bATIS\b',  # ATIS
    r'\bAPPROACH MINIMA\b',  # APPROACH MINIMA
    r'\bVDP\b',  # VDP
    r'\bEST\b',  # EST
    r'\bEastern Standard Time\b',  # Eastern Standard Time
    r'\bIAP\b',  # IAP
    r'\bRNAV\b',  # RNAV
    r'\bGPS\s+(?:APPROACH|APP|APPROACHES)\b',  # GPS APPROACH, GPS APP 등
    r'\bLPV\b',  # LPV
    r'\bDA\b',  # DA
    r'\b주기장\b',  # 주기장
    r'\b주기장\s+\d+\b',  # 주기장 + 숫자
    r'\b활주로\s+\d+[A-Z]?\b',  # 활주로 + 숫자 + 선택적 알파벳
    r'\bP\d+\b',  # P + 숫자
    r'\bSTANDS?\s*(?:NR\.)?\s*(\d+)\b',  # STANDS NR. 711 형식
    r'\bSTANDS?\s*(\d+)\b',  # STANDS 711 형식
]

def apply_color_styles(text):
    """텍스트에 색상 스타일을 적용합니다."""
    
    # HTML 태그가 이미 있는지 확인하고 제거
    text = re.sub(r'<span[^>]*>', '', text)
    text = re.sub(r'</span>', '', text)
    
    # Runway를 RWY로 변환
    text = re.sub(r'\bRunway\s+', 'RWY ', text, flags=re.IGNORECASE)
    text = re.sub(r'\brunway\s+', 'RWY ', text, flags=re.IGNORECASE)
    
    # GPS RAIM을 하나의 단어로 처리
    text = re.sub(
        r'\bGPS\s+RAIM\b',
        r'<span style="color: red; font-weight: bold;">GPS RAIM</span>',
        text
    )
    
    # 빨간색 스타일 적용 (GPS RAIM 제외)
    for term in [t for t in RED_STYLE_TERMS if t != 'GPS RAIM']:
        if term.lower() in text.lower():
            text = re.sub(
                re.escape(term),
                lambda m: f'<span style="color: red; font-weight: bold;">{m.group()}</span>',
                text,
                flags=re.IGNORECASE
            )
    
    # 활주로 및 유도로 패턴 처리
    rwy_twy_patterns = [
        (r'(?:^|\s)(RWY\s*\d{2}[LRC]?(?:/\d{2}[LRC]?)?)', 'blue'),  # RWY 15L/33R
        (r'(?:^|\s)(TWY\s*[A-Z](?:\s+AND\s+[A-Z])*)', 'blue'),  # TWY D, TWY D AND E
        (r'(?:^|\s)(TWY\s*[A-Z]\d+)', 'blue'),  # TWY D1
    ]
    
    for pattern, color in rwy_twy_patterns:
        text = re.sub(
            pattern,
            lambda m: f' <span style="color: {color}; font-weight: bold;">{m.group(1).strip()}</span>',
            text
        )
    
    # 파란색 스타일 적용 (RWY, TWY 제외)
    for pattern in [p for p in BLUE_STYLE_PATTERNS if not (p.startswith(r'\bRWY') or p.startswith(r'\bTWY'))]:
        text = re.sub(
            pattern,
            lambda m: f'<span style="color: blue; font-weight: bold;">{m.group(0)}</span>',
            text,
            flags=re.IGNORECASE
        )
    
    # HTML 태그 중복 방지
    text = re.sub(r'(<span[^>]*>)+', r'\1', text)
    text = re.sub(r'(</span>)+', r'\1', text)
    text = re.sub(r'\s+', ' ', text)  # 중복 공백 제거
    
    return text.strip()

def translate_notam(text):
    """NOTAM 텍스트를 영어와 한국어로 번역합니다."""
    try:
        # NOTAM 번호 추출
        notam_number = text.split()[0]
        # NOTAM 타입 식별
        notam_type = identify_notam_type(notam_number)
        # 영어 번역
        english_translation = perform_translation(text, "en", notam_type)
        english_translation = apply_color_styles(english_translation)
        # 한국어 번역
        korean_translation = perform_translation(text, "ko", notam_type)
        korean_translation = apply_color_styles(korean_translation)
        return {
            'english_translation': english_translation,
            'korean_translation': korean_translation,
            'error_message': None
        }
    except Exception as e:
        print(f"번역 수행 중 오류 발생: {str(e)}")
        return {
            'english_translation': 'Translation failed',
            'korean_translation': '번역 실패',
            'error_message': str(e)
        }

def extract_e_section(notam_text):
    """
    NOTAM 텍스트에서 E 섹션만 추출합니다.
    """
    # E 섹션 패턴 매칭
    e_section_pattern = r'E\)\s*(.*?)(?=\s*[A-Z]\)|$)'
    match = re.search(e_section_pattern, notam_text, re.DOTALL)
    
    if match:
        e_section = match.group(1).strip()
        # CREATED: 이후의 텍스트 제거
        e_section = re.sub(r'CREATED:.*$', '', e_section, flags=re.DOTALL).strip()
        return e_section
    return notam_text

def preprocess_notam_text(notam_text):
    """
    NOTAM 텍스트를 번역 전에 전처리합니다.
    """
    # AIRAC AIP SUP과 UTC를 임시 토큰으로 대체
    notam_text = re.sub(r'\bAIRAC AIP SUP\b', 'AIRAC_AIP_SUP', notam_text)
    notam_text = re.sub(r'\bUTC\b', 'UTC_TOKEN', notam_text)
    
    # 다른 NO_TRANSLATE_TERMS 처리
    for term in NO_TRANSLATE_TERMS:
        if term not in ["AIRAC AIP SUP", "UTC"]:  # 이미 처리한 항목 제외
            notam_text = re.sub(r'\b' + re.escape(term) + r'\b', term.replace(' ', '_'), notam_text)
    
    return notam_text

def postprocess_translation(translated_text):
    """
    번역된 텍스트를 후처리합니다.
    """
    # 임시 토큰을 원래 형태로 복원
    translated_text = translated_text.replace("AIRAC_AIP_SUP", "AIRAC AIP SUP")
    translated_text = translated_text.replace("UTC_TOKEN", "UTC")
    
    # 다른 NO_TRANSLATE_TERMS 복원
    for term in NO_TRANSLATE_TERMS:
        if term not in ["AIRAC AIP SUP", "UTC"]:  # 이미 처리한 항목 제외
            translated_text = translated_text.replace(term.replace(' ', '_'), term)
    
    return translated_text

def perform_translation(text, target_lang, notam_type):
    """Gemini를 사용하여 NOTAM 번역 수행"""
    try:
        # E 섹션만 추출
        e_section = extract_e_section(text)
        if not e_section:
            return "번역할 내용이 없습니다."

        # 번역 프롬프트 설정
        if target_lang == "en":
            prompt = f"""Translate the following NOTAM E section to English. Follow these rules strictly:

1. Keep these terms exactly as they are:
   - NOTAM, AIRAC, AIP, SUP, AMDT, WEF, TIL, UTC
   - GPS, RAIM, NPA, PBN, RNAV, RNP
   - RWY, TWY, APRON, TAXI, SID, STAR, IAP
   - SFC, AMSL, AGL, MSL
   - PSN, RADIUS, HGT, HEIGHT
   - TEMP, PERM, OBST, FIREWORKS
   - All coordinates, frequencies, and measurements
   - All dates and times in original format
   - All aircraft stand numbers and references

2. For specific terms:
   - Translate "CLOSED" as "CLOSED"
   - Translate "PAVEMENT CONSTRUCTION" as "PAVEMENT CONSTRUCTION"
   - Translate "OUTAGES" as "OUTAGES"
   - Translate "PREDICTED FOR" as "PREDICTED FOR"
   - Translate "WILL TAKE PLACE" as "WILL TAKE PLACE"
   - Keep "ACFT" as "ACFT"
   - Keep "NR." as "NR."
   - Keep all parentheses and their contents intact
   - Always close parentheses if they are opened

3. Maintain the exact format of:
   - Multiple items (e.g., "1.PSN: ..., 2.PSN: ...")
   - Coordinates and measurements
   - Dates and times
   - NOTAM sections
   - Aircraft stand numbers and references
   - Complete all unfinished sentences or phrases

4. Do not include:
   - NOTAM number
   - Dates or times from outside the E section
   - Airport codes
   - "E:" prefix
   - Any additional text or explanations
   - "CREATED:" and following text

Original text:
{e_section}

Translated text:"""
        else:  # Korean
            prompt = f"""다음 NOTAM E 섹션을 한국어로 번역하세요. 다음 규칙을 엄격히 따르세요:

1. 다음 용어는 그대로 유지:
   - NOTAM, AIRAC, AIP, SUP, AMDT, WEF, TIL, UTC
   - GPS, RAIM, PBN, RNAV, RNP
   - RWY, TWY, APRON, TAXI, SID, STAR, IAP
   - SFC, AMSL, AGL, MSL
   - PSN, RADIUS, HGT, HEIGHT
   - TEMP, PERM, OBST, FIREWORKS
   - 모든 좌표, 주파수, 측정값
   - 모든 날짜와 시간은 원래 형식 유지
   - 모든 항공기 주기장 번호와 참조

2. 특정 용어 번역:
   - "CLOSED"는 "폐쇄"로 번역
   - "PAVEMENT CONSTRUCTION"은 "포장 공사"로 번역
   - "OUTAGES"는 "기능 상실"로 번역
   - "PREDICTED FOR"는 "에 영향을 줄 것으로 예측됨"으로 번역
   - "WILL TAKE PLACE"는 "진행될 예정"으로 번역
   - "NPA"는 "비정밀접근"으로 번역
   - "FLW"는 "다음과 같이"로 번역
   - "ACFT"는 "항공기"로 번역
   - "NR."는 "번호"로 번역
   - "ESTABLISHMENT OF"는 "신설"로 번역
   - "INFORMATION OF"는 "정보"로 번역
   - "CIRCLE"은 "원형"으로 번역
   - "CENTERED"는 "중심"으로 번역
   - "DUE TO"는 "로 인해"로 번역
   - "MAINT"는 "정비"로 번역
   - "NML OPS"는 "정상 운영"으로 번역
   - 괄호 안의 내용은 가능한 한 번역
   - 열린 괄호는 반드시 닫기

3. 다음 형식 정확히 유지:
   - 여러 항목 (예: "1.PSN: ..., 2.PSN: ...")
   - 좌표와 측정값
   - 날짜와 시간
   - NOTAM 섹션
   - 항공기 주기장 번호와 참조
   - 문장이나 구절이 완성되지 않은 경우 완성

4. 다음 내용 포함하지 않음:
   - NOTAM 번호
   - E 섹션 외부의 날짜나 시간
   - 공항 코드
   - "E:" 접두사
   - 추가 설명이나 텍스트
   - "CREATED:" 이후의 텍스트

5. 번역 스타일:
   - 자연스러운 한국어 어순 사용
   - 불필요한 조사나 어미 제거
   - 간결하고 명확한 표현 사용
   - 중복된 표현 제거
   - 띄어쓰기 오류 없도록 주의
   - "DUE TO"는 항상 "로 인해"로 번역하고 "TO"를 추가하지 않음

원문:
{e_section}

번역문:"""
        
        # Gemini API 호출
        response = model.generate_content(prompt)
        translated_text = response.text.strip()
        
        # "CREATED:" 이후의 텍스트 제거
        translated_text = re.sub(r'\s*CREATED:.*$', '', translated_text)
        
        # 불필요한 공백 제거
        translated_text = re.sub(r'\s+', ' ', translated_text)
        
        # 괄호 닫기 확인
        if translated_text.count('(') > translated_text.count(')'):
            translated_text += ')'
        
        # 띄어쓰기 오류 수정
        translated_text = re.sub(r'폐\s+쇄', '폐쇄', translated_text)
        
        return translated_text
    except Exception as e:
        print(f"번역 중 오류 발생: {str(e)}")
        return "번역 중 오류가 발생했습니다."

def identify_notam_type(notam_number):
    """NOTAM 번호를 기반으로 NOTAM 타입을 식별합니다."""
    prefix = notam_number[0].upper()
    
    notam_types = {
        'A': "AERODROME NOTAM",
        'B': "BEACON NOTAM",
        'C': "COMMUNICATION NOTAM",
        'D': "DANGER AREA NOTAM",
        'E': "ENROUTE NOTAM",
        'F': "FLIGHT INFORMATION NOTAM",
        'G': "GENERAL NOTAM",
        'H': "HELIPORT NOTAM",
        'I': "INSTRUMENT APPROACH NOTAM",
        'L': "LIGHTING NOTAM",
        'M': "MILITARY NOTAM",
        'N': "NEW NOTAM",
        'O': "OBSTACLE NOTAM",
        'P': "PROHIBITED AREA NOTAM",
        'R': "RESTRICTED AREA NOTAM",
        'S': "SNOWTAM",
        'T': "TERMINAL NOTAM",
        'U': "UNMANNED AIRCRAFT NOTAM",
        'V': "VOLCANIC ACTIVITY NOTAM",
        'W': "WARNING NOTAM",
        'X': "OTHER NOTAM",
        'Z': "TRIGGER NOTAM"
    }
    
    return notam_types.get(prefix, "GENERAL NOTAM")

__all__ = ['apply_color_styles', 'RED_STYLE_TERMS', 'BLUE_STYLE_PATTERNS', 'NOTAMFilter']


class NOTAMFilter:
    """NOTAM 필터링 및 파싱 클래스"""
    
    def __init__(self):
        """NOTAMFilter 초기화"""
        # 공항 데이터 로드
        self.airports_data = self._load_airports_data()
        
    def _load_airports_data(self):
        """공항 데이터 로드"""
        airports_data = {}
        try:
            # SmartNOTAMgemini_GCR 폴더의 공항 데이터 사용
            csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                  'SmartNOTAMgemini_GCR', 'AirportsDatawithUTCTimeZones copy.csv')
            
            if os.path.exists(csv_path):
                with open(csv_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        icao_code = row.get('ICAO')
                        if icao_code:
                            airports_data[icao_code] = {
                                'name': row.get('Airport Name', ''),
                                'country': row.get('Country', ''),
                                'timezone': row.get('Timezone', 'UTC'),
                                'utc_offset': row.get('UTC_Offset', '+00:00')
                            }
            else:
                print(f"공항 데이터 파일을 찾을 수 없습니다: {csv_path}")
                
        except Exception as e:
            print(f"공항 데이터 로드 중 오류: {e}")
            
        return airports_data
    
    def get_timezone(self, airport_code):
        """공항 코드에 따른 타임존 정보 반환"""
        if airport_code in self.airports_data:
            return self.airports_data[airport_code].get('utc_offset', '+00:00')
        
        # 기본 타임존 설정 (ICAO 코드 첫 글자 기준)
        if airport_code.startswith('RK'):  # 한국
            return '+09:00'
        elif airport_code.startswith('RJ'):  # 일본
            return '+09:00'
        elif airport_code.startswith('ZB') or airport_code.startswith('ZG'):  # 중국
            return '+08:00'
        else:
            return '+00:00'  # UTC
    
    def _parse_notam_section(self, notam_text):
        """NOTAM 텍스트를 파싱하여 정보 추출"""
        parsed_notam = {}
        
        # ICAO 공항 코드 추출 (4글자)
        airport_match = re.search(r'\b([A-Z]{4})\b', notam_text)
        if airport_match:
            parsed_notam['airport_code'] = airport_match.group(1)
        
        # NOTAM 번호 추출
        notam_number_match = re.search(r'([A-Z]\d{4}/\d{2})', notam_text)
        if notam_number_match:
            parsed_notam['notam_number'] = notam_number_match.group(1)
        
        # 시간 정보 파싱
        self._parse_time_info(notam_text, parsed_notam)
        
        # E) 필드 추출
        e_field_match = re.search(r'E\)\s*(.+?)(?=\s*F\)|$)', notam_text, re.DOTALL)
        if e_field_match:
            parsed_notam['e_field'] = e_field_match.group(1).strip()
        
        return parsed_notam
    
    def _parse_time_info(self, notam_text, parsed_notam):
        """시간 정보 파싱 (UFN 지원 포함)"""
        
        # 1. UFN (Until Further Notice) 패턴 먼저 확인
        ufn_pattern = r'(\d{2}[A-Z]{3}\d{2}) (\d{2}:\d{2}) - UFN'
        ufn_match = re.search(ufn_pattern, notam_text)
        
        if ufn_match:
            start_date, start_time = ufn_match.groups()
            try:
                # 시작 시간 파싱
                day = int(start_date[:2])
                month_str = start_date[2:5]
                year = int('20' + start_date[5:7])
                
                month_map = {
                    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                    'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
                }
                month = month_map[month_str]
                
                hour, minute = map(int, start_time.split(':'))
                start_dt = datetime(year, month, day, hour, minute)
                
                parsed_notam['effective_time'] = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                parsed_notam['expiry_time'] = 'UFN'
                
                return
                
            except Exception as e:
                print(f"UFN 시간 파싱 오류: {e}")
        
        # 2. WEF/TIL 패턴
        wef_til_pattern = r'(\d{2}[A-Z]{3}\d{2}) (\d{2}:\d{2}) - (\d{2}[A-Z]{3}\d{2}) (\d{2}:\d{2})'
        wef_til_match = re.search(wef_til_pattern, notam_text)
        
        if wef_til_match:
            start_date, start_time, end_date, end_time = wef_til_match.groups()
            try:
                # 시작 시간 파싱
                start_dt = self._parse_datetime_string(start_date, start_time)
                end_dt = self._parse_datetime_string(end_date, end_time)
                
                parsed_notam['effective_time'] = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                parsed_notam['expiry_time'] = end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                
                return
                
            except Exception as e:
                print(f"WEF/TIL 시간 파싱 오류: {e}")
        
        # 3. B) C) 필드 패턴
        b_field_match = re.search(r'B\)\s*(\d{10})', notam_text)
        c_field_match = re.search(r'C\)\s*(\d{10})', notam_text)
        
        if b_field_match:
            b_time = b_field_match.group(1)
            try:
                start_dt = self._parse_b_c_time(b_time)
                parsed_notam['effective_time'] = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            except Exception as e:
                print(f"B) 필드 시간 파싱 오류: {e}")
        
        if c_field_match:
            c_time = c_field_match.group(1)
            try:
                end_dt = self._parse_b_c_time(c_time)
                parsed_notam['expiry_time'] = end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            except Exception as e:
                print(f"C) 필드 시간 파싱 오류: {e}")
    
    def _parse_datetime_string(self, date_str, time_str):
        """날짜 문자열 파싱 (30MAY24 01:15 형식)"""
        day = int(date_str[:2])
        month_str = date_str[2:5]
        year = int('20' + date_str[5:7])
        
        month_map = {
            'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
            'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
        }
        month = month_map[month_str]
        
        hour, minute = map(int, time_str.split(':'))
        return datetime(year, month, day, hour, minute)
    
    def _parse_b_c_time(self, time_str):
        """B), C) 필드 시간 파싱 (2503200606 형식)"""
        year = int('20' + time_str[:2])
        month = int(time_str[2:4])
        day = int(time_str[4:6])
        hour = int(time_str[6:8])
        minute = int(time_str[8:10])
        
        return datetime(year, month, day, hour, minute)
    
    def _generate_local_time_display(self, parsed_notam):
        """로컬 시간 표시 생성"""
        if not parsed_notam.get('effective_time'):
            return None
        
        airport_code = parsed_notam.get('airport_code', '')
        timezone_offset = self.get_timezone(airport_code)
        
        try:
            # UTC 시간을 datetime 객체로 변환
            effective_dt = datetime.fromisoformat(parsed_notam['effective_time'].replace('Z', '+00:00'))
            
            # 타임존 오프셋 파싱 (+09:00 형식)
            offset_sign = 1 if timezone_offset.startswith('+') else -1
            offset_hours = int(timezone_offset[1:3])
            offset_minutes = int(timezone_offset[4:6])
            offset_delta = timedelta(hours=offset_hours * offset_sign, minutes=offset_minutes * offset_sign)
            
            # 로컬 시간 계산
            local_start = effective_dt + offset_delta
            
            # 만료 시간 처리
            if parsed_notam.get('expiry_time') == 'UFN':
                # UFN인 경우
                local_time_str = f"{local_start.strftime('%m/%d %H:%M')} - UFN ({timezone_offset})"
            elif parsed_notam.get('expiry_time'):
                # 일반적인 만료 시간이 있는 경우
                expiry_dt = datetime.fromisoformat(parsed_notam['expiry_time'].replace('Z', '+00:00'))
                local_end = expiry_dt + offset_delta
                local_time_str = f"{local_start.strftime('%m/%d %H:%M')} - {local_end.strftime('%m/%d %H:%M')} ({timezone_offset})"
            else:
                # 만료 시간이 없는 경우
                local_time_str = f"{local_start.strftime('%m/%d %H:%M')} ({timezone_offset})"
            
            return local_time_str
            
        except Exception as e:
            print(f"로컬 시간 변환 오류: {e}")
            return None
    
    def format_notam_time_with_local(self, effective_time, expiry_time, airport_code):
        """NOTAM 시간을 로컬 시간으로 포맷팅"""
        if not effective_time:
            return None
        
        timezone_offset = self.get_timezone(airport_code)
        
        try:
            # UTC 시간을 datetime 객체로 변환
            effective_dt = datetime.fromisoformat(effective_time.replace('Z', '+00:00'))
            
            # 타임존 오프셋 파싱 (+09:00 형식)
            offset_sign = 1 if timezone_offset.startswith('+') else -1
            offset_hours = int(timezone_offset[1:3])
            offset_minutes = int(timezone_offset[4:6])
            offset_delta = timedelta(hours=offset_hours * offset_sign, minutes=offset_minutes * offset_sign)
            
            # 로컬 시간 계산
            local_start = effective_dt + offset_delta
            
            # 만료 시간 처리
            if expiry_time == 'UFN':
                # UFN인 경우
                local_time_str = f"{local_start.strftime('%m/%d %H:%M')} - UFN ({timezone_offset})"
            elif expiry_time:
                # 일반적인 만료 시간이 있는 경우
                expiry_dt = datetime.fromisoformat(expiry_time.replace('Z', '+00:00'))
                local_end = expiry_dt + offset_delta
                local_time_str = f"{local_start.strftime('%m/%d %H:%M')} - {local_end.strftime('%m/%d %H:%M')} ({timezone_offset})"
            else:
                # 만료 시간이 없는 경우
                local_time_str = f"{local_start.strftime('%m/%d %H:%M')} ({timezone_offset})"
            
            return local_time_str
            
        except Exception as e:
            print(f"시간 포맷팅 오류: {e}")
            return None
    
    def filter_korean_air_notams(self, text):
        """한국 항공 관련 NOTAM 필터링"""
        korean_airports = ['RKSI', 'RKPK', 'RKPC', 'RKTU', 'RKJJ', 'RKNY', 'RKJY', 'RKJB', 'RKJK']
        
        # NOTAM 섹션으로 분할 (공항코드 + NOTAM번호 패턴)
        notam_sections = re.split(r'\n(?=[A-Z]{4}\s+[A-Z]\d{3,4}/\d{2})', text)
        filtered_notams = []
        
        for section in notam_sections:
            section = section.strip()
            if not section:
                continue
                
            # 한국 공항 코드가 포함된 NOTAM만 필터링
            for airport in korean_airports:
                if airport in section:
                    # NOTAM 파싱
                    parsed_notam = self._parse_notam_section(section)
                    
                    # 기본 정보 설정
                    notam_dict = {
                        'id': parsed_notam.get('notam_number', 'Unknown'),
                        'notam_number': parsed_notam.get('notam_number', 'Unknown'),
                        'airport_code': parsed_notam.get('airport_code', airport),
                        'effective_time': parsed_notam.get('effective_time', ''),
                        'expiry_time': parsed_notam.get('expiry_time', ''),
                        'description': parsed_notam.get('e_field', section),
                        'original_text': section
                    }
                    
                    # UFN을 포함한 모든 시간 정보에 대해 local_time_display 생성
                    if parsed_notam.get('effective_time') and (parsed_notam.get('expiry_time') or parsed_notam.get('expiry_time') == 'UFN'):
                        local_time_display = self._generate_local_time_display(parsed_notam)
                        if local_time_display:
                            notam_dict['local_time_display'] = local_time_display
                            # 원본 텍스트에도 로컬 시간 추가
                            notam_dict['original_text'] = section + f"\n\n로컬 시간: {local_time_display}"
                    
                    filtered_notams.append(notam_dict)
                    break
        
        return filtered_notams