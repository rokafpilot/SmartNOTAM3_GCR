import os
import pytest

# 테스트 대상 파일 경로
SPLIT_FILE = os.path.join(os.path.dirname(__file__), '../temp/20250926_195743_Notam-20250923_1_split.txt')

# NOTAM 번호 패턴 (예: A2702/25)
import re
NOTAM_NUMBER_PATTERN = re.compile(r'^[A-Z]\d{4}/\d{2}$')


def load_split_notams(filepath):
    """split.txt 파일을 NOTAM 단위로 분리해서 리스트로 반환"""
    with open(filepath, encoding='utf-8') as f:
        lines = [line.rstrip() for line in f]
    notams = []
    current = []
    for line in lines:
        if line.strip().startswith('===='):
            if current:
                notams.append('\n'.join(current).strip())
                current = []
        else:
            current.append(line)
    if current:
        notams.append('\n'.join(current).strip())
    return notams


def test_notam_split_count():
    notams = load_split_notams(SPLIT_FILE)
    # 최소 5개 이상 NOTAM이 분리되어야 한다 (예시)
    assert len(notams) >= 5, f"분리된 NOTAM 개수: {len(notams)}"


def test_notam_number_format():
    notams = load_split_notams(SPLIT_FILE)
    # 각 NOTAM의 첫 줄에 NOTAM 번호가 있는지 확인
    for i, notam in enumerate(notams):
        first_line = notam.split('\n', 1)[0].strip()
        assert NOTAM_NUMBER_PATTERN.match(first_line), f"{i+1}번째 NOTAM의 첫 줄이 NOTAM 번호 형식이 아님: {first_line}"


def test_notam_body_not_empty():
    notams = load_split_notams(SPLIT_FILE)
    # 각 NOTAM의 본문(2번째 줄 이후)이 비어있지 않은지 확인
    for i, notam in enumerate(notams):
        lines = notam.split('\n')
        body = '\n'.join(lines[1:]).strip()
        assert body, f"{i+1}번째 NOTAM의 본문이 비어있음"
