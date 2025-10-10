#!/usr/bin/env python3
"""
NOTAM 종합 분석기 - GEMINI AI를 활용한 고급 NOTAM 분석
"""

import google.generativeai as genai
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

class NotamComprehensiveAnalyzer:
    """GEMINI AI를 활용한 NOTAM 종합 분석기"""
    
    def __init__(self):
        """초기화"""
        self.api_key = os.getenv('GEMINI_API_KEY')
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-pro')
        else:
            self.model = None
    
    def analyze_airport_notams_comprehensive(self, airport_code: str, notams_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        공항별 NOTAM을 종합적으로 분석 (GEMINI AI 활용)
        
        Args:
            airport_code: 공항 코드
            notams_data: NOTAM 데이터 리스트
            
        Returns:
            Dict[str, Any]: 종합 분석 결과
        """
        if not self.model:
            return self._fallback_analysis(airport_code, notams_data)
        
        # 해당 공항의 NOTAM 필터링
        airport_notams = self._filter_airport_notams(airport_code, notams_data)
        
        if not airport_notams:
            return {
                'airport_code': airport_code,
                'analysis_type': 'comprehensive',
                'summary': f'{airport_code} 공항에는 현재 NOTAM이 없습니다.',
                'critical_issues': [],
                'approach_landing_guidance': [],
                'ground_operations': [],
                'recommendations': []
            }
        
        # GEMINI AI로 종합 분석
        analysis_result = self._gemini_comprehensive_analysis(airport_code, airport_notams)
        
        return analysis_result
    
    def _filter_airport_notams(self, airport_code: str, notams_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """특정 공항의 NOTAM 필터링"""
        filtered_notams = []
        
        for notam in notams_data:
            # airports 필드에서 확인
            airports = notam.get('airports', [])
            if isinstance(airports, list) and airport_code in airports:
                filtered_notams.append(notam)
                continue
            
            # airport_code 필드에서 확인
            if notam.get('airport_code') == airport_code:
                filtered_notams.append(notam)
                continue
            
            # text/description에서 공항 코드 확인
            text = notam.get('text', '').upper()
            description = notam.get('description', '').upper()
            
            if airport_code in text or airport_code in description:
                filtered_notams.append(notam)
        
        return filtered_notams
    
    def _gemini_comprehensive_analysis(self, airport_code: str, notams: List[Dict[str, Any]]) -> Dict[str, Any]:
        """GEMINI AI를 활용한 종합 분석"""
        
        # NOTAM 텍스트 준비
        notam_texts = []
        for i, notam in enumerate(notams, 1):
            text = notam.get('text', '')
            description = notam.get('description', '')
            content = text if text else description
            
            notam_texts.append(f"[NOTAM #{i}]: {airport_code} - {content}")
        
        notam_summary = "\n".join(notam_texts)
        
        # GEMINI AI 프롬프트
        prompt = f"""
당신은 항공 전문가입니다. 다음 {airport_code} 공항의 NOTAM들을 종합 분석하여 실무진이 즉시 활용할 수 있는 분석 보고서를 작성해주세요.

NOTAM 목록:
{notam_summary}

다음 형식으로 JSON 응답해주세요:
{{
    "airport_code": "{airport_code}",
    "analysis_type": "comprehensive",
    "summary": "전체 요약 (2-3문장)",
    "critical_issues": [
        {{
            "category": "접근/착륙/지상운영",
            "issue": "구체적인 문제",
            "impact": "운항에 미치는 영향",
            "notam_refs": ["NOTAM #번호"]
        }}
    ],
    "approach_landing_guidance": [
        {{
            "runway": "활주로 번호",
            "approach_type": "접근 방식",
            "restrictions": "제한사항",
            "recommendations": "권장사항"
        }}
    ],
    "ground_operations": [
        {{
            "area": "지역/택싱웨이",
            "restrictions": "제한사항",
            "alternatives": "대안"
        }}
    ],
    "recommendations": [
        "실무적 권장사항 1",
        "실무적 권장사항 2"
    ]
}}

중요한 점:
1. Critical, High, Medium 우선순위로 분류
2. 접근(Approach)과 착륙 시 주의사항 명확히 구분
3. 지상운영 시 주의사항 별도 정리
4. 실무진이 즉시 활용할 수 있는 구체적 조언
5. NOTAM 번호 참조 포함
"""
        
        try:
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()
            
            # JSON 파싱 시도
            import json
            try:
                # JSON 부분만 추출
                json_start = result_text.find('{')
                json_end = result_text.rfind('}') + 1
                if json_start != -1 and json_end != -1:
                    json_text = result_text[json_start:json_end]
                    result = json.loads(json_text)
                    result['timestamp'] = datetime.now().isoformat()
                    return result
            except json.JSONDecodeError:
                pass
            
            # JSON 파싱 실패 시 텍스트 기반 응답
            return {
                'airport_code': airport_code,
                'analysis_type': 'comprehensive',
                'summary': f'{airport_code} 공항 NOTAM 종합 분석 완료',
                'gemini_analysis': result_text,
                'critical_issues': [],
                'approach_landing_guidance': [],
                'ground_operations': [],
                'recommendations': [],
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"GEMINI 분석 오류: {e}")
            return self._fallback_analysis(airport_code, notams)
    
    def _fallback_analysis(self, airport_code: str, notams: List[Dict[str, Any]]) -> Dict[str, Any]:
        """GEMINI 사용 불가 시 기본 분석"""
        return {
            'airport_code': airport_code,
            'analysis_type': 'basic',
            'summary': f'{airport_code} 공항 {len(notams)}개 NOTAM 분석 완료 (기본 분석)',
            'total_notams': len(notams),
            'critical_issues': [],
            'approach_landing_guidance': [],
            'ground_operations': [],
            'recommendations': ['GEMINI AI 분석을 위해 API 키를 설정해주세요.'],
            'timestamp': datetime.now().isoformat()
        }

def analyze_flight_airports_comprehensive(dep: str, dest: str, altn: str = None, edto: str = None, notams_data: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    항공편의 모든 공항에 대한 종합 NOTAM 분석 (GEMINI AI 활용)
    
    Args:
        dep: 출발 공항
        dest: 목적지 공항
        altn: 대체 공항 (선택)
        edto: EDTO 공항 (선택)
        notams_data: NOTAM 데이터
        
    Returns:
        Dict[str, Any]: 전체 종합 분석 결과
    """
    if not notams_data:
        notams_data = []
    
    analyzer = NotamComprehensiveAnalyzer()
    
    # 각 공항별 종합 분석
    airports = {
        'DEP': dep,
        'DEST': dest
    }
    
    if altn:
        airports['ALTN'] = altn
    if edto:
        airports['EDTO'] = edto
    
    results = {}
    for airport_type, airport_code in airports.items():
        results[airport_type] = analyzer.analyze_airport_notams_comprehensive(airport_code, notams_data)
    
    # 전체 요약
    total_notams = sum(len(analyzer._filter_airport_notams(airport_code, notams_data)) 
                      for airport_code in airports.values())
    
    return {
        'airports': results,
        'summary': {
            'total_airports': len(airports),
            'total_notams': total_notams,
            'analysis_type': 'comprehensive_gemini'
        },
        'timestamp': datetime.now().isoformat()
    }
