"""
Smart NOTAM3 - 시간 필터링과 로컬시간 변환이 적용된 NOTAM 처리 애플리케이션
"""

from flask import Flask, request, render_template, jsonify, redirect, url_for, flash
from werkzeug.utils import secure_filename
import os
import subprocess
import logging
from datetime import datetime
import json
import glob

# 로컬 모듈
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.pdf_converter import PDFConverter
from src.notam_filter import NOTAMFilter  
from src.notam_translator import NOTAMTranslator
from src.hybrid_translator import HybridNOTAMTranslator
from src.parallel_translator import ParallelHybridNOTAMTranslator
from src.integrated_translator import IntegratedNOTAMTranslator
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# pdfminer의 DEBUG 로그 억제로 성능 향상
logging.getLogger('pdfminer').setLevel(logging.WARNING)
logging.getLogger('pdfminer.psparser').setLevel(logging.WARNING)
logging.getLogger('pdfminer.pdfinterp').setLevel(logging.WARNING)
logging.getLogger('pdfminer.pdfdocument').setLevel(logging.WARNING)
logging.getLogger('pdfminer.pdfpage').setLevel(logging.WARNING)

# Flask 앱 설정
app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# 설정
UPLOAD_FOLDER = 'uploads'
TEMP_FOLDER = 'temp'
ALLOWED_EXTENSIONS = {'pdf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['TEMP_FOLDER'] = TEMP_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def cleanup_files(directory, max_files=5):
    """
    지정된 디렉토리에서 최대 파일 개수만 유지하고 나머지는 삭제
    파일은 생성 시간 기준으로 오래된 것부터 삭제
    """
    try:
        if not os.path.exists(directory):
            return
            
        # 디렉토리 내 모든 파일 목록 가져오기
        files = glob.glob(os.path.join(directory, '*'))
        
        # 파일과 디렉토리만 필터링 (숨김 파일 제외)
        files = [f for f in files if os.path.isfile(f) and not os.path.basename(f).startswith('.')]
        
        if len(files) <= max_files:
            return

        # 파일 생성 시간 기준으로 정렬 (오래된 것부터)
        files.sort(key=lambda x: os.path.getctime(x))
        
        # 초과 파일들 삭제
        files_to_delete = files[:-max_files]
        for file_path in files_to_delete:
            try:
                os.remove(file_path)
                logger.info(f"오래된 파일 삭제: {file_path}")
            except Exception as e:
                logger.error(f"파일 삭제 실패 {file_path}: {str(e)}")
                
    except Exception as e:
        logger.error(f"파일 정리 중 오류 ({directory}): {str(e)}")

# 폴더 생성
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TEMP_FOLDER, exist_ok=True)

# 애플리케이션 시작 시 기존 파일 정리
cleanup_files(UPLOAD_FOLDER, max_files=5)
cleanup_files(TEMP_FOLDER, max_files=5)

# 모듈 초기화
pdf_converter = PDFConverter()
notam_filter = NOTAMFilter()
notam_translator = NOTAMTranslator()
hybrid_translator = HybridNOTAMTranslator()
parallel_translator = ParallelHybridNOTAMTranslator()
integrated_translator = IntegratedNOTAMTranslator()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    # 전체 처리 시간 측정 시작
    total_start_time = datetime.now()
    processing_times = {}
    
    try:
        if 'file' not in request.files:
            flash('파일이 선택되지 않았습니다.')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('파일이 선택되지 않았습니다.')
            return redirect(request.url)
        
        if file and file.filename and allowed_file(file.filename):
            # 파일 저장 시간 측정
            file_save_start = datetime.now()
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # 업로드 파일 정리 (최대 5개만 유지)
            cleanup_files(app.config['UPLOAD_FOLDER'], max_files=5)
            
            processing_times['file_save'] = (datetime.now() - file_save_start).total_seconds()
            
            # PDF 텍스트 변환 시간 측정
            pdf_conversion_start = datetime.now()
            logger.info(f"PDF 변환 시작: {filepath}")
            text = pdf_converter.convert_pdf_to_text(filepath)
            processing_times['pdf_conversion'] = (datetime.now() - pdf_conversion_start).total_seconds()
            
            logger.info(f"PDF 텍스트 변환 완료: {len(text)} 문자 ({processing_times['pdf_conversion']:.2f}초)")
            logger.info(f"텍스트 내용 미리보기: {text[:200]}...")
            
            if not text.strip():
                logger.error("PDF에서 추출된 텍스트가 비어있습니다.")
                flash('PDF에서 텍스트를 추출할 수 없습니다.')
                return redirect(url_for('index'))
            
            # 먼저 Package 정보를 추출하여 동적 순서 설정
            logger.info("Package 정보 추출 시작")
            temp_notams = notam_filter.filter_korean_air_notams(text)
            all_airports = set()
            for notam in temp_notams:
                airport_code = notam.get('airport_code', '')
                if airport_code:
                    all_airports.add(airport_code)
            
            # Package 정보 추출하여 동적 순서로 업데이트
            filtered_package_airports = notam_filter.extract_package_airports(text, all_airports)
            
            # 동적 순서가 적용된 상태에서 NOTAM 필터링 재실행
            filtering_start = datetime.now()
            logger.info("NOTAM 필터링 시작 (동적 순서 적용)")
            notams = notam_filter.filter_korean_air_notams(text)
            processing_times['notam_filtering'] = (datetime.now() - filtering_start).total_seconds()
            logger.info(f"NOTAM 필터링 완료: {len(notams)}개 ({processing_times['notam_filtering']:.2f}초)")
            
            # 공항 필터링 처리 시간 측정 (선택사항)
            airport_filter_start = datetime.now()
            airport_filter_data = request.form.get('airport_filter')
            if airport_filter_data:
                try:
                    airport_filter = json.loads(airport_filter_data)
                    selected_airports = airport_filter.get('selected_airports', [])
                    
                    if selected_airports:
                        logger.info(f"공항 필터 적용: {selected_airports}")
                        # 선택된 공항과 관련된 NOTAM만 필터링 (원본 순서 유지)
                        filtered_notams = []
                        for i, notam in enumerate(notams):
                            notam_airport = notam.get('airport_code', '')
                            # 선택된 공항과 일치하면 포함
                            if notam_airport in selected_airports:
                                filtered_notams.append(notam)
                                logger.debug(f"공항 필터링: NOTAM {i+1} -> {notam_airport} {notam.get('notam_number', 'N/A')} 포함")
                        
                        notams = filtered_notams
                        logger.info(f"공항 필터링 후 NOTAM 수: {len(notams)}개 (원본 순서 유지)")
                        
                        # 필터링된 NOTAM 순서 로깅
                        logger.info("=== 공항 필터링 후 NOTAM 순서 ===")
                        for i, notam in enumerate(notams[:10], 1):  # 첫 10개만 로깅
                            logger.info(f"필터링 후 {i}: {notam.get('airport_code', 'N/A')} {notam.get('notam_number', 'N/A')}")
                        
                except Exception as e:
                    logger.error(f"공항 필터 파싱 오류: {str(e)}")
            processing_times['airport_filtering'] = (datetime.now() - airport_filter_start).total_seconds()
            
            # NOTAM 시간을 로컬 시간으로 변환 시간 측정
            time_conversion_start = datetime.now()
            for notam in notams:
                airport_code = notam.get('airport_code', 'RKSI')  # 기본값: 인천공항
                
                effective_time = notam.get('effective_time', '')
                expiry_time = notam.get('expiry_time', '')
                
                # 로컬 시간으로 변환된 시간 문자열 생성
                if effective_time and expiry_time:
                    local_time_str = notam_filter.format_notam_time_with_local(
                        effective_time, expiry_time, airport_code, notam
                    )
                    notam['local_time_display'] = local_time_str
            processing_times['time_conversion'] = (datetime.now() - time_conversion_start).total_seconds()
            
            if not notams:
                flash('필터링된 NOTAM이 없습니다.')
                return redirect(url_for('index'))
            
            # NOTAM 번역 및 요약 시간 측정 (병렬 번역기 사용)
            translation_start = datetime.now()
            logger.info(f"병렬 번역 시작: {len(notams)}개 NOTAM")
            
            # 병렬 번역기로 모든 NOTAM을 처리
            logger.info(f"번역 전 NOTAM 개수: {len(notams)}")
            
            # 번역 전 NOTAM 데이터 샘플 로깅
            for i, notam in enumerate(notams[:3]):  # 처음 3개만 로깅
                logger.info(f"NOTAM {i+1} 번역 전: {notam.get('notam_number', 'N/A')} - {notam.get('description', '')[:100]}...")
            
            # 통합 번역기 사용 (개별 처리로 변경)
            translated_notams = integrated_translator.process_notams_individual(notams)
            processing_times['translation'] = (datetime.now() - translation_start).total_seconds()
            
            # 번역 후 결과 샘플 로깅
            logger.info(f"번역 후 NOTAM 개수: {len(translated_notams)}")
            for i, notam in enumerate(translated_notams[:3]):  # 처음 3개만 로깅
                logger.info(f"NOTAM {i+1} 번역 후: {notam.get('notam_number', 'N/A')} - 타입: {notam.get('notam_type', 'N/A')} - 한국어: {notam.get('korean_translation', 'N/A')[:50]}...")
            
            logger.info(f"병렬 번역 완료: {len(translated_notams)}개 NOTAM, {processing_times['translation']:.2f}초")
            logger.info(f"평균 처리 시간: {processing_times['translation']/len(translated_notams):.2f}초/NOTAM")
            
            # 결과를 원래 notams 리스트에 반영
            notams = translated_notams
            
            # 전체 처리 시간 계산
            total_processing_time = (datetime.now() - total_start_time).total_seconds()
            processing_times['total'] = total_processing_time
            
            # 시간 측정 결과 로깅
            logger.info("=== 처리 시간 요약 ===")
            logger.info(f"파일 저장: {processing_times['file_save']:.2f}초")
            logger.info(f"PDF 변환: {processing_times['pdf_conversion']:.2f}초")
            logger.info(f"NOTAM 필터링: {processing_times['notam_filtering']:.2f}초")
            logger.info(f"공항 필터링: {processing_times['airport_filtering']:.2f}초")
            logger.info(f"시간 변환: {processing_times['time_conversion']:.2f}초")
            logger.info(f"번역: {processing_times['translation']:.2f}초")
            logger.info(f"전체 처리 시간: {processing_times['total']:.2f}초")
            logger.info("==================")
            
            # 템플릿에 공항 정보 전달
            return render_template('results.html', 
                                 notams=notams, 
                                 current_date=datetime.now().strftime('%Y-%m-%d'),
                                 all_airports=sorted(list(all_airports)),
                                 package_airports=filtered_package_airports)
        
        else:
            flash('허용되지 않는 파일 형식입니다. PDF 파일만 업로드 가능합니다.')
            return redirect(url_for('index'))
    
    except Exception as e:
        logger.error(f"업로드 처리 중 오류: {str(e)}")
        flash(f'파일 처리 중 오류가 발생했습니다: {str(e)}')
        return redirect(url_for('index'))

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/api/analyze_route', methods=['POST'])
def analyze_route():
    """GEMINI를 사용한 AI 기반 루트 분석 API"""
    logger.info("analyze_route API 호출됨")
    try:
        data = request.get_json()
        route = data.get('route', '').strip()
        
        if not route:
            return jsonify({'error': '항로를 입력해주세요.'}), 400
        
        logger.info(f"분석할 항로: {route}")
        
        # GEMINI를 사용한 루트 분석
        analysis_result = analyze_route_with_gemini(route)
        
        return jsonify({
            'route': route,
            'analysis': analysis_result,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"루트 분석 중 오류: {str(e)}")
        return jsonify({'error': f'루트 분석 중 오류가 발생했습니다: {str(e)}'}), 500

def analyze_route_with_gemini(route):
    """GEMINI를 사용한 루트 분석"""
    try:
        import google.generativeai as genai
        
        # GEMINI API 키 확인
        api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        if not api_key:
            return "GEMINI API 키가 설정되지 않았습니다."
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        prompt = f"""다음 항공 항로를 분석하여 상세한 비행 브리핑을 작성해주세요.

항로: {route}

분석 요구사항:
1. 항로의 주요 지점들을 식별하고 설명
2. 각 구간별 비행 특성 분석 (거리, 예상 비행시간, 고도 등)
3. 항로상의 잠재적 위험 요소 식별
4. 기상, 관제, 항로 변경 등의 고려사항
5. 비행 계획 수립 시 주의사항
6. 대체 항로 제안 (필요시)

분석 결과를 다음 형식으로 제공해주세요:

## 항로 개요
- 출발지: [공항코드]
- 목적지: [공항코드]
- 총 거리: [예상거리]
- 예상 비행시간: [시간]

## 주요 지점 분석
1. [지점명]: [설명]
2. [지점명]: [설명]
...

## 비행 특성
- 권장 고도: [고도]
- 항로 유형: [SID/STAR/ENROUTE]
- 관제 구역: [FIR 정보]

## 주의사항
- [주의사항 1]
- [주의사항 2]
...

## 권장사항
- [권장사항 1]
- [권장사항 2]
...

한국어로 상세하고 전문적으로 작성해주세요."""

        response = model.generate_content(prompt)
        return response.text.strip()
        
    except Exception as e:
        logger.error(f"GEMINI 루트 분석 중 오류: {str(e)}")
        return f"AI 분석 중 오류가 발생했습니다: {str(e)}"

@app.route('/api/extract_airports', methods=['POST'])
def extract_airports():
    """PDF에서 공항 코드를 추출하는 API"""
    logger.info("extract_airports API 호출됨")
    try:
        logger.info(f"요청 파일: {request.files.keys()}")
        
        if 'file' not in request.files:
            logger.error("파일이 요청에 포함되지 않음")
            return jsonify({'error': '파일이 선택되지 않았습니다.'}), 400
        
        file = request.files['file']
        logger.info(f"파일명: {file.filename}")
        
        if file.filename == '' or not allowed_file(file.filename):
            logger.error(f"유효하지 않은 파일: {file.filename}")
            return jsonify({'error': '유효하지 않은 파일입니다.'}), 400
        
        # 임시 파일 저장
        filename = secure_filename(file.filename or 'unknown.pdf')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_filename = f"temp_{timestamp}_{filename}"
        temp_filepath = os.path.join(app.config['TEMP_FOLDER'], temp_filename)
        file.save(temp_filepath)
        
        # 임시 파일 정리 (최대 5개만 유지)
        cleanup_files(app.config['TEMP_FOLDER'], max_files=5)
        
        try:
            logger.info("PDF 텍스트 변환 시작")
            # PDF 텍스트 변환 (임시 파일 저장 비활성화)
            text = pdf_converter.convert_pdf_to_text(temp_filepath, save_temp=False)
            logger.info(f"PDF 텍스트 변환 완료: {len(text)} 문자")
            
            if not text.strip():
                logger.error("PDF에서 텍스트 추출 실패")
                return jsonify({'error': 'PDF에서 텍스트를 추출할 수 없습니다.'}), 400
            
            logger.info("NOTAM 필터링 시작")
            # NOTAM 필터링하여 공항 코드 추출
            notams = notam_filter.filter_korean_air_notams(text)
            logger.info(f"NOTAM 필터링 완료: {len(notams)}개")
            
            # 모든 공항 코드 수집
            all_airports = set()
            for notam in notams:
                airport_code = notam.get('airport_code', '')
                logger.debug(f"NOTAM에서 공항 코드: {airport_code}")
                if airport_code:
                    all_airports.add(airport_code)
            
            logger.info(f"추출된 공항 코드: {sorted(list(all_airports))}")
            
            return jsonify({
                'airports': sorted(list(all_airports)),
                'notam_count': len(notams)
            })
            
        finally:
            # 임시 파일 삭제
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
    
    except Exception as e:
        logger.error(f"공항 추출 중 오류: {str(e)}")
        return jsonify({'error': f'공항 추출 중 오류가 발생했습니다: {str(e)}'}), 500

@app.route('/google_maps')
def google_maps():
    """구글지도 페이지"""
    return render_template('google_maps.html')

@app.route('/health')
def health():
    """헬스 체크 엔드포인트"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    # Cloud Run에서는 PORT 환경변수를 사용, 로컬에서는 5005 사용
    port = int(os.environ.get('PORT', 5005))
    app.run(debug=True, host='0.0.0.0', port=port)