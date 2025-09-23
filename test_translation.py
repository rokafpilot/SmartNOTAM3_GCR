#!/usr/bin/env python3
"""
Z0582/25 NOTAM 번역 테스트 스크립트
"""

from src.notam_translator import NOTAMTranslator

def test_z0582_translation():
    """Z0582/25 NOTAM 번역 테스트"""
    
    # 실제 Z0582/25 NOTAM 텍스트
    notam_text = """09JUL25 16:00 - 25SEP25 09:00 RKSI Z0582/25
E) TRIGGER NOTAM - AIRAC AIP SUP 52/25
WEF 1600 UTC 9 JUL 2025 TIL 0900 UTC 1 AUG 2025
- RWY 15L/33R WILL BE CLOSED DUE TO PAVEMENT CONSTRUCTION.
- SOME PARTS OF TWYS C, D, E WILL BE CLOSED DUE TO PAVEMENT
CONSTRUCTION.
.
COMMENT) CLSD AREAS
*AREA B (FM 1600 UTC 9 JUL 2025 TO 0900 UTC 25 SEP 2025)
- RWY 15L/33R BTN TWY J AND TWY K
(NO EFFECT ON TWY K OPERATION)
- TWY D BTN TWY G AND D8
(NO EFFECT ON TWY G AND TWY D8 OPERATION)
- TWY E BTN TWY C AND D
(NO EFFECT ON TWY C AND D OPERATION)
- RAPID EXIT TWY C1-C8 & TWY D1-D4
*ANY CHANGE TO THE CONTENTS OF THESE PAGES WILL BE NOTIFIED BY
NOTAM."""

    print("=== Z0582/25 NOTAM 번역 테스트 ===")
    print("원문:")
    print(notam_text)
    print("=" * 50)
    
    # 번역기 초기화
    translator = NOTAMTranslator()
    
    # 번역 수행
    result = translator.translate_notam(notam_text, target_lang="ko", use_ai=True)
    
    print("번역 결과:")
    print(result.get('korean_translation', '번역 실패'))
    print("=" * 50)
    
    # E 섹션 추출 테스트
    e_section = translator.extract_e_section(notam_text)
    print("E 섹션 추출:")
    print(e_section)
    print("=" * 50)

if __name__ == "__main__":
    test_z0582_translation()