import os
import google.generativeai as genai
from dotenv import load_dotenv
import re
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

__all__ = ['apply_color_styles', 'RED_STYLE_TERMS', 'BLUE_STYLE_PATTERNS']