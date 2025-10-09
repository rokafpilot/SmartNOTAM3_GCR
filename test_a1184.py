import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from src.notam_filter import NOTAMFilter

# 테스트 파일 읽기
with open('temp/20251009_094823_Notam-20251008_split.txt', 'r', encoding='utf-8') as f:
    content = f.read()

# NOTAM 필터 생성
notam_filter = NOTAMFilter()

# 전체 NOTAM 필터링
all_notams = notam_filter.filter_korean_air_notams(content)

print('=== A1184/25 NOTAM 찾기 ===')
for i, notam in enumerate(all_notams):
    notam_number = notam.get('notam_number', '')
    
    # A1184/25 NOTAM 찾기
    if 'A1184/25' in notam_number:
        print(f'Found NOTAM at index {i}:')
        print(f'  NOTAM Number: {notam_number}')
        print(f'  Airport Code: {notam.get("airport_code", "N/A")}')
        print(f'  effective_time: {notam.get("effective_time", "N/A")}')
        print(f'  expiry_time: {notam.get("expiry_time", "N/A")}')
        
        # local_time_display 생성 테스트
        effective_time = notam.get('effective_time', '')
        expiry_time = notam.get('expiry_time', '')
        airport_code = notam.get('airport_code', 'RKRR')
        
        if effective_time and (expiry_time or expiry_time == 'UFN'):
            local_time_str = notam_filter.format_notam_time_with_local(
                effective_time, expiry_time, airport_code, notam
            )
            print(f'  local_time_display: {local_time_str}')
        else:
            print(f'  local_time_display: None (effective_time: {effective_time}, expiry_time: {expiry_time})')
        
        print(f'  timezone: {notam_filter.get_timezone(airport_code)}')
