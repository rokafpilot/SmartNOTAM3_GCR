"""
최적화된 NOTAM 번역 및 요약 시스템

주요 최적화 기능:
1. 배치 처리: 여러 NOTAM을 한 번에 처리
2. 병렬 처리: 동시 API 호출
3. 통합 처리: 번역과 요약을 한 번에
4. 스마트 캐싱: 유사한 내용 재사용
"""

import os
import asyncio
import logging
import time
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import google.generativeai as genai
from dotenv import load_dotenv
import re

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logger = logging.getLogger(__name__)

@dataclass
class NotamBatch:
    """NOTAM 배치 처리를 위한 데이터 클래스"""
    notams: List[Dict[str, Any]]
    batch_id: str
    language: str  # 'en' 또는 'ko'

class TranslationCache:
    """번역 결과 캐싱 시스템"""
    
    def __init__(self, max_size: int = 1000):
        self.cache = {}
        self.max_size = max_size
        self.access_count = {}
    
    def get_hash(self, text: str) -> str:
        """텍스트의 해시값 생성"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def get(self, text: str, operation_type: str) -> Optional[Dict[str, Any]]:
        """캐시에서 결과 조회"""
        key = f"{operation_type}_{self.get_hash(text)}"
        if key in self.cache:
            self.access_count[key] = self.access_count.get(key, 0) + 1
            logger.debug(f"캐시 히트: {operation_type} for {text[:50]}...")
            return self.cache[key]
        return None
    
    def set(self, text: str, operation_type: str, result: Dict[str, Any]):
        """캐시에 결과 저장"""
        if len(self.cache) >= self.max_size:
            # LRU 방식으로 가장 적게 사용된 항목 제거
            least_used = min(self.access_count.items(), key=lambda x: x[1])
            del self.cache[least_used[0]]
            del self.access_count[least_used[0]]
        
        key = f"{operation_type}_{self.get_hash(text)}"
        self.cache[key] = result
        self.access_count[key] = 1
        logger.debug(f"캐시 저장: {operation_type} for {text[:50]}...")

class OptimizedNOTAMTranslator:
    """최적화된 NOTAM 번역기"""
    
    def __init__(self, max_workers: int = 5, batch_size: int = 10):
        """
        초기화
        
        Args:
            max_workers: 병렬 처리 워커 수
            batch_size: 배치 처리 크기
        """
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.cache = TranslationCache()
        
        # Gemini 설정
        self.gemini_enabled = False
        try:
            api_key = os.getenv('GOOGLE_API_KEY')
            if api_key:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel('gemini-1.5-flash')
                self.gemini_enabled = True
                logger.info("Gemini API 초기화 완료")
            else:
                logger.warning("GOOGLE_API_KEY가 설정되지 않음")
        except Exception as e:
            logger.error(f"Gemini 초기화 실패: {str(e)}")
            self.gemini_enabled = False
    
    def extract_e_section(self, notam_text: str) -> str:
        """NOTAM에서 E 섹션 추출"""
        # E) 섹션 추출
        e_pattern = r'E\)\s*(.+?)(?=\n[A-Z]\)|$)'
        e_match = re.search(e_pattern, notam_text, re.DOTALL | re.IGNORECASE)
        
        if e_match:
            e_content = e_match.group(1).strip()
            # 불필요한 공백과 줄바꿈 정리
            e_content = re.sub(r'\s+', ' ', e_content)
            return e_content
        
        # E 섹션이 없으면 전체 텍스트에서 주요 내용 추출
        lines = notam_text.strip().split('\n')
        content_lines = []
        for line in lines:
            line = line.strip()
            if line and not re.match(r'^[A-Z]\)', line):
                content_lines.append(line)
        
        return ' '.join(content_lines) if content_lines else notam_text
    
    def create_batch_prompt(self, notams: List[str], target_language: str, include_summary: bool = True) -> str:
        """배치 처리용 프롬프트 생성"""
        
        if target_language == 'ko':
            lang_instruction = "한국어로 번역"
            summary_instruction = "각 NOTAM의 핵심 내용을 한 줄로 요약" if include_summary else ""
        else:
            lang_instruction = "translate to English"
            summary_instruction = "summarize each NOTAM's key content in one line" if include_summary else ""
        
        # 배치 프롬프트 구성
        prompt_parts = [
            f"You are an aviation NOTAM translation expert. Please {lang_instruction} the following NOTAMs.",
            "",
            "Instructions:",
            f"1. {lang_instruction} each NOTAM accurately",
        ]
        
        if include_summary:
            prompt_parts.append(f"2. {summary_instruction}")
            prompt_parts.append("3. Format: NOTAM_ID|TRANSLATION|SUMMARY")
        else:
            prompt_parts.append("2. Format: NOTAM_ID|TRANSLATION")
        
        prompt_parts.extend([
            "",
            "NOTAMs to process:",
            ""
        ])
        
        # NOTAM 목록 추가
        for i, notam in enumerate(notams, 1):
            prompt_parts.append(f"NOTAM_{i:03d}: {notam}")
            prompt_parts.append("")
        
        return "\n".join(prompt_parts)
    
    def parse_batch_response(self, response: str, notam_count: int, include_summary: bool = True) -> List[Dict[str, str]]:
        """배치 응답 파싱"""
        results = []
        lines = response.strip().split('\n')
        
        current_result = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # NOTAM_ID|TRANSLATION|SUMMARY 형태 파싱
            if '|' in line:
                parts = line.split('|', 2 if include_summary else 1)
                if len(parts) >= 2:
                    notam_id = parts[0].strip()
                    translation = parts[1].strip()
                    summary = parts[2].strip() if include_summary and len(parts) > 2 else ""
                    
                    results.append({
                        'notam_id': notam_id,
                        'translation': translation,
                        'summary': summary
                    })
        
        # 결과가 부족하면 기본값으로 채움
        while len(results) < notam_count:
            results.append({
                'notam_id': f'NOTAM_{len(results)+1:03d}',
                'translation': '번역 실패',
                'summary': '요약 실패' if include_summary else ''
            })
        
        return results[:notam_count]
    
    async def translate_batch_async(self, notams: List[str], target_language: str, include_summary: bool = True) -> List[Dict[str, str]]:
        """비동기 배치 번역"""
        if not self.gemini_enabled:
            return [{'translation': notam, 'summary': ''} for notam in notams]
        
        # 캐시 확인
        batch_key = f"batch_{target_language}_{hashlib.md5(''.join(notams).encode()).hexdigest()}"
        cached = self.cache.get(batch_key, 'batch_translation')
        if cached:
            return cached
        
        try:
            prompt = self.create_batch_prompt(notams, target_language, include_summary)
            
            # 비동기 API 호출
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.model.generate_content, prompt)
                response = await loop.run_in_executor(None, lambda: future.result())
            
            # 응답 파싱
            results = self.parse_batch_response(response.text, len(notams), include_summary)
            
            # 캐시에 저장
            self.cache.set(batch_key, 'batch_translation', results)
            
            return results
            
        except Exception as e:
            logger.error(f"배치 번역 오류: {e}")
            return [{'translation': f'번역 오류: {str(e)}', 'summary': '오류'} for _ in notams]
    
    def translate_batch(self, notams: List[str], target_language: str, include_summary: bool = True) -> List[Dict[str, str]]:
        """동기 배치 번역 (비동기 래퍼)"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self.translate_batch_async(notams, target_language, include_summary)
        )
    
    def process_notams_optimized(self, notams_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """최적화된 NOTAM 처리 (배치 + 병렬)"""
        if not notams_data:
            return []
        
        logger.info(f"최적화된 번역 시작: {len(notams_data)}개 NOTAM")
        start_time = time.time()
        
        # E 섹션 추출
        e_sections = []
        for notam in notams_data:
            e_section = self.extract_e_section(notam.get('description', ''))
            e_sections.append(e_section)
        
        # 배치로 나누기
        batches = []
        for i in range(0, len(e_sections), self.batch_size):
            batch = e_sections[i:i + self.batch_size]
            batches.append(batch)
        
        results = []
        
        # 병렬 배치 처리
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 한국어 번역+요약 작업 제출
            korean_futures = {
                executor.submit(self.translate_batch, batch, 'ko', True): i 
                for i, batch in enumerate(batches)
            }
            
            # 영어 번역+요약 작업 제출
            english_futures = {
                executor.submit(self.translate_batch, batch, 'en', True): i 
                for i, batch in enumerate(batches)
            }
            
            # 결과 수집
            korean_results = {}
            english_results = {}
            
            # 한국어 결과 수집
            for future in as_completed(korean_futures):
                batch_idx = korean_futures[future]
                try:
                    batch_result = future.result()
                    korean_results[batch_idx] = batch_result
                    logger.info(f"한국어 배치 {batch_idx + 1}/{len(batches)} 완료")
                except Exception as e:
                    logger.error(f"한국어 배치 {batch_idx} 오류: {e}")
                    korean_results[batch_idx] = []
            
            # 영어 결과 수집
            for future in as_completed(english_futures):
                batch_idx = english_futures[future]
                try:
                    batch_result = future.result()
                    english_results[batch_idx] = batch_result
                    logger.info(f"영어 배치 {batch_idx + 1}/{len(batches)} 완료")
                except Exception as e:
                    logger.error(f"영어 배치 {batch_idx} 오류: {e}")
                    english_results[batch_idx] = []
        
        # 결과 조합
        korean_flat = []
        english_flat = []
        
        for i in range(len(batches)):
            korean_flat.extend(korean_results.get(i, []))
            english_flat.extend(english_results.get(i, []))
        
        # 최종 결과 구성
        for i, notam in enumerate(notams_data):
            korean_result = korean_flat[i] if i < len(korean_flat) else {}
            english_result = english_flat[i] if i < len(english_flat) else {}
            
            enhanced_notam = notam.copy()
            enhanced_notam.update({
                'korean_translation': korean_result.get('translation', '번역 실패'),
                'korean_summary': korean_result.get('summary', '요약 실패'),
                'english_translation': english_result.get('translation', 'Translation failed'),
                'english_summary': english_result.get('summary', 'Summary failed'),
                'e_section': e_sections[i] if i < len(e_sections) else ''
            })
            results.append(enhanced_notam)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        logger.info(f"최적화된 번역 완료: {len(results)}개 NOTAM, {processing_time:.2f}초")
        logger.info(f"평균 처리 시간: {processing_time/len(results):.2f}초/NOTAM")
        
        return results
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 반환"""
        return {
            'cache_size': len(self.cache.cache),
            'total_access': sum(self.cache.access_count.values()),
            'hit_rate': len(self.cache.cache) / max(sum(self.cache.access_count.values()), 1)
        }

# 편의 함수들
def create_optimized_translator(max_workers: int = 5, batch_size: int = 10) -> OptimizedNOTAMTranslator:
    """최적화된 번역기 생성"""
    return OptimizedNOTAMTranslator(max_workers=max_workers, batch_size=batch_size)

def translate_notams_fast(notams_data: List[Dict[str, Any]], 
                         max_workers: int = 5, 
                         batch_size: int = 10) -> List[Dict[str, Any]]:
    """빠른 NOTAM 번역 (원샷 함수)"""
    translator = create_optimized_translator(max_workers, batch_size)
    return translator.process_notams_optimized(notams_data)

if __name__ == "__main__":
    # 테스트 코드
    logging.basicConfig(level=logging.INFO)
    
    # 샘플 NOTAM 데이터
    sample_notams = [
        {
            'id': 'A1234/25',
            'description': 'E) RWY 24 CLSD DUE TO CONSTRUCTION. COMMENT) RUNWAY CLOSED FOR MAINTENANCE.',
            'airport_code': 'KSEA'
        },
        {
            'id': 'A5678/25',
            'description': 'E) TWY A BTN AIR CARGO RAMP CLSD. COMMENT) TAXIWAY CLOSED.',
            'airport_code': 'KLAX'
        }
    ]
    
    # 성능 테스트
    print("=== 최적화된 번역 시스템 테스트 ===")
    start_time = time.time()
    
    results = translate_notams_fast(sample_notams, max_workers=3, batch_size=5)
    
    end_time = time.time()
    
    print(f"처리 시간: {end_time - start_time:.2f}초")
    print(f"처리된 NOTAM: {len(results)}개")
    
    for result in results:
        print(f"\nNOTAM {result['id']}:")
        print(f"  한국어: {result.get('korean_translation', 'N/A')}")
        print(f"  요약: {result.get('korean_summary', 'N/A')}")