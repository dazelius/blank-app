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


# 1. 데이터 전처리 최적화
@st.cache_data(ttl=3600)
def preprocess_patterns(data):
    """패턴 데이터 전처리 및 캐싱 - 최적화 버전"""
    processed_patterns = []
    
    # 길이별로 패턴 분류
    short_patterns = []
    medium_patterns = []
    long_patterns = []
    
    for record in data:
        pattern_text = record.get('text', '').lower()
        pattern_text_cleaned = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', pattern_text)
        pattern_words = set(pattern_text_cleaned.split())
        
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
    
    return {
        'short': short_patterns,
        'medium': medium_patterns,
        'long': long_patterns
    }


# 2. 패턴 매칭 최적화
def check_pattern(input_data, pattern_data, threshold=0.7):
    """단일 패턴 매칭 검사 - 최적화 버전"""
    input_text_cleaned, input_words, input_chars = input_data
    
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
            danger_level = int(record.get('dangerlevel', 0))
        except (ValueError, TypeError):
            danger_level = 0
            
        return {
            'pattern': record['text'],
            'analysis': record['output'],
            'danger_level': danger_level,
            'url': record.get('url', ''),
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'match_score': similarity
        }
    
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
    """병렬 처리 최적화 버전 - 유사 패턴 그룹화"""
    input_text = input_text.strip()
    if not input_text or input_text.isspace():
        return []
    
    # 입력 텍스트 전처리
    input_text_cleaned = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', input_text.lower())
    input_words = set(w for w in input_text_cleaned.split() if w.strip())
    input_chars = set(input_text_cleaned)
    
    if len(input_words) < 2:
        return []
        
    patterns = preprocess_patterns(data)
    input_data = (input_text_cleaned, input_words, input_chars)
    
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from functools import partial
    
    found_patterns = []
    pattern_groups = {}  # 패턴 그룹을 저장할 딕셔너리
    
    def get_pattern_key(text):
        """패턴의 핵심 키워드를 추출하여 정렬된 튜플로 반환"""
        cleaned = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', text.lower())
        words = sorted(set(w for w in cleaned.split() if len(w) >= 2))
        return tuple(words)
    
    def merge_patterns(existing, new_pattern):
        """두 패턴을 병합"""
        # 위험도는 최대값 사용
        existing['danger_level'] = max(existing['danger_level'], new_pattern['danger_level'])
        # 매치 점수는 최대값 사용
        existing['match_score'] = max(existing['match_score'], new_pattern['match_score'])
        # 키워드 병합
        existing_keywords = set(existing.get('matched_keywords', []))
        new_keywords = set(new_pattern.get('matched_keywords', []))
        existing['matched_keywords'] = sorted(existing_keywords | new_keywords)
        # URL이 있는 경우 추가
        if new_pattern.get('url') and not existing.get('url'):
            existing['url'] = new_pattern['url']
        # 분석 내용이 다른 경우 추가
        if new_pattern['analysis'] != existing['analysis']:
            existing['analysis'] = f"{existing['analysis']}\n추가 분석: {new_pattern['analysis']}"
        return existing
    
    def process_pattern_batch(patterns_batch):
        batch_results = []
        check_func = partial(check_pattern, input_data, threshold=threshold)
        for pattern in patterns_batch:
            if not pattern['cleaned_text'].strip():
                continue
            result = check_func(pattern)
            if result:
                result['original_text'] = input_text
                result['matched_keywords'] = extract_keywords(result['pattern'])
                # 패턴 키 생성
                pattern_key = get_pattern_key(result['pattern'])
                batch_results.append((pattern_key, result))
        return batch_results
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = []
        
        # 모든 길이의 패턴을 처리
        for pattern_type in ['short', 'medium', 'long']:
            patterns_list = patterns[pattern_type]
            chunk_size = max(1, len(patterns_list) // 4)
            for i in range(0, len(patterns_list), chunk_size):
                chunk = patterns_list[i:i + chunk_size]
                futures.append(executor.submit(process_pattern_batch, chunk))
        
        # 결과 수집 및 그룹화
        for future in as_completed(futures):
            try:
                results = future.result()
                for pattern_key, result in results:
                    if pattern_key in pattern_groups:
                        pattern_groups[pattern_key] = merge_patterns(pattern_groups[pattern_key], result)
                    else:
                        pattern_groups[pattern_key] = result
            except Exception as e:
                st.error(f"패턴 매칭 중 오류 발생: {str(e)}")
    
    # 그룹화된 결과를 리스트로 변환
    found_patterns = list(pattern_groups.values())
    
    # 매치 점수와 위험도로 정렬
    found_patterns.sort(key=lambda x: (x['match_score'], x['danger_level']), reverse=True)
    
    # 유튜브 썸네일 처리
    for pattern in found_patterns:
        if pattern.get('url') and 'youtube.com' in pattern['url']:
            thumbnail = get_youtube_thumbnail(pattern['url'])
            if thumbnail:
                pattern['thumbnail'] = thumbnail
    
    return found_patterns

def extract_keywords(text):
    """텍스트에서 핵심 키워드 추출"""
    # 특수문자 제거 및 소문자 변환
    cleaned = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', text.lower())
    # 2글자 이상 단어만 추출
    words = [w for w in cleaned.split() if len(w) >= 2]
    # 중복 제거 및 정렬
    return sorted(set(words))

def display_analysis_results(patterns, total_score):
    """분석 결과 표시 - 하이라이트 기능 추가"""
    danger_level_class = get_danger_level_class(total_score)
    st.markdown(f"""
        <div class="danger-meter">
            <h2>전체 위험도 점수</h2>
            <div class="danger-score {danger_level_class}">{total_score}</div>
        </div>
    """, unsafe_allow_html=True)

    for pattern in patterns:
        danger_level_class = get_danger_level_class(pattern['danger_level'])
        thumbnail_html = ""
        if 'thumbnail' in pattern:
            thumbnail_html = f'<img src="{pattern["thumbnail"]}" style="width:100%; max-width:480px; border-radius:10px; margin-top:10px;">'
        
        # 원본 텍스트에서 패턴 하이라이트
        highlighted_text = highlight_pattern_in_text(pattern['original_text'], pattern['pattern'])
        
        # 매치 점수를 퍼센트로 표시
        match_percentage = int(pattern['match_score'] * 100)
        
        st.markdown(f"""
            <div class="analysis-card">
                <h3>🔍 발견된 패턴:</h3>
                <div class="highlighted-text" style="
                    background-color: #2A2A2A;
                    padding: 15px;
                    border-radius: 8px;
                    margin: 10px 0;
                    line-height: 1.6;
                    font-family: 'Noto Sans KR', sans-serif;">
                    {highlighted_text}
                </div>
                <p>📊 위험도: <span class="{danger_level_class}">{pattern['danger_level']}</span></p>
                <p>🎯 일치율: {match_percentage}%</p>
                <p>📝 분석: {pattern['analysis']}</p>
                {f'<p>🔗 <a href="{pattern["url"]}" target="_blank">참고 자료</a></p>' if pattern['url'] else ''}
                {thumbnail_html}
            </div>
        """, unsafe_allow_html=True)

def highlight_pattern_in_text(original_text, pattern):
    """텍스트 내의 패턴을 하이라이트"""
    # 패턴과 원본 텍스트를 정규화
    pattern_cleaned = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', pattern.lower())
    text_cleaned = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', original_text.lower())
    
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
    
    try:
        # 패턴의 각 단어에 대해 하이라이트 처리
        pattern_words = pattern_cleaned.split()
        result_text = original_text
        
        for word in pattern_words:
            if len(word) >= 2:  # 2글자 이상의 단어만 처리
                # 대소문자 구분 없이 매칭하되, 원본 텍스트의 대소문자는 유지
                pattern = re.compile(re.escape(word), re.IGNORECASE)
                result_text = pattern.sub(
                    lambda m: f'<span style="{highlight_style}">{m.group()}</span>',
                    result_text
                )
        
        return result_text
    except Exception as e:
        st.error(f"하이라이트 처리 중 오류 발생: {str(e)}")
        return original_text

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
            def update_log(message):
                log_container.markdown(f"""
                    <div style="background-color: #2D2D2D; padding: 10px; border-radius: 5px; margin: 5px 0;">
                        {message}
                    </div>
                """, unsafe_allow_html=True)

            update_log("📂 파일 로딩 및 패턴 최적화 중...")
            
            # 파일 로드 최적화
            dfs = []
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
                        for filename in z.namelist():
                            if filename.endswith(('.csv', '.xlsx', '.xls')):
                                with z.open(filename) as f:
                                    if filename.endswith('.csv'):
                                        df = pd.read_csv(io.BytesIO(f.read()), dtype=str)
                                    else:
                                        df = pd.read_excel(io.BytesIO(f.read()), dtype=str)
                                    df['source_file'] = filename
                                    dfs.append(df)

            if not dfs:
                st.error("지원하지 않는 파일 형식이거나 처리할 수 있는 파일이 없습니다.")
                return None
                
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

            update_log("🚀 초고속 분석 시작...")

            # 텍스트 컬럼 처리
            text_columns = df.select_dtypes(include=['object']).columns
            total_patterns_found = 0
            all_results = []
            
            progress_bar = st.progress(0)
            progress_text = st.empty()
            
            def analyze_text_batch(texts, batch_idx, total_batches):
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
                                    'source_file': df.iloc[text_idx].get('source_file', 'Unknown')
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
                total_batches = (len(texts) + batch_size - 1) // batch_size
                
                for batch_idx in range(total_batches):
                    start_idx = batch_idx * batch_size
                    end_idx = min((batch_idx + 1) * batch_size, len(texts))
                    batch_texts = texts[start_idx:end_idx]
                    
                    # 배치 분석
                    results = analyze_text_batch(batch_texts, batch_idx, total_batches)
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
                        """)
            
            # 최종 결과 정리
            progress_bar.empty()
            progress_text.empty()
            
            if all_results:
                # 최종 정렬 및 중복 제거
                seen = set()
                unique_results = []
                for r in sorted(all_results, key=lambda x: (-x['match_score'], -x['danger_level'])):
                    key = (r['text'], r['pattern'])
                    if key not in seen:
                        seen.add(key)
                        unique_results.append(r)
                
                total_time = time.time() - start_time
                update_log(f"""
                    ✅ 분석 완료:
                    - 처리 시간: {total_time:.1f}초
                    - 처리 속도: {total_rows/total_time:.0f} 행/초
                    - 총 처리된 행: {processed_rows:,}개
                    - 발견된 패턴: {total_patterns_found:,}개
                """)
                
                return {
                    'total_patterns': len(unique_results),
                    'results': unique_results[:1000]  # 상위 1000개 결과만 반환
                }
            else:
                update_log("⚠️ 발견된 패턴이 없습니다.")
                return None
            
        except Exception as e:
            st.error(f"파일 분석 중 오류가 발생했습니다: {str(e)}")
            import traceback
            st.error(f"상세 오류: {traceback.format_exc()}")
            return None
    return None

import streamlit as st
import html

def display_file_analysis_results(analysis_results):
    """파일 분석 결과 표시 - 개선된 버전"""
    if not analysis_results or not analysis_results['results']:
        st.warning("🔍 분석 결과가 없습니다.")
        return

    # 통계 계산
    total_score = sum(result['danger_level'] for result in analysis_results['results'])
    avg_score = total_score / len(analysis_results['results']) if analysis_results['results'] else 0
    high_risk_count = sum(1 for r in analysis_results['results'] if r['danger_level'] >= 70)

    # 결과 정렬 및 그룹화
    sorted_results = sorted(
        analysis_results['results'],
        key=lambda x: (x['danger_level'], x['match_score']),
        reverse=True
    )

    # 위험도별 결과 표시
    for severity in ['high', 'medium', 'low']:
        if severity == 'high':
            results = [r for r in sorted_results if r['danger_level'] >= 70]
            title = "🚨 고위험 항목"
            border_color = "#FF5252"
        elif severity == 'medium':
            results = [r for r in sorted_results if 30 <= r['danger_level'] < 70]
            title = "⚠️ 주의 항목"
            border_color = "#FFD700"
        else:
            results = [r for r in sorted_results if r['danger_level'] < 30]
            title = "✅ 안전 항목"
            border_color = "#00E676"

        if results:
            st.markdown(f"<h3 style='color:{border_color}; border-left: 6px solid {border_color}; padding-left: 10px;'>{title} ({len(results)}개)</h3>", unsafe_allow_html=True)

            for result in results:
                match_percentage = int(result['match_score'] * 100)

                with st.container():
                    # 위험도, 일치율, 컬럼 정보 표시
                    cols = st.columns([2, 1, 1])
                    with cols[0]:
                        if result['danger_level'] >= 70:
                            danger_level_text = "위험"
                            danger_level_color = "#FF5252"
                        elif result['danger_level'] >= 30:
                            danger_level_text = "주의"
                            danger_level_color = "#FFD700"
                        else:
                            danger_level_text = "안전"
                            danger_level_color = "#00E676"
                        st.markdown(f"<p style='color:#FFFFFF;'><strong>위험도:</strong> <span style='color:{danger_level_color}; font-weight:bold;'>{danger_level_text}</span></p>", unsafe_allow_html=True)
                    with cols[1]:
                        st.markdown(f"<p style='color:#FFFFFF;'><strong>일치율:</strong> {match_percentage}%</p>", unsafe_allow_html=True)
                    with cols[2]:
                        st.markdown(f"<p style='color:#FFFFFF;'><strong>컬럼:</strong> {html.escape(result['column'])}</p>", unsafe_allow_html=True)

                    # 원본 텍스트 섹션
                    st.markdown("<div style='font-weight:bold; margin-top: 10px; color: #FFFFFF;'>원본 텍스트:</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='white-space: pre-wrap; font-family: \"Noto Sans KR\", sans-serif; background-color: #333333; padding: 10px; border-radius: 5px; color: #FFFFFF;'>{html.escape(result['text'])}</div>", unsafe_allow_html=True)

                    # 매칭된 패턴 섹션
                    st.markdown("<div style='font-weight:bold; margin-top: 10px; color: #FFFFFF;'>매칭된 패턴:</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='background-color: #444444; padding: 8px; border-radius: 5px; color: #FFFFFF;'>{html.escape(result['pattern'])}</div>", unsafe_allow_html=True)

                    # 분석 섹션
                    st.markdown("<div style='font-weight:bold; margin-top: 10px; color: #FFFFFF;'>분석:</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='background-color: rgba{tuple(int(border_color[i:i+2], 16) for i in (1, 3, 5))}, 0.1); padding: 10px; border-radius: 5px; color: #FFFFFF;'>{html.escape(result['analysis'])}</div>", unsafe_allow_html=True)

                    # 썸네일 및 참고 자료 링크
                    with st.container():
                        # 썸네일 가져오기
                        thumbnail_url = get_thumbnail_url(result.get("url"))
                        if thumbnail_url:
                            try:
                                response = requests.get(thumbnail_url)
                                image = Image.open(BytesIO(response.content))
                                st.image(image, width=200, use_column_width=False)
                            except:
                                pass

                        # 참고 자료 링크
                        if result.get("url"):
                            st.markdown(f"<p><strong>🔗 <a href='{html.escape(result['url'])}' target='_blank' style='color:{border_color};'>참고 자료</a></strong></p>", unsafe_allow_html=True)

                # 구분선
                st.markdown("<hr style='border: none; height: 1px; background-color: #555555;'>", unsafe_allow_html=True)

    # 분석 완료 메시지
    if sorted_results:
        st.success(f"✨ 총 {analysis_results['total_patterns']}개의 패턴이 발견되었습니다.")
    else:
        st.info("👀 발견된 패턴이 없습니다.")

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



def main():
    st.markdown('<h1 class="main-title">⚠️스트링 테이블 분석⚠️</h1>', unsafe_allow_html=True)
    st.markdown("""
    > 💡 입력된 문장을 분석하고 점수화하여 보여드립니다.
    """)

    # 데이터 로드
    data = load_sheet_data()
    if data is None:
        st.error("데이터를 불러올 수 없습니다.")
        return

    # 탭 생성
    tab1, tab2 = st.tabs(["🔍 문장 분석", "✏️ 패턴 등록"])

    with tab1:
        analysis_type = st.radio(
            "분석 유형 선택:",
            ["텍스트 직접 입력", "파일/폴더 업로드"],
            horizontal=True
        )
        
        if analysis_type == "텍스트 직접 입력":
            # ... (텍스트 분석 코드 유지)
            pass
        
        else:  # 파일/폴더 업로드
            st.markdown("""
                <div style="background-color: #2D2D2D; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                    <h4>📁 파일 업로드 안내</h4>
                    <p>• 단일 파일: CSV, Excel 파일 직접 업로드</p>
                    <p>• 폴더 업로드: 여러 파일을 ZIP으로 압축하여 업로드</p>
                    <p>• 지원 형식: .csv, .xlsx, .xls, .zip</p>
                </div>
            """, unsafe_allow_html=True)
            
            uploaded_file = st.file_uploader(
                "파일 또는 ZIP 폴더 업로드", 
                type=['csv', 'xlsx', 'xls', 'zip'],
                help="여러 파일을 분석하려면 ZIP 파일로 압축하여 업로드하세요."
            )
            
            if uploaded_file is not None:
                if st.button("📂 파일 분석", use_container_width=True):
                    with st.spinner('🔄 파일을 분석하고 있습니다...'):
                        analysis_results = analyze_file_contents(uploaded_file, data)
                        if analysis_results and analysis_results['total_patterns'] > 0:
                            st.success(f"🎯 분석이 완료되었습니다! 총 {analysis_results['total_patterns']}개의 패턴이 발견되었습니다.")
                            display_file_analysis_results(analysis_results)
                        elif analysis_results:
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
                        # 캐시 갱신
                        st.cache_data.clear()
                        # 페이지 새로고침
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
        
        # 데이터프레임 생성 및 표시
        if data:
            df = pd.DataFrame(data)
            
            # 컬럼명 변경
            column_mapping = {
                'text': '패턴',
                'output': '분석',
                'url': '참고 URL',
                'dangerlevel': '위험도',
                'timestamp': '등록일시'
            }
            
            # 존재하는 컬럼만 이름 변경
            for old_col, new_col in column_mapping.items():
                if old_col in df.columns:
                    df = df.rename(columns={old_col: new_col})
            
            # 검색/필터링 기능
            search_term = st.text_input("🔍 패턴 검색:", placeholder="검색어를 입력하세요...")
            if search_term:
                pattern_mask = df['패턴'].astype(str).str.contains(search_term, case=False, na=False)
                analysis_mask = df['분석'].astype(str).str.contains(search_term, case=False, na=False)
                df = df[pattern_mask | analysis_mask]
            
            # 위험도 필터링
            if '위험도' in df.columns:
                col1, col2 = st.columns(2)
                with col1:
                    min_danger = st.number_input("최소 위험도:", min_value=0, max_value=100, value=0)
                with col2:
                    max_danger = st.number_input("최대 위험도:", min_value=0, max_value=100, value=100)
                
                df['위험도'] = pd.to_numeric(df['위험도'], errors='coerce')
                df = df[(df['위험도'] >= min_danger) & (df['위험도'] <= max_danger)]
            
            # 테이블 표시
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                height=400
            )
            
            # 통계 정보 표시
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


if __name__ == "__main__":
    main()