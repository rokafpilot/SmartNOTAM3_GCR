#!/usr/bin/env python3
"""
PROC 추출 원인 디버깅
"""

import sys
import os
sys.path.append('src')

from flight_info_extractor import FlightInfoExtractor

def debug_proc_extraction():
    """PROC 추출 원인 디버깅"""
    
    # 최신 NOTAM 파일 찾기
    temp_files = [f for f in os.listdir('temp') if f.endswith('.txt')]
    if not temp_files:
        print("❌ temp 폴더에 NOTAM 파일이 없습니다.")
        return
    
    latest_file = sorted(temp_files)[-1]
    file_path = os.path.join('temp', latest_file)
    
    print(f"🔍 테스트 파일: {file_path}")
    
    # 파일 읽기
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 추출기 초기화
    extractor = FlightInfoExtractor()
    
    print("\n🔍 PROC 추출 원인 분석:")
    
    # 전체 텍스트에서 PROC 검색
    lines = content.split('\n')
    print(f"\n🔍 전체 텍스트에서 'PROC' 검색:")
    for i, line in enumerate(lines):
        if 'PROC' in line.upper():
            print(f"  라인 {i+1}: {line.strip()}")
    
    # DEP, DEST, ALTN 키워드 검색
    print(f"\n🔍 DEP, DEST, ALTN 키워드 검색:")
    for i, line in enumerate(lines):
        line_upper = line.upper().strip()
        if 'DEP:' in line_upper or 'DEST:' in line_upper or 'ALTN:' in line_upper:
            print(f"  라인 {i+1}: {line.strip()}")
    
    # PACKAGE별 추출 테스트
    print(f"\n🔍 PACKAGE별 추출 테스트:")
    package_info = extractor._extract_by_packages(content)
    print(f"📦 PACKAGE 정보: {package_info}")
    
    # 백업 추출 테스트
    print(f"\n🔍 백업 추출 테스트:")
    cleaned_text = extractor._clean_text(content)
    
    dep_backup = extractor._extract_airport_by_keyword(cleaned_text, 'dep')
    dest_backup = extractor._extract_airport_by_keyword(cleaned_text, 'dest')
    altn_backup = extractor._extract_airport_by_keyword(cleaned_text, 'altn')
    
    print(f"DEP 백업: {dep_backup}")
    print(f"DEST 백업: {dest_backup}")
    print(f"ALTN 백업: {altn_backup}")

if __name__ == "__main__":
    debug_proc_extraction()
