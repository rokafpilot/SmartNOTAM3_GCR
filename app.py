"""
Smart NOTAM3 - 시간 필터링과 로컬시간 변환이 적용된 NOTAM 처리 애플리케이션
"""

from flask import Flask, request, render_template, jsonify, redirect, url_for, flash, send_file
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
        notam_data = data.get('notam_data', [])
        
        if not route:
            return jsonify({'error': '항로를 입력해주세요.'}), 400
        
        logger.info(f"분석할 항로: {route}")
        logger.info(f"NOTAM 데이터 개수: {len(notam_data)}")
        
        # GEMINI를 사용한 루트 분석
        analysis_result = analyze_route_with_gemini(route, notam_data)
        
        return jsonify({
            'route': route,
            'analysis': analysis_result,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"루트 분석 중 오류: {str(e)}")
        return jsonify({'error': f'루트 분석 중 오류가 발생했습니다: {str(e)}'}), 500

def analyze_route_with_gemini(route, notam_data):
    """GEMINI를 사용한 루트 분석 - NOTAM과 항로 연관성 중심"""
    try:
        import google.generativeai as genai
        
        # GEMINI API 키 확인
        api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        if not api_key:
            return "GEMINI API 키가 설정되지 않았습니다."
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # NOTAM 데이터를 문자열로 변환
        notam_text = format_notam_data_for_analysis(notam_data)
        
        prompt = f"""다음 항공 항로와 관련된 NOTAM을 분석하여 항로에 미치는 영향을 평가해주세요.

분석할 항로: {route}

현재 NOTAM 데이터:
{notam_text}

분석 요구사항:
1. 항로상의 각 공항(VVDN, RKSI)과 waypoint가 NOTAM에 언급되어 있는지 확인
2. NOTAM이 항로의 특정 구간에 영향을 미치는지 분석
3. 항로 변경, 고도 제한, 속도 제한 등이 필요한지 판단
4. 비행 안전에 직접적인 영향을 미치는 NOTAM 식별
5. 각 NOTAM의 중요도와 우선순위 평가

분석 결과를 다음 형식으로 제공해주세요:

## 항로-NOTAM 연관성 분석

### 직접 영향 NOTAM
- [NOTAM 번호]: [항로 구간] - [영향 내용] - [조치사항]

### 간접 영향 NOTAM  
- [NOTAM 번호]: [관련 공항/지점] - [영향 내용] - [주의사항]

### 항로별 영향 분석
**VVDN 구간:**
- [NOTAM 영향 분석]

**중간 구간 (BUNT2G ~ OLMEN):**
- [NOTAM 영향 분석]

**RKSI 구간:**
- [NOTAM 영향 분석]

## 비행 계획 권장사항
- [NOTAM 기반 비행 계획 수정사항]
- [대체 절차 또는 항로]
- [특별 주의사항]

## 우선순위별 조치사항
**긴급 (즉시 조치 필요):**
- [항목들]

**중요 (비행 전 확인 필요):**
- [항목들]

**참고 (인지 필요):**
- [항목들]

NOTAM 데이터가 없거나 항로와 관련이 없는 경우, 해당 사실을 명확히 명시해주세요.
한국어로 간결하고 실용적으로 작성해주세요."""

        response = model.generate_content(prompt)
        return response.text.strip()
        
    except Exception as e:
        logger.error(f"GEMINI 루트 분석 중 오류: {str(e)}")
        return f"AI 분석 중 오류가 발생했습니다: {str(e)}"

def format_notam_data_for_analysis(notam_data):
    """NOTAM 데이터를 분석용 문자열로 변환"""
    if not notam_data:
        return "현재 NOTAM 데이터가 없습니다."
    
    formatted_text = "NOTAM 목록:\n\n"
    for notam in notam_data:
        formatted_text += f"NOTAM #{notam['index']}: {notam['notam_number']}\n"
        formatted_text += f"공항: {', '.join(notam['airports'])}\n"
        formatted_text += f"유효시간: {notam['effective_time']} - {notam['expiry_time']}\n"
        formatted_text += f"내용: {notam['text']}\n"
        formatted_text += "---\n"
    
    return formatted_text

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

@app.route('/save_html', methods=['POST'])
def save_html():
    """현재 페이지를 그대로 HTML 파일로 저장"""
    try:
        # 현재 페이지의 HTML을 그대로 가져오기
        from flask import request
        
        # 클라이언트에서 현재 페이지의 HTML을 전송받음
        html_content = request.get_json().get('html_content', '')
        
        if not html_content:
            return jsonify({'error': 'HTML 내용이 없습니다.'}), 400
        
        # HTML 파일명 생성
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'NOTAM_Results_{timestamp}.html'
        
        # 저장할 디렉토리 생성
        save_dir = os.path.join(os.path.dirname(__file__), 'saved_results')
        os.makedirs(save_dir, exist_ok=True)
        
        # HTML 파일 경로
        file_path = os.path.join(save_dir, filename)
        
        # 외부 리소스를 로컬로 변환
        processed_html = process_html_for_offline(html_content)
        
        # 파일 저장
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(processed_html)
        
        logger.info(f"HTML 파일 저장 완료: {filename}")
        
        return jsonify({
            'success': True,
            'filename': filename,
            'message': f'HTML 파일이 저장되었습니다: {filename}'
        })
        
    except Exception as e:
        logger.error(f"HTML 저장 중 오류: {str(e)}")
        return jsonify({'error': f'HTML 저장 중 오류가 발생했습니다: {str(e)}'}), 500

def process_html_for_offline(html_content):
    """HTML을 오프라인에서 볼 수 있도록 처리"""
    
    # Bootstrap CSS를 로컬로 다운로드하거나 인라인으로 포함
    bootstrap_css = """
    <style>
        /* Bootstrap 5.3.3 CSS (간소화된 버전) */
        *,*::before,*::after{box-sizing:border-box}
        body{margin:0;font-family:var(--bs-font-sans-serif);font-size:1rem;font-weight:400;line-height:1.5;color:#212529;background-color:#fff;-webkit-text-size-adjust:100%;-webkit-tap-highlight-color:transparent}
        .container{width:100%;padding-right:var(--bs-gutter-x,.75rem);padding-left:var(--bs-gutter-x,.75rem);margin-right:auto;margin-left:auto}
        .row{--bs-gutter-x:1.5rem;--bs-gutter-y:0;display:flex;flex-wrap:wrap;margin-top:calc(-1 * var(--bs-gutter-y));margin-right:calc(-.5 * var(--bs-gutter-x));margin-left:calc(-.5 * var(--bs-gutter-x))}
        .col{flex:1 0 0%}
        .col-md-12{flex:0 0 auto;width:100%}
        .btn{display:inline-block;font-weight:400;line-height:1.5;color:#212529;text-align:center;text-decoration:none;vertical-align:middle;cursor:pointer;-webkit-user-select:none;-moz-user-select:none;user-select:none;background-color:transparent;border:1px solid transparent;padding:.375rem .75rem;font-size:1rem;border-radius:.375rem;transition:color .15s ease-in-out,background-color .15s ease-in-out,border-color .15s ease-in-out,box-shadow .15s ease-in-out}
        .btn-primary{color:#fff;background-color:#0d6efd;border-color:#0d6efd}
        .btn-success{color:#fff;background-color:#198754;border-color:#198754}
        .btn-info{color:#000;background-color:#0dcaf0;border-color:#0dcaf0}
        .card{position:relative;display:flex;flex-direction:column;min-width:0;word-wrap:break-word;background-color:#fff;background-clip:border-box;border:1px solid rgba(0,0,0,.125);border-radius:.375rem}
        .card-header{padding:.5rem 1rem;margin-bottom:0;background-color:rgba(0,0,0,.03);border-bottom:1px solid rgba(0,0,0,.125)}
        .card-body{flex:1 1 auto;padding:1rem 1rem}
        .table{width:100%;margin-bottom:1rem;color:#212529;vertical-align:top;border-color:#dee2e6}
        .table>tbody{vertical-align:inherit}
        .table>thead{vertical-align:bottom}
        .table>:not(caption)>*>*{padding:.5rem .5rem;background-color:var(--bs-table-bg);border-bottom-width:1px}
        .badge{display:inline-block;padding:.35em .65em;font-size:.75em;font-weight:700;line-height:1;color:#fff;text-align:center;white-space:nowrap;vertical-align:baseline;border-radius:.375rem}
        .bg-info{background-color:#0dcaf0!important}
        .bg-success{background-color:#198754!important}
        .bg-warning{background-color:#ffc107!important}
        .bg-danger{background-color:#dc3545!important}
        .text-muted{color:#6c757d!important}
        .d-flex{display:flex!important}
        .justify-content-between{justify-content:space-between!important}
        .align-items-center{align-items:center!important}
        .mb-4{margin-bottom:1.5rem!important}
        .gap-2{gap:.5rem!important}
        .me-2{margin-right:.5rem!important}
        .fas{font-family:"Font Awesome 6 Free";font-weight:900}
        .fa-download:before{content:"\\f019"}
        .fa-spinner:before{content:"\\f110"}
        .fa-spin{animation:fa-spin 2s infinite linear}
        @keyframes fa-spin{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}
        .alert{padding:.75rem 1.25rem;margin-bottom:1rem;border:1px solid transparent;border-radius:.375rem}
        .alert-success{color:#0f5132;background-color:#d1e7dd;border-color:#badbcc}
        .alert-danger{color:#842029;background-color:#f8d7da;border-color:#f5c2c7}
        .alert-dismissible{padding-right:4rem}
        .btn-close{padding:.25em .25em;margin:.25rem -.25rem -.25rem auto;background:transparent;border:0;border-radius:.375rem;opacity:.5}
        .btn-close:hover{color:#000;text-decoration:none;opacity:.75}
        .btn-close:focus{outline:0;box-shadow:0 0 0 .25rem rgba(13,110,253,.25);opacity:1}
        .btn-close:disabled{pointer-events:none;-webkit-user-select:none;-moz-user-select:none;user-select:none;opacity:.25}
        .btn-close::before{content:"\\00d7"}
        .fade{transition:opacity .15s linear}
        .show{opacity:1}
        .table-responsive{overflow-x:auto;-webkit-overflow-scrolling:touch}
        .border-primary{border-color:#0d6efd!important}
        .bg-primary{background-color:#0d6efd!important}
        .text-white{color:#fff!important}
        .form-check{display:block;min-height:1.5rem;padding-left:1.5em}
        .form-check-input{width:1em;height:1em;margin-top:.25em;vertical-align:top;background-color:#fff;background-repeat:no-repeat;background-position:center;background-size:contain;border:1px solid rgba(0,0,0,.25);-webkit-appearance:none;-moz-appearance:none;appearance:none}
        .form-check-input:checked{background-color:#0d6efd;border-color:#0d6efd}
        .form-check-input[type=checkbox]{border-radius:.25em}
        .form-check-inline{display:inline-block;margin-right:1rem}
        .flex-wrap{flex-wrap:wrap!important}
        .translation-text{white-space:normal;font-size:.95rem;line-height:1.6;text-align:left;word-wrap:break-word;padding:10px;background-color:#f8f9fa;border-radius:.25rem;margin:.5rem 0}
        .notam-text{font-family:'Courier New',monospace;background-color:#f8f9fa;padding:.5rem;border-radius:.25rem;margin:.5rem 0}
        .airport-badges{margin:.5rem 0}
        .airport-badges .badge{margin-right:.25rem;margin-bottom:.25rem}
        .time-info{font-size:.875rem;color:#6c757d}
        .notam-item{border-bottom:1px solid #dee2e6;padding:1rem 0}
        .notam-item:last-child{border-bottom:none}
        .small{font-size:.875em}
        .text-center{text-align:center!important}
        .fw-bold{font-weight:700!important}
        .mb-0{margin-bottom:0!important}
        .mb-1{margin-bottom:.25rem!important}
        .mb-2{margin-bottom:.5rem!important}
        .mb-3{margin-bottom:1rem!important}
        .mt-3{margin-top:1rem!important}
        .p-2{padding:.5rem!important}
        .px-2{padding-right:.5rem!important;padding-left:.5rem!important}
        .py-1{padding-top:.25rem!important;padding-bottom:.25rem!important}
        .border{border:1px solid #dee2e6!important}
        .border-top{border-top:1px solid #dee2e6!important}
        .border-bottom{border-bottom:1px solid #dee2e6!important}
        .rounded{border-radius:.375rem!important}
        .shadow{box-shadow:0 .5rem 1rem rgba(0,0,0,.15)!important}
        .w-100{width:100%!important}
        .h-100{height:100%!important}
        .position-relative{position:relative!important}
        .position-absolute{position:absolute!important}
        .position-fixed{position:fixed!important}
        .top-0{top:0!important}
        .end-0{right:0!important}
        .start-0{left:0!important}
        .translate-middle{transform:translate(-50%,-50%)!important}
        .z-3{z-index:3!important}
        .overflow-hidden{overflow:hidden!important}
        .opacity-75{opacity:.75!important}
        .opacity-50{opacity:.5!important}
        .opacity-25{opacity:.25!important}
        .opacity-0{opacity:0!important}
        .visually-hidden{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important}
        .stretched-link::after{position:absolute;top:0;right:0;bottom:0;left:0;z-index:1;content:""}
        .text-truncate{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
        .align-baseline{vertical-align:baseline!important}
        .align-top{vertical-align:top!important}
        .align-middle{vertical-align:middle!important}
        .align-bottom{vertical-align:bottom!important}
        .align-text-bottom{vertical-align:text-bottom!important}
        .align-text-top{vertical-align:text-top!important}
        .float-start{float:left!important}
        .float-end{float:right!important}
        .float-none{float:none!important}
        .user-select-all{-webkit-user-select:all!important;-moz-user-select:all!important;user-select:all!important}
        .user-select-auto{-webkit-user-select:auto!important;-moz-user-select:auto!important;user-select:auto!important}
        .user-select-none{-webkit-user-select:none!important;-moz-user-select:none!important;user-select:none!important}
        .pe-none{pointer-events:none!important}
        .pe-auto{pointer-events:auto!important}
        .rounded-circle{border-radius:50%!important}
        .rounded-pill{border-radius:50rem!important}
        .rounded-0{border-radius:0!important}
        .rounded-1{border-radius:.2rem!important}
        .rounded-2{border-radius:.375rem!important}
        .rounded-3{border-radius:.5rem!important}
        .visible{visibility:visible!important}
        .invisible{visibility:hidden!important}
        @media (max-width:768px){
            .container{padding:0 10px}
            .table{font-size:.875rem}
            .card-body{padding:.75rem}
            .btn{padding:.25rem .5rem;font-size:.875rem}
        }
    </style>
    """
    
    # Font Awesome 아이콘을 위한 CSS 추가
    fontawesome_css = """
    <style>
        @font-face{font-family:"Font Awesome 6 Free";font-style:normal;font-weight:400;font-display:block;src:url("data:font/woff2;base64,") format("woff2")}
        .fas{font-family:"Font Awesome 6 Free";font-weight:900}
        .fa-download:before{content:"\\f019"}
        .fa-spinner:before{content:"\\f110"}
        .fa-map-marked-alt:before{content:"\\f5fa"}
        .fa-spin{animation:fa-spin 2s infinite linear}
        @keyframes fa-spin{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}
    </style>
    """
    
    # 외부 링크를 제거하고 로컬 스타일로 대체
    processed_html = html_content
    
    # Bootstrap CDN 링크 제거
    processed_html = processed_html.replace(
        '<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">',
        bootstrap_css
    )
    
    # Font Awesome CDN 링크 제거
    processed_html = processed_html.replace(
        '<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">',
        fontawesome_css
    )
    
    # Bootstrap JS CDN 링크 제거 (기본 기능만 유지)
    processed_html = processed_html.replace(
        '<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>',
        '<script>/* Bootstrap JS functionality removed for offline use */</script>'
    )
    
    # HTML 저장 버튼 비활성화 (오프라인에서는 불필요)
    processed_html = processed_html.replace(
        'onclick="saveAsHTML()"',
        'onclick="alert(\'오프라인 모드에서는 사용할 수 없습니다.\')"'
    )
    
    return processed_html

@app.route('/download_html/<filename>')
def download_html(filename):
    """저장된 HTML 파일 다운로드"""
    try:
        save_dir = os.path.join(os.path.dirname(__file__), 'saved_results')
        file_path = os.path.join(save_dir, filename)
        
        if not os.path.exists(file_path):
            return jsonify({'error': '파일을 찾을 수 없습니다.'}), 404
        
        return send_file(file_path, as_attachment=True, download_name=filename)
        
    except Exception as e:
        logger.error(f"HTML 다운로드 중 오류: {str(e)}")
        return jsonify({'error': f'HTML 다운로드 중 오류가 발생했습니다: {str(e)}'}), 500


@app.route('/health')
def health():
    """헬스 체크 엔드포인트"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    # Cloud Run에서는 PORT 환경변수를 사용, 로컬에서는 5005 사용
    port = int(os.environ.get('PORT', 5005))
    app.run(debug=True, host='0.0.0.0', port=port)