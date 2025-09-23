#!/usr/bin/env python3
"""
실제 NOTAM 파일로 필터링 테스트
"""
import sys
sys.path.append('src')

from src.notam_filter import NOTAMFilter

def test_real_notam_file():
    """실제 NOTAM 파일 테스트"""
    file_path = "/Users/sunghyunkim/Documents/Documents - Sunghyun/AI/transformer/SmartNOTAM3/temp/20250920_203505_Notam-20250916_2_20250920_203506.txt"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print("실제 NOTAM 파일 필터링 테스트 시작...")
        print(f"파일 크기: {len(content)} 문자")
        
        filter_obj = NOTAMFilter()
        
        # 섹션 분할
        sections = filter_obj._split_notams(content)
        print(f"\n총 {len(sections)}개 섹션 발견")
        
        excluded_count = 0
        included_count = 0
        
        print("\n=== 섹션별 분석 ===")
        for i, section in enumerate(sections[:10]):  # 처음 10개만 표시
            first_line = section.split('\n')[0][:100]
            should_exclude = filter_obj._should_exclude_section(section)
            
            if should_exclude:
                excluded_count += 1
                print(f"섹션 {i+1}: [제외] {first_line}...")
            else:
                included_count += 1
                print(f"섹션 {i+1}: [포함] {first_line}...")
        
        # 전체 카운트
        for section in sections:
            if filter_obj._should_exclude_section(section):
                excluded_count += 1
            else:
                included_count += 1
        
        print(f"\n총 요약:")
        print(f"- 제외된 섹션: {excluded_count}개")
        print(f"- 포함된 섹션: {included_count}개")
        
        # 전체 필터링
        filtered_notams = filter_obj.filter_korean_air_notams(content)
        print(f"\n최종 필터링된 NOTAM: {len(filtered_notams)}개")
        
        for i, notam in enumerate(filtered_notams[:5]):  # 처음 5개만 표시
            print(f"\nNOTAM {i+1}:")
            print(f"  ID: {notam.get('id', 'N/A')}")
            print(f"  공항: {notam.get('airport_code', 'N/A')}")
            print(f"  설명: {notam.get('description', 'N/A')[:150]}...")
        
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    test_real_notam_file()