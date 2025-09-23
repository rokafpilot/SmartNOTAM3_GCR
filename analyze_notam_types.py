#!/usr/bin/env python3
"""
개선된 NOTAM 필터링 분석
"""

import sys
import os
sys.path.append('/Users/sunghyunkim/Documents/Documents - Sunghyun/AI/transformer/SmartNOTAM3/src')

from pdf_converter import PDFConverter
from notam_filter import NOTAMFilter
import re

def analyze_notam_content():
    """NOTAM 내용 분석"""
    
    # 최신 temp 파일 읽기
    temp_file = "/Users/sunghyunkim/Documents/Documents - Sunghyun/AI/transformer/SmartNOTAM3/temp/Notam-20250916 (2)_20250922_214832.txt"
    
    with open(temp_file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    print(f"텍스트 크기: {len(text):,} 문자")
    
    # NOTAM 필터링
    filter_instance = NOTAMFilter()
    filtered_notams = filter_instance.filter_korean_air_notams(text)
    
    print(f"필터링된 NOTAM 개수: {len(filtered_notams)}개")
    
    # 각 NOTAM 타입 분석
    notam_types = {}
    technical_info_count = 0
    actual_notam_count = 0
    
    for i, notam in enumerate(filtered_notams):
        # Dict에서 raw_text 추출
        if isinstance(notam, dict):
            notam_text = notam.get('raw_text', str(notam))
        else:
            notam_text = str(notam)
        
        # 기술정보 체크
        if any(keyword in notam_text.upper() for keyword in [
            'RUNWAY :', 'TAXIWAY :', 'COMPANY RADIO', 'COMPANY MINIMA', 
            'TECHNICAL INFORMATION', 'DEPARTURE AIRPORT', 'FREQUENCY'
        ]):
            technical_info_count += 1
            if i < 5:  # 처음 5개만 출력
                print(f"\n=== 기술정보 {technical_info_count} ===")
                print(notam_text[:150] + "...")
        else:
            # 실제 NOTAM ID 패턴 체크
            if re.search(r'[A-Z]\d{4}/\d{2}', notam_text):
                actual_notam_count += 1
                if actual_notam_count <= 5:  # 처음 5개만 출력
                    print(f"\n=== 실제 NOTAM {actual_notam_count} ===")
                    print(notam_text[:150] + "...")
    
    print(f"\n=== 분석 결과 ===")
    print(f"총 필터링된 항목: {len(filtered_notams)}개")
    print(f"기술정보: {technical_info_count}개")
    print(f"실제 NOTAM: {actual_notam_count}개")
    print(f"기타: {len(filtered_notams) - technical_info_count - actual_notam_count}개")
    
    return len(filtered_notams)

if __name__ == "__main__":
    try:
        result_count = analyze_notam_content()
        print(f"\n최종 결과: {result_count}개 항목 분석됨")
    except Exception as e:
        print(f"분석 중 오류: {e}")
        import traceback
        traceback.print_exc()