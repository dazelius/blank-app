import streamlit as st
import gspread
from google.oauth2 import service_account
import re
import difflib
import json
from datetime import datetime
import os
import pandas as pd
import html
import requests
import time
import gc
import zipfile
import io
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from io import BytesIO
import time


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
    """구글 시트 기반 맞춤법 검사기 - 캐싱 최적화 버전"""
    
    _instance = None
    _rules = None
    _last_update = None
    _update_interval = 300  # 5분마다 규칙 업데이트
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SheetBasedSpellChecker, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        # 초기화는 한 번만 수행
        if self._rules is None:
            self._rules = {}
            self.load_rules()
    
    def load_rules(self):
        """구글 시트에서 규칙 로드 - 캐싱 적용"""
        current_time = time.time()
        
        # 마지막 업데이트 후 지정된 시간이 지나지 않았다면 기존 규칙 사용
        if (self._last_update and 
            current_time - self._last_update < self._update_interval and 
            self._rules):
            return
        
        try:
            checker_sheet = get_or_create_checker_worksheet()
            if not checker_sheet:
                return
            
            # 데이터 한 번에 가져오기
            data = checker_sheet.get_all_values()
            
            # 규칙 딕셔너리 생성
            new_rules = {}
            if len(data) > 1:  # 헤더 제외
                for row in data[1:]:  # 첫 행(헤더) 제외
                    if len(row) >= 2 and row[0] and row[1]:
                        new_rules[row[0].strip()] = row[1].strip()
            
            # 새 규칙으로 업데이트
            self._rules = new_rules
            self._last_update = current_time
            
        except Exception as e:
            st.error(f"규칙 로딩 중 오류 발생: {str(e)}")

    def check(self, text):
        """텍스트 맞춤법 검사 - 캐시 활용"""
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
            processed_corrections = set()  # 중복 교정 방지
            
            for wrong, right in self._rules.items():
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
                        # 일반 문자열 매칭
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

    def get_rules(self):
        """현재 등록된 모든 규칙 반환"""
        return self._rules.copy()

    @classmethod
    def clear_cache(cls):
        """캐시 초기화"""
        cls._rules = None
        cls._last_update = None


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
def find_matching_patterns(input_text, data, threshold=0.5):  # 임계값을 0.7에서 0.5로 낮춤
    """텍스트 패턴 매칭 - 향상된 정확도"""
    if not data or not input_text:
        return []
        
    input_text = str(input_text).strip()
    if not input_text or input_text.isspace():
        return []
    
    try:
        # 입력 텍스트 전처리
        input_text_lower = str(input_text).lower()
        # 특수문자를 공백으로 변경 (제거 대신)
        input_text_cleaned = re.sub(r'[^가-힣a-zA-Z0-9\s]', ' ', input_text_lower)
        input_words = set(w for w in input_text_cleaned.split() if w.strip())
        
        # N-gram 생성 (2단어 및 3단어 연속 패턴)
        input_bigrams = set()
        input_trigrams = set()
        words = input_text_cleaned.split()
        for i in range(len(words)-1):
            input_bigrams.add(' '.join(words[i:i+2]))
            if i < len(words)-2:
                input_trigrams.add(' '.join(words[i:i+3]))
        
        found_patterns = []
        
        for pattern in data:
            try:
                if not isinstance(pattern, dict) or 'text' not in pattern:
                    continue
                
                pattern_text = str(pattern['text'])
                pattern_text_lower = pattern_text.lower()
                pattern_cleaned = re.sub(r'[^가-힣a-zA-Z0-9\s]', ' ', pattern_text_lower)
                pattern_words = set(w for w in pattern_cleaned.split() if w.strip())
                
                if not pattern_words:
                    continue
                
                # 1. 다양한 매칭 검사
                exact_match = pattern_text_lower in input_text_lower
                partial_match = any(word in input_text_lower for word in pattern_words if len(word) > 1)
                
                # 2. N-gram 매칭
                pattern_bigrams = set()
                pattern_trigrams = set()
                p_words = pattern_cleaned.split()
                for i in range(len(p_words)-1):
                    pattern_bigrams.add(' '.join(p_words[i:i+2]))
                    if i < len(p_words)-2:
                        pattern_trigrams.add(' '.join(p_words[i:i+3]))
                
                bigram_match = bool(input_bigrams & pattern_bigrams)
                trigram_match = bool(input_trigrams & pattern_trigrams)
                
                # 3. 단어 기반 유사도
                common_words = input_words & pattern_words
                word_similarity = len(common_words) / len(pattern_words) if pattern_words else 0
                
                # 4. 시퀀스 매칭
                text_similarity = difflib.SequenceMatcher(None, input_text_cleaned, pattern_cleaned).ratio()
                
                # 5. 연속 단어 매칭
                continuous_match = False
                if len(pattern_words) > 1:
                    pattern_seq = ' '.join(pattern_cleaned.split())
                    if pattern_seq in input_text_cleaned:
                        continuous_match = True
                
                # 최종 점수 계산 - 다양한 매칭 기준 통합
                matching_points = sum([
                    exact_match * 1.0,
                    continuous_match * 0.9,
                    bigram_match * 0.8,
                    trigram_match * 0.7,
                    word_similarity * 0.6,
                    text_similarity * 0.5,
                    partial_match * 0.4
                ])
                
                final_score = matching_points / 4.9  # 정규화
                
                # 매칭 조건 완화
                if final_score >= threshold or exact_match or continuous_match or (bigram_match and word_similarity > 0.3):
                    danger_level = int(pattern.get('dangerlevel', 0))
                        
                    found_pattern = {
                        'pattern': pattern_text,
                        'analysis': pattern.get('output', '분석 정보 없음'),
                        'danger_level': danger_level,
                        'url': pattern.get('url', ''),
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'match_score': final_score,
                        'original_text': input_text,
                        'matched_keywords': list(common_words),
                        'text': input_text,
                        'exact_match': exact_match,
                        'continuous_match': continuous_match,
                        'matching_details': {
                            'exact_match': exact_match,
                            'continuous_match': continuous_match,
                            'bigram_match': bigram_match,
                            'trigram_match': trigram_match,
                            'word_similarity': word_similarity,
                            'text_similarity': text_similarity,
                            'partial_match': partial_match
                        }
                    }
                    
                    if pattern.get('url') and 'youtube.com' in pattern['url']:
                        found_pattern['thumbnail'] = get_youtube_thumbnail(pattern['url'])
                        
                    found_patterns.append(found_pattern)
            
            except Exception as e:
                st.error(f"패턴 '{pattern.get('text', '알 수 없는 패턴')}' 처리 중 오류 발생: {str(e)}")
                continue
        
        # 매칭 품질 기반 정렬
        found_patterns.sort(key=lambda x: (
            x.get('exact_match', False),
            x.get('continuous_match', False),
            x['match_score'],
            x['danger_level']
        ), reverse=True)
        
        return found_patterns
        
    except Exception as e:
        st.error(f"패턴 매칭 중 오류 발생: {str(e)}")
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

def highlight_pattern_in_text(text, pattern, matched_keywords=None):
    """텍스트 내의 패턴을 하이라이트 - 공백 최적화"""
    try:
        if not text or not pattern:
            return html.escape(str(text))
            
        result = str(text)
        highlight_style = "background: linear-gradient(104deg, rgba(255,178,15,0.2) 0.9%, rgba(255,178,15,0.4) 2.4%, rgba(255,178,15,0.3) 5.8%, rgba(255,178,15,0.2) 93%, rgba(255,178,15,0.2) 96%); padding: 0.1em 0.2em; border-radius: 4px; color: #FFB20F; font-weight: 500;"
        
        if matched_keywords:
            for keyword in matched_keywords:
                if not keyword.strip():
                    continue
                pattern = re.compile(re.escape(keyword), re.IGNORECASE)
                result = pattern.sub(
                    lambda m: f'<span style="{highlight_style}">{m.group()}</span>',
                    result
                )
        
        return result
        
    except Exception as e:
        st.error(f"하이라이트 처리 중 오류 발생: {str(e)}")
        return html.escape(str(text))



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
    """파일 내용 분석 - 오류 수정 및 최적화 버전"""
    if file_content is not None:
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            from functools import partial
            import numpy as np
            
            filename = getattr(file_content, 'name', '알 수 없는 파일')
            
            # 패턴 인덱싱 수정 - 딕셔너리 키를 문자열로 변경
            pattern_lookup = {}
            for idx, pat in enumerate(data):
                if not isinstance(pat, dict) or 'text' not in pat:
                    continue
                key_words = set(re.sub(r'[^가-힣a-zA-Z0-9\s]', ' ', str(pat['text']).lower()).split())
                for word in key_words:
                    if len(word) >= 2:
                        if word not in pattern_lookup:
                            pattern_lookup[word] = []
                        pattern_lookup[word].append(idx)  # 패턴 대신 인덱스 저장

            # 배치 분석 함수 수정
            def analyze_text_batch(texts, source_files, column, sheet_names=None):
                batch_results = []
                checker = SheetBasedSpellChecker()
                
                for idx, (text, source_file) in enumerate(zip(texts, source_files)):
                    if not isinstance(text, str) or not text.strip():
                        continue

                    # 1단계: 빠른 키워드 매칭
                    text_lower = str(text).lower()
                    words = set(re.sub(r'[^가-힣a-zA-Z0-9\s]', ' ', text_lower).split())
                    
                    # 후보 패턴 인덱스 수집
                    candidate_pattern_indices = set()
                    matching_words = set()
                    for word in words:
                        if len(word) >= 2 and word in pattern_lookup:
                            candidate_pattern_indices.update(pattern_lookup[word])
                            matching_words.add(word)

                    # 2단계: 상세 패턴 매칭
                    for pat_idx in candidate_pattern_indices:
                        pattern = data[pat_idx]
                        match = find_matching_patterns(text, [pattern], threshold=0.5)
                        if match:
                            for m in match:
                                m.update({
                                    'source_file': source_file,
                                    'column': column,
                                    'matching_words': list(matching_words)
                                })
                                if sheet_names is not None:
                                    m['sheet_name'] = sheet_names.iloc[idx]
                                batch_results.append(m)

                    # 맞춤법 검사 (캐시 활용)
                    spell_result = checker.check(text)
                    if spell_result['corrections']:
                        spell_check = {
                            'text': text,
                            'source_file': source_file,
                            'column': column,
                            'sheet_name': sheet_names.iloc[idx] if sheet_names is not None else None,
                            'spelling_errors': spell_result['corrections'],
                            'corrected_text': spell_result['corrected'],
                            'is_spell_check': True,
                            'match_score': 1.0,
                            'danger_level': 0
                        }
                        batch_results.append(spell_check)
                        
                return batch_results

            # 파일 처리 최적화
            BATCH_SIZE = 10000
            MAX_WORKERS = min(32, (os.cpu_count() or 1) * 2)
            
            dfs = []
            file_type = filename.split('.')[-1].lower()
            
            # 파일 타입별 최적화된 로딩
            if file_type == 'csv':
                try:
                    df = pd.read_csv(file_content, dtype=str, engine='c', encoding='utf-8')
                except UnicodeDecodeError:
                    file_content.seek(0)
                    df = pd.read_csv(file_content, dtype=str, engine='c', encoding='euc-kr')
                df['source_file'] = filename
                dfs.append(df)
            
            elif file_type in ['xlsx', 'xls']:
                excel_file = pd.ExcelFile(file_content)
                for sheet_name in excel_file.sheet_names:
                    try:
                        df = pd.read_excel(excel_file, sheet_name=sheet_name, dtype=str, engine='openpyxl')
                        df['source_file'] = f"{filename} - {sheet_name}"
                        df['sheet_name'] = sheet_name
                        dfs.append(df)
                    except Exception as e:
                        st.warning(f"시트 '{sheet_name}' 처리 중 오류: {str(e)}")
                        continue
            
            elif file_type == 'zip':
                with zipfile.ZipFile(file_content) as z:
                    for zip_filename in z.namelist():
                        if zip_filename.endswith(('.csv', '.xlsx', '.xls')):
                            with z.open(zip_filename) as f:
                                try:
                                    if zip_filename.endswith('.csv'):
                                        df = pd.read_csv(io.BytesIO(f.read()), dtype=str, engine='c')
                                    else:
                                        df = pd.read_excel(io.BytesIO(f.read()), dtype=str, engine='openpyxl')
                                    df['source_file'] = f"{filename} - {zip_filename}"
                                    dfs.append(df)
                                except Exception as e:
                                    st.warning(f"ZIP 내부 파일 '{zip_filename}' 처리 중 오류: {str(e)}")
                                    continue

            if not dfs:
                return None

            # 데이터프레임 최적화
            df = pd.concat(dfs, ignore_index=True, copy=False)
            del dfs
            gc.collect()

            text_columns = df.select_dtypes(include=['object']).columns
            text_columns = [col for col in text_columns if col not in ['source_file', 'sheet_name']]
            
            if not text_columns:
                return None

            all_results = []
            total_rows = len(df)
            
            # 진행 상황 표시
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            processed_rows = 0
            start_time = time.time()

            # 병렬 처리
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_to_batch = {}
                
                for col in text_columns:
                    texts = df[col].dropna()
                    if texts.empty:
                        continue
                        
                    source_files = df.loc[texts.index, 'source_file']
                    sheet_names = df.loc[texts.index, 'sheet_name'] if 'sheet_name' in df.columns else None
                    
                    # 배치 단위로 분할
                    for batch_start in range(0, len(texts), BATCH_SIZE):
                        batch_end = min(batch_start + BATCH_SIZE, len(texts))
                        batch_texts = texts.iloc[batch_start:batch_end]
                        batch_sources = source_files.iloc[batch_start:batch_end]
                        batch_sheets = sheet_names.iloc[batch_start:batch_end] if sheet_names is not None else None
                        
                        future = executor.submit(
                            analyze_text_batch,
                            batch_texts,
                            batch_sources,
                            col,
                            batch_sheets
                        )
                        future_to_batch[future] = (batch_end - batch_start)

                # 결과 수집
                for future in as_completed(future_to_batch):
                    try:
                        batch_size = future_to_batch[future]
                        batch_results = future.result()
                        all_results.extend(batch_results)
                        
                        processed_rows += batch_size
                        progress = min(processed_rows / total_rows, 1.0)
                        progress_bar.progress(progress)
                        
                        elapsed_time = time.time() - start_time
                        speed = processed_rows / elapsed_time if elapsed_time > 0 else 0
                        remaining_time = (total_rows - processed_rows) / speed if speed > 0 else 0
                        
                        status_text.text(f"""
                            처리 중... {processed_rows:,}/{total_rows:,} 행
                            처리 속도: {speed:.0f} 행/초
                            예상 남은 시간: {remaining_time:.1f}초
                            발견된 패턴: {len(all_results)}개
                        """)
                        
                    except Exception as e:
                        st.error(f"배치 처리 중 오류: {str(e)}")
                        import traceback
                        st.error(f"상세 오류: {traceback.format_exc()}")

            progress_bar.empty()
            status_text.empty()

            if all_results:
                # 결과 중복 제거
                unique_keys = {}
                
                for result in all_results:
                    key = (
                        result.get('text', ''),
                        result.get('pattern', '') if not result.get('is_spell_check') else 'spell_check',
                        result.get('source_file', ''),
                        result.get('column', '')
                    )
                    
                    # 우선순위 기반 결과 선택
                    if (key not in unique_keys or
                        result.get('danger_level', 0) > unique_keys[key].get('danger_level', 0) or
                        (result.get('danger_level', 0) == unique_keys[key].get('danger_level', 0) and
                         result.get('match_score', 0) > unique_keys[key].get('match_score', 0))):
                        unique_keys[key] = result

                # 결과 정렬
                unique_results = sorted(
                    unique_keys.values(),
                    key=lambda x: (-x.get('danger_level', 0), -x.get('match_score', 0))
                )

                return {
                    'total_patterns': len([r for r in unique_results if not r.get('is_spell_check', False)]),
                    'results': unique_results[:1000],
                    'filename': filename
                }
                
            return None
            
        except Exception as e:
            st.error(f"파일 분석 중 오류 발생: {str(e)}")
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
    """파일 분석 결과 표시 - 공백 최적화"""
    try:
        if not analysis_results or not analysis_results['results']:
            st.warning(f"🔍 분석 결과가 없습니다.")
            return

        results = analysis_results['results']
        pattern_results = [r for r in results if not r.get('is_spell_check', False)]
        spell_check_results = [r for r in results if r.get('is_spell_check', False)]
        
        grouped_pattern_results = group_similar_patterns(pattern_results)
        total_score = sum(r['danger_level'] for r in pattern_results)
        high_risk_count = sum(1 for r in pattern_results if r['danger_level'] >= 70)

        st.markdown("""<div style='background-color:#2D2D2D;padding:15px;border-radius:10px;margin-bottom:20px'><h3 style='color:#E0E0E0;margin:0'>📊 분석 결과 요약</h3></div>""", unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("위험 패턴", f"{len(grouped_pattern_results)}개")
        with col2: st.metric("전체 위험도", f"{total_score}")
        with col3: st.metric("고위험 패턴", f"{high_risk_count}개")
        with col4: st.metric("맞춤법 오류", f"{len(spell_check_results)}개")

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

                            with st.container():
                                # 기본 정보 표시
                                cols = st.columns([2, 1])
                                with cols[0]:
                                    st.markdown(f"<p style='color:#FFFFFF;'><strong>위험도:</strong> <span style='color:{border_color}; font-weight:bold;'>{result['danger_level']}</span></p>", unsafe_allow_html=True)
                                with cols[1]:
                                    st.markdown(f"<p style='color:#FFFFFF;'><strong>일치율:</strong> {match_percentage}%</p>", unsafe_allow_html=True)

                                # 원본 텍스트 표시
                                st.markdown("<div style='font-weight:bold; margin-top: 10px; color: #FFFFFF;'>발견된 텍스트:</div>", unsafe_allow_html=True)
                                if 'text' in result:
                                    try:
                                        highlighted_text = highlight_pattern_in_text(result['text'], result['pattern'])
                                        st.markdown(f"""
                                            <div style='white-space: pre-wrap; font-family: "Noto Sans KR", sans-serif; 
                                                    background-color: #333333; padding: 10px; border-radius: 5px; 
                                                    color: #FFFFFF; margin-bottom: 10px;'>
                                                {highlighted_text}
                                            </div>
                                        """, unsafe_allow_html=True)
                                    except:
                                        st.markdown(f"""
                                            <div style='background-color: #333333; padding: 10px; border-radius: 5px; color: #FFFFFF;'>
                                                {html.escape(str(result['text']))}
                                            </div>
                                        """, unsafe_allow_html=True)

                                # 분석 정보 표시
                                st.markdown("<div style='font-weight:bold; margin-top: 10px; color: #FFFFFF;'>분석:</div>", unsafe_allow_html=True)
                                if 'analysis' in result:
                                    st.markdown(f"""
                                        <div style='background-color: rgba{tuple(int(border_color[i:i+2], 16) for i in (1, 3, 5))}, 0.1); 
                                                padding: 10px; border-radius: 5px; color: #FFFFFF;'>
                                            {html.escape(str(result['analysis']))}
                                        </div>
                                    """, unsafe_allow_html=True)

                                # 참고 자료 링크
                                if result.get("url"):
                                    with st.container():
                                        if 'thumbnail' in result:
                                            try:
                                                st.image(result['thumbnail'], width=200)
                                            except:
                                                pass
                                        st.markdown(f"""
                                            <p><strong>🔗 <a href='{html.escape(result["url"])}' 
                                               target='_blank' style='color:{border_color};'>참고 자료</a></strong></p>
                                        """, unsafe_allow_html=True)

                            st.markdown("<hr style='border: none; height: 1px; background-color: #555555;'>", unsafe_allow_html=True)
            else:
                st.info("위험 패턴이 발견되지 않았습니다.")

        # 맞춤법 검사 결과 표시
        with tab2:
            if spell_check_results:
                for result in spell_check_results:
                    source_file = result.get('source_file', '알 수 없는 파일')
                    st.markdown(f"""<div style='background-color:#2D2D2D;padding:15px;border-radius:10px;margin:10px 0'><h4 style='color:#E0E0E0;margin:0'>📄 {html.escape(source_file)}</h4></div>""", unsafe_allow_html=True)
                    
                    st.markdown("<div style='font-weight:bold;color:#FFFFFF'>원문:</div>", unsafe_allow_html=True)
                    st.markdown(f"""<div style='background-color:#333333;padding:10px;border-radius:5px;color:#FFFFFF'>{html.escape(str(result['text']))}</div>""", unsafe_allow_html=True)
                    
                    if result.get('corrected_text'):
                        st.markdown("<div style='font-weight:bold;color:#FFFFFF;margin-top:10px'>수정문:</div>", unsafe_allow_html=True)
                        st.markdown(f"""<div style='background-color:#333333;padding:10px;border-radius:5px;color:#00E676'>{html.escape(str(result['corrected_text']))}</div>""", unsafe_allow_html=True)
                    
                    if result['spelling_errors']:
                        st.markdown("<div style='font-weight:bold;color:#FFFFFF;margin-top:10px'>맞춤법 오류 목록:</div>", unsafe_allow_html=True)
                        for error, correction in result['spelling_errors']:
                            st.markdown(f"""
                                <div style='background-color:#3D3D3D;padding:10px;border-radius:5px;margin:5px 0'>
                                    <p style='color:#FF5252;margin:0'>🔍 오류: {html.escape(error)}</p>
                                    <p style='color:#00E676;margin:0'>✅ 수정: {html.escape(correction)}</p>
                                </div>
                            """, unsafe_allow_html=True)
                    st.markdown("<hr style='border:none;height:1px;background-color:#555555;margin:20px 0'>", unsafe_allow_html=True)
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
        if not patterns:
            st.info("매칭된 패턴이 없습니다.")
            return
            
        # 패턴별 결과 표시
        for pattern in patterns:
            danger_level = pattern['danger_level']
            match_score = pattern['match_score']
            match_percentage = int(match_score * 100)
            
            # 위험도에 따른 색상 설정
            if danger_level >= 70:
                border_color = "#FF5252"
                category = "🚨 고위험"
            elif danger_level >= 30:
                border_color = "#FFD700"
                category = "⚠️ 주의"
            else:
                border_color = "#00E676"
                category = "✅ 안전"

            # 결과 카드 표시
            st.markdown(f"""
                <div style='background-color: #2D2D2D; padding: 15px; border-radius: 10px; margin: 15px 0; border-left: 5px solid {border_color};'>
                    <h5 style='color: {border_color};'>{category} (위험도: {danger_level})</h3>
                </div>
            """, unsafe_allow_html=True)

            # 기본 정보
            cols = st.columns([2, 1])
            with cols[0]:
                st.markdown(f"<p style='color:#FFFFFF;'><strong>매칭 정확도:</strong> {match_percentage}%</p>", unsafe_allow_html=True)
            with cols[1]:
                if pattern.get('matched_keywords'):
                    keywords = ', '.join(pattern['matched_keywords'])
                    st.markdown(f"<p style='color:#FFFFFF;'><strong>매칭된 키워드:</strong> {keywords}</p>", unsafe_allow_html=True)

            # 원본 텍스트 표시
            if 'original_text' in pattern:
                st.markdown("<div style='font-weight:bold; margin-top: 10px; color: #FFFFFF;'>입력된 텍스트:</div>", unsafe_allow_html=True)
                highlighted_text = highlight_pattern_in_text(
                    pattern['original_text'],
                    pattern['pattern'],
                    pattern.get('matched_keywords', [])
                )
                st.markdown(f"""
                    <div style='white-space: pre-wrap; font-family: "Noto Sans KR", sans-serif; 
                            background-color: #333333; padding: 2px; border-radius: 5px; 
                            color: #FFFFFF; margin-bottom: 10px;'>
                        {highlighted_text}
                    </div>
                """, unsafe_allow_html=True)


            # 분석 정보
            if 'analysis' in pattern:
                st.markdown("<div style='font-weight:bold; margin-top: 10px; color: #FFFFFF;'>분석:</div>", unsafe_allow_html=True)
                st.markdown(f"""
                    <div style='background-color: rgba{tuple(int(border_color[i:i+2], 16) for i in (1, 3, 5))}, 0.1); 
                            padding: 10px; border-radius: 5px; color: #FFFFFF;'>
                        {html.escape(str(pattern['analysis']))}
                    </div>
                """, unsafe_allow_html=True)

            # 참고 자료
            if pattern.get("url"):
                with st.container():
                    if 'thumbnail' in pattern:
                        try:
                            st.image(pattern['thumbnail'], width=200)
                        except:
                            pass
                    st.markdown(f"""
                        <p><strong>🔗 <a href='{html.escape(pattern["url"])}' 
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