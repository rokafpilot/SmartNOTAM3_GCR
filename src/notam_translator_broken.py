"""
NOTAM Translation and Summary Module
NOTAM 텍스트를 한국어로 번역하고 요약하는 모듈
참조: SmartNOTAMgemini_GCR/notam_translator.py의 Gemini 기반 번역 구현
"""

import os
import logging
from typing import List, Dict, Optional
import json
import re
from datetime import datetime
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# Gemini API 시도
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from .constants import (
    NO_TRANSLATE_TERMS, 
    DEFAULT_ABBR_DICT, 
    RED_STYLE_TERMS, 
    BLUE_STYLE_PATTERNS,
    COLOR_STYLES,
    PRIORITY_KEYWORDS
)

class NOTAMTranslator:
    """NOTAM 번역 및 요약 클래스 (Gemini 기반)"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        
        # API 키 설정 - 환경변수 또는 매개변수에서 가져오기
        self.google_api_key = api_key or os.getenv('GOOGLE_API_KEY')
        
        # Gemini API 설정
        self.gemini_enabled = False
        if GEMINI_AVAILABLE and self.google_api_key:
            try:
                genai.configure(api_key=self.google_api_key)
                # 참조 파일과 동일한 모델 사용
                self.gemini_model = genai.GenerativeModel('gemini-2.5-flash-lite')
                self.gemini_enabled = True
                self.logger.info("Gemini API 초기화 완료")
            except Exception as e:
                self.logger.warning(f"Gemini API 초기화 실패: {str(e)}")
        
        # 항공 용어 사전 (참조 파일에서 가져온 용어들)
        self.aviation_terms = {
            'RUNWAY': '활주로',
            'TAXIWAY': '유도로', 
            'APRON': '계류장',
            'CLOSED': '폐쇄',
            'MAINTENANCE': '정비',
            'CONSTRUCTION': '공사',
        }
        
        # 색상 스타일링을 위한 용어 정의 (참조 프로젝트에서 가져옴)
        self.red_style_terms = [
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
            'GPS RAIM',
            'Non-Precision Approach', 'non-precision approach',
            '포장 공사', 'pavement construction',
        ]
        
        self.blue_style_patterns = [
            r'\bDVOR\b',
            r'\bAPRON\b',
            r'\bANTI-ICING\b',
            r'\bDE-ICING\b',
            r'\bSTAND\s+NUMBER\s+\d+\b',
            r'\bSTAND\s+\d+\b',
            r'\bSTAND\b',
            r'\bILS\b',
            r'\bLOC\b',
            r'\bS-LOC\b',
            r'\bMDA\b',
            r'\bCAT\b',
            r'\bVIS\b',
            r'\bRVR\b',
            r'\bHAT\b',
            r'\bRWY\s+(?:\d{2}[LRC]?(?:/\d{2}[LRC]?)?)\b',
            r'\bTWY\s+(?:[A-Z]|[A-Z]{2}|[A-Z]\d{1,2})\b',
            r'\bTWY\s+[A-Z]\b',
            r'\bTWY\s+[A-Z]{2}\b',
            r'\bTWY\s+[A-Z]\d{1,2}\b',
            r'\bVOR\b',
            r'\bDME\b',
            r'\bTWR\b',
            r'\bATIS\b',
            r'\bAPPROACH MINIMA\b',
            r'\bVDP\b',
            r'\bEST\b',
            r'\bEastern Standard Time\b',
            r'\bIAP\b',
            r'\bRNAV\b',
            r'\bGPS\s+(?:APPROACH|APP|APPROACHES)\b',
            r'\bLPV\b',
            r'\bDA\b',
            r'\b주기장\b',
            r'\b주기장\s+\d+\b',
            r'\b활주로\s+\d+[A-Z]?\b',
            r'\bP\d+\b',
            r'\bSTANDS?\s*(?:NR\.)?\s*(\d+)\b',
            r'\bSTANDS?\s*(\d+)\b',
        ]
        
        # 기본 항공 용어 확장
        self.aviation_terms.update({
            'OBSTACLE': '장애물',
            'LIGHTING': '조명',
            'NAVAID': '항행안전시설',
            'ILS': '계기착륙시설',
            'VOR': 'VOR',
            'DME': 'DME',
            'ATIS': 'ATIS',
            'TOWER': '관제탑',
            'APPROACH': '접근',
            'DEPARTURE': '출발',
            'CAUTION': '주의',
            'TEMPORARY': '임시',
            'PERMANENT': '영구',
            'RESTRICTED': '제한',
            'PROHIBITED': '금지',
            'AVAILABLE': '이용가능',
            'UNAVAILABLE': '이용불가',
            'OPERATIONAL': '운용중',
            'OUT OF SERVICE': '운용중단',
            'STAND': '주기장',
            'CRANE': '크레인',
            'GPS RAIM': 'GPS RAIM'
        })
        
    def apply_color_styles(self, text: str) -> str:
        """
        텍스트에 색상 스타일을 적용 (참조 파일의 apply_color_styles 기반)
        
        Args:
            text (str): 원본 텍스트
            
        Returns:
            str: 스타일이 적용된 텍스트 (HTML 태그 완전 제거)
        """
        if not text:
            return text
        
        # 모든 HTML 태그와 엔티티 완전 제거
        import re
        text = re.sub(r'<[^>]*>', '', text)
        text = re.sub(r'&[a-zA-Z0-9#]+;', '', text)
        
        # HTML 태그 없이 깨끗한 텍스트만 반환
        return text.strip()

    def extract_e_section(self, notam_text: str) -> str:
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

    def preprocess_notam_text(self, notam_text: str) -> str:
        """
        NOTAM 텍스트를 번역 전에 전처리합니다.
        """
        # 중요 용어들을 임시 토큰으로 대체하여 번역에서 보호
        protected_terms = [
            'AIRAC AIP SUP', 'UTC', 'NOTAM', 'GPS', 'RAIM', 'RWY', 'TWY', 
            'APRON', 'ILS', 'VOR', 'DME', 'ATIS', 'SID', 'STAR', 'IAP'
        ]
        
        for term in protected_terms:
            notam_text = re.sub(r'\b' + re.escape(term) + r'\b', 
                              term.replace(' ', '_TOKEN_'), notam_text)
        
        return notam_text

    def postprocess_translation(self, translated_text: str) -> str:
        """
        번역된 텍스트를 후처리합니다.
        """
        # 임시 토큰을 원래 형태로 복원
        protected_terms = [
            'AIRAC AIP SUP', 'UTC', 'NOTAM', 'GPS', 'RAIM', 'RWY', 'TWY', 
            'APRON', 'ILS', 'VOR', 'DME', 'ATIS', 'SID', 'STAR', 'IAP'
        ]
        
        for term in protected_terms:
            translated_text = translated_text.replace(term.replace(' ', '_TOKEN_'), term)
        
        # "CREATED:" 이후의 텍스트 제거
        translated_text = re.sub(r'\s*CREATED:.*$', '', translated_text)
        
        # 불필요한 공백 제거
        translated_text = re.sub(r'\s+', ' ', translated_text)
        
        # 괄호 닫기 확인
        if translated_text.count('(') > translated_text.count(')'):
            translated_text += ')'
        
        # 띄어쓰기 오류 수정
        translated_text = re.sub(r'폐\s+쇄', '폐쇄', translated_text)
        
        return translated_text.strip()

    def translate_notam(self, notam_text, target_lang: str = "ko", use_ai: bool = True) -> Dict:
        """
        NOTAM 텍스트를 번역 (SmartNOTAMgemini_GCR의 향상된 알고리즘 적용)
        
        Args:
            notam_text: 원본 NOTAM 텍스트 (문자열 또는 딕셔너리)
            target_lang (str): 목표 언어 ("ko" 또는 "en")
            use_ai (bool): AI 번역 사용 여부
            
        Returns:
            Dict: 번역 결과
        """
        try:
            # 입력이 딕셔너리인 경우 텍스트 추출
            if isinstance(notam_text, dict):
                text = notam_text.get('raw_text', '') or notam_text.get('text', '') or str(notam_text)
            else:
                text = str(notam_text)
            
            if not text.strip():
                return self._create_error_result("빈 텍스트입니다.")
            
            # E 섹션만 추출 (핵심 내용만 번역)
            e_section = self.extract_e_section(text)
            if not e_section:
                return self._create_error_result("번역할 내용이 없습니다.")
            
            # AI 번역 사용
            if use_ai and target_lang == "ko":
                korean_translation = self._perform_enhanced_translation(e_section, "ko")
                english_translation = self._perform_enhanced_translation(e_section, "en")
                
                return {
                    'korean_translation': korean_translation,
                    'english_translation': english_translation,
                    'original_text': text,
                    'e_section': e_section,
                    'error_message': None
                }
            elif use_ai and target_lang == "en":
                english_translation = self._perform_enhanced_translation(e_section, "en")
                
                return {
                    'english_translation': english_translation,
                    'korean_translation': '',
                    'original_text': text,
                    'e_section': e_section,
                    'error_message': None
                }
            else:
                # 기본 사전 기반 번역
                basic_translation = self._basic_translate(text, target_lang)
                return {
                    'korean_translation': basic_translation if target_lang == "ko" else '',
                    'english_translation': basic_translation if target_lang == "en" else '',
                    'original_text': text,
                    'error_message': None
                }
                
        except Exception as e:
            self.logger.error(f"번역 수행 중 오류 발생: {str(e)}")
            return self._create_error_result(str(e))

    def _perform_enhanced_translation(self, e_section: str, target_lang: str) -> str:
        """향상된 번역 수행 (SmartNOTAMgemini_GCR 알고리즘 기반)"""
        try:
            # 텍스트 전처리
            preprocessed_text = self.preprocess_notam_text(e_section)
            
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
{preprocessed_text}

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
   - "DUE TO"는 "로 인해"로 번역
   - "MAINT"는 "정비"로 번역
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
{preprocessed_text}

번역문:"""
            
            # Gemini API 호출
            response = self.model.generate_content(prompt)
            translated_text = response.text.strip()
            
            # 후처리
            translated_text = self.postprocess_translation(translated_text)
            
            return translated_text
            
        except Exception as e:
            self.logger.error(f"향상된 번역 중 오류 발생: {str(e)}")
            return "번역 중 오류가 발생했습니다."

    def _create_error_result(self, error_msg: str) -> Dict:
        """에러 결과 생성"""
        return {
            'korean_translation': '번역 실패',
            'english_translation': 'Translation failed',
            'original_text': '',
            'error_message': error_msg
        }
            
            if not text.strip():
                return {
                    'korean_translation': '텍스트가 없습니다',
                    'english_translation': 'No text available',
                    'error_message': 'Empty text'
                }
            
            # Gemini를 사용한 번역
            if use_ai and self.gemini_enabled:
                # 번역 전 HTML 태그 완전 제거
                clean_text = re.sub(r'<[^>]+>', '', text)  # 모든 HTML 태그 제거
                clean_text = re.sub(r'&[a-zA-Z]+;', '', clean_text)  # HTML 엔티티 제거
                
                if target_lang == "ko":
                    korean_translation = self._translate_with_gemini(clean_text, "ko")
                    # 번역 결과에서도 HTML 태그 제거
                    korean_translation = re.sub(r'<[^>]+>', '', korean_translation)
                    korean_translation = self.apply_color_styles(korean_translation)
                    return {
                        'korean_translation': korean_translation,
                        'english_translation': clean_text,  # 정제된 원문
                        'error_message': None
                    }
                else:  # English
                    english_translation = self._translate_with_gemini(clean_text, "en")
                    # 번역 결과에서도 HTML 태그 제거
                    english_translation = re.sub(r'<[^>]+>', '', english_translation)
                    english_translation = self.apply_color_styles(english_translation)
                    return {
                        'english_translation': english_translation,
                        'korean_translation': self._translate_with_gemini(clean_text, "ko"),
                        'error_message': None
                    }
            else:
                # 사전 기반 번역
                translated = self._translate_with_dictionary(text)
                return {
                    'korean_translation': translated if target_lang == "ko" else text,
                    'english_translation': text if target_lang == "ko" else translated,
                    'error_message': None
                }
                
        except Exception as e:
            self.logger.error(f"번역 수행 중 오류 발생: {str(e)}")
            return {
                'english_translation': 'Translation failed',
                'korean_translation': '번역 실패',
                'error_message': str(e)
            }
    
    def _translate_with_gemini(self, text: str, target_lang: str) -> str:
        """Gemini를 사용한 향상된 번역 (SmartNOTAMgemini_GCR 알고리즘 기반)"""
        try:
            # E 섹션만 추출 (핵심 내용만 번역)
            e_section = self.extract_e_section(text)
            if not e_section:
                return "번역할 내용이 없습니다."

            # 텍스트 전처리 (중요 용어 보호)
            preprocessed_text = self.preprocess_notam_text(e_section)

            # 향상된 번역 프롬프트 설정
            if target_lang == "ko":
                prompt = f"""다음 NOTAM E 섹션을 한국어로 번역하세요. 다음 규칙을 엄격히 따르세요:

1. 다음 용어는 그대로 유지:
   - NOTAM, AIRAC, AIP, SUP, AMDT, WEF, TIL, UTC
   - GPS, RAIM, PBN, RNAV, RNP
   - RWY, TWY, APRON, TAXI, SID, STAR, IAP
   - SFC, AMSL, AGL, MSL, PSN, RADIUS, HGT, HEIGHT
   - TEMP, PERM, OBST, FIREWORKS
   - 모든 좌표, 주파수, 측정값은 원래 형식 유지
   - 모든 날짜와 시간은 원래 형식 유지
   - 모든 항공기 주기장 번호와 참조

2. 특정 용어 번역:
   - "CLOSED" → "폐쇄"
   - "PAVEMENT CONSTRUCTION" → "포장 공사"
   - "OUTAGES" → "기능 상실"
   - "PREDICTED FOR" → "에 영향을 줄 것으로 예측됨"
   - "WILL TAKE PLACE" → "진행될 예정"
   - "DUE TO" → "로 인해"
   - "MAINT" → "정비"
   - "ACFT" → "항공기"
   - "NR." → "번호"
   - "ESTABLISHMENT OF" → "신설"
   - "INFORMATION OF" → "정보"

3. 번역 품질 규칙:
   - 자연스러운 한국어 어순 사용
   - 불필요한 조사나 어미 제거
   - 간결하고 명확한 표현 사용
   - 중복된 표현 제거
   - 띄어쓰기 정확히
   - 괄호 열고 닫기 정확히
   - 문장이 완성되지 않은 경우 완성

4. 포함하지 않을 내용:
   - NOTAM 번호, 공항 코드
   - "E:" 접두사
   - "CREATED:" 이후 텍스트
   - 추가 설명이나 해석

원문:
{preprocessed_text}

번역문:"""
            else:  # English
                prompt = f"""Translate the following NOTAM E section to English. Follow these rules:

1. Keep aviation terms unchanged:
   - NOTAM, AIRAC, AIP, SUP, UTC, GPS, RAIM
   - RWY, TWY, APRON, SID, STAR, IAP
   - All coordinates, frequencies, measurements
   - All dates and times in original format

2. Standard translations:
   - "CLOSED" as "CLOSED"
   - "PAVEMENT CONSTRUCTION" as "PAVEMENT CONSTRUCTION"
   - Keep "ACFT" as "ACFT"
   - Keep "NR." as "NR."

3. Quality rules:
   - Natural English word order
   - Complete unfinished sentences
   - Maintain proper parentheses
   - Remove redundant expressions

Original text:
{preprocessed_text}

Translated text:"""

            # Gemini API 호출
            response = self.model.generate_content(prompt)
            translated_text = response.text.strip()
            
            # 후처리 (중요 용어 복원, 괄호 정리 등)
            translated_text = self.postprocess_translation(translated_text)
            
            return translated_text
            
        except Exception as e:
            self.logger.error(f"Gemini 번역 중 오류 발생: {str(e)}")
            return f"번역 오류: {str(e)}"

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

2. HTML 태그 처리:
   - 원문에 <span>, </span> 등 HTML 태그가 있으면 완전히 무시하고 제거
   - 태그 내의 텍스트만 번역
   - 번역 결과에는 HTML 태그를 포함하지 않음

3. 특정 용어 번역:
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

4. 다음 형식 정확히 유지:
   - 여러 항목 (예: "1.PSN: ..., 2.PSN: ...")
   - 좌표와 측정값
   - 날짜와 시간
   - NOTAM 섹션
   - 항공기 주기장 번호와 참조
   - 문장이나 구절이 완성되지 않은 경우 완성

5. 다음 내용 포함하지 않음:
   - NOTAM 번호
   - E 섹션 외부의 날짜나 시간
   - 공항 코드
   - "E:" 접두사
   - 추가 설명이나 텍스트
   - "CREATED:" 이후의 텍스트
   - HTML 태그

6. 번역 스타일:
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
            response = self.gemini_model.generate_content(prompt)
            translated_text = response.text.strip()
            
            # "CREATED:" 이후의 텍스트만 제거 (더 정확하게)
            if 'CREATED:' in translated_text:
                translated_text = translated_text.split('CREATED:')[0].strip()
            
            # 불필요한 공백 정리 (덜 공격적으로)
            translated_text = re.sub(r'\s+', ' ', translated_text)
            
            # 괄호 닫기 확인
            open_parens = translated_text.count('(')
            close_parens = translated_text.count(')')
            if open_parens > close_parens:
                translated_text += ')' * (open_parens - close_parens)
            
            # 띄어쓰기 오류 수정
            translated_text = re.sub(r'폐\s+쇄', '폐쇄', translated_text)
            translated_text = re.sub(r'포\s+장', '포장', translated_text)
            
            return translated_text
            
        except Exception as e:
            self.logger.error(f"Gemini 번역 중 오류 발생: {str(e)}")
            return "번역 중 오류가 발생했습니다."
    
    def extract_e_section(self, notam_text: str) -> str:
        """
        NOTAM 텍스트에서 E 섹션만 추출 (개선된 버전)
        """
        # 실제 NOTAM 구조에 맞게 수정
        # E) 섹션 패턴 매칭 (더 관대하게)
        e_section_pattern = r'E\)\s*(.*?)(?=\s*CREATED:|$)'
        match = re.search(e_section_pattern, notam_text, re.DOTALL)
        
        if match:
            e_section = match.group(1).strip()
            return e_section
        
        # E) 패턴이 없으면 NOTAM 번호 이후의 모든 텍스트 반환
        # 예: "09JUL25 16:00 - 25SEP25 09:00 RKSI Z0582/25" 이후
        notam_header_pattern = r'\d{2}[A-Z]{3}\d{2} \d{2}:\d{2} - (?:\d{2}[A-Z]{3}\d{2} \d{2}:\d{2}|UFN) [A-Z]{4} [A-Z0-9/]+\s*'
        
        # 헤더 이후의 텍스트 추출
        after_header = re.sub(notam_header_pattern, '', notam_text, count=1).strip()
        
        # CREATED: 이후의 텍스트 제거 (덜 공격적으로)
        if 'CREATED:' in after_header:
            after_header = after_header.split('CREATED:')[0].strip()
        
        return after_header if after_header else notam_text

    def _translate_with_dictionary(self, text: str) -> str:
        """사전 기반 번역 (AI 사용 불가능한 경우)"""
        translated = text
        
        # 용어 사전을 이용한 기본 번역
        for english, korean in self.aviation_terms.items():
            translated = re.sub(r'\b' + re.escape(english) + r'\b', korean, translated, flags=re.IGNORECASE)
        
        return translated
    
    def summarize_notam(self, notam_data: Dict, use_ai: bool = True) -> str:
        """
        NOTAM 데이터를 요약
        
        Args:
            notam_data (Dict): 구조화된 NOTAM 데이터
            use_ai (bool): AI 요약 사용 여부
            
        Returns:
            str: 요약된 텍스트
        """
        if use_ai and self.gemini_enabled:
            return self._summarize_with_gemini(notam_data)
        else:
            return self._summarize_with_template(notam_data)
    
    def _summarize_with_gemini(self, notam_data: Dict) -> str:
        """Gemini를 사용한 요약 (참조 파일의 summary.py 기반)"""
        try:
            if not self.gemini_enabled:
                return self._summarize_with_template(notam_data)
                
            # NOTAM 데이터에서 필요한 정보 추출
            original_text = notam_data.get('original_text', '')
            english_translation = notam_data.get('english_translation', '')
            korean_translation = notam_data.get('korean_translation', '')
            
            return self.summarize_notam_with_gemini(original_text, english_translation, korean_translation)
            
        except Exception as e:
            self.logger.error(f"Gemini 요약 중 오류: {str(e)}")
            return self._summarize_with_template(notam_data)
    
    def summarize_notam_with_gemini(self, notam_text: str, english_translation: str, korean_translation: str) -> Dict:
        """
        Gemini를 사용한 NOTAM 요약 (참조 파일의 summary.py 기반)
        """
        try:
            # 영어 요약 프롬프트
            english_prompt = f"""Summarize the following NOTAM in English, focusing on key information only:

NOTAM Text:
{notam_text}

English Translation:
{english_translation}

⚠️ MOST IMPORTANT RULES: ⚠️
1. NEVER include ANY of the following:
   - Time information (dates, times, periods, UTC)
   - Document references (AIRAC, AIP, AMDT, SUP)
   - Phrases like "New information is available", "Information regarding", "Information about"
   - Airport names
   - Coordinates
   - Unnecessary parentheses or special characters
   - Redundant words and phrases

2. Focus on:
   - Key changes or impacts
   - Specific details about changes
   - Reasons for changes

3. Keep it concise and clear:
   - Make it as short as possible
   - Use direct and active voice
   - Include only essential information

4. For runway directions:
   - Always use "L/R" format (e.g., "RWY 15 L/R")
   - Do not translate "L/R" to "LEFT/RIGHT" or "좌/우"
   - Keep the space between runway number and L/R (e.g., "RWY 15 L/R")

Provide a brief summary that captures the essential information."""

            # 한국어 요약 프롬프트
            korean_prompt = f"""다음 NOTAM을 한국어로 요약하되, 핵심 정보만 포함하도록 하세요:

NOTAM 원문:
{notam_text}

한국어 번역:
{korean_translation}

⚠️ 가장 중요한 규칙: ⚠️
1. 절대로 다음 정보를 포함하지 마세요:
   - 시간 정보 (날짜, 시간, 기간, UTC)
   - 문서 참조 (AIRAC, AIP, AMDT, SUP)
   - "새로운 정보", "정보 포함", "정보 변경" 등의 표현
   - 공항명
   - 좌표
   - 불필요한 괄호나 특수문자
   - 중복되는 단어나 구문

2. 포함할 내용:
   - 주요 변경사항 또는 영향
   - 변경사항의 구체적 세부사항
   - 변경 사유

3. 간단명료하게 작성:
   - 가능한 짧게 표현
   - 직접적이고 능동적인 표현 사용
   - 핵심 정보만 포함

4. 활주로 방향 표시:
   - 항상 "L/R" 형식을 사용하세요 (예: "활주로 15 L/R")
   - "L/R"을 "좌/우"로 번역하지 마세요
   - 활주로 번호와 L/R 사이에 공백을 유지하세요 (예: "활주로 15 L/R")

핵심 정보를 간단히 요약해주세요."""

            # Gemini 모델을 사용하여 요약 생성
            english_summary = self.gemini_model.generate_content(english_prompt).text.strip()
            korean_summary = self.gemini_model.generate_content(korean_prompt).text.strip()

            # 색상 스타일 적용
            korean_summary = self.apply_color_styles(korean_summary)
            english_summary = self.apply_color_styles(english_summary)

            return {
                'english_summary': english_summary,
                'korean_summary': korean_summary
            }
            
        except Exception as e:
            self.logger.error(f"Gemini 요약 중 오류: {str(e)}")
            return {
                'english_summary': english_translation,
                'korean_summary': korean_translation
            }

            # 한국어 요약에서 공항명과 시간 정보 제거
            korean_summary = self._clean_korean_summary(korean_summary, korean_translation)
            
            # 주기장 정보 특별 처리
            if '주기장' in korean_summary or 'STANDS' in korean_translation.upper() or 'STAND' in korean_translation.upper():
                korean_summary = self._process_stands_summary(korean_summary, korean_translation)

            # 색상 스타일 적용
            korean_summary = self.apply_color_styles(korean_summary)
            english_summary = self.apply_color_styles(english_summary)
            
            # 활주로 표시 정규화
            korean_summary = self._normalize_runway_display(korean_summary)
            english_summary = self._normalize_runway_display(english_summary)

            # 불필요한 공백과 쉼표 정리
            korean_summary = re.sub(r'\s+', ' ', korean_summary).strip()
            korean_summary = re.sub(r',\s*,', ',', korean_summary)
            korean_summary = re.sub(r'\s*,\s*$', '', korean_summary)

            return {
                'english_summary': english_summary,
                'korean_summary': korean_summary
            }
            
        except Exception as e:
            self.logger.error(f"Gemini 요약 생성 중 오류: {str(e)}")
            return {
                'english_summary': english_translation,
                'korean_summary': korean_translation
            }
    
    def _clean_korean_summary(self, korean_summary: str, korean_translation: str) -> str:
        """한국어 요약에서 불필요한 정보 제거"""
        # 공항명 패턴 (공항, 국제공항, 공항국제 등 포함)
        airport_pattern = r'[가-힣]+(?:국제)?공항'
        
        # 시간 정보 패턴 (날짜와 시간 포함)
        time_patterns = [
            r'\d{2}/\d{2}\s+\d{2}:\d{2}\s*-\s*\d{2}/\d{2}\s+\d{2}:\d{2}',  # 기본 시간 형식
            r'\(\d{2}/\d{2}\s+\d{2}:\d{2}\s*-\s*\d{2}/\d{2}\s+\d{2}:\d{2}\)',  # 괄호 안의 시간
            r'\d{2}/\d{2}',  # 날짜만 있는 경우
            r'\d{2}:\d{2}',  # 시간만 있는 경우
            r'\d{4}\s*UTC',  # UTC 시간
            r'\d{4}년\s*\d{1,2}월\s*\d{1,2}일',  # 한국어 날짜
            r'~까지',  # 한국어 기간 표현
            r'부터',  # 한국어 기간 표현
            r'까지'   # 한국어 기간 표현
        ]
        
        # 공항명과 시간 정보 제거
        korean_summary = re.sub(airport_pattern, '', korean_summary)
        for pattern in time_patterns:
            korean_summary = re.sub(pattern, '', korean_summary)
            
        return korean_summary
    
    def _process_stands_summary(self, korean_summary: str, korean_translation: str) -> str:
        """주기장 정보 특별 처리"""
        # P4 정보 추출
        p4_info = ""
        if 'P4' in korean_translation:
            p4_info = "P4 일부, "
        
        # 원본 텍스트에서 주기장 번호 추출
        all_numbers = []
        
        # 패턴 1: STANDS NR. 35가 36으로 변경, 209
        pattern1 = r'STANDS?\s*(?:NR\.)?\s*(\d+)(?:\s*(?:가|changing to|to)\s*(\d+))?,?\s*(?:,\s*(\d+))?'
        matches1 = re.finditer(pattern1, korean_translation)
        for match in matches1:
            groups = match.groups()
            all_numbers.extend([num for num in groups if num])
        
        # 패턴 2: 주기장 35에서 36으로 변경
        pattern2 = r'주기장\s*(\d+)(?:\s*(?:에서|가|changing to|to)\s*(\d+))?,?\s*(?:,\s*(\d+))?'
        matches2 = re.finditer(pattern2, korean_translation)
        for match in matches2:
            groups = match.groups()
            all_numbers.extend([num for num in groups if num])
            
        # 패턴 3: 추가 숫자 찾기 (쉼표로 구분된 숫자)
        pattern3 = r',\s*(\d+)(?:\s*closed)?'
        matches3 = re.finditer(pattern3, korean_translation)
        for match in matches3:
            all_numbers.extend(match.groups())
        
        if all_numbers:
            # 중복 제거 및 정렬
            all_numbers = sorted(list(set(all_numbers)), key=int)
            stands_text = ', '.join(all_numbers)
            korean_summary = f"{p4_info}주기장 {stands_text} 포장 공사로 폐쇄"
            if '운용 제한' in korean_translation or '운항 제한' in korean_translation:
                korean_summary += ", 운용 제한"
        else:
            # 현재 요약에서 숫자 추출 시도
            current_numbers = re.findall(r'\d+', korean_summary)
            if current_numbers:
                # 중복 제거 및 정렬
                current_numbers = sorted(list(set(current_numbers)), key=int)
                stands_text = ', '.join(current_numbers)
                korean_summary = f"{p4_info}주기장 {stands_text} 포장 공사로 폐쇄"
                if '운용 제한' in korean_translation or '운항 제한' in korean_translation:
                    korean_summary += ", 운용 제한"
                    
        return korean_summary
    
    def _normalize_runway_display(self, text: str) -> str:
        """활주로 표시 정규화"""
        text = re.sub(r'활주로\s*RWY', r'RWY', text)
        text = re.sub(r'RWY<span[^>]*>(\d+[A-Z])</span>/([A-Z])', r'RWY<span style="color: blue">\1/\2</span>', text)
        return text
    
    def _summarize_with_template(self, notam_data: Dict) -> str:
        """템플릿 기반 요약"""
        summary_parts = []
        
        # NOTAM ID
        if notam_data.get('id'):
            summary_parts.append(f"NOTAM: {notam_data['id']}")
        
        # 공항/위치
        if notam_data.get('airport_codes'):
            airports = ', '.join(notam_data['airport_codes'])
            summary_parts.append(f"공항: {airports}")
        
        # 시간 정보
        if notam_data.get('effective_time') and notam_data.get('expiry_time'):
            summary_parts.append(f"기간: {notam_data['effective_time']} ~ {notam_data['expiry_time']}")
        
        # 설명 (첫 100자)
        if notam_data.get('description'):
            desc = notam_data['description'][:100]
            if len(notam_data['description']) > 100:
                desc += "..."
            summary_parts.append(f"내용: {desc}")
        
        return " | ".join(summary_parts)
    
    def translate_multiple_notams(self, notams: List[Dict]) -> List[Dict]:
        """
        여러 NOTAM을 일괄 번역
        
        Args:
            notams (List[Dict]): NOTAM 리스트
            
        Returns:
            List[Dict]: 번역된 NOTAM 리스트
        """
        translated_notams = []
        
        for i, notam in enumerate(notams):
            self.logger.info(f"NOTAM {i+1}/{len(notams)} 번역 및 요약 시작")
            
            # 디버깅: NOTAM 데이터 구조 로그
            self.logger.debug(f"NOTAM {i+1} 원본 필드: {list(notam.keys())}")
            self.logger.debug(f"effective_time: {notam.get('effective_time', 'N/A')}")
            self.logger.debug(f"expiry_time: {notam.get('expiry_time', 'N/A')}")
            
            # 새로운 NOTAM 데이터 구조 생성 (원본 필드 보존)
            translated_notam = {
                # 원본 필드들 보존
                'id': notam.get('id', ''),
                'location': notam.get('location', ''),
                'coordinates': notam.get('coordinates', ''),
                'effective_time': notam.get('effective_time'),  # 기본값 제거
                'expiry_time': notam.get('expiry_time'),        # 기본값 제거
                'description': notam.get('description', ''),
                'airport_codes': notam.get('airport_codes', []),
                'altitude': notam.get('altitude', ''),
                'raw_text': notam.get('raw_text', ''),
                'priority': notam.get('priority', 'normal'),
                'has_comment': notam.get('has_comment', False),
                
                # 번역 관련 새 필드들
                'original_text': notam.get('raw_text', ''),
                'korean_translation': '',
                'english_translation': '',
                'korean_summary': '',
                'english_summary': '',
                'error_message': None,
                'processed_at': datetime.now().isoformat()
            }
            
            # 원본 텍스트 번역
            if notam.get('raw_text'):
                translation_result = self.translate_notam(notam['raw_text'])
                if isinstance(translation_result, dict):
                    translated_notam['korean_translation'] = translation_result.get('korean_translation', '')
                    translated_notam['english_translation'] = translation_result.get('english_translation', '')
                    if translation_result.get('error_message'):
                        translated_notam['error_message'] = translation_result['error_message']
                else:
                    translated_notam['korean_translation'] = str(translation_result)
            
            # 설명 번역
            if notam.get('description'):
                desc_translation = self.translate_notam(notam['description'])
                if isinstance(desc_translation, dict):
                    translated_notam['translated_description'] = desc_translation.get('korean_translation', '')
            
            # 요약 생성 (번역된 데이터 기반)
            try:
                summary_result = self.summarize_notam(translated_notam)
                if isinstance(summary_result, dict):
                    translated_notam['korean_summary'] = summary_result.get('korean_summary', '')
                    translated_notam['english_summary'] = summary_result.get('english_summary', '')
                else:
                    translated_notam['korean_summary'] = str(summary_result)
            except Exception as e:
                self.logger.error(f"요약 생성 중 오류: {str(e)}")
                translated_notam['korean_summary'] = f"요약 생성 실패: {str(e)}"
                translated_notam['english_summary'] = f"Summary generation failed: {str(e)}"
            
            # 디버깅: 처리 후 필드 로그
            self.logger.debug(f"NOTAM {i+1} 처리 후 effective_time: {translated_notam.get('effective_time', 'N/A')}")
            self.logger.debug(f"NOTAM {i+1} 처리 후 expiry_time: {translated_notam.get('expiry_time', 'N/A')}")
            
            translated_notams.append(translated_notam)
            self.logger.info(f"NOTAM {i+1}/{len(notams)} 번역 및 요약 완료")
        
        return translated_notams
    
    def create_flight_briefing(self, notams: List[Dict], flight_route: Optional[List[str]] = None) -> str:
        """
        비행 브리핑용 NOTAM 요약 생성
        
        Args:
            notams (List[Dict]): NOTAM 리스트
            flight_route (List[str]): 비행 경로 공항 코드들
            
        Returns:
            str: 비행 브리핑 텍스트
        """
        briefing = "=== 대한항공 NOTAM 브리핑 ===\n\n"
        briefing += f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        if flight_route:
            briefing += f"비행 경로: {' → '.join(flight_route)}\n\n"
        
        # 중요도별 분류
        critical_notams = []
        normal_notams = []
        
        for notam in notams:
            description = notam.get('description', '').upper()
            if any(keyword in description for keyword in ['CLOSED', 'BLOCKED', 'UNAVAILABLE', 'PROHIBITED']):
                critical_notams.append(notam)
            else:
                normal_notams.append(notam)
        
        # 중요 NOTAM
        if critical_notams:
            briefing += "🚨 중요 NOTAM:\n"
            for notam in critical_notams:
                summary = self.summarize_notam(notam)
                briefing += f"- {summary}\n"
            briefing += "\n"
        
        # 일반 NOTAM
        if normal_notams:
            briefing += "📋 일반 NOTAM:\n"
            for notam in normal_notams:
                summary = self.summarize_notam(notam)
                briefing += f"- {summary}\n"
        
        return briefing
    
    def translate_multiple_notams(self, notams) -> List[Dict]:
        """
        여러 NOTAM을 일괄 번역 및 요약
        
        Args:
            notams: NOTAM 목록 (문자열 리스트 또는 딕셔너리 리스트)
            
        Returns:
            List[Dict]: 번역 및 요약된 NOTAM 목록
        """
        processed_notams = []
        
        for i, notam_item in enumerate(notams):
            try:
                # 입력이 딕셔너리인지 문자열인지 확인
                if isinstance(notam_item, dict):
                    # 딕셔너리에서 텍스트 추출
                    notam_text = notam_item.get('raw_text', '') or notam_item.get('text', '') or str(notam_item)
                    notam_id = notam_item.get('id', f'NOTAM_{i+1}')
                    # 필터에서 이미 추출된 시간 정보 사용
                    effective_time = notam_item.get('effective_time', 'N/A')
                    expiry_time = notam_item.get('expiry_time', 'N/A')
                else:
                    # 문자열인 경우
                    notam_text = str(notam_item)
                    notam_id = f'NOTAM_{i+1}'
                    effective_time = self._extract_effective_time(notam_text)
                    expiry_time = self._extract_expiry_time(notam_text)
                
                if not notam_text.strip():
                    self.logger.warning(f"NOTAM {i+1}: 빈 텍스트, 건너뜀")
                    continue
                
                # 한국어 번역
                translation_result = self.translate_notam(notam_text, target_lang="ko", use_ai=True)
                
                # 요약 생성 (참조 파일 기반)
                summary_result = self.summarize_notam_with_gemini(
                    notam_text,
                    translation_result.get('english_translation', notam_text),
                    translation_result.get('korean_translation', '번역 실패')
                )
                
                processed_notam = {
                    'id': notam_id,
                    'original_text': notam_text,
                    'description': notam_text,  # 템플릿에서 기대하는 필드
                    'translated_description': translation_result.get('korean_translation', '번역 실패'),
                    'korean_translation': translation_result.get('korean_translation', '번역 실패'),
                    'english_translation': translation_result.get('english_translation', notam_text),
                    'korean_summary': summary_result.get('korean_summary', '요약 실패'),
                    'english_summary': summary_result.get('english_summary', 'Summary failed'),
                    'error_message': translation_result.get('error_message', None),
                    'processed_at': datetime.now().isoformat(),
                    # 템플릿에서 기대하는 추가 필드들 - 필터에서 이미 추출된 정보 우선 사용
                    'airport_codes': notam_item.get('airport_codes', self._extract_airport_codes(notam_text)) if isinstance(notam_item, dict) else self._extract_airport_codes(notam_text),
                    'effective_time': effective_time,
                    'expiry_time': expiry_time,
                    'coordinates': notam_item.get('coordinates', self._extract_coordinates(notam_text)) if isinstance(notam_item, dict) else self._extract_coordinates(notam_text)
                }
                
                processed_notams.append(processed_notam)
                self.logger.info(f"NOTAM {i+1}/{len(notams)} 번역 및 요약 완료")
                
            except Exception as e:
                self.logger.error(f"NOTAM {i+1} 처리 중 오류: {str(e)}")
                processed_notams.append({
                    'id': f'NOTAM_{i+1}',
                    'original_text': notam_text,
                    'korean_translation': '번역 실패',
                    'english_translation': notam_text,
                    'korean_summary': '요약 실패',
                    'english_summary': 'Summary failed',
                    'error_message': str(e),
                    'processed_at': datetime.now().isoformat()
                })
        
        return processed_notams

    def _extract_airport_codes(self, notam_text: str) -> List[str]:
        """NOTAM 텍스트에서 공항 코드 추출"""
        import re
        # ICAO 공항 코드 패턴 (4글자)
        airport_pattern = r'\b[A-Z]{4}\b'
        codes = re.findall(airport_pattern, notam_text)
        # 필터링: 실제 공항 코드만 반환
        known_airports = ['RKSI', 'RKSS', 'RKPC', 'RKPK', 'RKTN', 'RKTU', 'RKJJ', 'RKNY']
        return [code for code in codes if code in known_airports or code.startswith('RK')]
    
    def _extract_effective_time(self, notam_text: str) -> str:
        """NOTAM 텍스트에서 유효 시작 시간 추출"""
        import re
        # B) 섹션에서 시작 시간 추출
        match = re.search(r'B\)(\d{10})', notam_text)
        if match:
            time_str = match.group(1)
            # YYMMDDHHMM 형식을 읽기 쉬운 형식으로 변환
            if len(time_str) == 10:
                year = f"20{time_str[:2]}"
                month = time_str[2:4]
                day = time_str[4:6] 
                hour = time_str[6:8]
                minute = time_str[8:10]
                return f"{year}-{month}-{day} {hour}:{minute} UTC"
        return "N/A"
    
    def _extract_expiry_time(self, notam_text: str) -> str:
        """NOTAM 텍스트에서 유효 종료 시간 추출"""
        import re
        # C) 섹션에서 종료 시간 추출
        match = re.search(r'C\)(\d{10})', notam_text)
        if match:
            time_str = match.group(1)
            # YYMMDDHHMM 형식을 읽기 쉬운 형식으로 변환
            if len(time_str) == 10:
                year = f"20{time_str[:2]}"
                month = time_str[2:4]
                day = time_str[4:6]
                hour = time_str[6:8] 
                minute = time_str[8:10]
                return f"{year}-{month}-{day} {hour}:{minute} UTC"
        return "N/A"
    
    def _extract_coordinates(self, notam_text: str) -> Optional[Dict]:
        """NOTAM 텍스트에서 좌표 정보 추출"""
        import re
        # Q) 섹션에서 좌표 정보 추출 (예: 3729N12629E005)
        coord_pattern = r'(\d{4})([NS])(\d{5})([EW])'
        match = re.search(coord_pattern, notam_text)
        if match:
            lat_deg = int(match.group(1)[:2])
            lat_min = int(match.group(1)[2:4])
            lat_dir = match.group(2)
            
            lon_deg = int(match.group(3)[:3])
            lon_min = int(match.group(3)[3:5])
            lon_dir = match.group(4)
            
            latitude = lat_deg + lat_min/60
            if lat_dir == 'S':
                latitude = -latitude
                
            longitude = lon_deg + lon_min/60
            if lon_dir == 'W':
                longitude = -longitude
                
            return {
                'latitude': latitude,
                'longitude': longitude
            }
        return None


if __name__ == "__main__":
    # 테스트 코드
    translator = NOTAMTranslator()
    
    # 번역 테스트
    test_notam = "A0001/24 NOTAMN Q)RKSI/QMXLC/IV/NBO/A/000/999/3729N12629E005 A)RKSI B)2412010000 C)2412010600 E)RWY 15L/33R CLOSED DUE MAINTENANCE"
    result = translator.translate_notam(test_notam)
    print(result)