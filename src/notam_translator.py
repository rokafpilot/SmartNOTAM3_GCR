import os
import re
import logging
from datetime import datetime
from typing import Dict, List, Optional
import google.generativeai as genai
from dotenv import load_dotenv

# 항공 용어 설정 import
try:
    from aviation_constants import DEFAULT_ABBR_DICT, NO_TRANSLATE_TERMS, RED_STYLE_TERMS, BLUE_STYLE_PATTERNS, apply_color_styles
except ImportError:
    # 기본값 설정 (aviation_constants.py가 없는 경우)
    DEFAULT_ABBR_DICT = {}
    NO_TRANSLATE_TERMS = []
    RED_STYLE_TERMS = []
    BLUE_STYLE_PATTERNS = []
    def apply_color_styles(text):
        return text

# 환경 변수 로드
load_dotenv()

class NOTAMTranslator:
    def __init__(self):
        """NOTAM 번역기 초기화"""
        self.logger = logging.getLogger(__name__)
        
        # Gemini API 설정
        self.gemini_enabled = False
        try:
            api_key = os.getenv('GOOGLE_API_KEY')
            if api_key:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel('gemini-2.5-flash-lite')
                self.gemini_enabled = True
                self.logger.info("Gemini API 초기화 완료")
            else:
                self.logger.warning("GOOGLE_API_KEY가 설정되지 않음")
        except Exception as e:
            self.logger.error(f"Gemini 초기화 실패: {str(e)}")
        
        # 기본 항공 용어 사전
        self.aviation_terms = {
            'RUNWAY': '활주로',
            'TAXIWAY': '유도로',
            'APRON': '에이프런',
            'CLOSED': '폐쇄',
            'CONSTRUCTION': '공사',
            'MAINTENANCE': '정비',
            'OBSTACLE': '장애물',
            'LIGHTING': '조명',
            'ILS': '계기착륙시설',
            'GPS': 'GPS',
            'RAIM': 'RAIM',
            'STAND': '주기장',
            'CRANE': '크레인',
            'TEMPORARY': '임시',
            'PERMANENT': '영구'
        }
        
        # SmartNOTAMgemini_GCR 색상 스타일 용어
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
            r'\bDVOR\b', r'\bAPRON\b', r'\bANTI-ICING\b', r'\bDE-ICING\b',
            r'\bSTAND\s+NUMBER\s+\d+\b', r'\bSTAND\s+\d+\b', r'\bSTAND\b',
            r'\bILS\b', r'\bLOC\b', r'\bS-LOC\b', r'\bMDA\b', r'\bCAT\b', r'\bVIS\b', r'\bRVR\b', r'\bHAT\b',
            r'\bRWY\s+(?:\d{2}[LRC]?(?:/\d{2}[LRC]?)?)\b',
            r'\bTWY\s+(?:[A-Z]|[A-Z]{2}|[A-Z]\d{1,2})\b',
            r'\bVOR\b', r'\bDME\b', r'\bTWR\b', r'\bATIS\b',
            r'\bAPPROACH MINIMA\b', r'\bVDP\b', r'\bEST\b',
            r'\bIAP\b', r'\bRNAV\b', r'\bGPS\s+(?:APPROACH|APP|APPROACHES)\b',
            r'\bLPV\b', r'\bDA\b', r'\b주기장\b', r'\b주기장\s+\d+\b',
            r'\b활주로\s+\d+[A-Z]?\b', r'\bP\d+\b',
            r'\bSTANDS?\s*(?:NR\.)?\s*(\d+)\b', r'\bSTANDS?\s*(\d+)\b',
        ]

    def extract_e_section(self, notam_text: str) -> str:
        """NOTAM 텍스트에서 E 섹션만 추출 (개선된 버전)"""
        # E 섹션 패턴 매칭 - 더 포괄적인 패턴 사용
        e_section_patterns = [
            # 패턴 1: E) 이후 다음 NOTAM 시작 전까지 (가장 포괄적)
            r'E\)\s*(.+?)(?=\n\s*\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*(?:\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}|UFN)\s+[A-Z]{4})',
            # 패턴 2: E) 이후 구분선 전까지
            r'E\)\s*(.+?)(?=\n\s*={20,}\s*$)',
            # 패턴 3: E) 이후 다른 섹션 전까지
            r'E\)\s*(.+?)(?=\n\s*[A-Z]\)\s*[A-Z])',
            # 패턴 4: E) 이후 문서 끝까지 (마지막 NOTAM인 경우)
            r'E\)\s*(.+?)$',
            # 패턴 5: 기존 패턴들 (폴백)
            r'E\)\s*(.*?)(?=\s*(?:F\)|G\)|COMMENT\)|SOURCE:|CREATED:))',  # 다음 섹션 전까지
            r'E\)\s*(.*?)(?=\s*[A-Z]\s*\)\s*[A-Z])',  # 다음 단일 문자 섹션 전까지
            r'E\)\s*(.*?)$'  # 문서 끝까지
        ]
        
        e_section = None
        for pattern in e_section_patterns:
            match = re.search(pattern, notam_text, re.DOTALL)
            if match:
                e_section = match.group(1).strip()
                break
        
        if e_section:
            # 정말 불필요한 내용만 제거 (CREATED: 이후의 메타데이터만)
            e_section = re.sub(r'CREATED:.*$', '', e_section, flags=re.DOTALL).strip()
            
            # SOURCE: 이후의 메타데이터 제거
            e_section = re.sub(r'SOURCE:.*$', '', e_section, flags=re.DOTALL).strip()
            
            # 연속된 공백 정리
            e_section = re.sub(r'\s+', ' ', e_section).strip()
            
            # 빈 문자열이거나 너무 짧은 경우 원본 텍스트 반환
            if len(e_section) < 10:
                # E) 이후의 모든 텍스트를 반환 (보수적 접근)
                fallback_match = re.search(r'E\)\s*(.*)', notam_text, re.DOTALL)
                if fallback_match:
                    return fallback_match.group(1).strip()[:500]  # 최대 500자
                return notam_text.strip()[:500]
            
            return e_section
        
        # E) 패턴이 없는 경우, 전체 텍스트에서 핵심 내용 추출
        core_patterns = [
            r'(?:RWY|RUNWAY).*?(?:CLOSED|CONSTRUCTION|MAINTENANCE)',
            r'(?:TWY|TAXIWAY).*?(?:CLOSED|CONSTRUCTION|MAINTENANCE)', 
            r'(?:GPS|RAIM).*?(?:NOT AVAILABLE|OUTAGES|UNSERVICEABLE)',
            r'(?:SID|STAR|IAP).*?(?:NOT AUTHORIZED|UNAVAILABLE)',
            r'(?:OBSTACLE|CRANE).*?(?:WILL TAKE PLACE|INSTALLED)',
            r'(?:LIGHTING|LIGHTS).*?(?:UNSERVICEABLE|OUT OF SERVICE)'
        ]
        
        for pattern in core_patterns:
            core_match = re.search(pattern, notam_text, re.IGNORECASE)
            if core_match:
                return core_match.group(0)
        
        return notam_text.strip()[:500]  # 최대 500자로 제한

    def expand_abbreviations(self, text: str) -> str:
        """항공 약어를 풀어서 번역 품질 향상"""
        if not DEFAULT_ABBR_DICT:
            return text
            
        expanded_text = text
        
        # 단어 경계를 고려한 약어 확장
        for abbr, expansion in DEFAULT_ABBR_DICT.items():
            # 단어 경계와 대소문자 고려
            pattern = r'\b' + re.escape(abbr) + r'\b'
            expanded_text = re.sub(pattern, expansion, expanded_text, flags=re.IGNORECASE)
        
        self.logger.debug(f"약어 확장: {text} → {expanded_text}")
        return expanded_text

    def remove_html_tags(self, text: str) -> str:
        """HTML 태그와 특수 문자 제거"""
        # HTML 태그 제거
        clean_text = re.sub(r'<[^>]+>', '', text)
        # HTML 엔티티 디코딩
        clean_text = clean_text.replace('&nbsp;', ' ')
        clean_text = clean_text.replace('&lt;', '<')
        clean_text = clean_text.replace('&gt;', '>')
        clean_text = clean_text.replace('&amp;', '&')
        # 연속된 공백을 하나로 줄이고 앞뒤 공백 제거
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        return clean_text
    
    def clean_text_formatting(self, text: str) -> str:
        """번역 텍스트의 불필요한 공백과 포맷팅 정리"""
        if not text:
            return ""
        
        # 줄바꿈과 연속된 공백 정리
        clean_text = re.sub(r'\n\s*\n', '\n', text)  # 연속된 줄바꿈 정리
        clean_text = re.sub(r'^\s+', '', clean_text, flags=re.MULTILINE)  # 줄 시작 공백 제거
        clean_text = re.sub(r'\s+$', '', clean_text, flags=re.MULTILINE)  # 줄 끝 공백 제거
        clean_text = re.sub(r'\s+', ' ', clean_text)  # 연속된 공백을 하나로
        clean_text = clean_text.strip()  # 전체 텍스트 앞뒤 공백 제거
        
        return clean_text

    def apply_color_styles(self, text: str) -> str:
        """텍스트에 색상 스타일을 적용합니다 (SmartNOTAMgemini_GCR 방식)"""
        if not text:
            return text
        
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
        for term in [t for t in self.red_style_terms if t != 'GPS RAIM']:
            if term.lower() in text.lower():
                text = re.sub(
                    re.escape(term),
                    lambda m: f'<span style="color: red; font-weight: bold;">{m.group()}</span>',
                    text,
                    flags=re.IGNORECASE
                )
        
        # 파란색 스타일 패턴 적용
        for pattern in self.blue_style_patterns:
            text = re.sub(
                pattern,
                lambda m: f'<span style="color: blue; font-weight: bold;">{m.group()}</span>',
                text,
                flags=re.IGNORECASE
            )
        
        return text.strip()

    def translate_notam(self, notam_text, target_lang: str = "ko", use_ai: bool = True) -> Dict:
        """NOTAM 텍스트 번역"""
        try:
            # 입력이 딕셔너리인 경우 텍스트 추출
            if isinstance(notam_text, dict):
                text = notam_text.get('raw_text', '') or notam_text.get('text', '') or str(notam_text)
            else:
                text = str(notam_text)
            
            if not text.strip():
                return {
                    'korean_translation': '텍스트가 없습니다',
                    'english_translation': 'No text available',
                    'error_message': 'Empty text'
                }
            
            # E 섹션만 추출하여 번역
            e_section = self.extract_e_section(text)
            
            # Gemini를 사용한 향상된 번역
            if use_ai and self.gemini_enabled:
                if target_lang == "ko":
                    korean_translation = self._translate_with_gemini(e_section, "ko")
                    english_translation = self._translate_with_gemini(e_section, "en")
                    
                    # HTML 태그 제거
                    korean_translation = self.apply_color_styles(korean_translation)
                    english_translation = self.apply_color_styles(english_translation)
                    
                    return {
                        'korean_translation': korean_translation,
                        'english_translation': english_translation,
                        'error_message': None
                    }
                else:  # English
                    english_translation = self._translate_with_gemini(e_section, "en")
                    english_translation = self.apply_color_styles(english_translation)
                    
                    return {
                        'english_translation': english_translation,
                        'korean_translation': '',
                        'error_message': None
                    }
            else:
                # 기본 사전 기반 번역
                translated = self._basic_translate(text, target_lang)
                return {
                    'korean_translation': translated if target_lang == "ko" else text,
                    'english_translation': text if target_lang == "ko" else translated,
                    'error_message': None
                }
                
        except Exception as e:
            self.logger.error(f"번역 수행 중 오류 발생: {str(e)}")
            return {
                'korean_translation': '번역 실패',
                'english_translation': 'Translation failed',
                'error_message': str(e)
            }

    def _translate_with_gemini(self, text: str, target_lang: str) -> str:
        """Gemini를 사용한 향상된 번역 (SmartNOTAMgemini_GCR 품질)"""
        try:
            # E 섹션만 추출
            e_section = self.extract_e_section(text)
            if not e_section:
                return "번역할 내용이 없습니다."

            # SmartNOTAMgemini_GCR의 정교한 번역 프롬프트 사용
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
   - "CENTRE RWY"는 "중앙 활주로"로 번역
   - "ON STANDBY"는 "대기 상태로"로 번역
   - "DUE WIP"는 "공사로 인해"로 번역
   - "WIP"는 "공사"로 번역
   - "CLSD"는 "폐쇄"로 번역
   - "CEILING"은 "운고"로 번역
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
            response = self.model.generate_content(prompt)
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
            
            # 색상 스타일 적용
            translated_text = apply_color_styles(translated_text)
            
            return translated_text
        except Exception as e:
            self.logger.error(f"번역 중 오류 발생: {str(e)}")
            return "번역 중 오류가 발생했습니다."
            return f"번역 오류: {str(e)}"

    def _basic_translate(self, text: str, target_lang: str) -> str:
        """기본 사전 기반 번역"""
        if target_lang != "ko":
            return text
        
        translated = text
        for eng, kor in self.aviation_terms.items():
            translated = re.sub(r'\b' + eng + r'\b', kor, translated, flags=re.IGNORECASE)
        
        return translated

    def summarize_notam_with_gemini(self, original_text: str, english_translation: str, korean_translation: str) -> Dict:
        """NOTAM 요약 생성 (SmartNOTAMgemini_GCR 품질)"""
        try:
            if not self.gemini_enabled:
                return {
                    'korean_summary': '요약 기능을 사용할 수 없습니다',
                    'english_summary': 'Summary function not available'
                }

            # SmartNOTAMgemini_GCR의 정교한 요약 프롬프트 사용
            english_prompt = f"""Summarize the following NOTAM in English, focusing on key information only:

NOTAM Text:
{original_text}

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

            korean_prompt = f"""다음 NOTAM을 한국어로 요약하되, 핵심 정보만 포함하도록 하세요:

NOTAM 원문:
{original_text}

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
            english_summary = self.model.generate_content(english_prompt).text.strip()
            korean_summary = self.model.generate_content(korean_prompt).text.strip()

            # 한국어 요약에서 공항명과 시간 정보 제거
            airport_pattern = r'[가-힣]+(?:국제)?공항'
            time_patterns = [
                r'\d{2}/\d{2}\s+\d{2}:\d{2}\s*-\s*\d{2}/\d{2}\s+\d{2}:\d{2}',
                r'\(\d{2}/\d{2}\s+\d{2}:\d{2}\s*-\s*\d{2}/\d{2}\s+\d{2}:\d{2}\)',
                r'\d{2}/\d{2}', r'\d{2}:\d{2}', r'\d{4}\s*UTC',
                r'\d{4}년\s*\d{1,2}월\s*\d{1,2}일',
                r'~까지', r'부터', r'까지'
            ]
            
            korean_summary = re.sub(airport_pattern, '', korean_summary)
            for pattern in time_patterns:
                korean_summary = re.sub(pattern, '', korean_summary)
            
            # 주기장 정보 특별 처리
            if '주기장' in korean_summary or 'STANDS' in korean_translation.upper() or 'STAND' in korean_translation.upper():
                # 주기장 번호 추출
                all_numbers = []
                
                # 다양한 패턴으로 주기장 번호 추출
                patterns = [
                    r'STANDS?\s*(?:NR\.)?\s*(\d+)(?:\s*(?:가|changing to|to)\s*(\d+))?,?\s*(?:,\s*(\d+))?',
                    r'주기장\s*(\d+)(?:\s*(?:에서|가|changing to|to)\s*(\d+))?,?\s*(?:,\s*(\d+))?',
                    r',\s*(\d+)(?:\s*closed)?'
                ]
                
                for pattern in patterns:
                    matches = re.finditer(pattern, korean_translation)
                    for match in matches:
                        groups = match.groups()
                        all_numbers.extend([num for num in groups if num])
                
                if all_numbers:
                    all_numbers = sorted(list(set(all_numbers)), key=int)
                    stands_text = ', '.join(all_numbers)
                    korean_summary = f"주기장 {stands_text} 포장 공사로 폐쇄"
                    if '운용 제한' in korean_translation or '운항 제한' in korean_translation:
                        korean_summary += ", 운용 제한"
                else:
                    current_numbers = re.findall(r'\d+', korean_summary)
                    if current_numbers:
                        current_numbers = sorted(list(set(current_numbers)), key=int)
                        stands_text = ', '.join(current_numbers)
                        korean_summary = f"주기장 {stands_text} 포장 공사로 폐쇄"
                        if '운용 제한' in korean_translation or '운항 제한' in korean_translation:
                            korean_summary += ", 운용 제한"
            
            korean_summary = korean_summary.strip()
            
            # 요약이 불가능한 경우 원본 표시
            if not korean_summary or korean_summary == "정보 없음" or korean_summary == "요약 생성 중 오류 발생":
                korean_summary = korean_translation
            if not english_summary or english_summary == "Error generating summary":
                english_summary = english_translation

            # 색상 스타일 적용
            korean_summary = apply_color_styles(korean_summary)
            english_summary = apply_color_styles(english_summary)
            
            # 활주로 표시 정규화
            korean_summary = re.sub(r'활주로\s*RWY', r'RWY', korean_summary)
            english_summary = re.sub(r'활주로\s*RWY', r'RWY', english_summary)

            # 불필요한 공백과 쉼표 정리
            korean_summary = re.sub(r'\s+', ' ', korean_summary)
            korean_summary = re.sub(r',\s*,', ',', korean_summary)
            korean_summary = re.sub(r'\s*,\s*$', '', korean_summary)

            return {
                'korean_summary': korean_summary,
                'english_summary': english_summary
            }
            
        except Exception as e:
            self.logger.error(f"요약 생성 중 오류 발생: {str(e)}")
            return {
                'korean_summary': '요약 실패',
                'english_summary': 'Summary failed'
            }

    def translate_multiple_notams(self, notams) -> List[Dict]:
        """여러 NOTAM을 일괄 번역"""
        processed_notams = []
        
        for i, notam_item in enumerate(notams):
            try:
                # 입력이 딕셔너리인지 문자열인지 확인
                if isinstance(notam_item, dict):
                    notam_text = notam_item.get('raw_text', '') or notam_item.get('text', '') or str(notam_item)
                    notam_id = notam_item.get('id', f'NOTAM_{i+1}')
                    # 필터에서 이미 추출된 시간 정보 사용
                    effective_time = notam_item.get('effective_time', 'N/A')
                    expiry_time = notam_item.get('expiry_time', 'N/A')
                else:
                    notam_text = str(notam_item)
                    notam_id = f'NOTAM_{i+1}'
                    effective_time = 'N/A'
                    expiry_time = 'N/A'
                
                if not notam_text.strip():
                    self.logger.warning(f"NOTAM {i+1}: 빈 텍스트, 건너뜀")
                    continue
                
                # 한국어 번역
                translation_result = self.translate_notam(notam_text, target_lang="ko", use_ai=True)
                
                # 요약 생성
                summary_result = self.summarize_notam_with_gemini(
                    notam_text,
                    translation_result.get('english_translation', notam_text),
                    translation_result.get('korean_translation', '번역 실패')
                )
                
                processed_notam = {
                    'id': notam_id,
                    'original_text': notam_text,
                    'description': notam_text,
                    'translated_description': translation_result.get('korean_translation', '번역 실패'),
                    'korean_translation': translation_result.get('korean_translation', '번역 실패'),
                    'english_translation': translation_result.get('english_translation', notam_text),
                    'korean_summary': summary_result.get('korean_summary', '요약 실패'),
                    'english_summary': summary_result.get('english_summary', 'Summary failed'),
                    'error_message': translation_result.get('error_message', None),
                    'processed_at': datetime.now().isoformat(),
                    'effective_time': effective_time,
                    'expiry_time': expiry_time,
                    'airport_codes': self._extract_airport_codes(notam_text),
                    'coordinates': self._extract_coordinates(notam_text)
                }
                
                processed_notams.append(processed_notam)
                self.logger.info(f"NOTAM {i+1}/{len(notams)} 번역 및 요약 완료")
                
            except Exception as e:
                self.logger.error(f"NOTAM {i+1} 처리 중 오류: {str(e)}")
                processed_notams.append({
                    'id': f'NOTAM_{i+1}',
                    'original_text': notam_text if 'notam_text' in locals() else '',
                    'korean_translation': '번역 실패',
                    'english_translation': 'Translation failed',
                    'korean_summary': '요약 실패',
                    'english_summary': 'Summary failed',
                    'error_message': str(e),
                    'processed_at': datetime.now().isoformat(),
                    'effective_time': 'N/A',
                    'expiry_time': 'N/A'
                })
        
        return processed_notams

    def _extract_airport_codes(self, notam_text: str) -> List[str]:
        """NOTAM 텍스트에서 공항 코드 추출"""
        airport_pattern = r'\b[A-Z]{4}\b'
        codes = re.findall(airport_pattern, notam_text)
        # RK로 시작하는 한국 공항 코드나 CSV에서 찾을 수 있는 공항 코드만 반환
        return [code for code in codes if code.startswith('RK') or self._is_valid_airport_code(code)]
    
    def _is_valid_airport_code(self, code: str) -> bool:
        """공항 코드가 유효한지 CSV 데이터베이스에서 확인"""
        try:
            from .icao import get_utc_offset
            # CSV에서 조회해서 유효한 공항 코드인지 확인
            offset = get_utc_offset(code)
            return offset != 'UTC+0'  # 기본값이 아니면 유효한 공항 코드
        except:
            return False

    def _extract_coordinates(self, notam_text: str) -> Optional[Dict]:
        """NOTAM 텍스트에서 좌표 정보 추출"""
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
    
    def translate_to_korean(self, text: str) -> str:
        """텍스트를 한국어로 번역 (SmartNOTAMgemini_GCR 방식 + 약어 전처리)"""
        try:
            # HTML 태그 제거
            clean_text = self.remove_html_tags(text)
            # 약어 확장 (번역 품질 향상)
            expanded_text = self.expand_abbreviations(clean_text)
            result = self.translate_notam_smart(expanded_text)
            korean_result = result.get('korean_translation', clean_text)
            # 번역 결과에서도 HTML 태그 제거 및 포맷팅 정리
            korean_result = self.remove_html_tags(korean_result)
            korean_result = self.clean_text_formatting(korean_result)
            return korean_result
        except Exception as e:
            self.logger.error(f"한국어 번역 오류: {str(e)}")
            return self.clean_text_formatting(self.remove_html_tags(text))
    
    def translate_to_english(self, text: str) -> str:
        """텍스트를 영어로 번역 (SmartNOTAMgemini_GCR 방식 + 약어 전처리)"""
        try:
            # HTML 태그 제거
            clean_text = self.remove_html_tags(text)
            # 약어 확장 (번역 품질 향상)
            expanded_text = self.expand_abbreviations(clean_text)
            result = self.translate_notam_smart(expanded_text)
            english_result = result.get('english_translation', clean_text)
            # 번역 결과에서도 HTML 태그 제거 및 포맷팅 정리
            english_result = self.remove_html_tags(english_result)
            english_result = self.clean_text_formatting(english_result)
            return english_result
        except Exception as e:
            self.logger.error(f"영어 번역 오류: {str(e)}")
            return self.clean_text_formatting(self.remove_html_tags(text))

    def translate_notam_smart(self, text: str):
        """NOTAM 텍스트를 영어와 한국어로 번역합니다 (SmartNOTAMgemini_GCR 방식)"""
        try:
            # 영어 번역
            english_translation = self.perform_translation_smart(text, "en")
            english_translation = self.apply_color_styles(english_translation)
            
            # 한국어 번역
            korean_translation = self.perform_translation_smart(text, "ko")
            korean_translation = self.apply_color_styles(korean_translation)
            
            return {
                'english_translation': english_translation,
                'korean_translation': korean_translation,
                'error_message': None
            }
        except Exception as e:
            self.logger.error(f"번역 수행 중 오류 발생: {str(e)}")
            return {
                'english_translation': 'Translation failed',
                'korean_translation': '번역 실패',
                'error_message': str(e)
            }

    def perform_translation_smart(self, text: str, target_lang: str):
        """Gemini를 사용하여 NOTAM 번역 수행 (SmartNOTAMgemini_GCR 프롬프트)"""
        try:
            # E 섹션만 추출
            e_section = self.extract_e_section(text)
            if not e_section:
                return "번역할 내용이 없습니다."

            # 번역 프롬프트 설정 (SmartNOTAMgemini_GCR 방식)
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
   - "CENTRE RWY"는 "중앙 활주로"로 번역
   - "ON STANDBY"는 "대기 상태로"로 번역
   - "DUE WIP"는 "공사로 인해"로 번역
   - "WIP"는 "공사"로 번역
   - "CLSD"는 "폐쇄"로 번역
   - "CEILING"은 "운고"로 번역
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
            response = self.model.generate_content(prompt)
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
            self.logger.error(f"번역 중 오류 발생: {str(e)}")
            return "번역 중 오류가 발생했습니다."
    
    def summarize_english(self, text: str) -> str:
        """영어 요약 생성 (SmartNOTAMgemini_GCR 방식)"""
        try:
            if not self.gemini_enabled:
                return apply_color_styles(text)
                
            # HTML 태그 제거
            clean_text = self.remove_html_tags(text)
            
            # SmartNOTAMgemini_GCR의 영어 요약 프롬프트
            prompt = f"""Summarize the following NOTAM in English, focusing on key information only:

NOTAM Text:
{clean_text}

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
            
            response = self.model.generate_content(prompt)
            summary = response.text.strip()
            
            # 색상 스타일 적용
            summary = apply_color_styles(summary)
            
            return summary if summary else clean_text
            
        except Exception as e:
            self.logger.error(f"영어 요약 생성 오류: {str(e)}")
            return clean_text
    
    def summarize_korean(self, text: str) -> str:
        """한국어 요약 생성 (SmartNOTAMgemini_GCR 방식)"""
        try:
            if not self.gemini_enabled:
                return apply_color_styles(text)
                
            # HTML 태그 제거
            clean_text = self.remove_html_tags(text)
            
            # SmartNOTAMgemini_GCR의 한국어 요약 프롬프트
            prompt = f"""다음 NOTAM을 한국어로 요약하되, 핵심 정보만 포함하도록 하세요:

NOTAM 원문:
{clean_text}

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
            
            response = self.model.generate_content(prompt)
            summary = response.text.strip()
            
            # 공항명과 시간 정보 제거
            airport_pattern = r'[가-힣]+(?:국제)?공항'
            summary = re.sub(airport_pattern, '', summary)
            
            # 시간 정보 패턴 제거
            time_patterns = [
                r'\d{4}년\s*\d{1,2}월\s*\d{1,2}일',  # 2024년 1월 1일
                r'\d{1,2}월\s*\d{1,2}일',  # 1월 1일
                r'\d{4}-\d{2}-\d{2}',  # 2024-01-01
                r'\d{2}:\d{2}',  # 12:30
                r'UTC[+-]?\d*',  # UTC+9
                r'부터.*까지',  # 시간 범위
                r'에서.*까지',  # 시간 범위
                r'기간.*동안',  # 기간 표현
            ]
            
            for pattern in time_patterns:
                summary = re.sub(pattern, '', summary)
            
            # 공백 정리
            summary = re.sub(r'\s+', ' ', summary).strip()
            summary = re.sub(r'^\s*[-,.:]\s*', '', summary)  # 시작 부분 특수문자 제거
            summary = re.sub(r'\s*[-,.:]\s*$', '', summary)  # 끝 부분 특수문자 제거
            
            # 색상 스타일 적용
            summary = apply_color_styles(summary)
            
            return summary if summary else clean_text
            
        except Exception as e:
            self.logger.error(f"한국어 요약 생성 오류: {str(e)}")
            return clean_text