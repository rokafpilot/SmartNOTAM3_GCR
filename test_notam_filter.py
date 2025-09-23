#!/usr/bin/env python3
"""
NOTAM 필터링 테스트 스크립트
실제 PDF에서 추출된 텍스트로 필터링 로직을 테스트
"""

from src.notam_filter import NOTAMFilter
import os

def test_notam_filtering():
    """실제 PDF 텍스트로 NOTAM 필터링 테스트"""
    
    # 가장 최근의 변환된 텍스트 파일 찾기
    temp_dir = "/Users/sunghyunkim/Documents/Documents - Sunghyun/AI/transformer/SmartNOTAM3/temp"
    if os.path.exists(temp_dir):
        txt_files = [f for f in os.listdir(temp_dir) if f.endswith('.txt')]
        if txt_files:
            latest_file = max(txt_files, key=lambda x: os.path.getctime(os.path.join(temp_dir, x)))
            txt_path = os.path.join(temp_dir, latest_file)
            
            print(f"테스트 파일: {txt_path}")
            
            with open(txt_path, 'r', encoding='utf-8') as f:
                text = f.read()
            
            print(f"전체 텍스트 길이: {len(text)} 문자")
            print("=" * 50)
            
            # NOTAM 필터 생성
            notam_filter = NOTAMFilter()
            
            # 필터링 수행
            filtered_notams = notam_filter.filter_korean_air_notams(text)
            
            print(f"필터링된 NOTAM 개수: {len(filtered_notams)}")
            print("=" * 50)
            
            # 처음 3개 NOTAM만 출력
            for i, notam in enumerate(filtered_notams[:3]):
                print(f"\n### NOTAM {i+1} ###")
                print(f"ID: {notam.get('id', 'NO_ID')}")
                print(f"원문 길이: {len(notam.get('raw_text', ''))}")
                print(f"원문 미리보기: {notam.get('raw_text', '')[:200]}...")
                print("-" * 30)
            
            return filtered_notams
        else:
            print("temp 디렉토리에 텍스트 파일이 없습니다.")
            return []
    else:
        print("temp 디렉토리가 존재하지 않습니다.")
        return []

if __name__ == "__main__":
    test_notam_filtering()