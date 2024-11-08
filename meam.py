import streamlit as st
import gspread
from google.oauth2 import service_account
import re
import difflib
import json
from datetime import datetime
import os
import pandas as pd

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
    """병렬 처리 최적화 버전 - 키워드 표시 및 개선된 중복 제거"""
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
    seen_patterns = {}  # 패턴의 핵심 키워드를 저장하는 딕셔너리
    
    def extract_keywords(text):
        """텍스트에서 핵심 키워드 추출"""
        cleaned = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', text.lower())
        words = [w for w in cleaned.split() if len(w) >= 2]  # 2글자 이상 단어만 추출
        return set(words)
    
    def is_duplicate_pattern(new_pattern, keywords):
        """개선된 중복 패턴 감지"""
        new_keywords = extract_keywords(new_pattern)
        
        for existing_pattern, existing_keywords in seen_patterns.items():
            # 키워드 overlap 비율 계산
            if new_keywords and existing_keywords:
                overlap = len(new_keywords & existing_keywords)
                union = len(new_keywords | existing_keywords)
                similarity = overlap / union
                
                # 80% 이상 키워드가 겹치면 중복으로 판단
                if similarity >= 0.8:
                    return True
                
                # 한 패턴이 다른 패턴을 완전히 포함하는 경우
                if new_pattern in existing_pattern or existing_pattern in new_pattern:
                    return True
        
        return False
    
    def process_pattern_batch(patterns_batch):
        batch_results = []
        check_func = partial(check_pattern, input_data, threshold=threshold)
        for pattern in patterns_batch:
            if not pattern['cleaned_text'].strip():
                continue
            result = check_func(pattern)
            if result:
                # 매칭된 키워드 추출 및 저장
                keywords = extract_keywords(result['pattern'])
                result['matched_keywords'] = list(keywords)
                result['original_text'] = input_text
                batch_results.append(result)
        return batch_results
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = []
        
        # 패턴 길이별 처리
        for pattern_type in ['short', 'medium', 'long']:
            patterns_list = patterns[pattern_type]
            chunk_size = max(1, len(patterns_list) // 4)
            for i in range(0, len(patterns_list), chunk_size):
                chunk = patterns_list[i:i + chunk_size]
                futures.append(executor.submit(process_pattern_batch, chunk))
        
        # 결과 수집 및 중복 제거
        for future in as_completed(futures):
            try:
                results = future.result()
                for result in results:
                    keywords = set(result['matched_keywords'])
                    
                    if not is_duplicate_pattern(result['pattern'], keywords):
                        found_patterns.append(result)
                        seen_patterns[result['pattern']] = keywords
            except Exception as e:
                st.error(f"패턴 매칭 중 오류 발생: {str(e)}")
    
    # 매치 점수와 위험도로 정렬
    found_patterns.sort(key=lambda x: (x['match_score'], x['danger_level']), reverse=True)
    found_patterns = found_patterns[:10]
    
    # 썸네일 처리
    for pattern in found_patterns:
        if pattern['url'] and 'youtube.com' in pattern['url']:
            thumbnail = get_youtube_thumbnail(pattern['url'])
            if thumbnail:
                pattern['thumbnail'] = thumbnail
    
    return found_patterns

def display_analysis_results(patterns, total_score):
    """분석 결과 표시 - 완전한 버전"""
    # 상단 전체 위험도 점수 표시
    danger_level_class = get_danger_level_class(total_score)
    st.markdown(f"""
        <style>
        .danger-score {
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
        }
        .matched-keywords {
            background-color: #3D3D3D;
            padding: 4px 8px;
            border-radius: 4px;
            font-family: 'Noto Sans KR', monospace;
            margin: 2px;
            display: inline-block;
        }
        .keyword-container {
            margin: 10px 0;
            line-height: 2;
        }
        .pattern-metadata {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 10px;
            margin: 15px 0;
            background-color: #2A2A2A;
            padding: 10px;
            border-radius: 8px;
        }
        .metadata-item {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .analysis-content {
            background-color: #2A2A2A;
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
            line-height: 1.6;
        }
        </style>
        <div class="danger-meter">
            <h2>전체 위험도 점수</h2>
            <div class="danger-score {danger_level_class}">{total_score}</div>
        </div>
    """, unsafe_allow_html=True)

    # 각 패턴별 결과 표시
    for pattern in patterns:
        danger_level_class = get_danger_level_class(pattern['danger_level'])
        
        # 썸네일 처리
        thumbnail_html = ""
        if 'thumbnail' in pattern:
            thumbnail_html = f'<img src="{pattern["thumbnail"]}" style="width:100%; max-width:480px; border-radius:10px; margin-top:10px;">'
        
        # 하이라이트된 텍스트 생성
        highlighted_text = highlight_pattern_in_text(pattern['original_text'], pattern['pattern'])
        
        # 매치 점수를 퍼센트로 변환
        match_percentage = int(pattern['match_score'] * 100)
        
        # 매칭된 키워드 처리
        keywords_html = ""
        if 'matched_keywords' in pattern and pattern['matched_keywords']:
            keywords = pattern['matched_keywords']
            keyword_spans = ''.join([
                f'<span class="matched-keywords">{keyword}</span>'
                for keyword in keywords
            ])
            keywords_html = f"""
            <div class="keyword-container">
                <p>🔑 매칭된 키워드:</p>
                <div>{keyword_spans}</div>
            </div>
            """
        
        # 메인 카드 표시
        st.markdown(f"""
            <div class="analysis-card">
                <h3>🔍 발견된 패턴:</h3>
                {keywords_html}
                
                <div class="pattern-metadata">
                    <div class="metadata-item">
                        <span>📊 위험도:</span>
                        <span class="{danger_level_class}">{pattern['danger_level']}</span>
                    </div>
                    <div class="metadata-item">
                        <span>🎯 일치율:</span>
                        <span>{match_percentage}%</span>
                    </div>
                    <div class="metadata-item">
                        <span>⏰ 검출 시각:</span>
                        <span>{pattern['timestamp']}</span>
                    </div>
                </div>
                
                <div class="analysis-content">
                    <div style="font-weight: bold;">원본 텍스트:</div>
                    <div style="font-family: 'Noto Sans KR', sans-serif;">
                        {highlighted_text}
                    </div>
                </div>
                
                <div class="analysis-content">
                    <div style="font-weight: bold;">📝 분석:</div>
                    <div>{pattern['analysis']}</div>
                </div>
                
                {f'<div class="metadata-item"><span>🔗</span><a href="{pattern["url"]}" target="_blank">참고 자료</a></div>' if pattern.get('url') else ''}
                {thumbnail_html}
            </div>
        """, unsafe_allow_html=True)
        
        # 추가 정보가 있는 경우 expander로 표시
        if pattern.get('additional_info'):
            with st.expander("추가 정보"):
                st.markdown(pattern['additional_info'])

    # 요약 정보 표시 (여러 패턴이 있는 경우)
    if len(patterns) > 1:
        unique_keywords = set()
        max_danger = 0
        avg_match = 0
        
        for pattern in patterns:
            if 'matched_keywords' in pattern:
                unique_keywords.update(pattern['matched_keywords'])
            max_danger = max(max_danger, pattern['danger_level'])
            avg_match += pattern['match_score']
        
        avg_match = (avg_match / len(patterns)) * 100
        
        st.markdown(f"""
            <div class="analysis-card">
                <h3>📊 분석 요약</h3>
                <div class="pattern-metadata">
                    <div class="metadata-item">
                        <span>발견된 패턴 수:</span>
                        <span>{len(patterns)}개</span>
                    </div>
                    <div class="metadata-item">
                        <span>고유 키워드 수:</span>
                        <span>{len(unique_keywords)}개</span>
                    </div>
                    <div class="metadata-item">
                        <span>최대 위험도:</span>
                        <span class="{get_danger_level_class(max_danger)}">{max_danger}</span>
                    </div>
                    <div class="metadata-item">
                        <span>평균 일치율:</span>
                        <span>{avg_match:.1f}%</span>
                    </div>
                </div>
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
    """파일 내용 분석"""
    results = []
    
    if file_content is not None:
        try:
            # 파일 확장자 확인
            file_type = file_content.name.split('.')[-1].lower()
            
            if file_type == 'csv':
                df = pd.read_csv(file_content)
            elif file_type in ['xlsx', 'xls']:
                df = pd.read_excel(file_content)
            else:
                st.error("지원하지 않는 파일 형식입니다. CSV 또는 Excel 파일만 지원합니다.")
                return None
            
            # 모든 텍스트 컬럼 분석
            text_columns = df.select_dtypes(include=['object']).columns
            total_patterns_found = 0
            all_results = []
            
            # 프로그레스 바 생성
            progress_bar = st.progress(0)
            progress_text = st.empty()
            
            for idx, col in enumerate(text_columns):
                for text in df[col].dropna():
                    if isinstance(text, str):  # 문자열인 경우만 분석
                        patterns = find_matching_patterns(text, data)
                        if patterns:
                            score = calculate_danger_score(patterns)
                            all_results.append({
                                'text': text,
                                'column': col,
                                'patterns': patterns,
                                'score': score
                            })
                            total_patterns_found += len(patterns)
                
                # 진행률 업데이트
                progress = (idx + 1) / len(text_columns)
                progress_bar.progress(progress)
                progress_text.text(f'분석 진행 중... {int(progress * 100)}%')
            
            # 프로그레스 바와 텍스트 제거
            progress_bar.empty()
            progress_text.empty()
            
            return {
                'total_patterns': total_patterns_found,
                'results': all_results
            }
            
        except Exception as e:
            st.error(f"파일 분석 중 오류가 발생했습니다: {str(e)}")
            return None
    return None

def display_file_analysis_results(analysis_results):
    """파일 분석 결과 표시 - 개선된 형식"""
    if not analysis_results or not analysis_results['results']:
        return
    
    # Calculate statistics
    total_score = sum(result['score'] for result in analysis_results['results'])
    avg_score = total_score / len(analysis_results['results']) if analysis_results['results'] else 0
    
    st.markdown("""
        <div class="database-title">
            📊 파일 분석 결과
        </div>
        
        <style>
        .text-header {
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 10px;
            font-family: 'Noto Sans KR', sans-serif;
        }
        
        .perfect-match {
            background-color: rgba(255, 165, 0, 0.2);
            border-left: 4px solid #FFA500;
        }
        
        .partial-match {
            background-color: #2D2D2D;
            border-left: 4px solid #4A4A4A;
        }
        
        .match-info {
            color: #888;
            font-size: 0.9em;
        }
        
        .match-100 {
            color: #FFA500;
            font-weight: bold;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # 결과를 위험도 순으로 정렬
    sorted_results = sorted(analysis_results['results'], key=lambda x: x['score'], reverse=True)
    
    for result in sorted_results:
        # 검출된 단어 목록 생성
        detected_words = []
        match_percentage = 0
        
        for pattern in result['patterns']:
            pattern_words = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', pattern['pattern'].lower()).split()
            detected_words.extend(pattern_words)
            match_percentage = max(match_percentage, pattern.get('match_score', 0) * 100)
        
        # 중복 제거 및 정렬
        detected_words = sorted(list(set(detected_words)))
        
        # 일치율에 따른 스타일 선택
        is_perfect_match = match_percentage >= 99.9  # 반올림 오차를 고려하여 99.9% 이상을 100%로 취급
        style_class = "perfect-match" if is_perfect_match else "partial-match"
        match_class = "match-100" if is_perfect_match else ""
        
        st.markdown(f"""
            <div class="text-header {style_class}">
                <div>검출된 텍스트 (컬럼: {result['column']}, 위험도: {result['score']})</div>
                <div class="match-info">
                    검출 단어: [{', '.join(detected_words)}]
                </div>
                <div class="match-info">
                    일치율: <span class="{match_class}">{match_percentage:.1f}%</span>
                </div>
                <div style="margin-top: 5px;">
                    {result['text']}
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # 패턴 상세 정보는 expander로 표시
        with st.expander("상세 정보 보기"):
            for pattern in result['patterns']:
                match_score = pattern.get('match_score', 0) * 100
                st.markdown(f"""
                    <div style="padding: 10px; background-color: #3D3D3D; border-radius: 5px; margin: 5px 0;">
                        <p>🔍 패턴: {pattern['pattern']}</p>
                        <p>📊 위험도: {pattern['danger_level']}</p>
                        <p>📝 분석: {pattern['analysis']}</p>
                        <p>🎯 일치율: {match_score:.1f}%</p>
                    </div>
                """, unsafe_allow_html=True)

    # CSS 스타일 추가
    st.markdown("""
    <style>
        .expander-content {
            background-color: #2D2D2D;
            padding: 10px;
            border-radius: 5px;
            margin-top: 5px;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # 위험도에 따른 색상 정의
    def get_color_style(score):
        if score >= 70:
            return "color: #FF5252; font-weight: bold;"  # 빨간색
        elif score >= 30:
            return "color: #FFD700; font-weight: bold;"  # 노란색
        else:
            return "color: #00E676; font-weight: bold;"  # 초록색
    
    # 통계 표시
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
            <div style="text-align: center; padding: 10px; background-color: #2D2D2D; border-radius: 10px;">
                <div style="font-size: 1.2em;">분석된 패턴 수</div>
                <div style="font-size: 2em; {get_color_style(0)}">{analysis_results['total_patterns']}</div>
            </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
            <div style="text-align: center; padding: 10px; background-color: #2D2D2D; border-radius: 10px;">
                <div style="font-size: 1.2em;">평균 위험도</div>
                <div style="font-size: 2em; {get_color_style(avg_score)}">{avg_score:.1f}</div>
            </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
            <div style="text-align: center; padding: 10px; background-color: #2D2D2D; border-radius: 10px;">
                <div style="font-size: 1.2em;">총 위험도</div>
                <div style="font-size: 2em; {get_color_style(total_score)}">{total_score}</div>
            </div>
        """, unsafe_allow_html=True)

    
    # 결과를 위험도 순으로 정렬
    sorted_results = sorted(analysis_results['results'], key=lambda x: x['score'], reverse=True)
    
    # 하이라이트 스타일 정의
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
    
    # 상세 결과 표시
    for result in sorted_results:
        # 원본 텍스트에 모든 패턴의 하이라이트 적용
        highlighted_text = result['text']
        for pattern in result['patterns']:
            pattern_text = pattern['pattern']
            pattern_words = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', pattern_text.lower()).split()
            
            for word in pattern_words:
                if len(word) >= 2:  # 2글자 이상의 단어만 처리
                    pattern_regex = re.compile(f'({re.escape(word)})', re.IGNORECASE)
                    highlighted_text = pattern_regex.sub(
                        fr'<span style="{highlight_style}">\1</span>',
                        highlighted_text
                    )
        
        # 위험도에 따른 확장 여부 설정
        is_high_risk = result['score'] >= 70
        with st.expander(
            f"🔍 검출된 텍스트 (컬럼: {result['column']}, 위험도: {result['score']})",
            expanded=is_high_risk
        ):
            # 원본 텍스트와 하이라이트된 버전 표시
            st.markdown(f"""
                <div style="padding: 15px; background-color: #2D2D2D; border-radius: 10px; margin-bottom: 10px;">
                    <div style="font-weight: bold;">원본 텍스트 (하이라이트 표시):</div>
                    <div style="padding: 10px; background-color: #3D3D3D; border-radius: 5px; margin-top: 5px; line-height: 1.6;">
                        {highlighted_text}
                    </div>
                    <div style="margin-top: 10px;">
                        <span style="font-weight: bold;">검출된 컬럼:</span> {result['column']}
                    </div>
                    <div style="margin-top: 5px;">
                        <span style="font-weight: bold;">위험도 점수:</span> 
                        <span style="{get_color_style(result['score'])}">{result['score']}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            # 개별 패턴 분석 결과 표시
            for pattern in result['patterns']:
                danger_style = get_color_style(pattern['danger_level'])
                thumbnail_html = ""
                if 'thumbnail' in pattern:
                    thumbnail_html = f'<img src="{pattern["thumbnail"]}" style="width:100%; max-width:480px; border-radius:10px; margin-top:10px;">'
                
                match_percentage = int(pattern.get('match_score', 0) * 100)
                
                st.markdown(f"""
                    <div class="analysis-card" style="border-left: 4px solid {danger_style.split(':')[1].split(';')[0].strip()};">
                        <h3>🔍 발견된 패턴: {pattern['pattern']}</h3>
                        <p>📊 위험도: <span style="{danger_style}">{pattern['danger_level']}</span></p>
                        <p>🎯 일치율: {match_percentage}%</p>
                        <p>📝 분석: {pattern['analysis']}</p>
                        {f'<p>🔗 <a href="{pattern["url"]}" target="_blank">참고 자료</a></p>' if pattern["url"] else ''}
                        {thumbnail_html}
                    </div>
                """, unsafe_allow_html=True)

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
            ["텍스트 직접 입력", "파일 업로드"],
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
                    found_patterns = find_matching_patterns(input_text, data)
                    if found_patterns:
                        total_score = calculate_danger_score(found_patterns)
                        st.success(f"🎯 분석이 완료되었습니다! {len(found_patterns)}개의 패턴이 발견되었습니다.")
                        display_analysis_results(found_patterns, total_score)
                    else:
                        st.info("👀 특별한 위험 패턴이 발견되지 않았습니다.")
        
        else:  # 파일 업로드
            uploaded_file = st.file_uploader("CSV 또는 Excel 파일 업로드", type=['csv', 'xlsx', 'xls'])
            
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