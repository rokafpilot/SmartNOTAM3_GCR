#!/usr/bin/env python3
"""
특정 NOTAM의 상세 정보를 확인하는 스크립트
"""

from src.notam_filter import NOTAMFilter
import os

def test_specific_notam():
    """Z0582/25 NOTAM의 상세 정보 확인"""
    
    # 가장 최근의 변환된 텍스트 파일 찾기
    temp_dir = "/Users/sunghyunkim/Documents/Documents - Sunghyun/AI/transformer/SmartNOTAM3/temp"
    if os.path.exists(temp_dir):
        txt_files = [f for f in os.listdir(temp_dir) if f.endswith('.txt')]
        if txt_files:
            latest_file = max(txt_files, key=lambda x: os.path.getctime(os.path.join(temp_dir, x)))
            txt_path = os.path.join(temp_dir, latest_file)
            
            with open(txt_path, 'r', encoding='utf-8') as f:
                text = f.read()
            
            # NOTAM 필터 생성
            notam_filter = NOTAMFilter()
            
            # 필터링 수행
            filtered_notams = notam_filter.filter_korean_air_notams(text)
            
            # Z0582/25 찾기
            for notam in filtered_notams:
                if 'Z0582/25' in notam.get('raw_text', ''):
                    print("=== Z0582/25 NOTAM 상세 정보 ===")
                    print(f"ID: {notam.get('id', 'NO_ID')}")
                    print(f"유효시작시간: {notam.get('effective_time', 'N/A')}")
                    print(f"유효종료시간: {notam.get('expiry_time', 'N/A')}")
                    print(f"공항코드: {notam.get('airport_codes', [])}")
                    print(f"좌표: {notam.get('coordinates', 'N/A')}")
                    print("="*50)
                    print("원문 전체:")
                    print(notam.get('raw_text', ''))
                    print("="*50)
                    break
            else:
                print("Z0582/25 NOTAM을 찾을 수 없습니다.")

if __name__ == "__main__":
    test_specific_notam()