#!/usr/bin/env python3
"""
개선된 PDF 변환기 테스트 - 카테고리 헤더 기반
"""
import sys
sys.path.append('src')

from src.pdf_converter import PDFConverter
from src.notam_filter import NOTAMFilter

def test_category_based_extraction():
    """카테고리 헤더 기반 NOTAM 추출 테스트"""
    
    file_path = "/Users/sunghyunkim/Documents/Documents - Sunghyun/AI/transformer/SmartNOTAM3/temp/20250920_203505_Notam-20250916_2_20250920_203506.txt"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_text = f.read()
        
        print("카테고리 헤더 기반 NOTAM 추출 테스트 시작...")
        print(f"원본 텍스트 크기: {len(original_text)} 문자")
        
        # PDF 변환기 초기화
        converter = PDFConverter()
        
        # 실제 NOTAM만 추출
        notam_only_text = converter.extract_actual_notams(original_text)
        print(f"카테고리 헤더 기반 추출: {len(notam_only_text)} 문자")
        print(f"크기 감소: {len(original_text) - len(notam_only_text)} 문자 ({((len(original_text) - len(notam_only_text)) / len(original_text) * 100):.1f}%)")
        
        # 추출된 텍스트의 첫 부분 확인
        print("\n=== 추출된 NOTAM 텍스트 (첫 1500자) ===")
        print(notam_only_text[:1500])
        
        # NOTAM 필터링도 테스트
        print("\n=== NOTAM 필터링 테스트 ===")
        filter_obj = NOTAMFilter()
        filtered_notams = filter_obj.filter_korean_air_notams(notam_only_text)
        print(f"필터링된 NOTAM 개수: {len(filtered_notams)}")
        
        # 처음 10개 NOTAM 정보 표시
        print("\n=== 처음 10개 NOTAM ===")
        for i, notam in enumerate(filtered_notams[:10]):
            print(f"NOTAM {i+1}:")
            print(f"  ID: {notam.get('id', 'N/A')}")
            print(f"  공항: {notam.get('airport_code', 'N/A')}")
            print(f"  시간: {notam.get('effective_time', 'N/A')} - {notam.get('expiry_time', 'N/A')}")
            print(f"  설명: {notam.get('description', 'N/A')[:80]}...")
            print()
        
        # 임시 파일로 저장
        temp_file = converter.save_to_temp_file(notam_only_text, "category_filtered_notams")
        print(f"\n카테고리 필터링된 NOTAM 저장: {temp_file}")
        
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_category_based_extraction()