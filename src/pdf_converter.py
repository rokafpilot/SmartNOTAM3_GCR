"""
PDF to Text Converter Module
대한항공 NOTAM PDF 파일을 텍스트로 변환하는 모듈
참조: SmartNOTAMgemini_GCR/enroute/notam_all_in_one.py
"""

import PyPDF2
import pdfplumber
import logging
import os
import tempfile
from typing import Optional, List
import re
from datetime import datetime
from constants import NOTAM_START_PATTERN, KOREAN_AIR_KEYWORDS

class PDFConverter:
    """PDF 파일을 텍스트로 변환하는 클래스"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def convert_with_pypdf2(self, pdf_path: str) -> str:
        """
        PyPDF2를 사용하여 PDF를 텍스트로 변환
        
        Args:
            pdf_path (str): PDF 파일 경로
            
        Returns:
            str: 변환된 텍스트
        """
        try:
            text = ""
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text() + "\n"
                    
            return text
            
        except Exception as e:
            self.logger.error(f"PyPDF2 변환 중 오류 발생: {str(e)}")
            return ""
    
    def convert_with_pdfplumber(self, pdf_path: str) -> str:
        """
        pdfplumber를 사용하여 PDF를 텍스트로 변환 (실제 NOTAM만 추출)
        
        Args:
            pdf_path (str): PDF 파일 경로
            
        Returns:
            str: 변환된 텍스트 (실제 NOTAM만)
        """
        try:
            full_text = ""
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        full_text += page_text + "\n"
            
            # 실제 NOTAM만 추출
            notam_only_text = self.extract_actual_notams(full_text)
            
            self.logger.info(f"PDF 변환 완료: 전체 {len(full_text)} 문자 -> NOTAM만 {len(notam_only_text)} 문자")
            return notam_only_text
            
        except Exception as e:
            self.logger.error(f"pdfplumber 변환 중 오류 발생: {str(e)}")
            return ""
    
    def convert_pdf_to_text(self, pdf_path: str, method: str = "pdfplumber", save_temp: bool = True) -> str:
        """
        PDF를 텍스트로 변환 (메인 메서드)
        
        Args:
            pdf_path (str): PDF 파일 경로
            method (str): 변환 방법 ("pdfplumber" 또는 "pypdf2")
            save_temp (bool): 임시 파일로 저장 여부
            
        Returns:
            str: 변환된 텍스트
        """
        if method == "pdfplumber":
            text = self.convert_with_pdfplumber(pdf_path)
            # pdfplumber가 실패하면 PyPDF2로 시도
            if not text.strip():
                self.logger.info("pdfplumber 실패, PyPDF2로 재시도...")
                text = self.convert_with_pypdf2(pdf_path)
        else:
            text = self.convert_with_pypdf2(pdf_path)
            
        # 텍스트 정리
        cleaned_text = self.clean_text(text)
        
        # 임시 파일로 저장
        if save_temp and cleaned_text.strip():
            temp_file_path = self.save_to_temp_file(cleaned_text, pdf_path)
            self.logger.info(f"변환된 텍스트를 임시 파일에 저장: {temp_file_path}")
            
        return cleaned_text
    
    def clean_text(self, text: str) -> str:
        """
        추출된 텍스트를 정리
        
        Args:
            text (str): 원본 텍스트
            
        Returns:
            str: 정리된 텍스트
        """
        # 불필요한 공백 제거
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        
        # 특수 문자 정리
        text = text.replace('\x00', '')
        text = text.replace('\ufeff', '')
        
        return text.strip()
    
    def save_to_temp_file(self, text: str, original_pdf_path: str) -> str:
        """
        변환된 텍스트를 임시 파일로 저장
        
        Args:
            text (str): 저장할 텍스트
            original_pdf_path (str): 원본 PDF 파일 경로
            
        Returns:
            str: 임시 파일 경로
        """
        try:
            # 원본 파일명에서 확장자 제거
            base_name = os.path.splitext(os.path.basename(original_pdf_path))[0]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # temp 폴더 생성 (없으면)
            temp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            
            # 임시 파일 경로 생성
            temp_filename = f"{base_name}_{timestamp}.txt"
            temp_file_path = os.path.join(temp_dir, temp_filename)
            
            # 파일 저장
            with open(temp_file_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            self.logger.info(f"임시 파일 저장 완료: {temp_file_path}")
            return temp_file_path
            
        except Exception as e:
            self.logger.error(f"임시 파일 저장 중 오류 발생: {str(e)}")
            return ""
    
    def extract_notam_sections(self, text: str) -> List[str]:
        """
        텍스트에서 NOTAM 섹션들을 추출
        참조 파일의 split_notams 함수 기능 적용
        
        Args:
            text (str): 전체 텍스트
            
        Returns:
            List[str]: NOTAM 섹션들의 리스트
        """
        notam_sections = []
        
        # 참조 파일의 NOTAM 패턴 사용
        notam_starts = [m.start() for m in re.finditer(NOTAM_START_PATTERN, text)]
        
        for i, start in enumerate(notam_starts):
            end = notam_starts[i+1] if i+1 < len(notam_starts) else len(text)
            notam_section = text[start:end].strip()
            if notam_section:
                notam_sections.append(notam_section)
        
        self.logger.info(f"총 {len(notam_sections)}개의 NOTAM 섹션 추출")
        return notam_sections
    
    def extract_comment_notams(self, notam_list: List[str]) -> List[str]:
        """
        COMMENT가 포함된 NOTAM만 추출
        참조 파일의 extract_comment_notams 함수 적용
        
        Args:
            notam_list (List[str]): 전체 NOTAM 리스트
            
        Returns:
            List[str]: COMMENT가 포함된 NOTAM 리스트
        """
        comment_notams = [notam for notam in notam_list if 'COMMENT' in notam]
        self.logger.info(f"COMMENT 포함 NOTAM: {len(comment_notams)}개 발견")
        return comment_notams
    
    def extract_actual_notams(self, text: str) -> str:
        """
        전체 텍스트에서 실제 NOTAM만 추출
        
        실제 NOTAM 시작점:
        - â—R¼U NWAY, â—T¼A XIWAY 등 카테고리 헤더부터 시작 (특수문자 포함)
        - 제외: â—C¼O MPANY ADVISORY 등 Company Advisory NOTAM
        
        Args:
            text (str): 전체 PDF 텍스트
            
        Returns:
            str: 실제 NOTAM만 포함된 텍스트
        """
        lines = text.split('\n')
        
        # 실제 NOTAM 카테고리 헤더들 (특수문자 패턴 + 일반 텍스트 패턴)
        notam_category_patterns = [
            r'â—R¼U NWAY|RUNWAY',        # RUNWAY
            r'â—T¼A XIWAY|TAXIWAY',      # TAXIWAY  
            r'â—R¼A MP|RAMP',            # RAMP
            r'â—A¼PP ROACH|APPROACH',    # APPROACH
            r'â—D¼E PARTURE|DEPARTURE',  # DEPARTURE
            r'â—G¼P S|GPS',              # GPS
            r'â—A¼IP|AIP',               # AIP
            r'â—A¼IR PORT|AIRPORT',      # AIRPORT
            r'â—O¼T HER|OTHER',          # OTHER
            r'â—R¼U NWAY LIGHT|RUNWAY LIGHT'   # RUNWAY LIGHT
        ]
        
        # 제외할 패턴들 (Company Advisory 등)
        exclude_patterns = [
            r'â—C¼O MPANY ADVISORY|COMPANY ADVISORY',
            r'â—C¼O MPANY MINIMA|COMPANY MINIMA',
            r'â—D¼E PARTURE AIRPORT TECHNICAL INFORMATION|DEPARTURE AIRPORT TECHNICAL INFORMATION'
        ]
        
        # 첫 번째 NOTAM 카테고리 헤더 찾기
        first_notam_line = -1
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # 제외 패턴 체크
            is_excluded = False
            for exclude_pattern in exclude_patterns:
                if exclude_pattern in line_stripped:
                    is_excluded = True
                    break
            
            if is_excluded:
                continue
            
            # NOTAM 카테고리 헤더 찾기
            for pattern in notam_category_patterns:
                if pattern in line_stripped:
                    first_notam_line = i
                    self.logger.info(f"첫 번째 NOTAM 카테고리 발견 (라인 {i}): {line_stripped}")
                    break
            
            if first_notam_line != -1:
                break
        
        if first_notam_line == -1:
            self.logger.warning("NOTAM 카테고리 헤더를 찾을 수 없음")
            return text  # 원본 반환
        
        # 첫 번째 NOTAM 카테고리부터 끝까지 추출
        notam_text = '\n'.join(lines[first_notam_line:])
        
        # Company Advisory 섹션들 제거
        for exclude_pattern in exclude_patterns:
            # 각 패턴부터 다음 NOTAM 카테고리까지 제거
            pattern_with_content = exclude_pattern + r'.*?(?=' + '|'.join(notam_category_patterns) + r'|$)'
            notam_text = re.sub(pattern_with_content, '', notam_text, flags=re.DOTALL | re.MULTILINE)
        
        # COAD (Company Advisory) NOTAM ID 패턴도 제거
        coad_pattern = r'COAD\d+/\d+.*?(?=' + '|'.join(notam_category_patterns) + r'|$)'
        notam_text = re.sub(coad_pattern, '', notam_text, flags=re.DOTALL | re.MULTILINE)
        
        result_text = notam_text.strip()
        
        self.logger.info(f"실제 NOTAM 추출 완료: {len(text)} -> {len(result_text)} 문자 ({((len(text) - len(result_text)) / len(text) * 100):.1f}% 감소)")
        return result_text
    
    def get_temp_files(self) -> List[str]:
        """
        생성된 임시 파일들의 목록을 반환
        
        Returns:
            List[str]: 임시 파일 경로들의 리스트
        """
        try:
            temp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'temp')
            if os.path.exists(temp_dir):
                temp_files = [os.path.join(temp_dir, f) for f in os.listdir(temp_dir) 
                            if f.endswith('.txt')]
                return sorted(temp_files, key=os.path.getmtime, reverse=True)
            return []
        except Exception as e:
            self.logger.error(f"임시 파일 목록 조회 중 오류: {str(e)}")
            return []
    
    def cleanup_temp_files(self, keep_latest: int = 5) -> None:
        """
        오래된 임시 파일들을 정리
        
        Args:
            keep_latest (int): 유지할 최신 파일 개수
        """
        try:
            temp_files = self.get_temp_files()
            if len(temp_files) > keep_latest:
                files_to_delete = temp_files[keep_latest:]
                for file_path in files_to_delete:
                    os.remove(file_path)
                    self.logger.info(f"임시 파일 삭제: {file_path}")
        except Exception as e:
            self.logger.error(f"임시 파일 정리 중 오류: {str(e)}")


if __name__ == "__main__":
    # 테스트 코드
    converter = PDFConverter()
    
    # 예시 사용법
    # text = converter.convert_pdf_to_text("sample_notam.pdf", save_temp=True)
    # print(f"변환된 텍스트 길이: {len(text)} 문자")
    # print(text[:500])  # 첫 500자 출력
    
    # 임시 파일 목록 확인
    # temp_files = converter.get_temp_files()
    # print(f"임시 파일 개수: {len(temp_files)}")
    
    # 오래된 임시 파일 정리
    # converter.cleanup_temp_files(keep_latest=3)