"""
통합 NOTAM 번역기 - 번역과 요약을 한 번의 API 호출로 처리
번역과 요약의 일관성을 보장하는 통합 파이프라인
"""

import os
import re
import time
import hashlib
import logging
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv

# 색상 스타일 상수 (다른 파일에서 가져온 것)
RED_STYLE_TERMS = [
        'CLOSED', 'PAVEMENT CONSTRUCTION', 'OUTAGES', 'PREDICTED FOR', 'WILL TAKE PLACE',
        'NPA', 'FLW', 'ACFT', 'NR.', 'ESTABLISHMENT OF', 'INFORMATION OF', 'CIRCLE',
        'CENTERED', 'DUE TO', 'MAINT', 'NML OPS', 'U/S', 'STANDBY', 'AVBL', 'UNAVBL',
        'GPS RAIM', 'OBST', 'FIREWORKS', 'TEMPORARY', 'PERMANENT', 'RESTRICTED',
        'PROHIBITED', 'DANGER', 'CAUTION', 'WARNING', 'EMERGENCY', 'CRITICAL',
        # 한국어 용어들
        '폐쇄', '폐쇄되었습니다', '폐쇄됨', '포장 공사', '공사', '기능 상실', '예측', '예측됩니다',
        '예정', '예정입니다', '발생', '발생합니다', '설립', '정보', '원형', '중심',
        '로 인해', '때문에', '유지보수', '정상 운영', '사용 불가', '대기', '사용 가능',
        '사용 불가능', 'GPS RAIM', '장애물', '불꽃놀이', '임시', '영구', '제한',
        '금지', '위험', '주의', '경고', '비상', '중요', '주의하십시오', '경고하십시오',
        '위험합니다', '금지됩니다', '제한됩니다', '사용 불가능합니다', '폐쇄됩니다',
        '확인', '확인하십시오', '확인됩니다', '차단', '차단하십시오', '차단됩니다',
        '방지', '방지하십시오', '방지됩니다', '손상', '손상하십시오', '손상됩니다',
        '분리', '분리하십시오', '분리됩니다', '닫힘', '닫으십시오', '닫힙니다',
        '전기', '전기적', '전원', '패널', '상부', '하부', '외부', '내부'
    ]

BLUE_STYLE_PATTERNS = [
    r'\bRWY\s*\d{2}[LRC]?(?:/\d{2}[LRC]?)?\b',  # RWY 15L/33R
    r'\bTWY\s*[A-Z](?:\s+AND\s+[A-Z])*\b',  # TWY D, TWY D AND E
    r'\bTWY\s*[A-Z]\d+\b',  # TWY D1
    r'\bAPRON\s*[A-Z]\d*\b',  # APRON A, APRON A1
    r'\bTAXI\s*[A-Z]\d*\b',  # TAXI A, TAXI A1
    r'\bSID\s*[A-Z]\d*\b',  # SID A, SID A1
    r'\bSTAR\s*[A-Z]\d*\b',  # STAR A, STAR A1
    r'\bIAP\s*[A-Z]\d*\b',  # IAP A, IAP A1
    r'\bGPS\b',  # GPS
    r'\bRAIM\b',  # RAIM
    r'\bPBN\b',  # PBN
    r'\bRNAV\b',  # RNAV
    r'\bRNP\b',  # RNP
    r'\bSFC\b',  # SFC
    r'\bAMSL\b',  # AMSL
    r'\bAGL\b',  # AGL
    r'\bMSL\b',  # MSL
    r'\bPSN\b',  # PSN
    r'\bRADIUS\b',  # RADIUS
    r'\bHGT\b',  # HGT
    r'\bHEIGHT\b',  # HEIGHT
    r'\bTEMP\b',  # TEMP
    r'\bPERM\b',  # PERM
    r'\bOBST\b',  # OBST
    r'\bFIREWORKS\b',  # FIREWORKS
    r'\bSTANDS?\s*(\d+)\b',  # STANDS 711 형식
    # 한국어 패턴들
    r'\b활주로\s*\d{2}[LRC]?(?:/\d{2}[LRC]?)?\b',  # 활주로 15L/33R
    r'\b유도로\s*[A-Z](?:\s+및\s+[A-Z])*\b',  # 유도로 D, 유도로 D 및 E
    r'\b유도로\s*[A-Z]\d+\b',  # 유도로 D1
    r'\b주기장\s*[A-Z]\d*\b',  # 주기장 A, 주기장 A1
    r'\bGPS\b',  # GPS (한국어에서도 그대로 사용)
    r'\bRAIM\b',  # RAIM (한국어에서도 그대로 사용)
    r'\bPBN\b',  # PBN (한국어에서도 그대로 사용)
    r'\bRNAV\b',  # RNAV (한국어에서도 그대로 사용)
    r'\bRNP\b',  # RNP (한국어에서도 그대로 사용)
    r'\b지면\b',  # 지면
    r'\b해발\b',  # 해발
    r'\b지상\b',  # 지상
    r'\b평균해수면\b',  # 평균해수면
    r'\b위치\b',  # 위치
    r'\b반경\b',  # 반경
    r'\b높이\b',  # 높이
    r'\b임시\b',  # 임시
    r'\b영구\b',  # 영구
    r'\b장애물\b',  # 장애물
    r'\b불꽃놀이\b',  # 불꽃놀이
    r'\b스탠드\s*(\d+)\b',  # 스탠드 711 형식
]

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntegratedNOTAMTranslator:
    """통합 NOTAM 번역기 - 번역과 요약을 한 번의 API 호출로 처리"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        
        # Gemini API 설정
        self.api_key = api_key or os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            self.logger.warning("Gemini API 키가 설정되지 않음. 번역 기능이 제한됩니다.")
            self.gemini_enabled = False
        else:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash-lite')
            self.gemini_enabled = True
        
        # 캐시 설정
        self.cache = {}
        self.cache_enabled = True
        
        # 처리 설정 (개별 처리 최적화 - notam_translator.py 참조)
        self.max_workers = 3  # 워커 수를 3으로 조정
        self.batch_size = 3   # 배치 크기를 3으로 조정
        
        self.logger.info("통합 NOTAM 번역기 초기화 완료")
    
    def apply_color_styles(self, text: str) -> str:
        """텍스트에 색상 스타일을 적용합니다."""
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
        # 줄바꿈은 유지하고 중복 공백만 제거
        text = re.sub(r'[ \t]+', ' ', text)  # 탭과 공백만 제거
        
        return text
    
    def convert_markdown_to_html(self, text: str) -> str:
        """마크다운 텍스트를 HTML로 변환"""
        if not text:
            return text
        
        # 줄 단위로 처리
        lines = text.split('\n')
        html_lines = []
        in_list = False
        in_paragraph = False
        paragraph_content = []
        
        for line in lines:
            line = line.strip()
            
            # 빈 줄 처리 - 단락 종료
            if not line:
                if in_paragraph and paragraph_content:
                    # 단락 내용을 하나로 합치기
                    combined_content = ' '.join(paragraph_content)
                    html_lines.append(f'<p>{combined_content}</p>')
                    paragraph_content = []
                    in_paragraph = False
                continue
            
            # 불릿 포인트 처리 (*   로 시작하는 줄)
            if line.startswith('*   '):
                if in_paragraph and paragraph_content:
                    # 기존 단락 종료
                    combined_content = ' '.join(paragraph_content)
                    html_lines.append(f'<p>{combined_content}</p>')
                    paragraph_content = []
                    in_paragraph = False
                if not in_list:
                    html_lines.append('<ul>')
                    in_list = True
                content = line[4:]  # '*   ' 제거
                # 내용에서 **굵은 텍스트** 처리
                content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
                html_lines.append(f'<li>{content}</li>')
            elif line.startswith('* '):
                # * 로 시작하는 줄도 불릿 포인트로 처리
                if in_paragraph and paragraph_content:
                    # 기존 단락 종료
                    combined_content = ' '.join(paragraph_content)
                    html_lines.append(f'<p>{combined_content}</p>')
                    paragraph_content = []
                    in_paragraph = False
                if not in_list:
                    html_lines.append('<ul>')
                    in_list = True
                content = line[2:]  # '* ' 제거
                # 내용에서 **굵은 텍스트** 처리
                content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
                html_lines.append(f'<li>{content}</li>')
            else:
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                
                # 헤더 처리
                if line.startswith('### '):
                    if in_paragraph and paragraph_content:
                        # 기존 단락 종료
                        combined_content = ' '.join(paragraph_content)
                        html_lines.append(f'<p>{combined_content}</p>')
                        paragraph_content = []
                        in_paragraph = False
                    content = line[4:]
                    content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
                    html_lines.append(f'<h3>{content}</h3>')
                elif line.startswith('## '):
                    if in_paragraph and paragraph_content:
                        # 기존 단락 종료
                        combined_content = ' '.join(paragraph_content)
                        html_lines.append(f'<p>{combined_content}</p>')
                        paragraph_content = []
                        in_paragraph = False
                    content = line[3:]
                    content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
                    html_lines.append(f'<h2>{content}</h2>')
                elif line.startswith('# '):
                    if in_paragraph and paragraph_content:
                        # 기존 단락 종료
                        combined_content = ' '.join(paragraph_content)
                        html_lines.append(f'<p>{combined_content}</p>')
                        paragraph_content = []
                        in_paragraph = False
                    content = line[2:]
                    content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
                    html_lines.append(f'<h1>{content}</h1>')
                else:
                    # 일반 텍스트 처리 - 단락 내용에 추가
                    content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line)
                    if content.strip():  # 빈 내용이 아닌 경우만
                        paragraph_content.append(content)
                        in_paragraph = True
        
        # 마지막 단락 처리
        if in_paragraph and paragraph_content:
            combined_content = ' '.join(paragraph_content)
            html_lines.append(f'<p>{combined_content}</p>')
        if in_list:
            html_lines.append('</ul>')
        
        return '\n'.join(html_lines)
    
    def process_single_notam_complete(self, notam: Dict[str, Any], e_section: str, index: int) -> Dict[str, Any]:
        """단일 NOTAM을 완전히 처리 (notam_translator.py 방식 참조)"""
        try:
            # 캐시 확인
            cache_key = f"{e_section[:100]}_{index}"
            if self.cache_enabled and cache_key in self.cache:
                cached_result = self.cache[cache_key]
                self.logger.debug(f"NOTAM {index+1} 캐시에서 결과 반환")
                return cached_result
            
            # 1단계: 영어 번역 (원문에서 직접)
            english_result = self.process_single_integrated(e_section, 'en')
            english_translation = english_result.get('translation', '')
            english_summary = english_result.get('summary', '')
            
            # 2단계: 한국어 번역 (영어 번역 결과 사용)
            if english_translation and len(english_translation.strip()) > 10:
                korean_result = self.process_single_integrated(english_translation, 'ko')
                korean_translation = korean_result.get('translation', '')
                korean_summary = korean_result.get('summary', '')
                self.logger.debug(f"NOTAM {index+1} 영어→한국어 2단계 번역 완료")
            else:
                # 영어 번역 실패 시 원문으로 직접 한국어 번역
                korean_result = self.process_single_integrated(e_section, 'ko')
                korean_translation = korean_result.get('translation', '')
                korean_summary = korean_result.get('summary', '')
                self.logger.warning(f"NOTAM {index+1} 영어 번역 실패, 원문으로 한국어 번역 시도")
            
            # 결과 생성
            enhanced_notam = notam.copy()
            enhanced_notam.update({
                'korean_translation': self.convert_markdown_to_html(self.apply_color_styles(korean_translation)) if korean_translation else '번역 실패',
                'korean_summary': korean_summary or '요약 실패',
                'english_translation': self.apply_color_styles(english_translation) if english_translation else 'Translation failed',
                'english_summary': english_summary or 'Summary failed',
                'e_section': e_section
            })
            
            # 캐시 저장
            if self.cache_enabled:
                self.cache[cache_key] = enhanced_notam
            
            return enhanced_notam
            
        except Exception as e:
            self.logger.error(f"NOTAM {index+1} 개별 처리 실패: {e}")
            return self._create_fallback_result(notam, e_section)
    
    def _create_fallback_result(self, notam: Dict[str, Any], e_section: str) -> Dict[str, Any]:
        """폴백 결과 생성"""
        enhanced_notam = notam.copy()
        enhanced_notam.update({
            'korean_translation': '번역 실패',
            'korean_summary': '요약 실패',
            'english_translation': 'Translation failed',
            'english_summary': 'Summary failed',
            'e_section': e_section
        })
        return enhanced_notam
        """
        NOTAM들을 통합 처리 (번역 + 요약을 한 번에)
        
        Args:
            notams_data: NOTAM 데이터 리스트
            
        Returns:
            처리된 NOTAM 데이터 리스트
        """
        if not self.gemini_enabled:
            self.logger.warning("Gemini API가 비활성화됨. 원본 데이터 반환")
            return self._create_fallback_results(notams_data)
        
        start_time = time.time()
        results = []
        
        # 번역 전 NOTAM 데이터 상세 로깅 및 고유 ID 추가
        self.logger.info(f"=== 번역 시작: {len(notams_data)}개 NOTAM ===")
        for i, notam in enumerate(notams_data):
            # 고유 식별자 추가
            notam['_internal_id'] = f"{notam.get('notam_number', 'N/A')}_{notam.get('airport_code', 'N/A')}_{i}"
            self.logger.info(f"NOTAM {i+1}: {notam.get('notam_number', 'N/A')} ({notam.get('airport_code', 'N/A')}) [ID: {notam['_internal_id']}]")
            self.logger.info(f"  원문: {notam.get('description', '')[:100]}...")
        
        # E 섹션 추출
        e_sections = []
        for i, notam in enumerate(notams_data):
            description = notam.get('description', '')
            e_section = self.extract_e_section(description)
            e_sections.append(e_section)
            self.logger.debug(f"NOTAM {i+1} E 섹션 추출: {e_section[:100]}...")
        
        # 긴 NOTAM 감지 및 개별 처리 결정
        long_notams = []
        short_notams = []
        for i, e_section in enumerate(e_sections):
            if len(e_section) > 800:  # 800자 이상은 긴 NOTAM으로 분류 (임계값 상향)
                long_notams.append((i, e_section))
            else:
                short_notams.append((i, e_section))
        
        self.logger.info(f"긴 NOTAM {len(long_notams)}개, 짧은 NOTAM {len(short_notams)}개 감지")
        
        # 배치로 나누어 처리 (짧은 NOTAM만)
        batches = []
        batch_indices = []
        if short_notams:
            short_sections = [item[1] for item in short_notams]
            short_indices = [item[0] for item in short_notams]
            batches = [short_sections[i:i + self.batch_size] for i in range(0, len(short_sections), self.batch_size)]
            batch_indices = [short_indices[i:i + self.batch_size] for i in range(0, len(short_indices), self.batch_size)]
        
        # 2단계 번역: 원문 → 영어 → 한국어
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 1단계: 원문을 영어로 번역
            english_futures = {
                executor.submit(self.process_batch_integrated, batch, 'en'): i 
                for i, batch in enumerate(batches)
            }
            
            # 영어 번역 결과 수집
            english_results = {}
            for future in as_completed(english_futures):
                batch_idx = english_futures[future]
                try:
                    result = future.result()
                    english_results[batch_idx] = result
                except Exception as e:
                    self.logger.error(f"영어 배치 {batch_idx} 처리 실패: {e}")
                    english_results[batch_idx] = []
            
            # 영어 번역 결과를 원래 순서로 정렬
            english_flat = []
            for i in range(len(batches)):
                if i in english_results:
                    english_flat.extend(english_results[i])
                else:
                    batch_size = len(batches[i])
                    english_flat.extend([{'translation': '', 'summary': ''} for _ in range(batch_size)])
            
            # 2단계: 영어 번역 결과를 한국어로 번역
            english_translations = [result.get('translation', '') for result in english_flat]
            korean_batches = [english_translations[i:i + self.batch_size] for i in range(0, len(english_translations), self.batch_size)]
            
            korean_futures = {
                executor.submit(self.process_batch_integrated, batch, 'ko'): i 
                for i, batch in enumerate(korean_batches)
            }
            
            # 한국어 번역 결과 수집
            korean_results = {}
            for future in as_completed(korean_futures):
                batch_idx = korean_futures[future]
                try:
                    result = future.result()
                    korean_results[batch_idx] = result
                except Exception as e:
                    self.logger.error(f"한국어 배치 {batch_idx} 처리 실패: {e}")
                    korean_results[batch_idx] = []
        
        # 한국어 번역 결과를 원래 순서로 정렬
        korean_flat = []
        for i in range(len(korean_batches)):
            if i in korean_results:
                korean_flat.extend(korean_results[i])
            else:
                batch_size = len(korean_batches[i])
                korean_flat.extend([{'translation': '', 'summary': ''} for _ in range(batch_size)])
        
        # 긴 NOTAM 개별 처리
        long_notam_results = {}
        if long_notams:
            self.logger.info(f"긴 NOTAM {len(long_notams)}개 개별 처리 시작")
            for idx, e_section in long_notams:
                try:
                    # 영어 번역
                    english_result = self.process_single_integrated(e_section, 'en')
                    english_translation = english_result.get('translation', '')
                    english_summary = english_result.get('summary', '')
                    
                    # 한국어 번역 (영어 번역에서)
                    if english_translation:
                        korean_result = self.process_single_integrated(english_translation, 'ko')
                        korean_translation = korean_result.get('translation', '')
                        korean_summary = korean_result.get('summary', '')
                    else:
                        korean_translation = ''
                        korean_summary = ''
                    
                    long_notam_results[idx] = {
                        'english_translation': english_translation,
                        'english_summary': english_summary,
                        'korean_translation': korean_translation,
                        'korean_summary': korean_summary
                    }
                    self.logger.info(f"긴 NOTAM {idx+1} 개별 처리 완료")
                except Exception as e:
                    self.logger.error(f"긴 NOTAM {idx+1} 개별 처리 실패: {e}")
                    long_notam_results[idx] = {
                        'english_translation': '처리 오류',
                        'english_summary': '오류',
                        'korean_translation': '처리 오류',
                        'korean_summary': '오류'
                    }
        
        # 최종 결과 구성
        for i, notam in enumerate(notams_data):
            if i in long_notam_results:
                # 긴 NOTAM 결과 사용
                result = long_notam_results[i]
                korean_translation = result['korean_translation']
                korean_summary = result['korean_summary']
                english_translation = result['english_translation']
                english_summary = result['english_summary']
            else:
                # 배치 처리 결과 사용
                batch_idx = next((j for j, batch in enumerate(batch_indices) if i in batch), -1)
                if batch_idx >= 0:
                    batch_position = batch_indices[batch_idx].index(i)
                    korean_translation = korean_flat[batch_position].get('translation', '') if batch_position < len(korean_flat) else ''
                    korean_summary = korean_flat[batch_position].get('summary', '') if batch_position < len(korean_flat) else ''
                    english_translation = english_flat[batch_position].get('translation', '') if batch_position < len(english_flat) else ''
                    english_summary = english_flat[batch_position].get('summary', '') if batch_position < len(english_flat) else ''
                else:
                    korean_translation = ''
                    korean_summary = ''
                    english_translation = ''
                    english_summary = ''
            
            # 개별 처리로 폴백 (통합 처리 실패 시)
            if not english_translation or not english_summary:
                self.logger.warning(f"영어 통합 처리 실패, 개별 처리로 폴백: NOTAM {i+1}")
                english_result = self.process_single_integrated(e_sections[i], 'en')
                english_translation = english_result.get('translation', '')
                english_summary = english_result.get('summary', '')
                self.logger.info(f"개별 처리 결과 - 번역: {english_translation[:50]}..., 요약: {english_summary[:30]}...")
            
            if not korean_translation or not korean_summary:
                self.logger.warning(f"한국어 통합 처리 실패, 영어 번역 결과를 한국어로 번역: NOTAM {i+1}")
                if english_translation:
                    # 영어 번역 결과를 한국어로 번역
                    korean_result = self.process_single_integrated(english_translation, 'ko')
                    korean_translation = korean_result.get('translation', '')
                    korean_summary = korean_result.get('summary', '')
                    self.logger.info(f"2단계 번역 결과 - 번역: {korean_translation[:50]}..., 요약: {korean_summary[:30]}...")
                else:
                    # 영어 번역도 실패한 경우 원문을 한국어로 번역
                    korean_result = self.process_single_integrated(e_sections[i], 'ko')
                    korean_translation = korean_result.get('translation', '')
                    korean_summary = korean_result.get('summary', '')
                    self.logger.info(f"폴백 번역 결과 - 번역: {korean_translation[:50]}..., 요약: {korean_summary[:30]}...")
            
            enhanced_notam = notam.copy()
            enhanced_notam.update({
                'korean_translation': self.convert_markdown_to_html(self.apply_color_styles(korean_translation)) if korean_translation else '번역 실패',
                'korean_summary': korean_summary or '요약 실패',
                'english_translation': self.apply_color_styles(english_translation) if english_translation else 'Translation failed',
                'english_summary': english_summary or 'Summary failed',
                'e_section': e_sections[i] if i < len(e_sections) else ''
            })
            
            # 번역 결과 로깅
            self.logger.info(f"NOTAM {i+1} 번역 완료: {enhanced_notam.get('notam_number', 'N/A')} ({enhanced_notam.get('airport_code', 'N/A')}) [ID: {enhanced_notam.get('_internal_id', 'N/A')}]")
            self.logger.info(f"  영어 번역: {enhanced_notam.get('english_translation', '')[:100]}...")
            self.logger.info(f"  한국어 번역: {enhanced_notam.get('korean_translation', '')[:100]}...")
            
            # 데이터 일관성 검증
            original_id = notam.get('_internal_id', '')
            result_id = enhanced_notam.get('_internal_id', '')
            if original_id != result_id:
                self.logger.error(f"데이터 일관성 오류: 원본 ID {original_id} != 결과 ID {result_id}")
            
            results.append(enhanced_notam)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        self.logger.info(f"통합 번역 완료: {len(results)}개 NOTAM, {processing_time:.2f}초")
        self.logger.info(f"평균 처리 시간: {processing_time/len(results):.2f}초/NOTAM")
        
        return results
    
    def process_batch_integrated(self, notams: List[str], target_language: str) -> List[Dict[str, str]]:
        """
        배치 단위로 통합 처리 (번역 + 요약)
        
        Args:
            notams: NOTAM 텍스트 리스트
            target_language: 대상 언어 ('ko' 또는 'en')
            
        Returns:
            번역과 요약이 포함된 결과 리스트
        """
        if not self.gemini_enabled:
            return [{'translation': notam, 'summary': ''} for notam in notams]
        
        # 캐시 확인
        batch_key = f"integrated_{target_language}_{hashlib.md5(''.join(notams).encode()).hexdigest()}"
        if self.cache_enabled and batch_key in self.cache:
            self.logger.info(f"캐시에서 배치 결과 반환: {target_language}")
            return self.cache[batch_key]
        
        try:
            self.logger.debug(f"배치 처리 시작 - 언어: {target_language}, NOTAM 수: {len(notams)}")
            prompt = self.create_integrated_prompt(notams, target_language)
            self.logger.debug(f"프롬프트 길이: {len(prompt)} 문자")
            
            response = self.model.generate_content(prompt)
            self.logger.debug(f"응답 길이: {len(response.text)} 문자")
            
            result = self.parse_integrated_response(response.text, len(notams))
            self.logger.debug(f"파싱된 결과 수: {len(result)}")
            
            # 캐시 저장
            if self.cache_enabled:
                self.cache[batch_key] = result
            
            return result
            
        except Exception as e:
            self.logger.error(f"배치 통합 처리 오류: {e}")
            self.logger.error(f"오류 발생 배치 - 언어: {target_language}, NOTAM 수: {len(notams)}")
            self.logger.error(f"첫 번째 NOTAM 미리보기: {notams[0][:100] if notams else 'None'}...")
            import traceback
            self.logger.error(f"상세 오류: {traceback.format_exc()}")
            return [{'translation': f'처리 오류: {str(e)}', 'summary': '오류'} for _ in notams]
    
    def process_single_integrated(self, notam_text: str, target_language: str) -> Dict[str, str]:
        """
        단일 NOTAM 통합 처리 (번역 + 요약)
        
        Args:
            notam_text: NOTAM 텍스트
            target_language: 대상 언어 ('ko' 또는 'en')
            
        Returns:
            번역과 요약이 포함된 결과
        """
        if not self.gemini_enabled:
            return {'translation': notam_text, 'summary': ''}
        
        # 캐시 확인
        cache_key = f"integrated_single_{target_language}_{hashlib.md5(notam_text.encode()).hexdigest()}"
        if self.cache_enabled and cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            self.logger.debug(f"단일 통합 처리 시작 - 언어: {target_language}, 텍스트: {notam_text[:100]}...")
            prompt = self.create_integrated_prompt([notam_text], target_language)
            response = self.model.generate_content(prompt)
            results = self.parse_integrated_response(response.text, 1)
            
            result = results[0] if results else {'translation': notam_text, 'summary': ''}
            
            # 한국어 번역인 경우 마크다운을 HTML로 변환
            if target_language == 'ko' and result.get('translation'):
                result['translation'] = self.convert_markdown_to_html(self.apply_color_styles(result['translation']))
            
            self.logger.debug(f"단일 통합 처리 완료 - 번역: {result.get('translation', '')[:50]}..., 요약: {result.get('summary', '')[:30]}...")
            
            # 캐시 저장
            if self.cache_enabled:
                self.cache[cache_key] = result
            
            return result
            
        except Exception as e:
            self.logger.error(f"단일 통합 처리 오류: {e}")
            self.logger.error(f"오류 발생 텍스트: {notam_text[:200]}...")
            return {'translation': notam_text, 'summary': f'처리 오류: {str(e)}'}
    
    def create_integrated_prompt(self, notams: List[str], target_language: str) -> str:
        """
        통합 처리용 프롬프트 생성 (번역 + 요약)
        
        Args:
            notams: NOTAM 텍스트 리스트
            target_language: 대상 언어
            
        Returns:
            통합 프롬프트
        """
        if target_language == 'ko':
            return self.create_korean_integrated_prompt(notams)
        else:
            return self.create_english_integrated_prompt(notams)
    
    def create_korean_integrated_prompt(self, notams: List[str]) -> str:
        """한국어 통합 프롬프트 생성"""
        notams_text = "\n\n".join([f"NOTAM {i+1}:\n{notam}" for i, notam in enumerate(notams)])
        
        return f"""다음 NOTAM을 명확하고 간결한 한국어로 정리해주세요.

{notams_text}

요청사항:
이 NOTAM을 사용자가 쉽게 이해할 수 있도록 구조화된 한국어로 정리해주세요.

출력 형식 (정확히 이 형식을 따라주세요):
**주요 내용:**
[핵심 내용을 한 줄로 요약]

**상세 내용:**

*   [구체적인 세부사항을 항목별로 정리]
*   [각 항목은 별도의 불릿 포인트로 구분]

**운영 지침:**

*   [운영상 주의사항이나 지침]
*   [각 지침은 별도의 불릿 포인트로 구분]

**기타:**

*   [기타 중요한 정보]
*   [각 정보는 별도의 불릿 포인트로 구분]

번역 규칙:
1. 자연스러운 한국어로 번역하되 전문용어는 정확하게
2. 시간 정보는 KST로 변환하여 표시 (예: 2025년 2월 3일 09:00)
3. 중요한 정보는 **굵게** 표시
4. 사용자가 쉽게 이해할 수 있도록 구조화
5. 불필요한 반복이나 어색한 표현 제거
6. 각 섹션 사이에는 빈 줄을 넣어 가독성 향상
7. 불릿 포인트는 "*   " 형식으로 시작

항공 전문용어 번역 (정확한 한국어 용어 사용):
- VDGS → 차량유도도킹시스템
- CONCOURSE → 탑승동
- MAINTENANCE → 정비
- AIRCRAFT → 항공기
- MARSHALLER → 유도요원
- DOCKING → 접현
- INFORMATION → 정보
- PROVIDED → 제공
- GUIDED BY → 지시에 따라
- TRIAL OPERATION → 시험운영
- IMPLEMENTED → 실시
- NOTIFIED → 공지
- CHANGE → 변경
- DURING THE PERIOD → 해당기간동안
- REMAINING DISTANCE → 잔여거리
- LEFT AND RIGHT DEVIATION → 좌우편차
- TOBT → 이륙예정시간
- TSAT → 이륙시정예정시간
- A-CDM → 공항협력결정관리
- UTC → 협정세계시
- FROM ... TO ... → ...부터 ...까지
- DUE TO → 로 인해
- SERVICE → 서비스
- CLOSED → 폐쇄
- NR. → 번호
- RWY → 활주로
- TWY → 택시웨이
- WIP → 작업 진행
- CLSD → 폐쇄
- NML OPS → 정상 운영
- SIMULTANEOUS PARALLEL APPROACHES → 동시 평행 접근
- SUSPENDED → 중단
- REF → 참조

예시:
원문: "VDGS CLOSED DUE TO MAINTENANCE OF SERVICE FOR CONCOURSE"
정리: 
**주요 내용:**
탑승동(Concourse)의 **차량유도도킹시스템(VDGS)**가 서비스 정비로 인해 폐쇄됩니다.

**상세 내용:**

*   **차량유도도킹시스템(VDGS)**가 **서비스 정비**로 인해 **폐쇄**됩니다.
*   **탑승동(Concourse)**에서의 VDGS 서비스가 중단됩니다.

**운영 지침:**

*   항공기 도킹 시 **유도요원**의 지시를 따라야 합니다.

**기타:**

*   정비 완료 후 별도 공지될 예정입니다.

원문: "THE AIRCRAFT SHALL BE GUIDED BY MARSHALLER"
정리:
**주요 내용:**
항공기는 **유도요원**의 지시에 따라야 합니다.

**상세 내용:**

*   항공기 유도 시 **유도요원(Marshaller)**의 지시를 따라야 합니다.

**운영 지침:**

*   자동 유도 시스템 사용 불가 시 **유도요원** 지시 준수

**기타:**

*   안전한 항공기 유도를 위한 필수 절차입니다.

각 NOTAM을 위 형식과 용어를 사용하여 정리해주세요."""
    
    def create_english_integrated_prompt(self, notams: List[str]) -> str:
        """영어 통합 프롬프트 생성"""
        notams_text = "\n\n".join([f"NOTAM {i+1}:\n{notam}" for i, notam in enumerate(notams)])
        
        return f"""Translate the following NOTAMs to proper English and summarize the key points of each translation.

{notams_text}

⚠️ CRITICAL TRANSLATION RULES ⚠️
1. ALWAYS translate ALL numbered lists completely:
   - "1. RTE : A593 VIA SADLI" → "1. ROUTE: A593 VIA SADLI"
   - "2. ACFT : LANDING RKRR" → "2. AIRCRAFT: LANDING RKRR"
   - "3. PROC : FL330 AT OR BELOW AVBL" → "3. PROCEDURE: FL330 AT OR BELOW AVAILABLE"

2. Handle "FLOW CTL AS FLW" pattern:
   - "FLOW CTL AS FLW" → "FLOW CONTROL AS FOLLOWING"
   - Translate ALL subsequent numbered items (1. 2. 3. ...)
   - DO NOT stop translation at numbered lists

3. NEVER stop translation:
   - Translate the entire text even if it's long
   - Translate all numbered lists completely
   - Handle complex structures fully

Output Format:
For each NOTAM, output in the following format:

NOTAM 1:
Translation: [Complete English translation - including ALL numbered lists]
Summary: [Brief summary of key points]

NOTAM 2:
Translation: [Complete English translation - including ALL numbered lists]
Summary: [Brief summary of key points]

Translation Rules:
1. Expand abbreviations and acronyms to full English words:
   - 'FLW' → 'FOLLOWING'
   - 'AS FLW' → 'AS FOLLOWING'
   - 'FLOW CTL AS FLW' → 'FLOW CONTROL AS FOLLOWING'
   - 'ACFT' → 'AIRCRAFT'
   - 'RTE' → 'ROUTE'
   - 'PROC' → 'PROCEDURE'
   - 'AWY' → 'AIRWAY'
   - 'ALTN' → 'ALTERNATE'
   - 'REQ' → 'REQUEST'
   - 'EXC' → 'EXCEPT'
   - 'DEP' → 'DEPARTURE'
   - 'ARR' → 'ARRIVAL'
   - 'MAINT' → 'MAINTENANCE'
   - 'NML OPS' → 'NORMAL OPERATIONS'
   - 'U/S' → 'UNSERVICEABLE'
   - 'STANDBY' → 'STANDBY'
   - 'AVBL' → 'AVAILABLE'
   - 'UNAVBL' → 'UNAVAILABLE'
   - 'NOT AVBL' → 'NOT AVAILABLE'
   - 'SEPARATION' → 'SEPARATION'
   - 'SAME ALTITUDE' → 'SAME ALTITUDE'
   - 'AT OR BELOW' → 'AT OR BELOW'
   - 'LANDING' → 'LANDING'
   - 'ENTERING' → 'ENTERING'
   - 'RMK' → 'REMARK'
   - 'WIP' → 'WORK IN PROGRESS'
   - 'CLSD' → 'CLOSED'
   - 'NML OPS' → 'NORMAL OPERATIONS'
   - 'TEL' → 'TELEPHONE'
   - 'PSN' → 'POSITION'
   - 'HGT' → 'HEIGHT'
   - 'RADIUS' → 'RADIUS'
   - 'OBST' → 'OBSTACLE'
   - 'FIREWORKS' → 'FIREWORKS'
   - 'NPA' → 'NON-PRECISION APPROACH'
   - 'PBN' → 'PERFORMANCE BASED NAVIGATION'
   - 'RNAV' → 'AREA NAVIGATION'
   - 'RNP' → 'REQUIRED NAVIGATION PERFORMANCE'

2. Translation Examples:
   Example 1:
   Original: "FLOW CTL AS FLW 1. RTE : A593 VIA SADLI 2. ACFT : LANDING RKRR 3. PROC : FL330 AT OR BELOW AVBL"
   Translation: "FLOW CONTROL AS FOLLOWING 1. ROUTE: A593 VIA SADLI 2. AIRCRAFT: LANDING RKRR 3. PROCEDURE: FL330 AT OR BELOW AVAILABLE"
   
   Example 2:
   Original: "RWY 15L/33R CLSD DUE TO WIP RMK: TWY L, TWY K, TWY E, TWY J, TWY G NML OPS"
   Translation: "RWY 15L/33R CLOSED DUE TO WORK IN PROGRESS REMARK: TWY L, TWY K, TWY E, TWY J, TWY G NORMAL OPERATIONS"

3. Keep the following terms as is (aviation standards):
   - NOTAM, AIRAC, AIP, SUP, AMDT, WEF, TIL, UTC
   - GPS, RAIM, PBN, RNAV, RNP
   - RWY, TWY, APRON, TAXI, SID, STAR, IAP
   - SFC, AMSL, AGL, MSL
   - All coordinates, frequencies, measurements
   - All dates and times in original format
   - Airport codes (RKSI, RJJJ, etc.)

3. Improve grammar and sentence structure:
   - Fix incomplete sentences
   - Add proper articles (a, an, the)
   - Use proper verb tenses
   - Make sentences clear and readable

4. Translate specific aviation terms:
   - 'CLOSED' → 'CLOSED'
   - 'PAVEMENT CONSTRUCTION' → 'PAVEMENT CONSTRUCTION'
   - 'OUTAGES' → 'OUTAGES'
   - 'PREDICTED FOR' → 'PREDICTED FOR'
   - 'WILL TAKE PLACE' → 'WILL TAKE PLACE'
   - 'ESTABLISHMENT OF' → 'ESTABLISHMENT OF'
   - 'INFORMATION OF' → 'INFORMATION OF'
   - 'CIRCLE' → 'CIRCLE'
   - 'CENTERED' → 'CENTERED'
   - 'DUE TO' → 'DUE TO'

Summary Rules:
1. NEVER include the following:
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
   - Do not translate "L/R" to "LEFT/RIGHT"
   - Keep the space between runway number and L/R

Please provide translation and summary for each NOTAM in the specified format."""
    
    def parse_integrated_response(self, response: str, notam_count: int) -> List[Dict[str, str]]:
        """
        통합 응답 파싱 (번역 + 요약)
        
        Args:
            response: 모델 응답 텍스트
            notam_count: 예상 NOTAM 개수
            
        Returns:
            파싱된 결과 리스트
        """
        results = []
        
        # 한국어 응답인 경우 전체를 번역으로 처리
        if '**주요 내용:**' in response or '**상세 내용:**' in response:
            # 한국어 구조화된 응답 파싱
            translation = response.strip()
            summary = ""
            
            # 주요 내용에서 요약 추출
            if '**주요 내용:**' in response:
                lines = response.split('\n')
                for i, line in enumerate(lines):
                    if '**주요 내용:**' in line:
                        # 다음 비어있지 않은 줄이 요약
                        for j in range(i + 1, len(lines)):
                            next_line = lines[j].strip()
                            if next_line and not next_line.startswith('**'):
                                summary = next_line.replace('*', '').strip()
                                break
                        break
            
            results.append({
                'translation': translation,
                'summary': summary
            })
            return results
        
        # 기존 영어 응답 파싱 로직
        lines = response.strip().split('\n')
        
        current_notam = None
        current_translation = ""
        current_summary = ""
        in_translation = False
        in_summary = False
        
        for line in lines:
            line = line.strip()
            
            # NOTAM 번호 감지
            if line.startswith('NOTAM'):
                # 이전 NOTAM 저장
                if current_notam is not None:
                    results.append({
                        'translation': current_translation.strip(),
                        'summary': current_summary.strip()
                    })
                
                # 새 NOTAM 시작
                current_notam = line
                current_translation = ""
                current_summary = ""
                in_translation = False
                in_summary = False
                continue
            
            # 번역 섹션 감지
            if line.startswith('번역:') or line.startswith('Translation:'):
                in_translation = True
                in_summary = False
                current_translation = line.split(':', 1)[1].strip() if ':' in line else ""
                continue
            
            # 요약 섹션 감지
            if line.startswith('요약:') or line.startswith('Summary:'):
                in_translation = False
                in_summary = True
                current_summary = line.split(':', 1)[1].strip() if ':' in line else ""
                continue
            
            # 내용 추가
            if in_translation and line:
                current_translation += " " + line
            elif in_summary and line:
                current_summary += " " + line
        
        # 마지막 NOTAM 저장
        if current_notam is not None:
            results.append({
                'translation': current_translation.strip(),
                'summary': current_summary.strip()
            })
        
        # 결과가 부족하면 기본값으로 채움
        while len(results) < notam_count:
            results.append({
                'translation': '번역 실패',
                'summary': '요약 실패'
            })
        
        # 결과가 너무 많으면 잘라냄
        results = results[:notam_count]
        
        return results
    
    def extract_e_section(self, notam_text: str) -> str:
        """
        NOTAM에서 E 섹션 추출 (사용하지 않음 - 이미 추출된 original_text 사용)
        이 함수는 하위 호환성을 위해 유지되지만 실제로는 사용되지 않습니다.
        
        Args:
            notam_text: NOTAM 텍스트
            
        Returns:
            E 섹션 내용
        """
        if not notam_text:
            return ""
        
        # E 섹션 패턴 찾기 (개선된 패턴 - 순서 변경)
        e_patterns = [
            r'E\)\s*(.*)',  # 전체 텍스트 패턴 (우선순위 1)
            r'^E\)\s*(.*?)(?=\n[A-Z]\)|$)',  # 줄바꿈 기준 패턴 (우선순위 2)
            r'E\)\s*(.*?)(?=\s*[A-Z]\)|$)',  # 기존 패턴 (우선순위 3)
        ]
        
        for pattern in e_patterns:
            match = re.search(pattern, notam_text, re.DOTALL | re.IGNORECASE)
            if match:
                e_section = match.group(1).strip()
                # 메타데이터 제거 (RMK는 중요한 정보이므로 제거하지 않음)
                e_section = re.sub(r'CREATED:.*$', '', e_section, flags=re.DOTALL).strip()
                e_section = re.sub(r'SOURCE:.*$', '', e_section, flags=re.DOTALL).strip()
                e_section = re.sub(r'COMMENT\).*$', '', e_section, flags=re.DOTALL).strip()
                
                # E 섹션이 있으면 반환
                if e_section:
                    return e_section
        
        # E 섹션을 찾지 못한 경우 전체 텍스트에서 핵심 내용만 추출
        cleaned_text = notam_text.strip()
        
        # 날짜 패턴 제거 (예: 20FEB25 00:00 - UFN 또는 03SEP25 23:11 - 02OCT25 23:59)
        cleaned_text = re.sub(r'\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2}\s*-\s*(?:UFN|\d{2}[A-Z]{3}\d{2}\s+\d{2}:\d{2})', '', cleaned_text)
        
        # 공항 코드와 NOTAM 번호 제거 (예: RKSI COAD01/25)
        cleaned_text = re.sub(r'[A-Z]{4}\s+[A-Z0-9]+/\d{2}', '', cleaned_text)
        
        # 메타데이터 제거 (RMK는 중요한 정보이므로 제거하지 않음)
        cleaned_text = re.sub(r'CREATED:.*$', '', cleaned_text, flags=re.DOTALL).strip()
        cleaned_text = re.sub(r'SOURCE:.*$', '', cleaned_text, flags=re.DOTALL).strip()
        cleaned_text = re.sub(r'COMMENT\).*$', '', cleaned_text, flags=re.DOTALL).strip()
        
        # 연속된 공백 정리
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        
        # 빈 문자열이면 원본 반환
        if not cleaned_text:
            return notam_text.strip()
        
        return cleaned_text
    
    def _create_fallback_results(self, notams_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """폴백 결과 생성 (API 비활성화 시)"""
        results = []
        for notam in notams_data:
            enhanced_notam = notam.copy()
            enhanced_notam.update({
                'korean_translation': notam.get('description', ''),
                'korean_summary': 'API 비활성화',
                'english_translation': notam.get('description', ''),
                'english_summary': 'API disabled',
                'e_section': self.extract_e_section(notam.get('description', ''))
            })
            results.append(enhanced_notam)
        return results
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 반환"""
        return {
            'cache_enabled': self.cache_enabled,
            'cache_size': len(self.cache),
            'cache_keys': list(self.cache.keys())[:10]  # 처음 10개 키만
        }
    
    def clear_cache(self):
        """캐시 초기화"""
        self.cache.clear()
        self.logger.info("캐시가 초기화되었습니다.")
    
    def process_notams_individual(self, notams_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        NOTAM들을 개별 처리 (배치 처리 문제 해결)
        
        Args:
            notams_data: NOTAM 데이터 리스트
            
        Returns:
            번역 및 요약이 완료된 NOTAM 리스트
        """
        if not notams_data:
            return []
        
        start_time = time.time()
        
        # 번역 전 NOTAM 데이터 상세 로깅 및 고유 ID 추가
        self.logger.info(f"=== 개별 처리 시작: {len(notams_data)}개 NOTAM ===")
        for i, notam in enumerate(notams_data):
            # 고유 식별자 추가
            notam['_internal_id'] = f"{notam.get('notam_number', 'N/A')}_{notam.get('airport_code', 'N/A')}_{i}"
            self.logger.info(f"NOTAM {i+1}: {notam.get('notam_number', 'N/A')} ({notam.get('airport_code', 'N/A')}) [ID: {notam['_internal_id']}]")
            self.logger.info(f"  원문: {notam.get('description', '')[:100]}...")
        
        # 이미 추출된 원문(original_text) 사용 - E 섹션 재추출하지 않음
        original_texts = []
        for i, notam in enumerate(notams_data):
            # original_text가 있으면 그것을 사용, 없으면 description 사용
            original_text = notam.get('original_text', notam.get('description', ''))
            
            # HTML 태그 제거 (색상 스타일 제거)
            if original_text:
                # <span> 태그와 style 속성 제거
                import re
                clean_text = re.sub(r'<span[^>]*>', '', original_text)
                clean_text = re.sub(r'</span>', '', clean_text)
                clean_text = re.sub(r'<[^>]+>', '', clean_text)  # 기타 HTML 태그 제거
                clean_text = clean_text.strip()
            else:
                clean_text = ''
            
            original_texts.append(clean_text)
            self.logger.debug(f"NOTAM {i+1} 원문 사용: {clean_text[:100]}...")
        
        # e_sections를 original_texts로 변경
        e_sections = original_texts
        
        # 개별 처리로 전환 (배치 처리 문제 해결)
        self.logger.info(f"개별 처리 모드로 전환: {len(notams_data)}개 NOTAM")
        
        # 모든 NOTAM을 개별적으로 처리 (병렬 처리 최적화)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 각 NOTAM에 대해 개별 처리 작업 생성
            futures = {}
            for i, notam in enumerate(notams_data):
                e_section = e_sections[i]
                future = executor.submit(self.process_single_notam_complete, notam, e_section, i)
                futures[future] = i
            
            # 결과 수집 (완료 순서대로)
            results = [None] * len(notams_data)
            completed_count = 0
            
            for future in as_completed(futures):
                notam_idx = futures[future]
                try:
                    result = future.result()
                    results[notam_idx] = result
                    completed_count += 1
                    self.logger.info(f"NOTAM {notam_idx+1} 개별 처리 완료 ({completed_count}/{len(notams_data)}): {result.get('notam_number', 'N/A')} ({result.get('airport_code', 'N/A')})")
                except Exception as e:
                    self.logger.error(f"NOTAM {notam_idx+1} 개별 처리 실패: {e}")
                    # 실패 시 폴백 결과 생성
                    results[notam_idx] = self._create_fallback_result(notams_data[notam_idx], e_sections[notam_idx])
                    completed_count += 1
            
            # None 값 제거 (실패한 경우)
            results = [r for r in results if r is not None]
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        self.logger.info(f"개별 처리 완료: {len(results)}개 NOTAM, {processing_time:.2f}초")
        self.logger.info(f"평균 처리 시간: {processing_time/len(results):.2f}초/NOTAM")
        
        return results
