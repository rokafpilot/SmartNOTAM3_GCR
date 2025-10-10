#!/usr/bin/env python3
"""
공항별 주요 NOTAM 분석기
DEP (출발), DEST (목적지), ALTN (대체), EDTO 공항의 주요 NOTAM 사항을 정리 분석
"""

import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

class AirportNotamAnalyzer:
    """공항별 주요 NOTAM 분석기"""
    
    def __init__(self):
        """초기화"""
        # 주요 NOTAM 카테고리 키워드
        self.critical_keywords = {
            'runway': ['RWY', 'RUNWAY', 'TAXIWAY', 'APRON', 'PARKING'],
            'approach': ['ILS', 'VOR', 'NDB', 'GPS', 'RNAV', 'APPROACH', 'MISSED APPROACH'],
            'lighting': ['LIGHTING', 'PAPI', 'VASI', 'REIL', 'MIRL', 'HIRL'],
            'weather': ['WEATHER', 'WIND', 'VISIBILITY', 'CEILING', 'RVR'],
            'fuel': ['FUEL', 'AVGAS', 'JET A1', 'FUELING'],
            'services': ['FIRE', 'RESCUE', 'MEDICAL', 'CUSTOMS', 'IMMIGRATION'],
            'restrictions': ['CLOSED', 'RESTRICTED', 'PROHIBITED', 'NOT AVAILABLE'],
            'construction': ['CONSTRUCTION', 'WORK IN PROGRESS', 'MAINTENANCE'],
            'equipment': ['RADAR', 'COMMUNICATION', 'NAVIGATION', 'SURVEILLANCE']
        }
        
        # 우선순위별 중요도
        self.priority_levels = {
            'critical': ['CLOSED', 'PROHIBITED', 'NOT AVAILABLE', 'EMERGENCY'],
            'high': ['RESTRICTED', 'LIMITED', 'CONSTRUCTION', 'MAINTENANCE'],
            'medium': ['CAUTION', 'ADVISORY', 'TEMPORARY'],
            'low': ['INFORMATION', 'NOTICE', 'GENERAL']
        }
    
    def analyze_airport_notams(self, airport_code: str, notams_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        특정 공항의 NOTAM 데이터를 분석하여 주요 사항을 정리
        
        Args:
            airport_code: 공항 코드 (예: RKSI, KSEA)
            notams_data: NOTAM 데이터 리스트
            
        Returns:
            Dict[str, Any]: 분석 결과
        """
        # 해당 공항의 NOTAM 필터링
        airport_notams = self._filter_airport_notams(airport_code, notams_data)
        
        if not airport_notams:
            return {
                'airport_code': airport_code,
                'total_notams': 0,
                'analysis': '해당 공항의 NOTAM이 없습니다.',
                'categories': {},
                'priority_summary': {},
                'recommendations': []
            }
        
        # 카테고리별 분석
        categorized_notams = self._categorize_notams(airport_notams)
        
        # 우선순위별 분석
        priority_analysis = self._analyze_by_priority(airport_notams)
        
        # 주요 사항 추출
        key_issues = self._extract_key_issues(airport_notams)
        
        # 권장사항 생성
        recommendations = self._generate_recommendations(categorized_notams, priority_analysis)
        
        return {
            'airport_code': airport_code,
            'total_notams': len(airport_notams),
            'analysis': self._generate_summary_analysis(airport_code, categorized_notams, priority_analysis),
            'categories': categorized_notams,
            'priority_summary': priority_analysis,
            'key_issues': key_issues,
            'recommendations': recommendations,
            'detailed_notams': airport_notams[:10]  # 상위 10개 NOTAM
        }
    
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
    
    def _categorize_notams(self, notams: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """NOTAM을 카테고리별로 분류"""
        categories = {category: [] for category in self.critical_keywords.keys()}
        categories['other'] = []
        
        for notam in notams:
            text = (notam.get('text', '') + ' ' + notam.get('description', '')).upper()
            categorized = False
            
            for category, keywords in self.critical_keywords.items():
                if any(keyword in text for keyword in keywords):
                    categories[category].append(notam)
                    categorized = True
                    break
            
            if not categorized:
                categories['other'].append(notam)
        
        return categories
    
    def _analyze_by_priority(self, notams: List[Dict[str, Any]]) -> Dict[str, Any]:
        """우선순위별 NOTAM 분석"""
        priority_counts = {level: 0 for level in self.priority_levels.keys()}
        priority_notams = {level: [] for level in self.priority_levels.keys()}
        
        for notam in notams:
            text = (notam.get('text', '') + ' ' + notam.get('description', '')).upper()
            
            for level, keywords in self.priority_levels.items():
                if any(keyword in text for keyword in keywords):
                    priority_counts[level] += 1
                    priority_notams[level].append(notam)
                    break
        
        return {
            'counts': priority_counts,
            'notams': priority_notams,
            'highest_priority': max(priority_counts, key=priority_counts.get) if any(priority_counts.values()) else 'none'
        }
    
    def _extract_key_issues(self, notams: List[Dict[str, Any]]) -> List[str]:
        """주요 이슈 추출 - 상세한 분석"""
        key_issues = []
        
        # 우선순위별로 NOTAM 분류
        critical_notams = []
        high_notams = []
        medium_notams = []
        
        for notam in notams:
            priority = self._get_priority_level(notam.get('text', ''))
            if priority == 'critical':
                critical_notams.append(notam)
            elif priority == 'high':
                high_notams.append(notam)
            elif priority == 'medium':
                medium_notams.append(notam)
        
        # Critical 이슈들
        for notam in critical_notams[:3]:  # 최대 3개
            text = notam.get('text', '')
            if 'CLOSED' in text.upper() or 'PROHIBITED' in text.upper():
                key_issues.append(f"🚨 폐쇠/금지: {self._extract_key_info(text)}")
            elif 'NOT AVAILABLE' in text.upper():
                key_issues.append(f"🚨 사용 불가: {self._extract_key_info(text)}")
            elif 'EMERGENCY' in text.upper():
                key_issues.append(f"🚨 비상: {self._extract_key_info(text)}")
        
        # High 이슈들
        for notam in high_notams[:3]:  # 최대 3개
            text = notam.get('text', '')
            if 'RESTRICTED' in text.upper():
                key_issues.append(f"⚠️ 제한: {self._extract_key_info(text)}")
            elif 'CONSTRUCTION' in text.upper() or 'MAINTENANCE' in text.upper():
                key_issues.append(f"⚠️ 공사/정비: {self._extract_key_info(text)}")
            elif 'LIMITED' in text.upper():
                key_issues.append(f"⚠️ 제한적 운영: {self._extract_key_info(text)}")
        
        # Medium 이슈들 (접근/착륙 관련)
        approach_notams = [n for n in medium_notams if any(kw in n.get('text', '').upper() for kw in ['APPROACH', 'ILS', 'RNAV', 'GPS'])]
        for notam in approach_notams[:2]:  # 최대 2개
            text = notam.get('text', '')
            key_issues.append(f"ℹ️ 접근 절차: {self._extract_key_info(text)}")
        
        return key_issues[:8]  # 최대 8개 반환
    
    def _extract_notam_summary(self, notam: Dict[str, Any]) -> Optional[str]:
        """NOTAM의 핵심 내용 추출"""
        text = notam.get('text', '')
        description = notam.get('description', '')
        
        # 첫 번째 문장이나 주요 내용 추출
        content = text if text else description
        if content:
            # 첫 100자 정도만 추출
            summary = content[:100].strip()
            if len(content) > 100:
                summary += "..."
            return summary
        
        return None
    
    def _generate_recommendations(self, categories: Dict[str, List], priority_analysis: Dict[str, Any]) -> List[str]:
        """권장사항 생성"""
        recommendations = []
        
        # 우선순위 기반 권장사항
        if priority_analysis['counts']['critical'] > 0:
            recommendations.append("🔴 긴급: Critical NOTAM이 있습니다. 반드시 확인하세요.")
        
        if priority_analysis['counts']['high'] > 0:
            recommendations.append("🟡 주의: High priority NOTAM이 있습니다. 사전 확인 필요.")
        
        # 카테고리 기반 권장사항
        if categories['runway']:
            recommendations.append("🛬 활주로 관련 NOTAM이 있습니다. 활주로 상태를 확인하세요.")
        
        if categories['approach']:
            recommendations.append("📡 접근 절차 관련 NOTAM이 있습니다. 접근 방식 변경 가능성을 확인하세요.")
        
        if categories['fuel']:
            recommendations.append("⛽ 연료 관련 NOTAM이 있습니다. 연료 공급 상태를 확인하세요.")
        
        if categories['construction']:
            recommendations.append("🏗️ 공사 관련 NOTAM이 있습니다. 지상 활동에 주의하세요.")
        
        if not recommendations:
            recommendations.append("✅ 특별한 주의사항이 없습니다. 정상 운항 가능합니다.")
        
        return recommendations
    
    def _generate_summary_analysis(self, airport_code: str, categories: Dict[str, List], priority_analysis: Dict[str, Any]) -> str:
        """상세 분석 생성"""
        total_notams = sum(len(notams) for notams in categories.values())
        
        if total_notams == 0:
            return f"{airport_code} 공항에는 현재 NOTAM이 없습니다."
        
        analysis = f"**{airport_code} 공항의 NOTAM들을 종합 분석**해보면, **접근(Approach)과 착륙 시 주의사항**을 명확히 파악할 수 있습니다.\n\n"
        
        # 우선순위별 상세 분석
        priority_counts = priority_analysis['counts']
        critical_count = priority_counts.get('critical', 0)
        high_count = priority_counts.get('high', 0)
        medium_count = priority_counts.get('medium', 0)
        low_count = priority_counts.get('low', 0)
        
        if critical_count > 0 or high_count > 0:
            analysis += "## 🛬 **접근 및 착륙 시 주요 주의사항**\n\n"
            
            if critical_count > 0:
                analysis += "### **1. 🚨 Critical 주의사항**\n\n"
                critical_notams = []
                for category, notams in categories.items():
                    for notam in notams:
                        if self._get_priority_level(notam.get('text', '')) == 'critical':
                            critical_notams.append(notam)
                
                # Critical NOTAM들을 카테고리별로 분류
                critical_by_category = {}
                for notam in critical_notams:
                    category = self._categorize_notam(notam.get('text', ''))
                    if category not in critical_by_category:
                        critical_by_category[category] = []
                    critical_by_category[category].append(notam)
                
                for category, notams in critical_by_category.items():
                    if category == 'approach':
                        analysis += "#### **RNAV(RNP) 접근 제한**\n"
                        for i, notam in enumerate(notams[:3], 1):  # 최대 3개만 표시
                            analysis += f"- **NOTAM #{i}**: {self._extract_key_info(notam.get('text', ''))}\n"
                        analysis += "\n"
                    elif category == 'runway':
                        analysis += "#### **활주로 제한**\n"
                        for i, notam in enumerate(notams[:3], 1):
                            analysis += f"- **NOTAM #{i}**: {self._extract_key_info(notam.get('text', ''))}\n"
                        analysis += "\n"
                    elif category == 'lighting':
                        analysis += "#### **조명 시스템 제한**\n"
                        for i, notam in enumerate(notams[:3], 1):
                            analysis += f"- **NOTAM #{i}**: {self._extract_key_info(notam.get('text', ''))}\n"
                        analysis += "\n"
            
            if high_count > 0:
                analysis += "### **2. ⚠️ High 주의사항**\n\n"
                high_notams = []
                for category, notams in categories.items():
                    for notam in notams:
                        if self._get_priority_level(notam.get('text', '')) == 'high':
                            high_notams.append(notam)
                
                # High NOTAM들을 카테고리별로 분류
                high_by_category = {}
                for notam in high_notams:
                    category = self._categorize_notam(notam.get('text', ''))
                    if category not in high_by_category:
                        high_by_category[category] = []
                    high_by_category[category].append(notam)
                
                for category, notams in high_by_category.items():
                    if category == 'runway':
                        analysis += "#### **활주로별 접근 제한**\n"
                        for i, notam in enumerate(notams[:3], 1):
                            analysis += f"- **{self._extract_runway_info(notam.get('text', ''))}**: {self._extract_key_info(notam.get('text', ''))}\n"
                        analysis += "\n"
                    elif category == 'approach':
                        analysis += "#### **접근 절차 제한**\n"
                        for i, notam in enumerate(notams[:3], 1):
                            analysis += f"- **{self._extract_approach_info(notam.get('text', ''))}**: {self._extract_key_info(notam.get('text', ''))}\n"
                        analysis += "\n"
        
        # 착륙 후 지상 주의사항
        ground_notams = []
        for category, notams in categories.items():
            if category in ['runway', 'lighting']:
                for notam in notams:
                    text = notam.get('text', '').upper()
                    if any(keyword in text for keyword in ['TAXIWAY', 'APRON', 'PARKING', 'GROUND']):
                        ground_notams.append(notam)
        
        if ground_notams:
            analysis += "### **3. 🛬 착륙 후 지상 주의사항**\n\n"
            
            # 지상 관련 NOTAM들을 세부 카테고리로 분류
            taxiway_notams = [n for n in ground_notams if 'TAXIWAY' in n.get('text', '').upper()]
            apron_notams = [n for n in ground_notams if any(kw in n.get('text', '').upper() for kw in ['APRON', 'PARKING', 'STAND'])]
            
            if taxiway_notams:
                analysis += "#### **택싱웨이 제한**\n"
                for i, notam in enumerate(taxiway_notams[:5], 1):
                    analysis += f"- **NOTAM #{i}**: {self._extract_key_info(notam.get('text', ''))}\n"
                analysis += "\n"
            
            if apron_notams:
                analysis += "#### **에이프런 제한**\n"
                for i, notam in enumerate(apron_notams[:3], 1):
                    analysis += f"- **NOTAM #{i}**: {self._extract_key_info(notam.get('text', ''))}\n"
                analysis += "\n"
        
        # 종합 권장사항
        analysis += "## 📋 **종합 권장사항**\n\n"
        
        if critical_count > 0 or high_count > 0:
            analysis += "### **🛬 접근 시:**\n"
            analysis += "1. **GPS RAIM 상태 확인** 필수\n"
            analysis += "2. **항공기 RNAV(RNP) 인증 상태** 확인\n"
            analysis += "3. **활주로별 접근 절차 변경사항** 숙지\n"
            analysis += "4. **시정 및 결심 고도 변경사항** 확인\n\n"
            
            analysis += "### **🛬 착륙 후:**\n"
            if taxiway_notams:
                analysis += "1. **제한된 택싱웨이 사용 시 주의**\n"
            if apron_notams:
                analysis += "2. **에이프런 제한사항 확인**\n"
            analysis += "3. **Ground Control과의 통신을 통한 안전한 경로 확인**\n\n"
            
            analysis += "### **🚨 특별 주의:**\n"
            if any('RNAV' in n.get('text', '') for category_notams in categories.values() for n in category_notams):
                analysis += "- **RNAV(RNP) 접근**: 항공기 인증 및 GPS 상태 필수 확인\n"
            if any('ILS' in n.get('text', '') for category_notams in categories.values() for n in category_notams):
                analysis += "- **ILS 접근**: 장비 요구사항 변경 확인\n"
            if ground_notams:
                analysis += "- **지상 이동**: 제한된 택싱웨이 및 속도 제한 준수\n\n"
        
        # 실무적 조언
        analysis += "## 💡 **실무적 조언**\n\n"
        analysis += f"**{airport_code} 공항은 현재 많은 접근 절차가 변경되어 있어** 사전에 **최신 접근 차트 및 NOTAM 확인**이 필수입니다. "
        
        if any('RNAV' in n.get('text', '') for category_notams in categories.values() for n in category_notams):
            analysis += "특히 **RNAV(RNP) 접근을 계획하는 경우** 항공기 인증 상태와 GPS RAIM 예측을 반드시 확인해야 합니다. "
        
        if ground_notams:
            analysis += "**지상에서는 택싱웨이 제한이 많으므로** **Ground Control과의 통신을 통해 안전한 경로를 확인**하는 것이 중요합니다! 🚀"
        
        return analysis
    
    def _extract_key_info(self, text: str) -> str:
        """NOTAM 텍스트에서 핵심 정보 추출"""
        if not text:
            return "정보 없음"
        
        # 첫 번째 문장 또는 핵심 키워드 추출
        sentences = text.split('.')
        if sentences:
            first_sentence = sentences[0].strip()
            if len(first_sentence) > 100:
                return first_sentence[:100] + "..."
            return first_sentence
        
        return text[:100] + "..." if len(text) > 100 else text
    
    def _extract_runway_info(self, text: str) -> str:
        """활주로 정보 추출"""
        import re
        runway_match = re.search(r'RWY\s+(\d+[LRC]?/?\d*[LRC]?)', text.upper())
        if runway_match:
            return f"활주로 {runway_match.group(1)}"
        return "활주로 정보"
    
    def _extract_approach_info(self, text: str) -> str:
        """접근 절차 정보 추출"""
        import re
        approach_match = re.search(r'(ILS|RNAV|GPS|VOR|NDB)\s+([A-Z0-9]+)', text.upper())
        if approach_match:
            return f"{approach_match.group(1)} {approach_match.group(2)}"
        return "접근 절차"
    
    def _get_priority_level(self, text: str) -> str:
        """NOTAM 텍스트의 우선순위 레벨 결정"""
        if not text:
            return 'low'
        
        text_upper = text.upper()
        
        # Critical 키워드 확인
        for keyword in self.priority_levels['critical']:
            if keyword in text_upper:
                return 'critical'
        
        # High 키워드 확인
        for keyword in self.priority_levels['high']:
            if keyword in text_upper:
                return 'high'
        
        # Medium 키워드 확인
        for keyword in self.priority_levels['medium']:
            if keyword in text_upper:
                return 'medium'
        
        # Low 키워드 확인
        for keyword in self.priority_levels['low']:
            if keyword in text_upper:
                return 'low'
        
        # 기본값
        return 'low'
    
    def _categorize_notam(self, text: str) -> str:
        """단일 NOTAM의 카테고리 결정"""
        if not text:
            return 'other'
        
        text_upper = text.upper()
        
        # 각 카테고리별 키워드 확인
        for category, keywords in self.critical_keywords.items():
            for keyword in keywords:
                if keyword in text_upper:
                    return category
        
        return 'other'

def analyze_flight_airports(dep: str, dest: str, altn: str = None, edto: str = None, notams_data: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    항공편의 모든 공항에 대한 NOTAM 분석
    
    Args:
        dep: 출발 공항
        dest: 목적지 공항
        altn: 대체 공항 (선택)
        edto: EDTO 공항 (선택)
        notams_data: NOTAM 데이터
        
    Returns:
        Dict[str, Any]: 전체 분석 결과
    """
    if not notams_data:
        notams_data = []
    
    analyzer = AirportNotamAnalyzer()
    
    # 각 공항별 분석
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
        results[airport_type] = analyzer.analyze_airport_notams(airport_code, notams_data)
    
    # 전체 요약
    total_notams = sum(result['total_notams'] for result in results.values())
    critical_airports = [airport_type for airport_type, result in results.items() 
                        if result.get('priority_summary', {}).get('counts', {}).get('critical', 0) > 0]
    
    return {
        'airports': results,
        'summary': {
            'total_airports': len(airports),
            'total_notams': total_notams,
            'critical_airports': critical_airports,
            'overall_status': 'CRITICAL' if critical_airports else 'NORMAL'
        },
        'timestamp': datetime.now().isoformat()
    }
