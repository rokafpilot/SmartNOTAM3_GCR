import os
import google.generativeai as genai
from dotenv import load_dotenv
import re
from datetime import datetime, timedelta
import json
import csv
import logging
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from constants import NO_TRANSLATE_TERMS, DEFAULT_ABBR_DICT
from typing import Dict, List, Optional

# 환경 변수 로드
load_dotenv()

# Google API 키 설정 (선택사항)
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
if GOOGLE_API_KEY:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash-lite')
        GEMINI_AVAILABLE = True
    except Exception as e:
        print(f"GEMINI 설정 실패: {e}")
        GEMINI_AVAILABLE = False
        model = None
else:
    GEMINI_AVAILABLE = False
    model = None

# NOTAM 카테고리 매핑 (아이콘과 색깔 포함)
NOTAM_CATEGORIES = {
    'RUNWAY': {
        'keywords': ['runway', 'rw', '활주로', '착륙', '이륙', 'landing', 'takeoff'],
        'q_codes': ['Q) RW', 'Q) RWY'],
        'icon': '🛬',
        'color': '#dc3545',  # 빨간색 (위험/중요)
        'bg_color': '#f8d7da'
    },
    'TAXIWAY': {
        'keywords': ['taxiway', 'tw', 'twy', '택시웨이', '유도로', 'movement area'],
        'q_codes': ['Q) TW', 'Q) TWY'],
        'icon': '🛣️',
        'color': '#fd7e14',  # 주황색
        'bg_color': '#fff3cd'
    },
    'APRON': {
        'keywords': ['apron', 'ramp', 'gate', 'docking', 'mars', '계류장', '게이트', '접현', '도킹', 'lead-in line', 'vdgs'],
        'q_codes': ['Q) APRON', 'Q) RAMP'],
        'icon': '🅿️',
        'color': '#6f42c1',  # 보라색
        'bg_color': '#e2d9f3'
    },
    'LIGHT': {
        'keywords': ['light', 'lighting', 'lgt', '조명', '등화', 'beacon', 'approach light', 'runway light'],
        'q_codes': ['Q) LGT', 'Q) LIGHT'],
        'icon': '💡',
        'color': '#ffc107',  # 노란색
        'bg_color': '#fff3cd'
    },
    'APPROACH': {
        'keywords': ['approach', 'app', '접근', 'ils', 'vor', 'ndb', 'gps approach', 'precision approach'],
        'q_codes': ['Q) APP', 'Q) ILS', 'Q) VOR', 'Q) NDB'],
        'icon': '📡',
        'color': '#20c997',  # 청록색
        'bg_color': '#d1ecf1'
    },
    'DEPARTURE': {
        'keywords': ['departure procedure', 'dep procedure', 'sid', 'standard instrument departure', '출발 절차', '이륙 절차'],
        'q_codes': ['Q) DEP', 'Q) SID'],
        'icon': '✈️',
        'color': '#0dcaf0',  # 하늘색
        'bg_color': '#cff4fc'
    },
    'GPS': {
        'keywords': ['gps', 'gnss', 'raim', 'gps approach', 'gps outage', 'gps unavailable'],
        'q_codes': ['Q) GPS', 'Q) GNSS', 'Q) RAIM'],
        'icon': '🛰️',
        'color': '#198754',  # 녹색
        'bg_color': '#d1e7dd'
    },
    'OBSTRUCTION': {
        'keywords': ['obstacle', 'obstruction', 'obstacles', 'obstructions', '장애물', '장애물 구역'],
        'q_codes': ['Q) OBST', 'Q) OBSTRUCTION'],
        'icon': '⚠️',
        'color': '#dc3545',  # 빨간색 (위험)
        'bg_color': '#f8d7da'
    },
    'NAVAID': {
        'keywords': ['navaid', 'navigation aid', 'vor', 'ndb', 'ils', 'dme', 'tacan', '항행보조시설'],
        'q_codes': ['Q) NAVAID', 'Q) VOR', 'Q) NDB', 'Q) ILS', 'Q) DME'],
        'icon': '📶',
        'color': '#6c757d',  # 회색
        'bg_color': '#e9ecef'
    },
    'COMMUNICATION': {
        'keywords': ['communication', 'comm', 'radio', 'frequency', '통신', '주파수', 'frequency change'],
        'q_codes': ['Q) COMM', 'Q) FREQ'],
        'icon': '📻',
        'color': '#0d6efd',  # 파란색
        'bg_color': '#cfe2ff'
    },
    'AIRWAY': {
        'keywords': ['airway', 'route', 'air route', '항로', '항공로', 'enroute'],
        'q_codes': ['Q) AWY', 'Q) AIRWAY'],
        'icon': '🗺️',
        'color': '#fd7e14',  # 주황색
        'bg_color': '#fff3cd'
    },
    'AIRSPACE': {
        'keywords': ['airspace', 'air space', 'controlled airspace', 'airspace restriction', '공역', '제한공역'],
        'q_codes': ['Q) AIRSPACE'],
        'icon': '🌐',
        'color': '#6f42c1',  # 보라색
        'bg_color': '#e2d9f3'
    },
    'AIP': {
        'keywords': ['aip', 'aeronautical information publication', '항공정보간행물'],
        'q_codes': ['Q) AIP'],
        'icon': '📋',
        'color': '#6c757d',  # 회색
        'bg_color': '#e9ecef'
    }
}

def analyze_notam_category(notam_text, q_code=None):
    """NOTAM 텍스트와 Q-code를 분석하여 카테고리 결정"""
    if not notam_text:
        return 'OTHER'
    
    # 텍스트를 소문자로 변환하여 분석
    text_lower = notam_text.lower()
    
    # Q-code가 있으면 우선적으로 사용
    if q_code:
        q_code_upper = q_code.upper()
        for category, data in NOTAM_CATEGORIES.items():
            for q_pattern in data['q_codes']:
                if q_pattern.upper() in q_code_upper:
                    return category
    
    # 키워드 기반 분석 (가중치 적용)
    category_scores = {}
    for category, data in NOTAM_CATEGORIES.items():
        score = 0
        for keyword in data['keywords']:
            keyword_lower = keyword.lower()
            # 정확한 단어 매칭 (단어 경계 고려)
            if re.search(r'\b' + re.escape(keyword_lower) + r'\b', text_lower):
                # 중요한 키워드는 더 높은 가중치
                if keyword_lower in ['gate', 'docking', 'mars', 'apron', 'ramp', 'vdgs']:
                    score += 3
                elif keyword_lower in ['runway', 'taxiway', 'approach', 'departure']:
                    score += 2
                else:
                    score += 1
        category_scores[category] = score
    
    # 가장 높은 점수의 카테고리 반환
    if category_scores:
        best_category = max(category_scores.items(), key=lambda x: x[1])[0]
        if category_scores[best_category] > 0:
            return best_category
    
    return 'OTHER'

# 색상 패턴 정의
RED_STYLE_TERMS = [
    'closed', 'close', 'closing','obstacle','obstacles','obstacle area','obstruction','obstructions',
    'restricted','prohibited','severe','severe weather','volcanic ash','volcanic ash cloud',
    'out of service', 'unserviceable', 'not available','not authorized',
    'caution','cautious','cautionary',
    'hazard','hazardous','hazardous weather','hazardous materials',
    'emergency','emergency landing','emergency landing procedure',
    '장애물', '장애물 구역', '장애물 설치', '장애물 설치됨',
    '사용 불가', '운용 중단', '제한됨', '폐쇄됨',
    '제한', '폐쇄', '중단', '불가능', '불가',
    '긴급', '긴급 착륙', '긴급 착륙 절차',
    '경보', '경보 발생', '경보 해제', '오경보',
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
    r'\bPAINTING\b',  # PAINTING
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
        (r'\b(RWY\s*\d{2}[LRC]?(?:/\d{2}[LRC]?)?)\b', 'blue'),  # RWY 15L/33R
        (r'\b(RWY\s*\|)\b', 'blue'),  # RWY |
        (r'\b(RWY)\b', 'blue'),  # RWY 단독
        (r'\b(TWY\s*[A-Z](?:\s+AND\s+[A-Z])*)\b', 'blue'),  # TWY D, TWY D AND E
        (r'\b(TWY\s*[A-Z]\d+)\b', 'blue'),  # TWY D1
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
        print(f"오류 타입: {type(e).__name__}")
        import traceback
        traceback.print_exc()
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
    return ""  # E 섹션을 찾지 못하면 빈 문자열 반환

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
    
    # 불필요한 번역 내용 제거
    unwanted_translation_patterns = [
        r'공간\s*-->\s*\*\*번역:\*\*.*?이건 필요없는 말이야\.\.\.',
        r'공간\s*-->\s*\*\*번역:\*\*.*?이건 필요없는 말이야',
        r'공간\s*-->\s*.*?이건 필요없는 말이야\.\.\.',
        r'공간\s*-->\s*.*?이건 필요없는 말이야',
        r'\*\*번역:\*\*.*?이건 필요없는 말이야\.\.\.',
        r'\*\*번역:\*\*.*?이건 필요없는 말이야',
        r'이건 필요없는 말이야\.\.\.',
        r'이건 필요없는 말이야',
        # 기타 불필요한 패턴들 - 더 정확한 패턴
        r'번역:\s*[^가-힣]*$',  # "번역:" 뒤에 한글이 아닌 내용
        r'번역\s*:\s*[^가-힣]*$',
        r'^\s*번역\s*$',
        r'^\s*번역:\s*$',
        r'^\s*\*\*번역:\*\*\s*$',
        r'^\s*공간\s*-->\s*$',
        r'^\s*공간\s*$',
        # "번역:" 뒤에 특정 패턴들
        r'번역:\s*이것은.*?입니다\.',
        r'번역:\s*테스트.*?입니다\.',
        r'번역:\s*[가-힣]*\s*테스트',
    ]
    
    import re
    for pattern in unwanted_translation_patterns:
        translated_text = re.sub(pattern, '', translated_text, flags=re.MULTILINE | re.DOTALL)
    
    # 빈 줄 정리
    lines = translated_text.split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        # "번역 실패"는 유지하고, 다른 불필요한 "번역:" 시작 라인만 제거
        if line and not (line.startswith('번역:') and not line.startswith('번역 실패')):
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines).strip()

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

3. 중요한 규칙:
   - 번역 결과에 "번역:", "공간", "이건 필요없는 말이야" 등의 불필요한 텍스트를 절대 포함하지 마세요
   - 순수하게 NOTAM 내용만 번역하세요
   - 번역 과정이나 메타데이터를 포함하지 마세요
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
   - "CEILING"은 반드시 "운고"로 번역

원문:
{e_section}

번역문:"""
        
        # Gemini API 호출
        if model and GEMINI_AVAILABLE:
            response = model.generate_content(prompt)
            translated_text = response.text.strip()
        else:
            translated_text = "GEMINI API를 사용할 수 없습니다."
        
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
        print(f"오류 타입: {type(e).__name__}")
        import traceback
        traceback.print_exc()
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
        # 로거 설정
        self.logger = logging.getLogger(__name__)
        
        # 패키지별 공항 순서 정의
        self.package_airport_order = {
            'package1': ['RKSI', 'VVDN', 'VVTS', 'VVCR', 'SECY'],
            'package2': ['RKSI', 'RKPC', 'ROAH', 'RJFF', 'RORS', 'RCTP', 'VHHH', 'ZJSY', 'VVNB', 'VVDN', 'VVTS'],
            'package3': ['RKRR', 'RJJJ', 'RCAA', 'VHHK', 'ZJSA', 'VVHN', 'VVHM']
        }
        
        # 로거 핸들러 설정
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
            
        # 공항 데이터 로드
        self.airports_data = self._load_airports_data()
        
        # 시간대 캐시 (성능 최적화)
        self.timezone_cache = {}
        
    def _detect_package_type(self, text):
        """텍스트에서 패키지 타입을 감지"""
        if 'KOREAN AIR NOTAM PACKAGE 1' in text:
            return 'package1'
        elif 'KOREAN AIR NOTAM PACKAGE 2' in text:
            return 'package2'
        elif 'KOREAN AIR NOTAM PACKAGE 3' in text:
            return 'package3'
        return None
        
    def _get_airport_priority(self, airport_code, package_type):
        """공항 코드의 우선순위를 반환"""
        if package_type and package_type in self.package_airport_order:
            order_list = self.package_airport_order[package_type]
            try:
                return order_list.index(airport_code)
            except ValueError:
                return 999  # 순서에 없는 공항은 마지막에
        return 999
        
    def _load_airports_data(self):
        """공항 데이터 로드"""
        airports_data = {}
        try:
            # src 폴더의 공항 데이터 사용
            csv_path = os.path.join(os.path.dirname(__file__), 'airports_timezones.csv')
            
            if os.path.exists(csv_path):
                with open(csv_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        icao_code = row.get('ident')  # CSV 파일의 실제 컬럼명
                        if icao_code:
                            time_zone = row.get('time_zone', 'UTC')
                            # UTC+8 -> +08:00 형식으로 변환
                            if time_zone.startswith('UTC+'):
                                utc_offset = '+' + time_zone[4:].zfill(2) + ':00'
                            elif time_zone.startswith('UTC-'):
                                utc_offset = '-' + time_zone[4:].zfill(2) + ':00'
                            else:
                                utc_offset = '+00:00'
                                
                            airports_data[icao_code] = {
                                'name': row.get('code', ''),
                                'country': '',
                                'timezone': time_zone,
                                'utc_offset': utc_offset
                            }
            else:
                print(f"Airport data file not found: {csv_path}")
                
        except Exception as e:
            print(f"Error loading airport data: {e}")
            
        return airports_data
    
    def get_timezone(self, airport_code):
        """공항 코드에 따른 타임존 정보 반환 (캐싱 적용)"""
        # 캐시 확인
        if airport_code in self.timezone_cache:
            return self.timezone_cache[airport_code]
        
        timezone_result = self._calculate_timezone(airport_code)
        
        # 캐시에 저장
        self.timezone_cache[airport_code] = timezone_result
        
        return timezone_result
    
    def _calculate_timezone(self, airport_code):
        """실제 시간대 계산 (캐싱 없이)"""
        # 1단계: CSV 데이터에서 정확한 시간대 조회
        if airport_code in self.airports_data:
            csv_timezone = self.airports_data[airport_code].get('utc_offset', '+00:00')
            # DST 적용 여부 확인
            return self._apply_dst_if_needed(airport_code, csv_timezone)
        
        # 2단계: 고급 시간대 시스템 사용 시도 (API 비활성화로 성능 향상)
        try:
            from src.icao import get_utc_offset
            advanced_timezone = get_utc_offset(airport_code, use_api=False)  # API 비활성화
            if advanced_timezone and advanced_timezone != "UTC+0":
                # UTC+9 -> +09:00 형식으로 변환
                if advanced_timezone.startswith('UTC+'):
                    return '+' + advanced_timezone[4:] + ':00'
                elif advanced_timezone.startswith('UTC-'):
                    return '-' + advanced_timezone[4:] + ':00'
        except Exception as e:
            print(f"Advanced timezone system failed: {e}")
        
        # 3단계: 기본 타임존 설정 (ICAO 코드 첫 글자 기준)
        if airport_code.startswith('RK'):  # 한국
            return '+09:00'
        elif airport_code.startswith('RJ'):  # 일본
            return '+09:00'
        elif airport_code.startswith('ZB') or airport_code.startswith('ZG'):  # 중국
            return '+08:00'
        elif airport_code.startswith('VV'):  # 베트남
            return '+07:00'
        elif airport_code.startswith('K'):  # 미국 공항들
            # 미국 시간대별 기본 설정 (DST 고려하지 않고 표준 시간 사용)
            if airport_code.startswith('KS'):  # 서부 (시애틀, 샌프란시스코)
                return '-08:00'  # PST
            elif airport_code.startswith('KL'):  # 서부 (로스앤젤레스)
                return '-08:00'  # PST
            elif airport_code.startswith('KD'):  # 중부 (덴버)
                return '-07:00'  # MST
            elif airport_code.startswith('KM'):  # 중부 (시카고)
                return '-06:00'  # CST
            elif airport_code.startswith('KE'):  # 동부 (뉴욕)
                return '-05:00'  # EST
            else:
                return '-06:00'  # 기본 중부 시간대
        else:
            return '+00:00'  # UTC
    
    def _apply_dst_if_needed(self, airport_code, timezone_offset):
        """DST가 필요한 공항에 대해 서머타임 적용"""
        # DST가 적용되는 지역들 (미국, 캐나다, 유럽 등)
        dst_regions = ['K', 'C', 'E', 'L']  # 미국, 캐나다, 유럽
        
        if airport_code[0] in dst_regions:
            try:
                # 간단한 DST 판단 (3월~10월)
                from datetime import datetime
                current_month = datetime.now().month
                dst_active = 3 <= current_month <= 10
                
                if dst_active:
                    # CSV의 값이 이미 DST 적용된 값이므로 그대로 사용
                    return timezone_offset
                else:
                    # 표준 시간으로 변환 (DST 비활성화 시)
                    if timezone_offset.startswith('-'):
                        # 음수 시간대에서 1시간 빼기 (표준 시간으로)
                        offset_hours = int(timezone_offset[1:3])
                        offset_minutes = int(timezone_offset[4:6])
                        new_hours = offset_hours - 1
                        if new_hours < 0:
                            new_hours = 0
                        return f"-{new_hours:02d}:{offset_minutes:02d}"
                    elif timezone_offset.startswith('+'):
                        # 양수 시간대에서 1시간 빼기 (표준 시간으로)
                        offset_hours = int(timezone_offset[1:3])
                        offset_minutes = int(timezone_offset[4:6])
                        new_hours = offset_hours - 1
                        if new_hours < 0:
                            new_hours = 0
                        return f"+{new_hours:02d}:{offset_minutes:02d}"
            
            except Exception as e:
                print(f"DST application error: {e}")
        
        return timezone_offset
    
    def _clean_additional_info(self, notam_text):
        """NOTAM에서 추가 정보 제거"""
        lines = notam_text.split('\n')
        cleaned_lines = []
        
        # 추가 정보 패턴들
        additional_info_patterns = [
            r'^\d+\.\s*COMPANY\s+RADIO\s*:',
            r'^\d+\.\s*COMPANY\s+ADVISORY\s*:',
            r'^\d+\.\s*RADIO\s*:',
            r'^\d+\.\s*ADVISORY\s*:',
            r'^\d+\.\s*[A-Z\s]+\s*:',
            r'^\[PAX\]',
            r'^\[JINAIR\]',
            r'^CTC\s+TWR',
            r'^NIL\s*$',
            r'^COMMENT\)\s*$',
            # 번호가 매겨진 COMPANY ADVISORY 항목들 (COAD NOTAM은 제외)
            # r'^\d+\.\s+\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*(?:UFN|PERM)\s+[A-Z]{4}\s+COAD\d+/\d+',  # COAD NOTAM은 유효한 NOTAM이므로 제거하지 않음
            r'^\d+\.\s+\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*(?:UFN|PERM)\s+[A-Z]{4}\s+(?!COAD)[A-Z]+\d+/\d+',
            # OCR 오류 패턴들 추가
            r'â—C¼O\s*MPANY',
            r'â—C¼O\s*COMPANY',
            r'â—A¼R\s*RIVAL',
            r'â—O¼B\s*STRUCTION',
            r'â—G¼P\s*S',
            r'â—R¼U\s*NWAY',
            r'â—A¼PP\s*ROACH',
            r'â—T¼A\s*XIWAY',
            r'â—N¼A\s*VAID',
            r'â—D¼E\s*PARTURE',
            r'â—R¼U\s*NWAY\s*LIGHT',
            r'â—A¼IP',
            r'â—O¼T\s*HER',
            # 추가 패턴들 - 베트남 관련 내용
            r'//REQUIRED WEATHER MINIMA IN VIETNAM//',
            r'// SPEED LIMIT WHEN USING VDGS //',
            r'CAAV\(CIVIL AVIATION AUTHORITY OF VIETNAM\)',
            r'CARGO FLIGHTS ARE NOT ALLOWED TO LAND EARLIER',
            r'PLZ DEPART TO HAN AFTER ETD ON FPL',
            r'ANY QUESTIONS ABOUT ETD OF FLT',
            r'CONTACT KOREANAIR DISPATCH BY CO-RADIO',
            r'// SIMILAR CALLSIGN //',
            r'KE\d+ AND KE\d+ MAY OPERATE ON SAME FREQ',
            r'PLZ PAY MORE ATTENTION TO ATC COMMUNICATION',
            r'CEILING IS ALWAYS SHOWN IN SMALLER SIZE',
            r'MUST NOT EXCEED \d+KTS FROM STARTING POINT',
            r'REDUCE SPEED TO STOP AT THE DESIGNATED STOP LINE',
            # 기타 불필요한 패턴들
            r'^\d+\.\s+ANY REVISION TO RWY CLOSURE',
            r'^\d+\.\s+IN THE EVENT THAT THE OPERATIONAL RWY',
            r'DEPENDENT ON THE WORK BEING CARRIED OUT',
            r'IT MAY TAKE UP TO \d+ HRS FOR A CLOSED RWY',
        ]
        
        for line in lines:
            line_stripped = line.strip()
            # 추가 정보 패턴에 매치되면 제거
            if any(re.search(pattern, line_stripped, re.IGNORECASE) for pattern in additional_info_patterns):
                continue
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines).strip()
    
    def _parse_notam_section(self, notam_text):
        """NOTAM 텍스트를 파싱하여 정보 추출"""
        # 추가 정보 제거
        cleaned_text = self._clean_additional_info(notam_text)
        
        parsed_notam = {}
        
        # NOTAM이 아닌 비정보 섹션 체크 (COMPANY ADVISORY 등)
        if any(phrase in cleaned_text.upper() for phrase in ['COMPANY ADVISORY', 'OTHER INFORMATION', 'DEP:', 'DEST:', 'ALTN:', 'SECY']):
            # 길이가 긴 경우 더 엄격한 체크
            if len(cleaned_text) > 400:
                self.logger.debug(f"긴 비NOTAM 섹션 감지하여 건너뛰기: {cleaned_text[:100]}...")
                return {}
        
        # 공항 정보 섹션 체크 (특별한 패턴들)
        airport_info_patterns = [
            r'^\d+\. RUNWAY',  # "1. RUNWAY :"
            r'^\d+\. COMPANY RADIO',  # "2. COMPANY RADIO :"
            r'TAKEOFF PERFORMANCE INFORMATION',
            r'NOTAM A\d{4}/\d{2}.*NO IMPACT',  # 성능 정보 관련
            r'CHECK RWY ID FOR TODC REQUEST',
            r'COMPANY MINIMA FOR CAT II/III',  # 추가 패턴
            r'131\.500.*KOREAN AIR INCHEON',  # 주파수 정보
            r'129\.35.*ASIANA INCHEON'  # 추가 주파수 정보
        ]
        
        if any(re.search(pattern, cleaned_text, re.IGNORECASE) for pattern in airport_info_patterns):
            if len(cleaned_text) > 500:  # 매우 긴 공항 정보 섹션
                self.logger.debug(f"긴 공항 정보 섹션 감지하여 건너뛰기: {cleaned_text[:100]}...")
                return {}
        
        # 추가 체크: 공항 정보로 보이는 특별한 패턴들
        # 단, NOTAM 번호가 있는 경우에는 진짜 NOTAM일 가능성이 높으므로 관대하게 처리
        has_notam_number = re.search(r'\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*(?:\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}|UFN)\s+[A-Z]{4}\s+[A-Z0-9]+/\d{2}', cleaned_text)
        if cleaned_text.count('RWY') > 3 or cleaned_text.count('CAT') > 2:
            if len(cleaned_text) > 800:  # 매우 긴 경로 정보나 성능 정보
                # NOTAM 번호가 있는 경우에는 건너뛰지 않음
                if not has_notam_number:
                    self.logger.debug(f"매우 긴 공항 성능 정보 감지하여 건너뛰기: {cleaned_text[:100]}...")
                    return {}
                else:
                    self.logger.debug(f"NOTAM 번호가 있으므로 길이 제한 예외 적용: {cleaned_text[:100]}...")

        # ICAO 공항 코드 추출 (더 유연한 패턴)
        # 예: 28JUN25 00:00 - 25SEP25 23:59 LOWW A1483/25
        # 예: 19SEP25 08:46 - UFN LOWW A2268/25
        # 예: 24MAR23 16:00 - UFN RKRR CHINA SUP 16/21
        # 예: 1. 20FEB25 00:00 - UFN RKSI COAD01/25
        # '공항코드 (AIP SUP) NOTAM번호' 형식도 인식하도록 정규식 보완
        airport_match = re.search(r'(?:\d+\.\s+)?\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*(?:\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}|UFN)\s+([A-Z]{4})(?:\s+(?:AIP\s+SUP|CHINA\s+SUP|COAD))?\s+[A-Z0-9]+/\d{2}', cleaned_text)
        if airport_match:
            parsed_notam['airport_code'] = airport_match.group(1)
        else:
            # 보완 패턴: 더 일반적인 4자리 공항 코드 패턴 (AIP SUP, CHINA SUP, COAD 포함)
            airport_fallback = re.search(r'\b([A-Z]{4})(?:\s+(?:AIP\s+SUP|CHINA\s+SUP|COAD))?\s+[A-Z0-9]+/\d{2}', cleaned_text)
            if airport_fallback:
                parsed_notam['airport_code'] = airport_fallback.group(1)
            else:
                # COAD 패턴 직접 매칭
                coad_airport_match = re.search(r'([A-Z]{4})\s+COAD\d{2}/\d{2}', cleaned_text)
                if coad_airport_match:
                    parsed_notam['airport_code'] = coad_airport_match.group(1)
                else:
                    # 실제 COAD NOTAM인지 확인 (시간 정보가 있는지 체크)
                    has_time_pattern = re.search(r'\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*(?:\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}|UFN)', cleaned_text)
                    # COAD가 포함되어 있지만 시간 정보가 없는 경우는 fake일 가능성이 높음
                    # 하지만 너무 엄격하지 않게 수정 (길이 제한을 더 크게)
                    if 'coad' in cleaned_text.lower() and not has_time_pattern and len(cleaned_text) > 800:
                        self.logger.debug(f"시간 정보 없는 매우 긴 COAD 섹션 건너뛰기: {cleaned_text[:100]}...")
                        return {}
                    # E) 형식 NOTAM (공항 이름에서 추출)
                    if cleaned_text.strip().startswith('E)'):
                        # HONG KONG -> VHHH, 등 매핑 
                        if 'HONG KONG' in cleaned_text.upper():
                            parsed_notam['airport_code'] = 'VHHH'
                        elif 'INCHEON' in cleaned_text.upper():
                            parsed_notam['airport_code'] = 'RKSI'
                        elif 'GIMPO' in cleaned_text.upper():
                            parsed_notam['airport_code'] = 'RKSS'
                        else:
                            # 기본값 설정
                            parsed_notam['airport_code'] = 'UNKNOWN'
        
        # NOTAM 번호 추출 (AIP SUP, CHINA SUP, COAD 등 다양한 형식 지원)
        notam_number_match = re.search(r'(?:\d+\.\s+)?\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*(?:\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}|UFN)\s+[A-Z]{4}(?:\s+(?:AIP\s+SUP|CHINA\s+SUP|COAD))?\s+([A-Z0-9]+/\d{2})', cleaned_text)
        if notam_number_match:
            # AIP SUP나 CHINA SUP가 있으면 전체를 붙여서 사용
            aip_sup_match = re.search(r'(?:\d+\.\s+)?\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*(?:\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}|UFN)\s+[A-Z]{4}\s+(AIP\s+SUP|CHINA\s+SUP|COAD)\s+([A-Z0-9]+/\d{2})', cleaned_text)
            if aip_sup_match:
                parsed_notam['notam_number'] = f"{aip_sup_match.group(1)} {aip_sup_match.group(2)}"
            else:
                parsed_notam['notam_number'] = notam_number_match.group(1)
        else:
            # 보완 패턴: AIP SUP, CHINA SUP, COAD 포함 일반적인 NOTAM 번호 패턴
            notam_fallback = re.search(r'(AIP\s+SUP|CHINA\s+SUP|COAD)\s+([A-Z0-9]+/\d{2})', cleaned_text)
            if notam_fallback:
                parsed_notam['notam_number'] = f"{notam_fallback.group(1)} {notam_fallback.group(2)}"
            else:
                # COAD 패턴 직접 매칭
                coad_match = re.search(r'([A-Z]{4})\s+COAD(\d{2}/\d{2})', cleaned_text)
                if coad_match:
                    parsed_notam['notam_number'] = f"COAD{coad_match.group(2)}"
                else:
                    # 기존 패턴도 시도
                    notam_fallback2 = re.search(r'\b([A-Z]\d{4}/\d{2})\b', cleaned_text)
                    if notam_fallback2:
                        parsed_notam['notam_number'] = notam_fallback2.group(1)
        
        # 시간 정보 파싱
        self._parse_time_info(cleaned_text, parsed_notam)
        
        # D) 필드 추출 (시간대 정보) - 원본 텍스트에서 추출
        lines = cleaned_text.split('\n')
        for i, line in enumerate(lines):
            if line.strip().startswith('D)'):
                d_content = []
                # D) 다음 줄들도 포함
                for j in range(i, len(lines)):
                    if j == i:
                        d_content.append(lines[j].strip()[2:].strip())  # D) 제거
                    elif lines[j].strip() and not lines[j].strip().startswith(('E)', 'F)', 'G)')):
                        d_content.append(lines[j].strip())
                    else:
                        break
                if d_content:
                    parsed_notam['d_field'] = '\n'.join(d_content)
                break
        
        
        # E) 필드 추출 - 더 유연한 종료 조건 사용
        e_field_match = re.search(r'E\)\s*(.+?)(?=(?:\n|^)\s*={20,}\s*$|(?:\n|^)\s*\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*(?:\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}|UFN)\s+[A-Z]{4}|(?:\n|^)\s*=+\s*$|(?:\n|^)={20,}(?:\n|$)|$)', cleaned_text, re.DOTALL)
        if e_field_match:
            e_field = e_field_match.group(1).strip()
            # NO CURRENT NOTAMS FOUND 이후의 내용 제거
            e_field = re.sub(r'\*{8}\s*NO CURRENT NOTAMS FOUND\s*\*{8}.*$', '', e_field, flags=re.DOTALL | re.IGNORECASE).strip()
            # E) 필드에 색상 스타일 적용
            e_field = apply_color_styles(e_field)
            parsed_notam['e_field'] = e_field
        
        return parsed_notam
    
    def _parse_time_info(self, notam_text, parsed_notam):
        """시간 정보 파싱 (UFN 지원 포함)"""
        
        # 1. UFN (Until Further Notice) 패턴 먼저 확인 (번호 포함) - Package 3 NOTAM 형식 지원
        ufn_pattern = r'(?:\d+\.\s+)?(\d{2}[A-Z]{3}\d{2}) (\d{2}:\d{2}) - UFN(?:\s+[A-Z]{4}(?:\s+[A-Z\s]+/\d{2})?)?'
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
        
        # 2. WEF/TIL 패턴 (번호 포함) - Package 3 NOTAM 형식 지원
        wef_til_pattern = r'(?:\d+\.\s+)?(\d{2}[A-Z]{3}\d{2}) (\d{2}:\d{2}) - (\d{2}[A-Z]{3}\d{2}) (\d{2}:\d{2})(?:\s+[A-Z]{4}(?:\s+[A-Z0-9]+/\d{2})?)?'
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
            
            # D) 필드가 있으면 시간대 정보 추가
            if parsed_notam and parsed_notam.get('d_field'):
                d_field = parsed_notam['d_field'].strip()
                # D) 필드의 시간 정보를 로컬 시간으로 변환
                local_d_field = self._convert_d_field_to_local_time(d_field, timezone_offset)
                local_time_str += f" / 시간대: {local_d_field}({timezone_offset})"
            
            return local_time_str
            
        except Exception as e:
            print(f"로컬 시간 변환 오류: {e}")
            return None
    
    def format_notam_time_with_local(self, effective_time, expiry_time, airport_code, parsed_notam=None):
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
            
            # D) 필드가 있으면 시간대 정보 추가
            if parsed_notam and parsed_notam.get('d_field'):
                d_field = parsed_notam['d_field'].strip()
                # D) 필드의 시간 정보를 로컬 시간으로 변환
                local_d_field = self._convert_d_field_to_local_time(d_field, timezone_offset)
                local_time_str += f" / 시간대: {local_d_field}({timezone_offset})"
            
            return local_time_str
            
        except Exception as e:
            print(f"시간 포맷팅 오류: {e}")
            return None
    
    def _convert_d_field_to_local_time(self, d_field, timezone_offset):
        """D) 필드의 시간을 로컬 시간으로 변환"""
        try:
            import re
            from datetime import datetime, timedelta
            
            # 타임존 오프셋 파싱 (+07:00 형식)
            offset_sign = 1 if timezone_offset.startswith('+') else -1
            offset_hours = int(timezone_offset[1:3])
            offset_minutes = int(timezone_offset[4:6])
            offset_delta = timedelta(hours=offset_hours * offset_sign, minutes=offset_minutes * offset_sign)
            
            lines = d_field.split('\n')
            converted_lines = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 날짜와 시간 패턴 매칭 (예: "05 1900-1930", "06-29 1900-2300")
                # 단일 날짜 패턴: DD HHMM-HHMM
                single_date_match = re.match(r'^(\d{1,2})\s+(\d{4})-(\d{4})$', line)
                if single_date_match:
                    day = int(single_date_match.group(1))
                    start_time = single_date_match.group(2)
                    end_time = single_date_match.group(3)
                    
                    # UTC 시간을 datetime으로 변환 (2025년 9월 기준)
                    utc_start = datetime(2025, 9, day, int(start_time[:2]), int(start_time[2:]))
                    utc_end = datetime(2025, 9, day, int(end_time[:2]), int(end_time[2:]))
                    
                    # 로컬 시간으로 변환
                    local_start = utc_start + offset_delta
                    local_end = utc_end + offset_delta
                    
                    # 날짜가 바뀌는 경우 처리
                    if local_start.day != day:
                        day_str = f"{local_start.day:02d}"
                    else:
                        day_str = f"{day:02d}"
                    
                    converted_line = f"{day_str} {local_start.strftime('%H%M')}-{local_end.strftime('%H%M')}"
                    converted_lines.append(converted_line)
                    continue
                
                # 날짜 범위 패턴: DD-DD HHMM-HHMM
                date_range_match = re.match(r'^(\d{1,2})-(\d{1,2})\s+(\d{4})-(\d{4})$', line)
                if date_range_match:
                    start_day = int(date_range_match.group(1))
                    end_day = int(date_range_match.group(2))
                    start_time = date_range_match.group(3)
                    end_time = date_range_match.group(4)
                    
                    # UTC 시간을 datetime으로 변환
                    utc_start = datetime(2025, 9, start_day, int(start_time[:2]), int(start_time[2:]))
                    utc_end = datetime(2025, 9, end_day, int(end_time[:2]), int(end_time[2:]))
                    
                    # 로컬 시간으로 변환
                    local_start = utc_start + offset_delta
                    local_end = utc_end + offset_delta
                    
                    # 날짜 범위 문자열 생성
                    if local_start.day != start_day or local_end.day != end_day:
                        converted_line = f"{local_start.day:02d}-{local_end.day:02d} {local_start.strftime('%H%M')}-{local_end.strftime('%H%M')}"
                    else:
                        converted_line = f"{start_day:02d}-{end_day:02d} {local_start.strftime('%H%M')}-{local_end.strftime('%H%M')}"
                    
                    converted_lines.append(converted_line)
                    continue
                
                # 변환할 수 없는 패턴은 그대로 유지
                converted_lines.append(line)
            
            return '\n'.join(converted_lines)
            
        except Exception as e:
            print(f"D) 필드 시간 변환 오류: {e}")
            return d_field  # 오류 시 원본 반환

    def _detect_notam_type(self, text):
        """텍스트에서 NOTAM 유형을 감지 (package or airport)"""
        if 'KOREAN AIR NOTAM PACKAGE' in text.upper():
            return 'package'
        return 'airport'

    def filter_korean_air_notams(self, text):
        """한국 항공사 노선 관련 모든 공항 NOTAM 처리 (패키지/개별 공항 자동 감지)"""
        import re
        
        # NOTAM 유형 감지
        notam_type = self._detect_notam_type(text)
        self.logger.info(f"NOTAM 유형 감지: {notam_type}")
        
        if notam_type == 'package':
            return self._filter_package_notams(text)
        else:
            return self._filter_airport_notams(text)

    def _filter_airport_notams(self, text):
        """공항 NOTAM 필터링 (기존 로직)"""
        import re
        
        # 더 유연한 NOTAM 시작 패턴 (다양한 형식 지원, SECY 제외, 번호 포함)
        notam_start_patterns = [
            r'^(?:\d+\.\s+)?\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*(?:\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}|UFN|PERM)\s+[A-Z]{4}(?!\s+SECY)',  # 번호 포함 패턴 (SECY 제외)
            r'^\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*(?:\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}|UFN|PERM)\s+[A-Z]{4}(?!\s+SECY)',  # 기존 패턴 (SECY 제외)
            r'^(?:\d+\.\s+)?\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*(?:\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}|UFN|PERM)\s+[A-Z]{4}\s+(?!SECY)[A-Z0-9]+/\d{2}',  # 번호 포함 NOTAM 번호 패턴 (SECY 제외)
            r'^\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*(?:\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}|UFN|PERM)\s+[A-Z]{4}\s+(?!SECY)[A-Z0-9]+/\d{2}',  # NOTAM 번호 포함 (SECY 제외)
            r'^(?:\d+\.\s+)?\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*(?:\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}|UFN|PERM)\s+[A-Z]{4}\s+AIP\s+SUP\s+\d{2}/\d{2}',  # 번호 포함 AIP SUP 형식
            r'^\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*(?:\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}|UFN|PERM)\s+[A-Z]{4}\s+AIP\s+SUP\s+\d{2}/\d{2}',  # AIP SUP 형식
            r'^[A-Z]{4}\s+COAD\d{2}/\d{2}$',  # VVCR COAD01/25 형식
        ]
        section_end_patterns = [
            r'^\[ALTN\]', r'^\[DEST\]', r'^\[ENRT\]', r'^\[ETC\]', r'^\[INFO\]', r'^\[ROUTE\]', r'^\[WX\]',
            r'^COAD',
            r'^[A-Z]{4} COAD\d{2}/\d{2}',
            r'^[A-Z]{4}\s*$',  # 공항코드만 단독 등장
            r'^1\.\s+RUNWAY\s*:',  # "1. RUNWAY :" 패턴 추가
            r'^={4,}$'  # 4개 이상의 등호로만 구성된 줄 (NOTAM 구분선)
        ]
        
        # 기존 공항 NOTAM 필터링 로직
        lines = text.split('\n')
        notam_sections = []
        current_notam = []
        found_first_notam = False
        skip_mode = False
        
        for line in lines:
            # skip_mode가 True일 때는 새로운 NOTAM 시작 패턴만 처리하고 나머지는 모두 건너뛰기
            if skip_mode:
                # 여러 패턴 시도
                if any(re.match(pattern, line) for pattern in notam_start_patterns):
                    found_first_notam = True
                    skip_mode = False
                    if current_notam:
                        notam_sections.append('\n'.join(current_notam).strip())
                        current_notam = []
                    current_notam.append(line)
                    self.logger.debug(f"새로운 NOTAM 시작으로 skip_mode 해제: {line.strip()[:50]}...")
                # skip_mode가 True면 어떤 줄도 current_notam에 추가하지 않음
                continue
            
            # END OF KOREAN AIR NOTAM PACKAGE 처리 - 현재 NOTAM을 종료하고 END OF KOREAN AIR NOTAM PACKAGE 이후 모든 내용 건너뛰기
            if re.search(r'END OF KOREAN AIR NOTAM PACKAGE', line.strip(), re.IGNORECASE):
                if current_notam:
                    notam_sections.append('\n'.join(current_notam).strip())
                    self.logger.debug(f"END OF KOREAN AIR NOTAM PACKAGE로 NOTAM 종료: {len(current_notam)}줄")
                    current_notam = []
                # END OF KOREAN AIR NOTAM PACKAGE 이후 모든 내용을 건너뛰기 위해 skip_mode 활성화
                skip_mode = True
                self.logger.debug(f"END OF KOREAN AIR NOTAM PACKAGE 이후 건너뛰기 시작")
                # END OF KOREAN AIR NOTAM PACKAGE 라인 자체도 current_notam에 추가하지 않음
                continue
                
            # NO CURRENT NOTAMS FOUND 처리 - 현재 NOTAM을 종료하고 이후 모든 내용 건너뛰기
            if re.search(r'\*{8}\s*NO CURRENT NOTAMS FOUND\s*\*{8}', line.strip(), re.IGNORECASE):
                if current_notam:
                    notam_sections.append('\n'.join(current_notam).strip())
                    self.logger.debug(f"NO CURRENT NOTAMS FOUND로 NOTAM 종료: {len(current_notam)}줄")
                    current_notam = []
                # NO CURRENT NOTAMS FOUND 이후 모든 내용을 건너뛰기 위해 skip_mode 활성화
                skip_mode = True
                self.logger.debug(f"NO CURRENT NOTAMS FOUND 이후 건너뛰기 시작")
                # NO CURRENT NOTAMS FOUND 라인 자체도 current_notam에 추가하지 않음
                continue
                
            # SECY 관련 패턴 완전 제외
            if (re.search(r'SECY\s*/\s*SECURITY INFORMATION', line.strip(), re.IGNORECASE) or
                re.search(r'SECY\s+COAD\d+/\d+', line.strip(), re.IGNORECASE) or
                re.search(r'\d+\.\s+\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s+SECY', line.strip(), re.IGNORECASE)):
                # SECY 섹션 전체를 건너뛰기 위해 skip_mode 활성화
                skip_mode = True
                self.logger.debug(f"SECY 관련 패턴 건너뛰기 시작: {line.strip()}")
                continue
                
            # COMPANY ADVISORY 섹션 완전 제외 - 모든 COMPANY ADVISORY 관련 내용 건너뛰기
            if re.search(r'COMPANY ADVISORY|MPANY ADVISORY', line.strip(), re.IGNORECASE):
                # COMPANY ADVISORY 섹션 전체를 건너뛰기 위해 skip_mode 활성화
                skip_mode = True
                self.logger.debug(f"COMPANY ADVISORY 섹션 건너뛰기 시작: {line.strip()}")
                continue
                
            # SECY 섹션 내 개별 항목들도 건너뛰기 (1., 2., 3. 등)
            if re.search(r'^\d+\.\s+\d{2}[A-Z]{3}\d{2}', line.strip()) and skip_mode:
                self.logger.debug(f"SECY/COMPANY ADVISORY 항목 건너뛰기: {line.strip()[:50]}...")
                continue
                
            # COMPANY ADVISORY 항목 종료 패턴에서 skip_mode 해제
            if re.search(r'--\s+BY\s+[A-Z]+--', line.strip()) and skip_mode:
                self.logger.debug(f"COMPANY ADVISORY 섹션 건너뛰기 종료")
                skip_mode = False
                continue
                
            # COMPANY ADVISORY 섹션에서 새로운 NOTAM이 시작되면 skip_mode 해제
            # 여러 패턴 시도하여 NOTAM 시작 확인
            notam_start_found = any(re.match(pattern, line) for pattern in notam_start_patterns)
            
            if notam_start_found and skip_mode:
                self.logger.debug(f"새로운 NOTAM 시작으로 COMPANY ADVISORY skip_mode 해제")
                skip_mode = False
                found_first_notam = True
                if current_notam:
                    notam_sections.append('\n'.join(current_notam).strip())
                    current_notam = []
                current_notam.append(line)
                continue
                
            if notam_start_found:
                found_first_notam = True
                skip_mode = False
                if current_notam:
                    notam_sections.append('\n'.join(current_notam).strip())
                    self.logger.debug(f"새 NOTAM 시작으로 이전 NOTAM 종료: {len(current_notam)}줄")
                    current_notam = []
                current_notam.append(line)
                self.logger.debug(f"새 NOTAM 시작: {line.strip()[:50]}...")
            elif any(re.match(pat, line) for pat in section_end_patterns):
                if current_notam:
                    notam_sections.append('\n'.join(current_notam).strip())
                    current_notam = []
                skip_mode = True
            elif found_first_notam:
                current_notam.append(line)
                
        if current_notam:
            notam_sections.append('\n'.join(current_notam).strip())

        filtered_notams = []
        self.logger.info(f"총 {len(notam_sections)}개의 NOTAM 섹션으로 분할됨")

        for i, section in enumerate(notam_sections):
            section = section.strip()
            if not section:
                continue

            # NOTAM 파싱
            parsed_notam = self._parse_notam_section(section)

            self.logger.debug(f"섹션 {i+1}: 공항코드={parsed_notam.get('airport_code')}, NOTAM번호={parsed_notam.get('notam_number')}")

            # 공항 코드가 있는 모든 NOTAM 처리 (한국 공항이 아니어도 포함)
            if parsed_notam.get('airport_code'):
                # 기본 정보 설정
                # COAD NOTAM의 경우 E) 필드가 없으므로 전체 섹션을 description으로 사용
                description = parsed_notam.get('e_field') or section
                
                # E 섹션만 원문으로 사용 (D 섹션 제외)
                e_field_content = extract_e_section(section)
                if not e_field_content:
                    # E 섹션 추출 실패 시 parsed_notam의 e_field 사용
                    e_field_content = parsed_notam.get('e_field', '')
                    if not e_field_content:
                        e_field_content = description  # 그래도 없으면 description 사용
                
                # 원문에도 색상 스타일 적용
                styled_section = apply_color_styles(e_field_content)
                
                # NOTAM 카테고리 분석
                category = analyze_notam_category(e_field_content, parsed_notam.get('q_code'))
                category_info = NOTAM_CATEGORIES.get(category, {
                    'icon': '📄',
                    'color': '#6c757d',
                    'bg_color': '#e9ecef'
                })
                
                notam_dict = {
                    'id': parsed_notam.get('notam_number', 'Unknown'),
                    'notam_number': parsed_notam.get('notam_number', 'Unknown'),
                    'airport_code': parsed_notam.get('airport_code'),
                    'effective_time': parsed_notam.get('effective_time', ''),
                    'expiry_time': parsed_notam.get('expiry_time', ''),
                    'description': description,
                    'original_text': styled_section,
                    'd_field': parsed_notam.get('d_field', ''),
                    'e_field': parsed_notam.get('e_field', ''),
                    'category': category,
                    'category_icon': category_info['icon'],
                    'category_color': category_info['color'],
                    'category_bg_color': category_info['bg_color']
                }

                # UFN을 포함한 모든 시간 정보에 대해 local_time_display 생성
                if parsed_notam.get('effective_time') and (parsed_notam.get('expiry_time') or parsed_notam.get('expiry_time') == 'UFN'):
                    local_time_display = self._generate_local_time_display(parsed_notam)
                    if local_time_display:
                        notam_dict['local_time_display'] = local_time_display
                        # 원본 텍스트에는 로컬 시간 추가하지 않음 (별도 필드로 관리)

                filtered_notams.append(notam_dict)
            else:
                self.logger.warning(f"섹션 {i+1}: 공항 코드를 찾을 수 없음 (섹션 시작: {section[:100]}...)")

        self.logger.info(f"최종 {len(filtered_notams)}개의 NOTAM 추출 완료")
        return filtered_notams
    
    def _extract_content_after_notam_number(self, text, notam_number):
        """NOTAM 번호 이후의 내용만 추출합니다."""
        self.logger.info(f"🔍 원문 추출 시작 - NOTAM: {notam_number}")
        self.logger.info(f"📝 원본 텍스트 길이: {len(text)}")
        
        if not notam_number:
            self.logger.warning("⚠️ NOTAM 번호가 없어서 원본 텍스트 반환")
            return text
        
        # NOTAM 번호를 찾아서 그 이후의 내용을 추출
        # 다양한 패턴으로 NOTAM 번호를 찾습니다
        patterns = [
            # COAD 패턴: RKSI COAD01/25
            rf'([A-Z]{{4}}\s+)?{re.escape(notam_number)}',
            # AIP SUP 패턴: AIP SUP 20/25
            rf'(AIP\s+SUP\s+)?{re.escape(notam_number)}',
            # 일반 패턴: A1234/25
            rf'\b{re.escape(notam_number)}\b'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # NOTAM 번호 이후의 내용 추출
                after_notam = text[match.end():].strip()
                
                # // 로 시작하는 경우 // 제거
                if after_notam.startswith('//'):
                    after_notam = after_notam[2:].strip()
                
                # -- BY로 끝나는 경우 그 이후 제거
                by_match = re.search(r'--\s*BY\s+[A-Z]+--', after_notam)
                if by_match:
                    after_notam = after_notam[:by_match.start()].strip()
                
                self.logger.info(f"✅ 첫 번째 패턴으로 추출 성공: {len(after_notam)}자")
                return after_notam
        
        # 패턴을 찾지 못한 경우, 더 간단한 방법으로 시도
        # NOTAM 번호만으로 직접 찾기
        simple_patterns = [
            rf'{re.escape(notam_number)}\s*//',  # COAD01/25 //
            rf'{re.escape(notam_number)}\s+//',  # COAD01/25 //
            rf'{re.escape(notam_number)}\s*$',   # 줄 끝에 있는 경우
        ]
        
        for pattern in simple_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                after_notam = text[match.end():].strip()
                if after_notam.startswith('//'):
                    after_notam = after_notam[2:].strip()
                
                by_match = re.search(r'--\s*BY\s+[A-Z]+--', after_notam)
                if by_match:
                    after_notam = after_notam[:by_match.start()].strip()
                
                self.logger.info(f"✅ 간단한 패턴으로 추출 성공: {len(after_notam)}자")
                return after_notam
        
        # 모든 패턴을 찾지 못한 경우 원본 텍스트 반환
        self.logger.warning(f"❌ 패턴을 찾지 못해서 원본 텍스트 반환")
        return text

    def _filter_package_notams(self, text):
        """패키지 NOTAM 필터링 (pdf_to_txt_test_package.py 기반)"""
        import re
        
        # 패키지 NOTAM의 복잡한 구조를 처리하기 위한 로직
        # 먼저 라인 병합 처리
        merged_text = self._merge_package_notam_lines(text)
        
        # NOTAM 분리
        notam_sections = self._split_package_notams(merged_text)
        
        filtered_notams = []
        self.logger.info(f"패키지 NOTAM 총 {len(notam_sections)}개의 섹션으로 분할됨")

        for i, section in enumerate(notam_sections):
            section = section.strip()
            if not section:
                continue

            # NOTAM 파싱
            parsed_notam = self._parse_notam_section(section)

            self.logger.debug(f"패키지 섹션 {i+1}: 공항코드={parsed_notam.get('airport_code')}, NOTAM번호={parsed_notam.get('notam_number')}")

            # 공항 코드가 있는 모든 NOTAM 처리
            if parsed_notam.get('airport_code'):
                # 기본 정보 설정
                # 원문에서 NOTAM 번호 이후의 내용만 추출
                original_content = self._extract_content_after_notam_number(section, parsed_notam.get('notam_number', ''))
                self.logger.debug(f"원문 추출 - NOTAM: {parsed_notam.get('notam_number')}, 원본 길이: {len(section)}, 추출된 길이: {len(original_content)}")
                styled_original = apply_color_styles(original_content)
                
                # NOTAM 카테고리 분석
                category = analyze_notam_category(original_content, parsed_notam.get('q_code'))
                category_info = NOTAM_CATEGORIES.get(category, {
                    'icon': '📄',
                    'color': '#6c757d',
                    'bg_color': '#e9ecef'
                })
                
                notam_dict = {
                    'id': parsed_notam.get('notam_number', 'Unknown'),
                    'notam_number': parsed_notam.get('notam_number', 'Unknown'),
                    'airport_code': parsed_notam.get('airport_code'),
                    'effective_time': parsed_notam.get('effective_time', ''),
                    'expiry_time': parsed_notam.get('expiry_time', ''),
                    'description': parsed_notam.get('e_field', section),
                    'original_text': styled_original,
                    'd_field': parsed_notam.get('d_field', ''),
                    'category': category,
                    'category_icon': category_info['icon'],
                    'category_color': category_info['color'],
                    'category_bg_color': category_info['bg_color']
                }

                # UFN을 포함한 모든 시간 정보에 대해 local_time_display 생성
                if parsed_notam.get('effective_time') and (parsed_notam.get('expiry_time') or parsed_notam.get('expiry_time') == 'UFN'):
                    local_time_display = self._generate_local_time_display(parsed_notam)
                    if local_time_display:
                        notam_dict['local_time_display'] = local_time_display
                        # 원본 텍스트에는 로컬 시간 추가하지 않음 (별도 필드로 관리)

                filtered_notams.append(notam_dict)
            else:
                self.logger.warning(f"패키지 섹션 {i+1}: 공항 코드를 찾을 수 없음 (섹션 시작: {section[:100]}...)")

        # 패키지 타입 감지 및 공항 순서 정렬
        package_type = self._detect_package_type(text)
        if package_type:
            self.logger.info(f"패키지 타입 감지: {package_type}")
            # 공항 순서에 따라 정렬
            filtered_notams.sort(key=lambda x: self._get_airport_priority(x.get('airport_code', ''), package_type))
            self.logger.info(f"패키지별 공항 순서로 정렬 완료: {package_type}")
            
            # 정렬 후 순서 로깅
            self.logger.info("=== 패키지별 공항 순서로 정렬된 NOTAM ===")
            for i, notam in enumerate(filtered_notams[:10], 1):  # 첫 10개만 로깅
                airport = notam.get('airport_code', 'N/A')
                notam_num = notam.get('notam_number', 'N/A')
                priority = self._get_airport_priority(airport, package_type)
                self.logger.info(f"정렬 후 {i}: {airport} {notam_num} (우선순위: {priority})")
        else:
            self.logger.warning("패키지 타입을 감지할 수 없음 - 원본 순서 유지")
        
        self.logger.info(f"패키지 NOTAM 최종 {len(filtered_notams)}개의 NOTAM 추출 완료")
        return filtered_notams

    def extract_package_airports(self, text, all_airports):
        """PDF 텍스트에서 Package별 공항 정보를 추출하고 순서를 동적으로 설정"""
        import re
        
        package_airports = {}
        
        # Package 1 정보 추출 - DEP, DEST, ALTN 라인에서 공항 코드 추출
        package1_airports = []
        
        # DEP 라인에서 공항 코드 추출
        dep_match = re.search(r'DEP:\s*([A-Z]{4})', text)
        if dep_match:
            package1_airports.append(dep_match.group(1))
        
        # DEST 라인에서 공항 코드 추출
        dest_match = re.search(r'DEST:\s*([A-Z]{4})', text)
        if dest_match:
            package1_airports.append(dest_match.group(1))
        
        # ALTN 라인에서 공항 코드 추출 (여러 개 가능)
        altn_match = re.search(r'ALTN:\s*([A-Z\s]+?)(?=\n|$)', text)
        if altn_match:
            altn_airports = re.findall(r'[A-Z]{4}', altn_match.group(1))
            package1_airports.extend(altn_airports)
        
        # 실제 존재하는 공항만 필터링 (추출한 순서 유지)
        existing_package1 = [airport for airport in package1_airports if airport in all_airports]
        
        # Package 1 정의상 포함되어야 하는 공항들 중 누락된 것 추가 (순서 유지)
        expected_package1 = ['RKSI', 'VVDN', 'VVCR']
        for airport in expected_package1:
            if airport in package1_airports and airport not in existing_package1:
                existing_package1.append(airport)
                
        if existing_package1:
            package_airports['package1'] = existing_package1
            # 동적으로 추출된 순서로 package_airport_order 업데이트
            self.package_airport_order['package1'] = existing_package1
        
        # Package 2 정보 추출 - 다양한 ERA 패턴에서 공항 코드 추출
        package2_airports = []
        
        # 다양한 ERA 패턴들 처리 (3% ERA, 5% ERA, ERA 등)
        era_patterns = [
            r'\d+%\s*ERA:\s*([A-Z\s]+?)(?=\n[A-Z]{2,}:\s*|\n=+|\n\[|$)',  # 3% ERA, 5% ERA 등
            r'ERA:\s*([A-Z\s]+?)(?=\n[A-Z]{2,}:\s*|\n=+|\n\[|$)'  # 일반 ERA
        ]
        
        for pattern in era_patterns:
            era_matches = re.findall(pattern, text, re.DOTALL)
            for era_match in era_matches:
                era_airports = re.findall(r'[A-Z]{4}', era_match)
                package2_airports.extend(era_airports)
        
        # REFILE 라인에서 공항 코드 추출 (있는 경우)
        refile_match = re.search(r'REFILE:\s*([A-Z\s]+?)(?=\n[A-Z]{2,}:\s*|\n=+|\n\[|$)', text, re.DOTALL)
        if refile_match:
            refile_airports = re.findall(r'[A-Z]{4}', refile_match.group(1))
            package2_airports.extend(refile_airports)
        
        # EDTO 라인에서 공항 코드 추출 (있는 경우)
        edto_match = re.search(r'EDTO:\s*([A-Z\s]+?)(?=\n[A-Z]{2,}:\s*|\n=+|\n\[|$)', text, re.DOTALL)
        if edto_match:
            edto_airports = re.findall(r'[A-Z]{4}', edto_match.group(1))
            package2_airports.extend(edto_airports)
        
        # 중복 제거 및 실제 존재하는 공항만 필터링 (추출한 순서 유지)
        package2_airports = list(set(package2_airports))
        existing_package2 = [airport for airport in package2_airports if airport in all_airports]
        if existing_package2:
            package_airports['package2'] = existing_package2
            # 동적으로 추출된 순서로 package_airport_order 업데이트
            self.package_airport_order['package2'] = existing_package2
        
        # Package 3 정보 추출 - FIR 라인에서 공항 코드 추출
        package3_airports = []
        
        # FIR 라인에서 공항 코드 추출
        fir_match = re.search(r'FIR:\s*([A-Z\s]+?)(?=\n[A-Z]{2,}:\s*|\n=+|\n\[|$)', text, re.DOTALL)
        if fir_match:
            fir_airports = re.findall(r'[A-Z]{4}', fir_match.group(1))
            package3_airports.extend(fir_airports)
        
        # 실제 존재하는 공항만 필터링 (추출한 순서 유지)
        existing_package3 = [airport for airport in package3_airports if airport in all_airports]
        if existing_package3:
            package_airports['package3'] = existing_package3
            # 동적으로 추출된 순서로 package_airport_order 업데이트
            self.package_airport_order['package3'] = existing_package3
        
        self.logger.info(f"추출된 Package별 공항 (동적 순서): {package_airports}")
        self.logger.info(f"업데이트된 package_airport_order: {self.package_airport_order}")
        return package_airports

    def _merge_package_notam_lines(self, text):
        """패키지 NOTAM 라인 병합 (pdf_to_txt_test_package.py 기반)"""
        lines = text.split('\n')
        
        # 삭제할 키워드 목록 (OCR 오류 패턴 포함)
        unwanted_keywords = [
            'â—R¼A MP', 'â—O¼B STRUCTION', 'â—G¼P S', 'â—R¼U NWAY', 'â—A¼PP ROACH', 'â—T¼A XIWAY',
            'â—N¼A VAID', 'â—D¼E PARTURE', 'â—R¼U NWAY LIGHT', 'â—A¼IP', 'â—O¼T HER'
        ]
        
        # 불필요한 키워드가 포함된 줄 삭제
        filtered_lines = [line for line in lines if not any(keyword in line for keyword in unwanted_keywords)]
        
        merged_lines = []
        i = 0
        
        # 더 정확한 패턴들
        notam_id_pattern = r'^[A-Z]{4}(?:\s+[A-Z]+(?:\s+[A-Z]+)*)?\s+\d{1,3}/\d{2}$|^[A-Z]{4}\s+[A-Z]\d{4}/\d{2}$'
        coad_pattern = r'^[A-Z]{4}\s+COAD\d{2}/\d{2}$'  # COAD 패턴 추가
        date_line_pattern = r'^(?:\d+\.\s+)?\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-'  # "3. " 패턴 포함
        
        while i < len(filtered_lines):
            line = filtered_lines[i].strip()
            
            # COAD NOTAM ID 패턴 체크
            if re.match(coad_pattern, line):
                # 다음 줄이 날짜 패턴이면 합침
                if i + 1 < len(filtered_lines) and re.match(date_line_pattern, filtered_lines[i+1].strip()):
                    next_line = filtered_lines[i+1].strip()
                    # "3. " 같은 번호 접두사 제거
                    cleaned_date_line = re.sub(r'^\d+\.\s+', '', next_line)
                    merged_lines.append(f"{cleaned_date_line} {line}")
                    i += 2
                    continue
            
            # 일반 NOTAM ID 패턴 체크
            elif re.match(notam_id_pattern, line):
                # 다음 줄이 날짜 패턴이면 합침
                if i + 1 < len(filtered_lines) and re.match(date_line_pattern, filtered_lines[i+1].strip()):
                    next_line = filtered_lines[i+1].strip()
                    # "3. " 같은 번호 접두사 제거
                    cleaned_date_line = re.sub(r'^\d+\.\s+', '', next_line)
                    merged_lines.append(f"{cleaned_date_line} {line}")
                    i += 2
                    continue
            
            merged_lines.append(line)
            i += 1
            
        return '\n'.join(merged_lines)

    def _split_package_notams(self, text):
        """패키지 NOTAM들을 원본 텍스트 파일의 줄 순서로 분할"""
        # 줄번호와 함께 관리하여 원본 ORDER 유지
        lines_with_index = []
        for i, line in enumerate(text.split('\n'), 1):
            if line.strip():  # 빈 줄이 아닌 경우만
                lines_with_index.append((i, line.strip()))
        
        # 패턴 정의 - 더 정확한 NOTAM 시작 패턴들
        notam_start_pattern = r'^(?:\d+\.\s+)?\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-'
        section_start_pattern = r'^\[.*\]'
        notam_id_pattern = r'^[A-Z]{4}(?:\s+(?!COAD)[A-Z]+)?\s*\d{1,3}/\d{2}$|^[A-Z]{4}\s+[A-Z]\d{4}/\d{2}$'
        coad_pattern = r'^[A-Z]{4}\s+COAD\d{2}/\d{2}$'  # COAD NOTAM 패턴 추가
        aip_ad_pattern = r'^\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*(?:UFN|PERM)\s+[A-Z]{4}\s+AIP\s+AD\s+\d+\.\d+'  # AIP AD 패턴 추가
        
        # 새로운 NOTAM 시작을 감지하는 더 정확한 패턴들
        new_notam_patterns = [
            # COAD 패턴들 - 숫자 접두사가 있는 형식
            r'^\d+\.\s*\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*UFN\s+[A-Z]{4}\s+COAD\d{2}/\d{2}',  # UFN 형식
            r'^\d+\.\s*\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*PERM\s+[A-Z]{4}\s+COAD\d{2}/\d{2}',  # PERM 형식  
            r'^\d+\.\s*\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s+[A-Z]{4}\s+COAD\d{2}/\d{2}',  # 온전한 날짜 형식
            # 일반 NOTAM 패턴들
            r'^\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*(?:\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}|UFN|PERM)\s+[A-Z]{4}\s+[A-Z]\d{4}/\d{2}',  # 일반 NOTAM - UFN/PERM 추가
            r'^\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*(?:\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}|UFN|PERM)\s+[A-Z]{4}\s+AIP\s+SUP\s+\d+/\d{2}',  # AIP SUP
            r'^\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*(?:\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}|UFN|PERM)\s+[A-Z]{4}\s+AIP\s+AD\s+\d+\.\d+',  # AIP AD (예: AIP AD 2.9)
            r'^\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*(?:\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}|UFN|PERM)\s+[A-Z]{4}\s+Z\d{4}/\d{2}',  # Z NOTAM
            r'^\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*(?:\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}|UFN|PERM)\s+[A-Z]{4}\s+COAD\d{2}/\d{2}',  # COAD
            r'^\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*UFN\s+[A-Z]{4}\s+CHINA\s+SUP\s+\d+/\d{2}',  # CHINA SUP 패턴 추가
            r'^\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*(?:[A-Z]{3}\d{2}|UFN|PERM)\s+[A-Z]{4}\s+[A-Z]+\d+/\d{2}',  # 더 일반적인 패턴 추가
            r'^\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s+[A-Z]{4}\s+[A-Z]\d{4}/\d{2}',  # 연속 날짜 패턴
        ]
        
        end_phrase_pattern = r'ANY CHANGE WILL BE NOTIFIED BY NOTAM\.'
        
        # 섹션 종료 패턴들
        section_end_patterns = [
            r'^\[ALTN\]', r'^\[DEST\]', r'^\[ENRT\]', r'^\[ETC\]', r'^\[INFO\]', r'^\[ROUTE\]', r'^\[WX\]',
            r'^COAD',
            r'^[A-Z]{4} COAD\d{2}/\d{2}',
            r'^[A-Z]{4}\s*$',  # 공항코드만 단독 등장
            r'^1\.\s+RUNWAY\s*:',  # "1. RUNWAY :" 패턴 추가
            r'^={4,}$'  # 4개 이상의 등호로만 구성된 줄 (NOTAM 구분선)
        ]

        notams_with_index = []
        current_notam_lines = []
        
        for line_num, line in lines_with_index:
            # 구분선 감지 (먼저 체크) - = 구분선만 사용
            if re.match(r'^={20,}$', line):
                if current_notam_lines:
                    notams_with_index.append((current_notam_lines[0][0], '\n'.join([l[1] for l in current_notam_lines]).strip()))
                    current_notam_lines = []
                continue  # 구분선 라인은 다음 NOTAM에 포함하지 않음
            
            # 섹션 종료 패턴 감지 ([ALTN], "1. RUNWAY :" 등)
            if any(re.match(pattern, line.strip()) for pattern in section_end_patterns):
                if current_notam_lines:
                    notams_with_index.append((current_notam_lines[0][0], '\n'.join([l[1] for l in current_notam_lines]).strip()))
                    current_notam_lines = []
                continue  # 섹션 종료 라인은 다음 NOTAM에 포함하지 않음
            
            # 새로운 NOTAM 시작 감지 (더 정확한 패턴 사용)
            is_new_notam = False
            for pattern in new_notam_patterns:
                if re.match(pattern, line.strip()):
                    is_new_notam = True
                    break
            
            # AIP AD 패턴도 체크
            if not is_new_notam and re.match(aip_ad_pattern, line.strip()):
                is_new_notam = True
            
            if is_new_notam:
                # 현재 NOTAM이 있으면 저장하고 새로 시작
                if current_notam_lines:
                    notams_with_index.append((current_notam_lines[0][0], '\n'.join([l[1] for l in current_notam_lines]).strip()))
                current_notam_lines = [(line_num, line)]
            else:
                current_notam_lines.append((line_num, line))
                
            # 끝 문구 등장 시 강제 끊기
            if re.search(end_phrase_pattern, line):
                if current_notam_lines:
                    notams_with_index.append((current_notam_lines[0][0], '\n'.join([l[1] for l in current_notam_lines]).strip()))
                    current_notam_lines = []
                
        if current_notam_lines:
            notams_with_index.append((current_notam_lines[0][0], '\n'.join([l[1] for l in current_notam_lines]).strip()))
        
        # 줄번호 순으로 정렬하여 원본 텍스트 순서 엄격히 유지
        notams_with_index.sort(key=lambda x: x[0])
        
        # 로깅으로 순서 확인 (디버깅용)
        self.logger.info("=== 원본 텍스트 파일 순서로 NOTAM 정렬 ===")
        for i, (line_num, notam_text) in enumerate(notams_with_index[:10], 1):  # 첫 10개만 로깅
            coad_match = re.search(r'COAD\d+/\d+', notam_text)
            coad_number = coad_match.group(0) if coad_match else "N/A"
            notam_type = "RKSI" if "RKSI" in notam_text else ""
            self.logger.info(f"줄 {line_num}: NOTAM {i} -> {notam_type} {coad_number}")
            
        return [notam_text for _, notam_text in notams_with_index]