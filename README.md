# Smart NOTAM - 대한항공 NOTAM 처리 시스템

## 개요
Smart NOTAM은 대한항공의 NOTAM(Notice to Airmen) PDF 파일을 자동으로 처리하여 한국어로 번역하고 요약하는 웹 애플리케이션입니다.

## 주요 기능
- **PDF 변환**: NOTAM PDF 파일을 텍스트로 정확하게 변환
- **자동 필터링**: 대한항공 관련 NOTAM만 자동 추출
- **한국어 번역**: 영문 NOTAM을 한국어로 번역 (AI 또는 사전 기반)
- **자동 요약**: NOTAM 내용을 간단명료하게 요약
- **지도 표시**: Google Maps API를 통한 위치 정보 시각화
- **비행 브리핑**: 처리된 NOTAM들을 브리핑 형태로 생성

## 시스템 요구사항
- Python 3.8 이상
- 웹 브라우저 (Chrome, Firefox, Safari 등)
- 인터넷 연결 (Google Maps API 사용)

## 설치 방법

### 1. 프로젝트 클론/다운로드
```bash
# 또는 ZIP 파일 다운로드 후 압축 해제
cd SmartNOTAM3
```

### 2. 가상환경 생성 (권장)
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. 패키지 설치
```bash
pip install -r requirements.txt
```

### 4. 환경 설정
```bash
# .env 파일 생성
cp .env.example .env

# .env 파일을 편집하여 필요한 API 키 설정
# - GOOGLE_MAPS_API_KEY: Google Maps API 키 (필수)
# - OPENAI_API_KEY: OpenAI API 키 (선택사항)
```

### 5. 실행
```bash
python app.py
```

웹 브라우저에서 `http://localhost:5000` 접속

## 사용 방법

### 1. NOTAM PDF 업로드
- 메인 페이지에서 "파일 선택" 버튼 클릭
- 대한항공 NOTAM PDF 파일 선택 (최대 16MB)
- 옵션 설정 후 "NOTAM 처리 시작" 클릭

### 2. 처리 결과 확인
- 자동으로 필터링된 NOTAM 목록 확인
- 각 NOTAM의 번역 및 요약 확인
- 지도에서 위치 정보 확인

### 3. 필터링 및 검색
- 날짜 범위로 필터링
- 특정 공항 코드로 필터링
- NOTAM 타입별 필터링

### 4. 브리핑 생성
- "브리핑 생성" 버튼 클릭
- 자동 생성된 비행 브리핑 확인
- 필요시 텍스트 파일로 다운로드

## 프로젝트 구조
```
SmartNOTAM3/
├── app.py                 # Flask 메인 애플리케이션
├── requirements.txt       # Python 패키지 목록
├── .env.example          # 환경 설정 예시
├── README.md             # 프로젝트 문서
├── src/                  # 핵심 모듈
│   ├── pdf_converter.py  # PDF 변환 모듈
│   ├── notam_filter.py   # NOTAM 필터링 모듈
│   └── notam_translator.py # 번역/요약 모듈
├── templates/            # HTML 템플릿
│   ├── index.html        # 메인 페이지
│   └── results.html      # 결과 페이지
├── static/               # 정적 파일
│   ├── css/
│   │   └── style.css     # 스타일시트
│   └── js/
│       ├── main.js       # 메인 JavaScript
│       └── results.js    # 결과 페이지 JavaScript
└── uploads/              # 업로드된 파일 저장
```

## API 키 설정

### Google Maps API
1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 새 프로젝트 생성 또는 기존 프로젝트 선택
3. Maps JavaScript API 활성화
4. API 키 생성
5. `.env` 파일의 `GOOGLE_MAPS_API_KEY`에 설정

### OpenAI API (선택사항)
1. [OpenAI Platform](https://platform.openai.com/) 접속
2. API 키 생성
3. `.env` 파일의 `OPENAI_API_KEY`에 설정

## 기술 스택
- **백엔드**: Python, Flask
- **프론트엔드**: HTML5, CSS3, JavaScript, Bootstrap 5
- **PDF 처리**: PyPDF2, pdfplumber
- **AI/번역**: OpenAI API (선택사항)
- **지도**: Google Maps JavaScript API
- **스타일링**: Font Awesome, Bootstrap

## 주요 특징
- 반응형 웹 디자인 (모바일 지원)
- 드래그 앤 드롭 파일 업로드
- 실시간 진행 상황 표시
- 다국어 지원 (한국어/영어)
- RESTful API 구조
- 확장 가능한 모듈 설계

## 개발 정보
- **언어**: Python 3.8+
- **프레임워크**: Flask 2.3+
- **라이선스**: MIT
- **개발자**: Smart NOTAM Team

## 문제 해결

### 자주 발생하는 문제
1. **PDF 변환 실패**: 파일이 손상되었거나 보안이 설정된 PDF인 경우
2. **지도 표시 안됨**: Google Maps API 키가 설정되지 않은 경우
3. **번역 실패**: OpenAI API 키가 없거나 잘못된 경우

### 로그 확인
```bash
tail -f logs/smartnotam.log
```

## 기여 방법
1. 이슈 리포트
2. 기능 제안
3. 코드 기여

## 업데이트 계획
- [ ] 데이터베이스 연동
- [ ] 사용자 인증 시스템
- [ ] NOTAM 히스토리 관리
- [ ] 이메일 알림 기능
- [ ] 모바일 앱 개발

## 라이선스
MIT License - 자유롭게 사용, 수정, 배포 가능합니다.

## 연락처
문의사항이 있으시면 이슈를 등록해 주세요.