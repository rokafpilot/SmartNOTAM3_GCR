#!/usr/bin/env python3
"""
업데이트된 카테고리 헤더 기반 NOTAM 추출 테스트
"""

import sys
import os
sys.path.append('/Users/sunghyunkim/Documents/Documents - Sunghyun/AI/transformer/SmartNOTAM3/src')

from pdf_converter import PDFConverter
from notam_filter import NOTAMFilter

def test_updated_extraction():
    """업데이트된 카테고리 헤더 기반 추출 테스트"""
    
    # PDF 변환
    converter = PDFConverter()
    pdf_path = "/Users/sunghyunkim/Documents/Documents - Sunghyun/AI/transformer/SmartNOTAM3/templates/Notam-20250916 (2).pdf"
    
    print("=== 업데이트된 PDF 변환 테스트 ===")
    text = converter.convert_pdf_to_text(pdf_path, save_temp=True)
    
    print(f"변환된 텍스트 크기: {len(text):,} 문자")
    
    # NOTAM 필터링
    filter_instance = NOTAMFilter()
    filtered_notams = filter_instance.filter_korean_air_notams(text)
    
    print(f"필터링된 NOTAM 개수: {len(filtered_notams)}개")
    
    # 크기 비교
    if len(text) > 0:
        reduction_percent = ((len(text) - len(''.join(filtered_notams))) / len(text)) * 100
        print(f"텍스트 크기 감소: {reduction_percent:.1f}%")
    
    # 처음 3개 NOTAM 샘플 출력
    print("\n=== 필터링된 NOTAM 샘플 (처음 3개) ===")
    for i, notam in enumerate(filtered_notams[:3]):
        print(f"\n--- NOTAM {i+1} ---")
        print(notam[:200] + "..." if len(notam) > 200 else notam)
    
    return len(filtered_notams)

if __name__ == "__main__":
    try:
        result_count = test_updated_extraction()
        print(f"\n최종 결과: {result_count}개 NOTAM 추출됨")
    except Exception as e:
        print(f"테스트 중 오류: {e}")
        import traceback
        traceback.print_exc()