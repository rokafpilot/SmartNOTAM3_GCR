"""
Smart NOTAM3 - 시간 필터링과 로컬시간 변환이 적용된 NOTAM 처리 애플리케이션
"""

from flask import Flask, request, render_template, jsonify, redirect, url_for, flash
from werkzeug.utils import secure_filename
import os
import logging
from datetime import datetime
import json

# 로컬 모듈
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.pdf_converter import PDFConverter
from src.notam_filter import NOTAMFilter  
from src.notam_translator import NOTAMTranslator
from src.optimized_translator import OptimizedNOTAMTranslator
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

# 폴더 생성
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TEMP_FOLDER, exist_ok=True)

# 모듈 초기화
pdf_converter = PDFConverter()
notam_filter = NOTAMFilter()
notam_translator = NOTAMTranslator()
optimized_translator = OptimizedNOTAMTranslator(max_workers=5, batch_size=10)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            flash('파일이 선택되지 않았습니다.')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('파일이 선택되지 않았습니다.')
            return redirect(request.url)
        
        if file and file.filename and allowed_file(file.filename):
            # 파일 저장
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # PDF 텍스트 변환
            logger.info(f"PDF 변환 시작: {filepath}")
            text = pdf_converter.convert_pdf_to_text(filepath)
            
            if not text.strip():
                flash('PDF에서 텍스트를 추출할 수 없습니다.')
                return redirect(url_for('index'))
            
            # NOTAM 필터링
            logger.info("NOTAM 필터링 시작")
            notams = notam_filter.filter_korean_air_notams(text)
            
            # 공항 코드 추출 (필터링 전)
            all_airports = set()
            for notam in notams:
                airport_codes = notam.get('airport_codes', [])
                all_airports.update(airport_codes)
            
            # 공항 필터링 처리 (선택사항)
            airport_filter_data = request.form.get('airport_filter')
            if airport_filter_data:
                try:
                    airport_filter = json.loads(airport_filter_data)
                    selected_airports = airport_filter.get('selected_airports', [])
                    
                    if selected_airports:
                        logger.info(f"공항 필터 적용: {selected_airports}")
                        # 선택된 공항과 관련된 NOTAM만 필터링
                        filtered_notams = []
                        for notam in notams:
                            notam_airports = notam.get('airport_codes', [])
                            # 하나라도 선택된 공항과 일치하면 포함
                            if any(airport in selected_airports for airport in notam_airports):
                                filtered_notams.append(notam)
                        
                        notams = filtered_notams
                        logger.info(f"공항 필터링 후 NOTAM 수: {len(notams)}개")
                        
                except Exception as e:
                    logger.error(f"공항 필터 파싱 오류: {str(e)}")
            
            # NOTAM 시간을 로컬 시간으로 변환
            for notam in notams:
                airport_codes = notam.get('airport_codes', [])
                airport_code = airport_codes[0] if airport_codes else 'RKSI'  # 기본값: 인천공항
                
                effective_time = notam.get('effective_time', '')
                expiry_time = notam.get('expiry_time', '')
                
                # 로컬 시간으로 변환된 시간 문자열 생성
                if effective_time and expiry_time:
                    local_time_str = notam_filter.format_notam_time_with_local(
                        effective_time, expiry_time, airport_code
                    )
                    notam['local_time_display'] = local_time_str
            
            if not notams:
                flash('필터링된 NOTAM이 없습니다.')
                return redirect(url_for('index'))
            
            # NOTAM 번역 및 요약 (최적화된 배치 처리)
            logger.info(f"최적화된 번역 시작: {len(notams)}개 NOTAM")
            start_time = datetime.now()
            
            # 최적화된 번역기로 모든 NOTAM을 한 번에 처리
            translated_notams = optimized_translator.process_notams_optimized(notams)
            
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            logger.info(f"최적화된 번역 완료: {len(translated_notams)}개 NOTAM, {processing_time:.2f}초")
            logger.info(f"평균 처리 시간: {processing_time/len(translated_notams):.2f}초/NOTAM")
            
            # 캐시 통계 로깅
            cache_stats = optimized_translator.get_cache_stats()
            logger.info(f"캐시 통계: {cache_stats}")
            
            # 결과를 원래 notams 리스트에 반영
            notams = translated_notams
            
            # 템플릿에 공항 정보도 전달
            return render_template('results.html', 
                                 notams=notams, 
                                 current_date=datetime.now().strftime('%Y-%m-%d'),
                                 all_airports=sorted(list(all_airports)))
        
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
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_filename = f"temp_{timestamp}_{filename}"
        temp_filepath = os.path.join(app.config['TEMP_FOLDER'], temp_filename)
        file.save(temp_filepath)
        
        try:
            logger.info("PDF 텍스트 변환 시작")
            # PDF 텍스트 변환
            text = pdf_converter.convert_pdf_to_text(temp_filepath)
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

if __name__ == '__main__':
    # 포트 5005에서 실행
    app.run(debug=True, host='0.0.0.0', port=5005)