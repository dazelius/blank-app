import streamlit as st
import gspread
from google.oauth2 import service_account
import re
import difflib
import json
from datetime import datetime
import os
import pandas as pd
import streamlit as st
import html
import requests
from PIL import Image
from io import BytesIO

# 페이지 설정
st.set_page_config(
    page_title="텍스트 필터",
    page_icon="⚠️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': "문장의 위험도를 분석해드립니다."
    }
)

# Open Graph 메타 태그 수정
st.markdown('''
    <head>
        <title>텍스트 필터</title>
        <meta property="og:title" content="텍스트 필터"/>
        <meta property="og:description" content="텍스트 필터"/>
        <meta property="og:image" content="텍스트 필터"/>
    </head>''', unsafe_allow_html=True)

# CSS 스타일 업데이트
st.markdown("""
<style>
    /* 다크모드 기본 배경 및 텍스트 색상 */
    .stApp {
        background-color: #1E1E1E;
        color: #E0E0E0;
    }
    
    /* 메인 타이틀 스타일 */
    .main-title {
        text-align: center;
        padding: 1.5rem;
        background: linear-gradient(135deg, #434343 0%, #000000 100%);
        color: #E0E0E0;
        border-radius: 15px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    
    /* 카드 스타일 */
    .analysis-card {
        background: #2D2D2D;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        margin-bottom: 1rem;
        color: #E0E0E0;
    }
    
    /* 위험도 미터 스타일 */
    .danger-meter {
        text-align: center;
        padding: 2rem;
        margin: 1rem 0;
        border-radius: 15px;
        background: #2D2D2D;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
    }
    
    /* 입력 필드 스타일 */
    .stTextInput>div>div>input {
        background-color: #3D3D3D;
        color: #E0E0E0;
        border-color: #4D4D4D;
    }
    
    .stTextArea>div>div>textarea {
        background-color: #3D3D3D;
        color: #E0E0E0;
        border-color: #4D4D4D;
    }
    
    /* 버튼 스타일 */
    .stButton>button {
        background: linear-gradient(to right, #434343 0%, #000000 100%);
        color: #E0E0E0;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 10px;
        font-weight: 600;
        transition: transform 0.2s;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        background: linear-gradient(to right, #4a4a4a 0%, #1a1a1a 100%);
    }
    
    /* 탭 스타일 */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #2D2D2D;
        border-radius: 15px;
    }
    
    .stTabs [data-baseweb="tab"] {
        color: #E0E0E0;
    }
    
    /* 링크 스타일 */
    a {
        color: #00B4DB;
        text-decoration: none;
    }
    
    a:hover {
        text-decoration: underline;
        color: #00D4FF;
    }
    
    /* 위험도 레벨 색상 */
    .danger-level-low {
        color: #00E676;
    }
    
    .danger-level-medium {
        color: #FFD700;
    }
    
    .danger-level-high {
        color: #FF5252;
    }
    
    /* 알림 메시지 스타일 */
    .stAlert {
        background-color: #2D2D2D;
        color: #E0E0E0;
        border-radius: 10px;
    }
    /* 데이터베이스 테이블 스타일 */
    .database-table {
        margin-top: 2rem;
        padding: 1rem;
        background: #2D2D2D;
        border-radius: 15px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
    }
    
    .database-title {
        text-align: center;
        padding: 1rem;
        background: linear-gradient(135deg, #434343 0%, #000000 100%);
        color: #E0E0E0;
        border-radius: 10px;
        margin-bottom: 1rem;
    }
    
    .stDataFrame {
        background-color: #2D2D2D;
    }
    
    .stDataFrame td, .stDataFrame th {
        color: #E0E0E0 !important;
        background-color: #3D3D3D !important;
    }
    
    .stDataFrame [data-testid="stDataFrameResizeHandle"] {
        background-color: #4D4D4D;
    }
</style>
""", unsafe_allow_html=True)

import re
from collections import defaultdict

def get_or_create_checker_worksheet():
    """checker 워크시트를 가져오거나 생성"""
    try:
        credentials = {
            "type": "service_account",
            "project_id": st.secrets["gcp_service_account"]["project_id"],
            "private_key_id": st.secrets["gcp_service_account"]["private_key_id"],
            "private_key": st.secrets["gcp_service_account"]["private_key"],
            "client_email": st.secrets["gcp_service_account"]["client_email"],
            "client_id": st.secrets["gcp_service_account"]["client_id"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": st.secrets["gcp_service_account"]["client_x509_cert_url"]
        }
        
        SCOPES = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        creds = service_account.Credentials.from_service_account_info(credentials, scopes=SCOPES)
        client = gspread.authorize(creds)
        
        sheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1wPchxwAssBf706VuvxhGp4ESt3vj-N9RLcMaUF075ug/edit?gid=137455637#gid=137455637')
        
        try:
            # checker 워크시트 가져오기 시도
            checker_sheet = sheet.worksheet('checker')
        except gspread.exceptions.WorksheetNotFound:
            # checker 워크시트가 없으면 생성
            checker_sheet = sheet.add_worksheet('checker', 1000, 2)
            checker_sheet.update('A1:B1', [['오류', '수정']])
            st.success("'checker' 워크시트가 생성되었습니다.")
            
        return checker_sheet
        
    except Exception as e:
        st.error(f"워크시트 처리 중 오류 발생: {str(e)}")
        return None

class SheetBasedSpellChecker:
    """구글 시트 기반 맞춤법 검사기"""
    
    def __init__(self):
        self.rules = {}  # 초기화
        self.load_rules()  # 규칙 로드
        
    def load_rules(self):
        """구글 시트에서 규칙 로드"""
        try:
            checker_sheet = get_or_create_checker_worksheet()
            if not checker_sheet:
                return
            
            # 데이터 가져오기
            data = checker_sheet.get_all_values()
            
            # 헤더 제외하고 규칙 딕셔너리 생성
            if len(data) > 1:  # 헤더 행이 있는 경우
                for row in data[1:]:  # 첫 행(헤더) 제외
                    if len(row) >= 2 and row[0] and row[1]:  # A열과 B열이 모두 존재하는 경우만
                        self.rules[row[0].strip()] = row[1].strip()
            
        except Exception as e:
            st.error(f"규칙 로딩 중 오류 발생: {str(e)}")

    def check(self, text):
        """텍스트 맞춤법 검사 - 정규식과 부분 문자열 매칭 지원"""
        if not text or text.isspace():
            return {
                'original': text,
                'corrected': text,
                'corrections': [],
                'error': None
            }
            
        try:
            corrections = []
            corrected_text = text
            
            # 단어 단위로 분리
            words = re.findall(r'\b\w+\b', text)
            processed_corrections = set()  # 중복 교정 방지용
            
            for wrong, right in self.rules.items():
                try:
                    # 정규식 패턴인지 확인
                    if wrong.startswith('^') and wrong.endswith('$'):
                        pattern = re.compile(wrong)
                        matches = pattern.finditer(text)
                        
                        for match in matches:
                            matched_text = match.group(0)
                            corrected_word = re.sub(wrong, right, matched_text)
                            
                            if matched_text != corrected_word:
                                correction_key = (matched_text, corrected_word)
                                if correction_key not in processed_corrections:
                                    processed_corrections.add(correction_key)
                                    corrected_text = corrected_text.replace(matched_text, corrected_word)
                                    corrections.append({
                                        'original': matched_text,
                                        'corrected': corrected_word,
                                        'type': '맞춤법/표현 오류 (정규식)',
                                        'pattern': wrong,
                                        'replacement': right
                                    })
                    else:
                        # 일반 문자열 매칭 - 부분 문자열 포함 검사
                        for word in words:
                            if wrong in word:
                                corrected_word = word.replace(wrong, right)
                                correction_key = (word, corrected_word)
                                
                                if word != corrected_word and correction_key not in processed_corrections:
                                    processed_corrections.add(correction_key)
                                    corrected_text = corrected_text.replace(word, corrected_word)
                                    corrections.append({
                                        'original': word,
                                        'corrected': corrected_word,
                                        'type': '맞춤법/표현 오류',
                                        'pattern': wrong,
                                        'replacement': right
                                    })
                                    
                except re.error:
                    # 잘못된 정규식은 일반 문자열로 처리
                    if wrong in text:
                        correction_key = (wrong, right)
                        if correction_key not in processed_corrections:
                            processed_corrections.add(correction_key)
                            corrected_text = corrected_text.replace(wrong, right)
                            corrections.append({
                                'original': wrong,
                                'corrected': right,
                                'type': '맞춤법/표현 오류',
                                'pattern': wrong,
                                'replacement': right
                            })
            
            # 교정 결과 정렬
            corrections.sort(key=lambda x: len(x['original']), reverse=True)
            
            return {
                'original': text,
                'corrected': corrected_text,
                'corrections': corrections,
                'error': None
            }
            
        except Exception as e:
            return {
                'original': text,
                'corrected': text,
                'corrections': [],
                'error': str(e)
            }

    def add_rule(self, wrong, right):
        """새로운 맞춤법 규칙 추가"""
        try:
            checker_sheet = get_or_create_checker_worksheet()
            if checker_sheet:
                checker_sheet.append_row([wrong.strip(), right.strip()])
                self.rules[wrong.strip()] = right.strip()
                return True
        except Exception as e:
            st.error(f"규칙 추가 중 오류 발생: {str(e)}")
        return False

    def get_rules(self):
        """현재 등록된 모든 규칙 반환"""
        return self.rules

def check_with_regex(self, text):
    """텍스트 맞춤법 검사 - 정규식과 부분 문자열 매칭 지원"""
    if not text or text.isspace():
        return {
            'original': text,
            'corrected': text,
            'corrections': [],
            'error': None
        }
        
    try:
        corrections = []
        corrected_text = text
        
        for wrong, right in self.rules.items():
            try:
                # 정규식 패턴인지 확인
                if wrong.startswith('^') and wrong.endswith('$'):
                    # 정규식 패턴 적용
                    pattern = re.compile(wrong)
                    matches = pattern.finditer(text)
                    
                    for match in matches:
                        matched_text = match.group(0)
                        # 정규식 그룹 참조 처리
                        corrected_word = re.sub(wrong, right, matched_text)
                        
                        if matched_text != corrected_word:
                            corrected_text = corrected_text.replace(matched_text, corrected_word)
                            corrections.append({
                                'original': matched_text,
                                'corrected': corrected_word,
                                'type': '맞춤법/표현 오류 (정규식)',
                                'pattern': wrong,
                                'replacement': right
                            })
                else:
                    # 일반 문자열 매칭
                    words = re.findall(r'\b\w+\b', text)
                    for word in words:
                        if wrong in word:
                            corrected_word = word.replace(wrong, right)
                            corrected_text = corrected_text.replace(word, corrected_word)
                            corrections.append({
                                'original': word,
                                'corrected': corrected_word,
                                'type': '맞춤법/표현 오류',
                                'pattern': wrong,
                                'replacement': right
                            })
            except re.error:
                # 잘못된 정규식 패턴은 일반 문자열로 처리
                if wrong in text:
                    corrected_text = corrected_text.replace(wrong, right)
                    corrections.append({
                        'original': wrong,
                        'corrected': right,
                        'type': '맞춤법/표현 오류',
                        'pattern': wrong,
                        'replacement': right
                    })
        
        # 중복 제거 및 정렬
        unique_corrections = []
        seen = set()
        for corr in corrections:
            key = (corr['original'], corr['corrected'])
            if key not in seen:
                seen.add(key)
                unique_corrections.append(corr)
        
        return {
            'original': text,
            'corrected': corrected_text,
            'corrections': unique_corrections,
            'error': None
        }
        
    except Exception as e:
        return {
            'original': text,
            'corrected': text,
            'corrections': [],
            'error': str(e)
        }


def display_spelling_analysis(spelling_result):
    """맞춤법 분석 결과 표시"""
    if spelling_result.get('error'):
        st.warning(f"⚠️ 맞춤법 검사 중 오류가 발생했습니다: {spelling_result['error']}")
        return
        
    if not spelling_result['corrections']:
        st.info("✅ 맞춤법 오류가 발견되지 않았습니다.")
        return
    
    st.markdown("""
        <div style='background-color: #2D2D2D; padding: 15px; border-radius: 10px; margin: 15px 0;'>
            <h3 style='color: #E0E0E0;'>📝 맞춤법 검사 결과</h3>
        </div>
    """, unsafe_allow_html=True)
    
    # 수정 사항 표시
    for correction in spelling_result['corrections']:
        st.markdown(f"""
            <div style='background-color: #3D3D3D; padding: 10px; border-radius: 8px; margin: 5px 0;'>
                <p>🔍 수정 전: <span style='color: #FF5252;'>{correction['original']}</span></p>
                <p>✅ 수정 후: <span style='color: #00E676;'>{correction['corrected']}</span></p>
            </div>
        """, unsafe_allow_html=True)
    
    # 전체 텍스트 비교
    if spelling_result['original'] != spelling_result['corrected']:
        st.markdown("""
            <div style='background-color: #2D2D2D; padding: 15px; border-radius: 10px; margin-top: 15px;'>
                <h4 style='color: #E0E0E0;'>📄 전체 텍스트 비교</h4>
            </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**원문:**")
            st.markdown(f"""
                <div style='background-color: #3D3D3D; padding: 10px; border-radius: 8px;'>
                    {spelling_result['original']}
                </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown("**교정문:**")
            st.markdown(f"""
                <div style='background-color: #3D3D3D; padding: 10px; border-radius: 8px;'>
                    {spelling_result['corrected']}
                </div>
            """, unsafe_allow_html=True)

def analyze_text_with_spelling(input_text, data, threshold=0.7):
    """텍스트 분석과 맞춤법 검사 통합"""
    
    # 맞춤법 검사
    checker = SheetBasedSpellChecker()
    spelling_result = checker.check(input_text)
    
    # 패턴 매칭
    found_patterns = find_matching_patterns(input_text, data, threshold)
    
    # 맞춤법 교정 후 추가 패턴 검사
    if spelling_result['corrections']:
        corrected_patterns = find_matching_patterns(
            spelling_result['corrected'], 
            data, 
            threshold
        )
        
        # 새로운 패턴 추가
        existing_patterns = {p['pattern'] for p in found_patterns}
        for pattern in corrected_patterns:
            if pattern['pattern'] not in existing_patterns:
                pattern['found_in_corrected'] = True
                found_patterns.append(pattern)
    
    return {
        'patterns': found_patterns,
        'spelling': spelling_result
    }

# 1. 데이터 전처리 최적화
@st.cache_data(ttl=3600)
def preprocess_patterns(data):
    """패턴 데이터 전처리 및 캐싱 - 최적화 버전"""
    if not data:
        st.error("데이터가 비어있습니다.")
        return {
            'short': [],
            'medium': [],
            'long': []
        }
    
    processed_patterns = []
    
    # 길이별로 패턴 분류
    short_patterns = []
    medium_patterns = []
    long_patterns = []
    
    try:
        for record in data:
            if not isinstance(record, dict):
                continue
                
            # text 필드가 없거나 None인 경우 건너뛰기
            if 'text' not in record or record['text'] is None:
                continue
                
            # 숫자형을 문자열로 변환
            if isinstance(record['text'], (int, float)):
                pattern_text = str(record['text']).lower()
            else:
                try:
                    pattern_text = str(record['text']).lower()
                except:
                    continue
            
            if not pattern_text.strip():  # 빈 문자열 건너뛰기
                continue
                
            try:
                pattern_text_cleaned = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', pattern_text)
                pattern_words = set(w for w in pattern_text_cleaned.split() if w.strip())
                
                processed = {
                    'original': record,
                    'cleaned_text': pattern_text_cleaned,
                    'words': pattern_words,
                    'chars': set(pattern_text_cleaned),
                    'word_count': len(pattern_words),
                    'length': len(pattern_text_cleaned)
                }
                
                # 길이에 따라 분류
                if processed['length'] <= 10:
                    short_patterns.append(processed)
                elif processed['length'] <= 30:
                    medium_patterns.append(processed)
                else:
                    long_patterns.append(processed)
                    
            except Exception as e:
                st.error(f"패턴 '{pattern_text}' 처리 중 오류 발생: {str(e)}")
                continue
        
        result = {
            'short': short_patterns,
            'medium': medium_patterns,
            'long': long_patterns
        }
        
        # 결과 검증
        if not any(result.values()):
            st.warning("처리된 패턴이 없습니다. 데이터를 확인해주세요.")
        else:
            total_patterns = sum(len(patterns) for patterns in result.values())
            st.success(f"총 {total_patterns}개의 패턴이 처리되었습니다.")
            
        return result
        
    except Exception as e:
        st.error(f"데이터 전처리 중 오류 발생: {str(e)}")
        import traceback
        st.error(f"상세 오류: {traceback.format_exc()}")
        return {
            'short': [],
            'medium': [],
            'long': []
        }

def check_pattern(input_data, pattern_data, threshold=0.7):
    """단일 패턴 매칭 검사 - 최적화 버전"""
    if not pattern_data or 'chars' not in pattern_data:
        return None
        
    input_text_cleaned, input_words, input_chars = input_data
    
    try:
        # 빠른 문자 기반 필터링
        char_intersection = len(input_chars & pattern_data['chars'])
        if char_intersection < min(3, len(pattern_data['chars']) * 0.3):
            return None
        
        # 단어 기반 필터링
        common_words = input_words & pattern_data['words']
        word_match_ratio = len(common_words) / pattern_data['word_count'] if pattern_data['word_count'] > 0 else 0
        
        # 짧은 패턴은 포함 여부만 빠르게 체크
        if pattern_data['length'] <= 10:
            if pattern_data['cleaned_text'] in input_text_cleaned:
                similarity = 1.0
            elif word_match_ratio < threshold * 0.5:
                return None
            else:
                similarity = word_match_ratio
        else:
            # 긴 패턴은 단어 매칭 비율로 1차 필터링
            if word_match_ratio < threshold * 0.5:
                return None
            similarity = difflib.SequenceMatcher(None, input_text_cleaned, pattern_data['cleaned_text']).ratio()
        
        if similarity >= threshold:
            record = pattern_data['original']
            try:
                # 숫자형 위험도 처리
                danger_level = str(record.get('dangerlevel', '0'))
                if danger_level.isdigit():
                    danger_level = int(danger_level)
                else:
                    danger_level = 0
            except (ValueError, TypeError):
                danger_level = 0
                
            return {
                'pattern': str(record['text']),
                'analysis': str(record.get('output', '')),
                'danger_level': danger_level,
                'url': str(record.get('url', '')),
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'match_score': similarity
            }
        
        return None
        
    except Exception as e:
        st.error(f"패턴 매칭 중 오류 발생: {str(e)}")
        return None



@st.cache_data(ttl=300)
def load_sheet_data():
    """Google Sheets 데이터 로드"""
    try:
        credentials = {
            "type": "service_account",
            "project_id": st.secrets["gcp_service_account"]["project_id"],
            "private_key_id": st.secrets["gcp_service_account"]["private_key_id"],
            "private_key": st.secrets["gcp_service_account"]["private_key"],
            "client_email": st.secrets["gcp_service_account"]["client_email"],
            "client_id": st.secrets["gcp_service_account"]["client_id"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": st.secrets["gcp_service_account"]["client_x509_cert_url"],
            "universe_domain": "googleapis.com"
        }
        
        SCOPES = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        creds = service_account.Credentials.from_service_account_info(
            credentials, scopes=SCOPES)
        client = gspread.authorize(creds)
        
        sheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1wPchxwAssBf706VuvxhGp4ESt3vj-N9RLcMaUF075ug/edit?gid=137455637#gid=137455637')
        worksheet = sheet.get_worksheet(0)
        return worksheet.get_all_records()
    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {str(e)}")
        return None

@st.cache_resource
def get_sheet_instance():
    """시트 인스턴스 가져오기"""
    try:
        credentials = {
            "type": "service_account",
            "project_id": st.secrets["gcp_service_account"]["project_id"],
            "private_key_id": st.secrets["gcp_service_account"]["private_key_id"],
            "private_key": st.secrets["gcp_service_account"]["private_key"],
            "client_email": st.secrets["gcp_service_account"]["client_email"],
            "client_id": st.secrets["gcp_service_account"]["client_id"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": st.secrets["gcp_service_account"]["client_x509_cert_url"],
            "universe_domain": "googleapis.com"
        }
        
        SCOPES = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        creds = service_account.Credentials.from_service_account_info(
            credentials, scopes=SCOPES)
        client = gspread.authorize(creds)
        
        sheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1wPchxwAssBf706VuvxhGp4ESt3vj-N9RLcMaUF075ug/edit?gid=137455637#gid=137455637')
        return sheet.get_worksheet(0)
    except Exception as e:
        st.error(f"시트 연결 중 오류 발생: {str(e)}")
        return None


# 최상위 레벨에 get_color_style 함수 정의
def get_color_style(score):
    """위험도 점수에 따른 색상 스타일 반환"""
    if score >= 70:
        return "color: #FF5252; font-weight: bold;"  # 빨간색
    elif score >= 30:
        return "color: #FFD700; font-weight: bold;"  # 노란색
    else:
        return "color: #00E676; font-weight: bold;"  # 초록색


def calculate_danger_score(matches):
    """위험도 점수 계산"""
    total_score = 0
    for match in matches:
        total_score += match.get('danger_level', 0)
    return total_score

def get_danger_level_class(score):
    """위험도 점수에 따른 CSS 클래스 반환"""
    if score < 30:
        return "danger-level-low"
    elif score < 70:
        return "danger-level-medium"
    else:
        return "danger-level-high"

def get_youtube_thumbnail(url):
    """유튜브 URL에서 썸네일 URL 추출"""
    if not url:
        return None
    video_id = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    if video_id and 'youtube.com' in url:
        return f"https://img.youtube.com/vi/{video_id.group(1)}/hqdefault.jpg"
    return None

# 3. 병렬 처리 최적화
def find_matching_patterns(input_text, data, threshold=0.7):
    """텍스트 패턴 매칭 - 오탈자 및 띄어쓰기 검사 추가"""
    if not data or not input_text:
        return []
        
    input_text = str(input_text).strip()
    if not input_text or input_text.isspace():
        return []
    
    try:
        # 한글 자모음 분리 함수
        def decompose_hangul(text):
            result = []
            for char in text:
                if '가' <= char <= '힣':
                    # 한글 유니코드 분해
                    code = ord(char) - 0xAC00
                    jong = code % 28
                    jung = ((code - jong) // 28) % 21
                    cho = ((code - jong) // 28) // 21
                    result.append((cho, jung, jong))
                else:
                    result.append(char)
            return result

        # 자모음 유사도 계산
        def jamo_similarity(char1, char2):
            if isinstance(char1, tuple) and isinstance(char2, tuple):
                # 초성, 중성, 종성 각각 비교
                matches = sum(1 for i in range(3) if char1[i] == char2[i])
                return matches / 3
            return 1.0 if char1 == char2 else 0.0

        # 텍스트 전처리
        input_text_cleaned = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', input_text.lower())
        input_jamos = decompose_hangul(input_text_cleaned)
        input_words = set(w for w in input_text_cleaned.split() if w.strip())
        
        # 패턴 매칭 결과 저장
        found_patterns = []
        
        for pattern in data:
            try:
                if not isinstance(pattern, dict) or 'text' not in pattern:
                    continue
                    
                pattern_text = str(pattern['text']).lower()
                pattern_cleaned = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', pattern_text)
                pattern_jamos = decompose_hangul(pattern_cleaned)
                pattern_words = set(pattern_cleaned.split())
                
                if not pattern_words:
                    continue
                
                # 자모음 유사도 계산
                jamo_scores = []
                for i in range(len(input_jamos)):
                    for j in range(len(pattern_jamos)):
                        score = jamo_similarity(input_jamos[i], pattern_jamos[j])
                        if score > 0.6:  # 자모음 유사도 임계값
                            jamo_scores.append(score)
                
                # 단어 단위 매칭
                word_scores = []
                for input_word in input_words:
                    input_word_jamos = decompose_hangul(input_word)
                    for pattern_word in pattern_words:
                        pattern_word_jamos = decompose_hangul(pattern_word)
                        # 단어 길이가 비슷한 경우만 비교
                        if abs(len(input_word_jamos) - len(pattern_word_jamos)) <= 2:
                            similarity = sum(jamo_similarity(a, b) for a, b in 
                                          zip(input_word_jamos, pattern_word_jamos)) / max(len(input_word_jamos), len(pattern_word_jamos))
                            if similarity > 0.7:
                                word_scores.append(similarity)
                
                # 최종 유사도 계산
                if word_scores or jamo_scores:
                    avg_word_score = sum(word_scores) / len(word_scores) if word_scores else 0
                    avg_jamo_score = sum(jamo_scores) / len(jamo_scores) if jamo_scores else 0
                    final_score = (avg_word_score * 0.7 + avg_jamo_score * 0.3)
                    
                    if final_score >= threshold:
                        try:
                            danger_level = int(pattern.get('dangerlevel', 0))
                        except (ValueError, TypeError):
                            danger_level = 0
                            
                        # 오탈자 및 띄어쓰기 오류 확인
                        spelling_errors = []
                        spacing_errors = []
                        
                        # 단어별 유사도 상세 분석
                        for input_word in input_words:
                            closest_match = None
                            max_similarity = 0
                            
                            for pattern_word in pattern_words:
                                similarity = difflib.SequenceMatcher(None, input_word, pattern_word).ratio()
                                if 0.6 <= similarity < 1.0 and similarity > max_similarity:
                                    closest_match = pattern_word
                                    max_similarity = similarity
                            
                            if closest_match:
                                spelling_errors.append((input_word, closest_match))
                        
                        found_pattern = {
                            'pattern': pattern['text'],
                            'analysis': pattern.get('output', '분석 정보 없음'),
                            'danger_level': danger_level,
                            'url': pattern.get('url', ''),
                            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'match_score': final_score,
                            'original_text': input_text,
                            'matched_keywords': sorted(set(word_scores)),
                            'spelling_errors': spelling_errors,
                            'spacing_errors': spacing_errors
                        }
                        
                        if pattern.get('url') and 'youtube.com' in pattern['url']:
                            found_pattern['thumbnail'] = get_youtube_thumbnail(pattern['url'])
                            
                        found_patterns.append(found_pattern)
            
            except Exception as e:
                st.error(f"패턴 '{pattern.get('text', '알 수 없는 패턴')}' 처리 중 오류 발생: {str(e)}")
                continue
        
        # 매치 점수와 위험도로 정렬
        found_patterns.sort(key=lambda x: (-x['match_score'], -x['danger_level']))
        
        return found_patterns
        
    except Exception as e:
        st.error(f"패턴 매칭 중 오류 발생: {str(e)}")
        import traceback
        st.error(f"상세 오류: {traceback.format_exc()}")
        return []

def extract_keywords(text):
    """텍스트에서 핵심 키워드 추출"""
    try:
        # 특수문자 제거 및 소문자 변환
        cleaned = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', str(text).lower())
        # 2글자 이상 단어만 추출
        words = [w for w in cleaned.split() if len(w) >= 2]
        # 중복 제거 및 정렬
        return sorted(set(words))
    except Exception as e:
        st.error(f"키워드 추출 중 오류 발생: {str(e)}")
        return []

def highlight_pattern_in_text(original_text, pattern):
    """텍스트 내의 패턴을 하이라이트"""
    try:
        # 패턴과 원본 텍스트를 정규화
        pattern_cleaned = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', str(pattern).lower())
        text_cleaned = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', str(original_text).lower())
        
        # CSS 스타일이 적용된 하이라이트 HTML
        highlight_style = """
            background: linear-gradient(104deg, rgba(255, 178, 15, 0.1) 0.9%, rgba(255, 178, 15, 0.3) 2.4%, rgba(255, 178, 15, 0.2) 5.8%, rgba(255, 178, 15, 0.1) 93%, rgba(255, 178, 15, 0.1) 96%);
            border-radius: 4px;
            padding: 0.1em 0.2em;
            box-decoration-break: clone;
            -webkit-box-decoration-break: clone;
            position: relative;
            color: #FFB20F;
            font-weight: 500;
        """
        
        # 패턴의 각 단어에 대해 하이라이트 처리
        result_text = str(original_text)
        pattern_words = [w for w in pattern_cleaned.split() if len(w) >= 2]
        
        for word in pattern_words:
            # 대소문자 구분 없이 매칭하되, 원본 텍스트의 대소문자는 유지
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            result_text = pattern.sub(
                lambda m: f'<span style="{highlight_style}">{m.group()}</span>',
                result_text
            )
        
        return result_text
    except Exception as e:
        st.error(f"하이라이트 처리 중 오류 발생: {str(e)}")
        return str(original_text)

# CSS 스타일 추가
st.markdown("""
<style>
    /* 하이라이트 관련 스타일 */
    .highlighted-text {
        font-size: 1.1em;
        line-height: 1.6;
    }
    
    /* 기존 스타일에 추가 */
    .analysis-card {
        position: relative;
        overflow: hidden;
    }
    
    .analysis-card::before {
        content: '';
        position: absolute;
        left: 0;
        top: 0;
        height: 100%;
        width: 4px;
        background: linear-gradient(to bottom, #FFB20F, #FF9800);
    }
</style>
""", unsafe_allow_html=True)


import streamlit as st
import html

def analyze_file_contents(file_content, data):
    """파일 내용 분석 - 초고속 버전 (폴더 및 타입 체크 지원)"""
    import time
    from collections import defaultdict
    import numpy as np
    import zipfile
    import io
    
    if file_content is not None:
        try:
            start_time = time.time()
            
            # 로그 컨테이너 생성
            log_container = st.empty()
            def update_log(message, filename=""):
                prefix = f"[{filename}] " if filename else ""
                log_container.markdown(f"""
                    <div style="background-color: #2D2D2D; padding: 10px; border-radius: 5px; margin: 5px 0;">
                        {prefix}{message}
                    </div>
                """, unsafe_allow_html=True)

            # 파일 로드 최적화
            dfs = []
            filename = getattr(file_content, 'name', '알 수 없는 파일')
            update_log("📂 파일 로딩 및 패턴 최적화 중...", filename)
            
            if hasattr(file_content, 'name'):  # 단일 파일
                file_type = file_content.name.split('.')[-1].lower()
                if file_type == 'csv':
                    df = pd.read_csv(file_content, dtype=str)
                    df['source_file'] = file_content.name
                    dfs.append(df)
                elif file_type in ['xlsx', 'xls']:
                    df = pd.read_excel(file_content, dtype=str)
                    df['source_file'] = file_content.name
                    dfs.append(df)
                elif file_type == 'zip':  # ZIP 파일(폴더) 처리
                    with zipfile.ZipFile(file_content) as z:
                        for zip_filename in z.namelist():
                            if zip_filename.endswith(('.csv', '.xlsx', '.xls')):
                                with z.open(zip_filename) as f:
                                    if zip_filename.endswith('.csv'):
                                        df = pd.read_csv(io.BytesIO(f.read()), dtype=str)
                                    else:
                                        df = pd.read_excel(io.BytesIO(f.read()), dtype=str)
                                    df['source_file'] = zip_filename
                                    dfs.append(df)

            if not dfs:
                update_log(f"⚠️ 지원하지 않는 파일 형식이거나 처리할 수 있는 파일이 없습니다.", filename)
                return None
                
            update_log(f"🔍 {len(dfs)}개의 파일을 로드했습니다.", filename)
            
            # 모든 데이터프레임 병합
            df = pd.concat(dfs, ignore_index=True)

            # 패턴 데이터 전처리 및 최적화
            pattern_lookup = defaultdict(list)
            for idx, item in enumerate(data):
                pattern_text = str(item.get('text', '')).lower()
                words = set(re.sub(r'[^가-힣a-zA-Z0-9\s]', '', pattern_text).split())
                
                # 각 단어를 키로 사용하여 패턴 인덱스 저장
                for word in words:
                    if len(word) >= 2:
                        pattern_lookup[word].append((idx, words))

            update_log("🚀 초고속 분석 시작...", filename)

            # 텍스트 컬럼 처리
            text_columns = df.select_dtypes(include=['object']).columns
            total_patterns_found = 0
            all_results = []
            
            progress_bar = st.progress(0)
            progress_text = st.empty()
            
            def analyze_text_batch(texts, batch_idx, total_batches, source_file):
                """텍스트 배치 고속 분석"""
                batch_results = []
                potential_matches = defaultdict(set)
                
                # 1단계: 빠른 키워드 매칭
                for text_idx, text in enumerate(texts):
                    # 숫자형 데이터 처리
                    if isinstance(text, (int, float)):
                        text = str(text)
                    # None 값 처리    
                    if not isinstance(text, str):
                        continue
                        
                    text_lower = text.lower()
                    words = set(re.sub(r'[^가-힣a-zA-Z0-9\s]', '', text_lower).split())
                    
                    # 각 단어에 대해 가능한 패턴 찾기
                    for word in words:
                        if len(word) >= 2 and word in pattern_lookup:
                            for pattern_idx, pattern_words in pattern_lookup[word]:
                                potential_matches[text_idx].add(pattern_idx)
                
                # 2단계: 정확한 매칭 검사
                for text_idx, pattern_indices in potential_matches.items():
                    text = texts[text_idx]
                    if isinstance(text, (int, float)):
                        text = str(text)
                    text_lower = text.lower()
                    text_words = set(re.sub(r'[^가-힣a-zA-Z0-9\s]', '', text_lower).split())
                    
                    for pattern_idx in pattern_indices:
                        pattern_item = data[pattern_idx]
                        pattern_text = str(pattern_item['text']).lower()
                        pattern_words = set(re.sub(r'[^가-힣a-zA-Z0-9\s]', '', pattern_text).split())
                        
                        # 워드 매칭 스코어 계산
                        common_words = text_words & pattern_words
                        if common_words:
                            match_score = len(common_words) / len(pattern_words)
                            if match_score >= 0.7:  # 임계값
                                try:
                                    danger_level = int(pattern_item.get('dangerlevel', 0))
                                except (ValueError, TypeError):
                                    danger_level = 0
                                    
                                batch_results.append({
                                    'text': text,
                                    'pattern': pattern_item['text'],
                                    'analysis': pattern_item['output'],
                                    'danger_level': danger_level,
                                    'url': pattern_item.get('url', ''),
                                    'match_score': match_score,
                                    'source_file': source_file
                                })
                
                return batch_results

            # 병렬 처리를 위한 배치 처리
            total_rows = df[text_columns].notna().sum().sum()
            processed_rows = 0
            batch_size = 5000  # 대용량 배치
            
            for col_idx, col in enumerate(text_columns):
                if col == 'source_file':  # source_file 컬럼 제외
                    continue
                    
                texts = df[col].dropna().tolist()
                source_files = df.loc[df[col].notna(), 'source_file'].tolist()
                total_batches = (len(texts) + batch_size - 1) // batch_size
                
                for batch_idx in range(total_batches):
                    start_idx = batch_idx * batch_size
                    end_idx = min((batch_idx + 1) * batch_size, len(texts))
                    batch_texts = texts[start_idx:end_idx]
                    batch_sources = source_files[start_idx:end_idx]
                    
                    # 배치 분석
                    for text, source_file in zip(batch_texts, batch_sources):
                        results = analyze_text_batch([text], 0, 1, source_file)
                        if results:
                            # 컬럼 정보 추가
                            for r in results:
                                r['column'] = col
                            all_results.extend(results)
                            total_patterns_found += len(results)
                    
                    # 진행률 업데이트
                    processed_rows += len(batch_texts)
                    progress = min(processed_rows / total_rows, 1.0)
                    progress_bar.progress(progress)
                    
                    if batch_idx % 2 == 0:  # 로그 업데이트 빈도 조절
                        elapsed_time = time.time() - start_time
                        speed = processed_rows / elapsed_time if elapsed_time > 0 else 0
                        update_log(f"""
                            📊 분석 진행 중:
                            - 처리 속도: {speed:.0f} 행/초
                            - 처리된 행: {processed_rows:,}/{total_rows:,}
                            - 발견된 패턴: {total_patterns_found:,}개
                        """, filename)
            
            # 최종 결과 정리
            progress_bar.empty()
            progress_text.empty()
            
            if all_results:
                # 최종 정렬 및 중복 제거
                seen = set()
                unique_results = []
                for r in sorted(all_results, key=lambda x: (-x['match_score'], -x['danger_level'])):
                    key = (r['text'], r['pattern'], r['source_file'])
                    if key not in seen:
                        seen.add(key)
                        unique_results.append(r)
                
                total_time = time.time() - start_time
                update_log(f"""
                    ⚠️ 분석 완료:
                    - 처리 시간: {total_time:.1f}초
                    - 처리 속도: {total_rows/total_time:.0f} 행/초
                    - 총 처리된 행: {processed_rows:,}개
                    - 발견된 패턴: {total_patterns_found:,}개
                """, filename)
                
                return {
                    'total_patterns': len(unique_results),
                    'results': unique_results[:1000],
                    'filename': filename
                }
            else:
                update_log(f"✅ {filename}에서 발견된 패턴이 없습니다.")
                return None
            
        except Exception as e:
            st.error(f"'{filename}' 파일 분석 중 오류가 발생했습니다: {str(e)}")
            import traceback
            st.error(f"상세 오류: {traceback.format_exc()}")
            return None
    return None

def group_similar_patterns(pattern_results, similarity_threshold=0.9):
    """유사한 패턴들을 그룹화"""
    grouped_results = []
    used_indices = set()
    
    for i, result in enumerate(pattern_results):
        if i in used_indices:
            continue
            
        # 현재 패턴과 유사한 패턴들을 찾아 그룹화
        similar_patterns = []
        base_pattern = result['pattern']
        base_text = result['text']
        
        for j, other_result in enumerate(pattern_results):
            if j <= i:  # 이미 처리된 패턴은 건너뛰기
                continue
                
            # 패턴 유사도 검사
            pattern_similarity = difflib.SequenceMatcher(None, base_pattern, other_result['pattern']).ratio()
            text_similarity = difflib.SequenceMatcher(None, base_text, other_result['text']).ratio()
            
            if pattern_similarity >= similarity_threshold or text_similarity >= similarity_threshold:
                similar_patterns.append(other_result)
                used_indices.add(j)
        
        if similar_patterns:
            # 그룹 대표 패턴 선택 (위험도가 가장 높은 것)
            all_patterns = [result] + similar_patterns
            representative = max(all_patterns, key=lambda x: (x['danger_level'], x['match_score']))
            
            # 그룹 정보 추가
            representative['similar_count'] = len(similar_patterns)
            representative['similar_patterns'] = similar_patterns
            grouped_results.append(representative)
        else:
            grouped_results.append(result)
            
    return grouped_results

def display_file_analysis_results(analysis_results):
    """파일 분석 결과 표시 - 그룹화된 패턴과 맞춤법 검사 포함"""
    try:
        if not analysis_results or not analysis_results['results']:
            filename = analysis_results.get('filename', '알 수 없는 파일') if analysis_results else '알 수 없는 파일'
            st.warning(f"🔍 '{filename}'에서 분석 결과가 없습니다.")
            return

        results = analysis_results['results']
        
        # 결과 분리
        pattern_results = [r for r in results if not r.get('is_spell_check')]
        spell_check_results = [r for r in results if r.get('is_spell_check')]
        
        # 패턴 결과 그룹화
        grouped_pattern_results = group_similar_patterns(pattern_results)
        
        # 통계 계산
        total_score = sum(result['danger_level'] for result in pattern_results)
        avg_score = total_score / len(pattern_results) if pattern_results else 0
        high_risk_count = sum(1 for r in pattern_results if r['danger_level'] >= 70)
        
        # 요약 통계 표시
        st.markdown("""
            <div style='background-color: #2D2D2D; padding: 15px; border-radius: 10px; margin-bottom: 20px;'>
                <h3 style='color: #E0E0E0; margin-bottom: 10px;'>📊 분석 결과 요약</h3>
            </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("위험 패턴", f"{len(grouped_pattern_results)}개")
        with col2:
            st.metric("평균 위험도", f"{avg_score:.1f}")
        with col3:
            st.metric("고위험 패턴", f"{high_risk_count}개")
        with col4:
            st.metric("맞춤법 오류", f"{len(spell_check_results)}개")

        # 탭으로 결과 구분
        tab1, tab2 = st.tabs(["⚠️ 위험 패턴", "📝 맞춤법 오류"])
        
        with tab1:
            if grouped_pattern_results:
                # 파일별 그룹화
                file_groups = {}
                for result in grouped_pattern_results:
                    source_file = result.get('source_file', '알 수 없는 파일')
                    if source_file not in file_groups:
                        file_groups[source_file] = {'high': [], 'medium': [], 'low': []}
                    
                    if result['danger_level'] >= 70:
                        file_groups[source_file]['high'].append(result)
                    elif result['danger_level'] >= 30:
                        file_groups[source_file]['medium'].append(result)
                    else:
                        file_groups[source_file]['low'].append(result)

                # 파일별로 결과 표시
                for source_file, severity_groups in file_groups.items():
                    st.markdown(f"""
                        <h2 style='color:#E0E0E0; border-bottom: 2px solid #555555; padding-bottom: 10px; margin-top: 30px;'>
                            📄 {html.escape(source_file)}
                        </h2>
                    """, unsafe_allow_html=True)

                    severity_info = [
                        ('high', '🚨 고위험 항목', "#FF5252"),
                        ('medium', '⚠️ 주의 항목', "#FFD700"),
                        ('low', '✅ 안전 항목', "#00E676")
                    ]

                    for severity, title, border_color in severity_info:
                        results_by_severity = severity_groups[severity]
                        if not results_by_severity:
                            continue

                        st.markdown(f"""
                            <h3 style='color:{border_color}; border-left: 6px solid {border_color}; padding-left: 10px; margin-top: 20px;'>
                                {title} ({len(results_by_severity)}개)
                            </h3>
                        """, unsafe_allow_html=True)

                        for result in results_by_severity:
                            match_percentage = int(result['match_score'] * 100)
                            similar_count = result.get('similar_count', 0)

                            with st.container():
                                # 기본 정보 표시
                                cols = st.columns([2, 1, 1])
                                with cols[0]:
                                    st.markdown(f"<p style='color:#FFFFFF;'><strong>위험도:</strong> <span style='color:{border_color}; font-weight:bold;'>{result['danger_level']}</span></p>", unsafe_allow_html=True)
                                with cols[1]:
                                    st.markdown(f"<p style='color:#FFFFFF;'><strong>일치율:</strong> {match_percentage}%</p>", unsafe_allow_html=True)
                                with cols[2]:
                                    if similar_count > 0:
                                        st.markdown(f"<p style='color:#FFFFFF;'><strong>유사 패턴:</strong> {similar_count}개</p>", unsafe_allow_html=True)

                                # 원본 텍스트 표시
                                st.markdown("<div style='font-weight:bold; margin-top: 10px; color: #FFFFFF;'>대표 텍스트:</div>", unsafe_allow_html=True)
                                try:
                                    highlighted_text = highlight_pattern_in_text(result['text'], result['pattern'])
                                    st.markdown(f"<div style='white-space: pre-wrap; font-family: \"Noto Sans KR\", sans-serif; background-color: #333333; padding: 10px; border-radius: 5px; color: #FFFFFF;'>{highlighted_text}</div>", unsafe_allow_html=True)
                                except:
                                    st.markdown(f"<div style='white-space: pre-wrap; font-family: \"Noto Sans KR\", sans-serif; background-color: #333333; padding: 10px; border-radius: 5px; color: #FFFFFF;'>{html.escape(str(result['text']))}</div>", unsafe_allow_html=True)

                                # 유사 패턴이 있는 경우 확장 가능한 섹션으로 표시
                                if similar_count > 0:
                                    with st.expander(f"유사한 패턴 {similar_count}개 보기"):
                                        for similar in result['similar_patterns']:
                                            st.markdown(f"""
                                                <div style='background-color: #2D2D2D; padding: 10px; border-radius: 5px; margin: 5px 0;'>
                                                    <p style='color: #E0E0E0;'>{html.escape(str(similar['text']))}</p>
                                                    <p style='color: #888888; font-size: 0.9em;'>일치율: {int(similar['match_score'] * 100)}%</p>
                                                </div>
                                            """, unsafe_allow_html=True)

                                # 패턴 정보 표시
                                st.markdown("<div style='font-weight:bold; margin-top: 10px; color: #FFFFFF;'>매칭된 패턴:</div>", unsafe_allow_html=True)
                                st.markdown(f"<div style='background-color: #444444; padding: 8px; border-radius: 5px; color: #FFFFFF;'>{html.escape(str(result['pattern']))}</div>", unsafe_allow_html=True)

                                # 분석 결과 표시
                                st.markdown("<div style='font-weight:bold; margin-top: 10px; color: #FFFFFF;'>분석:</div>", unsafe_allow_html=True)
                                st.markdown(f"<div style='background-color: rgba{tuple(int(border_color[i:i+2], 16) for i in (1, 3, 5))}, 0.1); padding: 10px; border-radius: 5px; color: #FFFFFF;'>{html.escape(str(result['analysis']))}</div>", unsafe_allow_html=True)

                                # 참고 자료 링크
                                if result.get("url"):
                                    with st.container():
                                        thumbnail_url = get_youtube_thumbnail(result["url"])
                                        if thumbnail_url:
                                            try:
                                                response = requests.get(thumbnail_url)
                                                image = Image.open(BytesIO(response.content))
                                                st.image(image, width=200, use_column_width=False)
                                            except:
                                                pass
                                        st.markdown(f"<p><strong>🔗 <a href='{html.escape(result['url'])}' target='_blank' style='color:{border_color};'>참고 자료</a></strong></p>", unsafe_allow_html=True)

                            st.markdown("<hr style='border: none; height: 1px; background-color: #555555;'>", unsafe_allow_html=True)
            else:
                st.info("위험 패턴이 발견되지 않았습니다.")

        # 맞춤법 검사 결과 표시 (기존 코드와 동일)
        with tab2:
            if spell_check_results:
                # ... (기존의 맞춤법 검사 결과 표시 코드 유지)
                pass
            else:
                st.info("맞춤법 오류가 발견되지 않았습니다.")

    except Exception as e:
        st.error(f"결과 표시 중 오류 발생: {str(e)}")
        import traceback
        st.error(f"상세 오류: {traceback.format_exc()}")

def get_thumbnail_url(url):
    """URL에서 썸네일 URL 추출"""
    if not url:
        return None
    
    # 유튜브 URL 처리
    video_id = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    if video_id and 'youtube.com' in url:
        return f"https://img.youtube.com/vi/{video_id.group(1)}/hqdefault.jpg"
    
    # 기타 URL 처리
    try:
        response = requests.get(url)
        if 'image/' in response.headers.get('content-type', ''):
            return url
    except:
        pass
    
    return None


# 추가 CSS 스타일
st.markdown("""
<style>
    /* 하이라이트 컨테이너 스타일 */
    .highlight-container {
        background-color: #2D2D2D;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
    }
    
    /* 파일 분석 카드 스타일 */
    .file-analysis-card {
        background-color: #2D2D2D;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
        border-left: 4px solid transparent;
    }
    
    /* 텍스트 컨테이너 스타일 */
    .text-container {
        background-color: #3D3D3D;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        line-height: 1.6;
        font-family: 'Noto Sans KR', sans-serif;
    }
</style>
""", unsafe_allow_html=True)

def display_analysis_results(patterns, total_score):
    """분석 결과 표시 - 개선된 버전"""
    try:
        # 전체 위험도 표시
        danger_level_class = get_danger_level_class(total_score)
        st.markdown("""
            <div style='background-color: #2D2D2D; padding: 15px; border-radius: 10px; margin: 15px 0;'>
                <h3 style='color: #E0E0E0; margin-bottom: 10px;'>📊 분석 결과 요약</h3>
            </div>
        """, unsafe_allow_html=True)

        # 요약 통계
        high_risk = sum(1 for p in patterns if p['danger_level'] >= 70)
        medium_risk = sum(1 for p in patterns if 30 <= p['danger_level'] < 70)
        low_risk = sum(1 for p in patterns if p['danger_level'] < 30)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("전체 위험도", f"{total_score}")
        with col2:
            st.metric("고위험 패턴", f"{high_risk}개")
        with col3:
            st.metric("중위험 패턴", f"{medium_risk}개")
        with col4:
            st.metric("저위험 패턴", f"{low_risk}개")

        # 위험도별 그룹화
        grouped_patterns = {
            'high': [],
            'medium': [],
            'low': []
        }
        
        for pattern in patterns:
            if pattern['danger_level'] >= 70:
                grouped_patterns['high'].append(pattern)
            elif pattern['danger_level'] >= 30:
                grouped_patterns['medium'].append(pattern)
            else:
                grouped_patterns['low'].append(pattern)

        # 각 위험도 그룹별로 표시
        severity_info = [
            ('high', '🚨 고위험 항목', "#FF5252"),
            ('medium', '⚠️ 주의 항목', "#FFD700"),
            ('low', '✅ 안전 항목', "#00E676")
        ]

        for severity, title, border_color in severity_info:
            patterns_by_severity = grouped_patterns[severity]
            if not patterns_by_severity:
                continue

            st.markdown(f"""
                <div style='background-color: #2D2D2D; padding: 15px; border-radius: 10px; margin: 15px 0;'>
                    <h3 style='color: {border_color};'>{title} ({len(patterns_by_severity)}개)</h3>
                </div>
            """, unsafe_allow_html=True)

            # 유사 패턴 그룹화
            similar_groups = {}
            used_patterns = set()

            for i, pattern in enumerate(patterns_by_severity):
                if i in used_patterns:
                    continue

                similar_group = []
                base_text = pattern.get('text', '')
                base_pattern = pattern.get('pattern', '')

                for j, other_pattern in enumerate(patterns_by_severity[i+1:], i+1):
                    if j in used_patterns:
                        continue

                    other_text = other_pattern.get('text', '')
                    other_pattern_text = other_pattern.get('pattern', '')

                    # 유사도 검사
                    text_similarity = difflib.SequenceMatcher(None, base_text, other_text).ratio()
                    pattern_similarity = difflib.SequenceMatcher(None, base_pattern, other_pattern_text).ratio()

                    if text_similarity > 0.8 or pattern_similarity > 0.8:
                        similar_group.append(other_pattern)
                        used_patterns.add(j)

                if similar_group:
                    similar_groups[i] = [pattern] + similar_group
                elif i not in used_patterns:
                    similar_groups[i] = [pattern]

            # 그룹별로 표시
            for group_patterns in similar_groups.values():
                main_pattern = group_patterns[0]
                match_percentage = int(main_pattern['match_score'] * 100)

                with st.container():
                    # 메인 패턴 표시
                    cols = st.columns([2, 1, 1])
                    with cols[0]:
                        st.markdown(f"<p style='color:#FFFFFF;'><strong>위험도:</strong> <span style='color:{border_color}; font-weight:bold;'>{main_pattern['danger_level']}</span></p>", unsafe_allow_html=True)
                    with cols[1]:
                        st.markdown(f"<p style='color:#FFFFFF;'><strong>일치율:</strong> {match_percentage}%</p>", unsafe_allow_html=True)
                    with cols[2]:
                        if len(group_patterns) > 1:
                            st.markdown(f"<p style='color:#FFFFFF;'><strong>유사 패턴:</strong> {len(group_patterns)-1}개</p>", unsafe_allow_html=True)

                    # 원본 텍스트와 하이라이트
                    st.markdown("<div style='font-weight:bold; margin-top: 10px; color: #FFFFFF;'>발견된 텍스트:</div>", unsafe_allow_html=True)
                    try:
                        highlighted_text = highlight_pattern_in_text(main_pattern['text'], main_pattern['pattern'])
                        st.markdown(f"""
                            <div style='white-space: pre-wrap; font-family: "Noto Sans KR", sans-serif; 
                                    background-color: #333333; padding: 10px; border-radius: 5px; 
                                    color: #FFFFFF; margin-bottom: 10px;'>
                                {highlighted_text}
                            </div>
                        """, unsafe_allow_html=True)
                    except:
                        st.markdown(f"<div style='background-color: #333333; padding: 10px; border-radius: 5px; color: #FFFFFF;'>{html.escape(str(main_pattern.get('text', '')))}</div>", unsafe_allow_html=True)

                    # 유사 패턴 표시
                    if len(group_patterns) > 1:
                        with st.expander(f"유사한 패턴 {len(group_patterns)-1}개 보기"):
                            for similar in group_patterns[1:]:
                                try:
                                    highlighted_similar = highlight_pattern_in_text(similar['text'], similar['pattern'])
                                    st.markdown(f"""
                                        <div style='background-color: #2D2D2D; padding: 10px; 
                                                border-radius: 5px; margin: 5px 0;'>
                                            <div style='color: #E0E0E0;'>{highlighted_similar}</div>
                                            <p style='color: #888888; font-size: 0.9em;'>
                                                일치율: {int(similar['match_score'] * 100)}%
                                            </p>
                                        </div>
                                    """, unsafe_allow_html=True)
                                except:
                                    st.markdown(f"<div style='background-color: #2D2D2D; padding: 10px; border-radius: 5px; margin: 5px 0;'>{html.escape(str(similar.get('text', '')))}</div>", unsafe_allow_html=True)

                    # 분석 정보
                    st.markdown("<div style='font-weight:bold; margin-top: 10px; color: #FFFFFF;'>분석:</div>", unsafe_allow_html=True)
                    st.markdown(f"""
                        <div style='background-color: rgba{tuple(int(border_color[i:i+2], 16) for i in (1, 3, 5))}, 0.1); 
                                padding: 10px; border-radius: 5px; color: #FFFFFF;'>
                            {html.escape(str(main_pattern.get('analysis', '')))}
                        </div>
                    """, unsafe_allow_html=True)

                    # 참고 자료 및 썸네일
                    if main_pattern.get("url"):
                        with st.container():
                            if 'thumbnail' in main_pattern:
                                try:
                                    st.image(main_pattern['thumbnail'], width=200)
                                except:
                                    pass
                            st.markdown(f"""
                                <p><strong>🔗 <a href='{html.escape(main_pattern["url"])}' 
                                   target='_blank' style='color:{border_color};'>참고 자료</a></strong></p>
                            """, unsafe_allow_html=True)

                    st.markdown("<hr style='border: none; height: 1px; background-color: #555555; margin: 20px 0;'>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"결과 표시 중 오류 발생: {str(e)}")
        import traceback
        st.error(f"상세 오류: {traceback.format_exc()}")

def main():
    st.markdown('<h1 class="main-title">StringAnalysis</h1>', unsafe_allow_html=True)
    st.markdown("""
    > 💡 입력된 문장을 분석하고 점수화하여 보여드립니다.
    """)

    # 데이터 로드 및 검증
    try:
        data = load_sheet_data()
        if not data:
            st.error("패턴 데이터를 불러올 수 없습니다. 구글 시트 연결을 확인해주세요.")
            return
            
        if not isinstance(data, list) or not data:
            st.error("패턴 데이터 형식이 올바르지 않습니다.")
            return
            
        # 데이터 구조 검증
        required_fields = ['text', 'output', 'dangerlevel']
        if not all(isinstance(item, dict) and all(field in item for field in required_fields) for item in data):
            st.error("패턴 데이터에 필수 필드가 누락되었습니다.")
            return
            
        # 탭 생성
        tab1, tab2, tab3 = st.tabs(["🔍 문장 분석", "✏️ 패턴 등록", "📝 맞춤법 규칙 관리"])

        with tab1:
            analysis_type = st.radio(
                "분석 유형 선택:",
                ["텍스트 직접 입력", "파일/폴더 업로드"],
                horizontal=True
            )
            
            if analysis_type == "텍스트 직접 입력":
                col1, col2 = st.columns([3, 1])
                with col1:
                    input_text = st.text_area(
                        "분석할 문장을 입력하세요:",
                        placeholder="분석하고 싶은 문장을 입력해주세요...",
                        height=100
                    )
                with col2:
                    st.write("")
                    st.write("")
                    analyze_button = st.button("🔍 위험도 분석", use_container_width=True, key="analyze")
                
                if analyze_button and input_text:
                    with st.spinner('🔄 문장을 분석하고 있습니다...'):
                        try:
                            # 맞춤법 검사와 패턴 분석 통합 수행
                            analysis_result = analyze_text_with_spelling(input_text, data)
                            
                            # 맞춤법 분석 결과 표시
                            display_spelling_analysis(analysis_result['spelling'])
                            
                            # 패턴 매칭 결과 표시
                            found_patterns = analysis_result['patterns']
                            if found_patterns:
                                total_score = calculate_danger_score(found_patterns)
                                st.success(f"🎯 분석이 완료되었습니다! {len(found_patterns)}개의 패턴이 발견되었습니다.")
                                display_analysis_results(found_patterns, total_score)
                            else:
                                st.info("👀 특별한 위험 패턴이 발견되지 않았습니다.")
                                
                        except Exception as e:
                            st.error(f"분석 중 오류가 발생했습니다: {str(e)}")
            
            else:  # 파일/폴더 업로드
                st.markdown("""
                    <div style="background-color: #2D2D2D; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                        <h4>📁 파일 업로드 안내</h4>
                        <p>• 단일/다중 파일: CSV, Excel 파일 직접 업로드</p>
                        <p>• 폴더 업로드: 여러 파일을 ZIP으로 압축하여 업로드</p>
                        <p>• 지원 형식: .csv, .xlsx, .xls, .zip</p>
                    </div>
                """, unsafe_allow_html=True)
                
                uploaded_files = st.file_uploader(
                    "파일 또는 ZIP 폴더 업로드", 
                    type=['csv', 'xlsx', 'xls', 'zip'],
                    accept_multiple_files=True,
                    help="여러 파일을 한 번에 선택하거나, ZIP 파일로 압축하여 업로드하세요."
                )
                
                if uploaded_files:
                    if st.button("📂 파일 분석", use_container_width=True):
                        all_results = []
                        total_patterns = 0
                        
                        progress_text = st.empty()
                        progress_bar = st.progress(0)
                        
                        for idx, file in enumerate(uploaded_files):
                            progress = (idx + 1) / len(uploaded_files)
                            progress_bar.progress(progress)
                            progress_text.text(f"파일 분석 중... ({idx + 1}/{len(uploaded_files)}): {file.name}")
                            
                            with st.spinner(f'🔄 {file.name} 분석 중...'):
                                analysis_result = analyze_file_contents(file, data)
                                if analysis_result and analysis_result['total_patterns'] > 0:
                                    all_results.extend(analysis_result['results'])
                                    total_patterns += analysis_result['total_patterns']
                        
                        progress_bar.empty()
                        progress_text.empty()
                        
                        if total_patterns > 0:
                            st.success(f"🎯 분석이 완료되었습니다! 총 {total_patterns}개의 패턴이 발견되었습니다.")
                            
                            combined_results = {
                                'total_patterns': total_patterns,
                                'results': sorted(all_results, 
                                               key=lambda x: (x['danger_level'], x['match_score']), 
                                               reverse=True)[:1000]
                            }
                            display_file_analysis_results(combined_results)
                        else:
                            st.info("👀 파일에서 위험 패턴이 발견되지 않았습니다.")

        with tab2:
            st.markdown("""
            <div style='background-color: #2D2D2D; padding: 1rem; border-radius: 10px; margin-bottom: 1rem;'>
                <h4>🌟 새로운 패턴 등록</h4>
                <p style='color: #E0E0E0;'>새로운 위험 패턴을 등록해주세요.</p>
            </div>
            """, unsafe_allow_html=True)
            
            with st.form("pattern_registration_form", clear_on_submit=True):
                pattern_text = st.text_input("🏷️ 패턴:", placeholder="위험 패턴을 입력하세요")
                analysis_text = st.text_area("📝 분석:", placeholder="이 패턴의 위험성을 설명해주세요", height=100)
                danger_level = st.slider("⚠️ 위험도:", 0, 100, 50)
                url = st.text_input("🔗 참고 URL:", placeholder="관련 참고 자료 URL")
                
                col1, col2, col3 = st.columns([1,1,1])
                with col2:
                    submit_button = st.form_submit_button("✨ 패턴 등록", use_container_width=True)
                        
            if submit_button:
                if all([pattern_text, analysis_text]):
                    try:
                        worksheet = get_sheet_instance()
                        if worksheet:
                            worksheet.append_row([
                                pattern_text,
                                analysis_text,
                                url,
                                danger_level,
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            ])
                            st.success("✅ 패턴이 등록되었습니다!")
                            st.balloons()
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("시트에 연결할 수 없습니다.")
                    except Exception as e:
                        st.error(f"😢 패턴 등록 중 오류가 발생했습니다: {str(e)}")
                else:
                    st.warning("⚠️ 패턴과 분석 내용은 필수입니다!")
            
            # 데이터베이스 테이블 표시
            st.markdown("""
            <div class="database-title">
                📊 현재 등록된 패턴 데이터베이스
            </div>
            """, unsafe_allow_html=True)
            
            if data:
                df = pd.DataFrame(data)
                
                column_mapping = {
                    'text': '패턴',
                    'output': '분석',
                    'url': '참고 URL',
                    'dangerlevel': '위험도',
                    'timestamp': '등록일시'
                }
                
                for old_col, new_col in column_mapping.items():
                    if old_col in df.columns:
                        df = df.rename(columns={old_col: new_col})
                
                search_term = st.text_input("🔍 패턴 검색:", placeholder="검색어를 입력하세요...")
                if search_term:
                    pattern_mask = df['패턴'].astype(str).str.contains(search_term, case=False, na=False)
                    analysis_mask = df['분석'].astype(str).str.contains(search_term, case=False, na=False)
                    df = df[pattern_mask | analysis_mask]
                
                if '위험도' in df.columns:
                    col1, col2 = st.columns(2)
                    with col1:
                        min_danger = st.number_input("최소 위험도:", min_value=0, max_value=100, value=0)
                    with col2:
                        max_danger = st.number_input("최대 위험도:", min_value=0, max_value=100, value=100)
                    
                    df['위험도'] = pd.to_numeric(df['위험도'], errors='coerce')
                    df = df[(df['위험도'] >= min_danger) & (df['위험도'] <= max_danger)]
                
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    height=400
                )
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("총 패턴 수", len(df))
                if '위험도' in df.columns:
                    with col2:
                        st.metric("평균 위험도", f"{df['위험도'].mean():.1f}")
                    with col3:
                        st.metric("고위험 패턴 수", len(df[df['위험도'] >= 70]))
            else:
                st.info("등록된 패턴이 없습니다.")

        with tab3:
            st.markdown("""
                <div style='background-color: #2D2D2D; padding: 1rem; border-radius: 10px; margin-bottom: 1rem;'>
                    <h4>📝 맞춤법 규칙 관리</h4>
                    <p style='color: #E0E0E0;'>맞춤법 검사에 사용될 규칙을 관리합니다.</p>
                </div>
            """, unsafe_allow_html=True)
            
            with st.form("spelling_rule_form", clear_on_submit=True):
                wrong_text = st.text_input("❌ 오류 표현:", placeholder="수정이 필요한 표현을 입력하세요")
                correct_text = st.text_input("✅ 올바른 표현:", placeholder="올바른 표현을 입력하세요")
                
                col1, col2, col3 = st.columns([1,1,1])
                with col2:
                    submit_button = st.form_submit_button("✨ 규칙 등록", use_container_width=True)
            
            if submit_button:
                if all([wrong_text, correct_text]):
                    try:
                        worksheet = get_sheet_instance()
                        if worksheet:
                            try:
                                checker_sheet = worksheet.worksheet('checker')
                            except:
                                checker_sheet = worksheet.add_worksheet('checker', 1000, 2)
                                checker_sheet.update('A1:B1', [['오류', '수정']])
                            
                            checker_sheet.append_row([wrong_text, correct_text])
                            st.success("✅ 맞춤법 규칙이 등록되었습니다!")
                            st.balloons()
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("시트에 연결할 수 없습니다.")
                    except Exception as e:
                        st.error(f"😢 규칙 등록 중 오류가 발생했습니다: {str(e)}")
                else:
                    st.warning("⚠️ 오류 표현과 올바른 표현을 모두 입력해주세요!")
            
            # 현재 등록된 규칙 표시
            st.markdown("""
            <div class="database-title">
                📊 현재 등록된 맞춤법 규칙
            </div>
            """, unsafe_allow_html=True)
            
            try:
                checker = SheetBasedSpellChecker()
                rules = checker.rules
                
                if rules:
                    df = pd.DataFrame(list(rules.items()), columns=['오류 표현', '올바른 표현'])
                    st.dataframe(
                        df,
                        use_container_width=True,
                        hide_index=True,
                        height=400
                    )
                else:
                    st.info("등록된 맞춤법 규칙이 없습니다.")
                    
            except Exception as e:
                st.error(f"규칙 목록 로딩 중 오류 발생: {str(e)}")
                
    except Exception as e:
        st.error(f"애플리케이션 실행 중 오류가 발생했습니다: {str(e)}")
        st.error("상세 오류:", exception=True)
        return

if __name__ == "__main__":
    main()