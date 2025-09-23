"""
All-in-One NOTAM Processor
모든 기능을 통합한 NOTAM 처리 메인 스크립트
기존 notam_all_in_one.py 참조하여 구현
"""

import os
import sys
import logging
from datetime import datetime
from typing import List, Dict, Optional

# 프로젝트 모듈 import
from src.pdf_converter import PDFConverter
from src.notam_filter import NOTAMFilter
from src.notam_translator import NOTAMTranslator

class SmartNOTAMProcessor:
    """
    Smart NOTAM 통합 처리기
    PDF → 텍스트 변환 → 필터링 → 번역/요약 → 결과 출력
    """
    
    def __init__(self, openai_api_key: Optional[str] = None):
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # 모듈 인스턴스 생성
        self.pdf_converter = PDFConverter()
        self.notam_filter = NOTAMFilter()
        self.notam_translator = NOTAMTranslator(api_key=openai_api_key)
        
        self.logger.info("Smart NOTAM Processor 초기화 완료")
    
    def setup_logging(self):
        """로깅 설정"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('notam_processor.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
    
    def process_pdf_file(self, pdf_path: str, use_ai: bool = False) -> Dict:
        """
        PDF 파일을 처리하여 NOTAM 정보 추출 및 번역/요약
        
        Args:
            pdf_path (str): PDF 파일 경로
            use_ai (bool): AI 번역/요약 사용 여부
            
        Returns:
            Dict: 처리 결과
        """
        try:
            self.logger.info(f"PDF 파일 처리 시작: {pdf_path}")
            
            # 1. PDF → 텍스트 변환
            self.logger.info("1. PDF 텍스트 변환 중...")
            text = self.pdf_converter.convert_pdf_to_text(pdf_path)
            
            if not text.strip():
                raise ValueError("PDF에서 텍스트를 추출할 수 없습니다.")
            
            self.logger.info(f"텍스트 추출 완료: {len(text)} 문자")
            
            # 2. NOTAM 필터링
            self.logger.info("2. NOTAM 필터링 중...")
            notams = self.notam_filter.filter_korean_air_notams(text)
            
            if not notams:
                self.logger.warning("대한항공 관련 NOTAM을 찾을 수 없습니다.")
                return {
                    'success': False,
                    'message': '대한항공 관련 NOTAM을 찾을 수 없습니다.',
                    'notams': []
                }
            
            self.logger.info(f"{len(notams)}개의 NOTAM 발견")
            
            # 3. 번역 및 요약
            self.logger.info("3. NOTAM 번역 및 요약 중...")
            processed_notams = self.notam_translator.translate_multiple_notams(notams)
            
            # 4. 지도용 좌표 데이터 추출
            self.logger.info("4. 좌표 데이터 추출 중...")
            map_data = self.notam_filter.get_coordinates_for_map(processed_notams)
            
            # 5. 브리핑 생성
            self.logger.info("5. 비행 브리핑 생성 중...")
            briefing = self.notam_translator.create_flight_briefing(processed_notams)
            
            result = {
                'success': True,
                'message': f'{len(processed_notams)}개의 NOTAM 처리 완료',
                'notams': processed_notams,
                'map_data': map_data,
                'briefing': briefing,
                'stats': {
                    'total_notams': len(processed_notams),
                    'with_coordinates': len(map_data),
                    'original_text_length': len(text),
                    'processed_at': datetime.now().isoformat()
                }
            }
            
            self.logger.info("PDF 파일 처리 완료")
            return result
            
        except Exception as e:
            self.logger.error(f"PDF 처리 중 오류: {str(e)}")
            return {
                'success': False,
                'message': f'처리 중 오류 발생: {str(e)}',
                'notams': []
            }
    
    def process_text_input(self, text: str, use_ai: bool = False) -> Dict:
        """
        텍스트 입력을 직접 처리
        
        Args:
            text (str): NOTAM 텍스트
            use_ai (bool): AI 번역/요약 사용 여부
            
        Returns:
            Dict: 처리 결과
        """
        try:
            self.logger.info("텍스트 입력 처리 시작")
            
            # NOTAM 필터링
            notams = self.notam_filter.filter_korean_air_notams(text)
            
            if not notams:
                return {
                    'success': False,
                    'message': '대한항공 관련 NOTAM을 찾을 수 없습니다.',
                    'notams': []
                }
            
            # 번역 및 요약
            processed_notams = self.notam_translator.translate_multiple_notams(notams)
            
            # 좌표 데이터 추출
            map_data = self.notam_filter.get_coordinates_for_map(processed_notams)
            
            # 브리핑 생성
            briefing = self.notam_translator.create_flight_briefing(processed_notams)
            
            return {
                'success': True,
                'message': f'{len(processed_notams)}개의 NOTAM 처리 완료',
                'notams': processed_notams,
                'map_data': map_data,
                'briefing': briefing
            }
            
        except Exception as e:
            self.logger.error(f"텍스트 처리 중 오류: {str(e)}")
            return {
                'success': False,
                'message': f'처리 중 오류 발생: {str(e)}',
                'notams': []
            }
    
    def filter_notams_by_criteria(self, notams: List[Dict], **filters) -> List[Dict]:
        """
        다양한 조건으로 NOTAM 필터링
        
        Args:
            notams: NOTAM 리스트
            **filters: 필터 조건들
            
        Returns:
            List[Dict]: 필터링된 NOTAM 리스트
        """
        filtered = notams
        
        # 날짜 범위 필터
        if filters.get('start_date') or filters.get('end_date'):
            filtered = self.notam_filter.filter_by_date_range(
                filtered, 
                filters.get('start_date'), 
                filters.get('end_date')
            )
        
        # 공항 필터
        if filters.get('airports'):
            filtered = self.notam_filter.filter_by_airport(
                filtered, 
                filters['airports']
            )
        
        # 타입 필터
        if filters.get('types'):
            filtered = self.notam_filter.filter_by_type(
                filtered, 
                filters['types']
            )
        
        return filtered
    
    def export_results(self, result: Dict, output_format: str = 'json', output_path: Optional[str] = None) -> str:
        """
        처리 결과를 파일로 출력
        
        Args:
            result: 처리 결과
            output_format: 출력 형식 ('json', 'txt', 'csv')
            output_path: 출력 경로 (None이면 자동 생성)
            
        Returns:
            str: 생성된 파일 경로
        """
        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f'notam_result_{timestamp}.{output_format}'
        
        try:
            if output_format.lower() == 'json':
                import json
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
            
            elif output_format.lower() == 'txt':
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write("=== Smart NOTAM 처리 결과 ===\n\n")
                    f.write(f"처리 시간: {datetime.now()}\n")
                    f.write(f"총 NOTAM 수: {len(result.get('notams', []))}\n\n")
                    
                    if result.get('briefing'):
                        f.write("=== 비행 브리핑 ===\n")
                        f.write(result['briefing'])
                        f.write("\n\n")
                    
                    f.write("=== NOTAM 상세 정보 ===\n")
                    for i, notam in enumerate(result.get('notams', []), 1):
                        f.write(f"\n{i}. NOTAM {notam.get('id', 'N/A')}\n")
                        f.write(f"   공항: {', '.join(notam.get('airport_codes', []))}\n")
                        f.write(f"   유효기간: {notam.get('effective_time', 'N/A')} ~ {notam.get('expiry_time', 'N/A')}\n")
                        f.write(f"   원문: {notam.get('description', 'N/A')}\n")
                        if notam.get('translated_description'):
                            f.write(f"   번역: {notam['translated_description']}\n")
                        if notam.get('summary'):
                            f.write(f"   요약: {notam['summary']}\n")
            
            elif output_format.lower() == 'csv':
                import csv
                with open(output_path, 'w', newline='', encoding='utf-8') as f:
                    if result.get('notams'):
                        fieldnames = ['id', 'type', 'airport_codes', 'effective_time', 'expiry_time', 
                                    'description', 'translated_description', 'summary', 'coordinates']
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        
                        for notam in result['notams']:
                            row = {
                                'id': notam.get('id', ''),
                                'type': notam.get('type', ''),
                                'airport_codes': ', '.join(notam.get('airport_codes', [])),
                                'effective_time': notam.get('effective_time', ''),
                                'expiry_time': notam.get('expiry_time', ''),
                                'description': notam.get('description', ''),
                                'translated_description': notam.get('translated_description', ''),
                                'summary': notam.get('summary', ''),
                                'coordinates': str(notam.get('coordinates', ''))
                            }
                            writer.writerow(row)
            
            self.logger.info(f"결과 파일 생성 완료: {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"파일 출력 중 오류: {str(e)}")
            raise


def main():
    """커맨드라인 인터페이스"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Smart NOTAM Processor')
    parser.add_argument('input', help='PDF 파일 경로 또는 텍스트 파일 경로')
    parser.add_argument('--ai', action='store_true', help='AI 번역/요약 사용')
    parser.add_argument('--output-format', choices=['json', 'txt', 'csv'], default='json', help='출력 형식')
    parser.add_argument('--output', help='출력 파일 경로')
    parser.add_argument('--openai-key', help='OpenAI API 키')
    
    args = parser.parse_args()
    
    # 환경 변수에서 API 키 가져오기
    openai_key = args.openai_key or os.getenv('OPENAI_API_KEY')
    
    # 프로세서 인스턴스 생성
    processor = SmartNOTAMProcessor(openai_api_key=openai_key)
    
    # 파일 처리
    if args.input.lower().endswith('.pdf'):
        result = processor.process_pdf_file(args.input, use_ai=args.ai)
    else:
        # 텍스트 파일로 가정
        with open(args.input, 'r', encoding='utf-8') as f:
            text = f.read()
        result = processor.process_text_input(text, use_ai=args.ai)
    
    # 결과 출력
    if result['success']:
        print(f"✅ {result['message']}")
        
        # 파일로 저장
        output_path = processor.export_results(result, args.output_format, args.output)
        print(f"📁 결과 파일: {output_path}")
        
        # 간단한 통계 출력
        print(f"\n📊 처리 통계:")
        print(f"   - 총 NOTAM 수: {len(result['notams'])}")
        print(f"   - 좌표 정보 포함: {len(result.get('map_data', []))}")
        
    else:
        print(f"❌ {result['message']}")
        sys.exit(1)


if __name__ == "__main__":
    main()