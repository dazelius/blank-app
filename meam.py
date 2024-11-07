import streamlit as st
import gspread
from google.oauth2 import service_account
import re
import difflib
import json
from datetime import datetime
import os

# 페이지 설정
st.set_page_config(
    page_title="문장 위험도 분석기",
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
        <title>문장 위험도 분석기</title>
        <meta property="og:title" content="문장 위험도 분석기"/>
        <meta property="og:description" content="문장의 위험도를 분석해드립니다."/>
        <meta property="og:image" content="문장 위험도 분석기"/>
    </head>''', unsafe_allow_html=True)

# CSS 스타일 업데이트
st.markdown("""
<style>
    .main-title {
        text-align: center;
        padding: 1.5rem;
        background: linear-gradient(135deg, #ff4e50 0%, #f9d423 100%);
        color: white;
        border-radius: 15px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .danger-meter {
        text-align: center;
        padding: 2rem;
        margin: 1rem 0;
        border-radius: 15px;
        background: #f8f9fa;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
    }
    .danger-score {
        font-size: 3rem;
        font-weight: bold;
        margin: 1rem 0;
    }
    .danger-level-low {
        color: #2ecc71;
    }
    .danger-level-medium {
        color: #f1c40f;
    }
    .danger-level-high {
        color: #e74c3c;
    }
    .analysis-card {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        margin-bottom: 1rem;
    }
    /* 기존 스타일 유지 */
    [이전 CSS 스타일들...]
</style>
""", unsafe_allow_html=True)

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

def find_matching_patterns(input_text, data, threshold=0.6):
    """입력 텍스트와 일치하는 패턴 찾기"""
    if not input_text.strip():
        return []
        
    found_patterns = []
    input_text_cleaned = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', input_text.lower())
    input_words = input_text_cleaned.split()
    matched_patterns = set()
    
    patterns_cleaned = [re.sub(r'[^가-힣a-zA-Z0-9\s]', '', record['text'].lower()) for record in data]
    
    for idx, pattern_text in enumerate(patterns_cleaned):
        if any(word in pattern_text for word in input_words):
            matched_patterns.add(idx)
            continue
            
        pattern_words = pattern_text.split()
        for input_word in input_words:
            for pattern_word in pattern_words:
                if (input_word in pattern_word or pattern_word in input_word):
                    matched_patterns.add(idx)
                    break
                if len(input_word) > 1:
                    score = difflib.SequenceMatcher(None, input_word, pattern_word).ratio()
                    if score >= threshold:
                        matched_patterns.add(idx)
                        break
    
    for idx in matched_patterns:
        record = data[idx]
        pattern_info = {
            'pattern': record['text'],
            'analysis': record['output'],
            'danger_level': int(record.get('danger_level', 0)),
            'url': record.get('url', ''),
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        found_patterns.append(pattern_info)
    
    return found_patterns

def display_analysis_results(patterns, total_score):
    """분석 결과 표시"""
    # 전체 위험도 점수 표시
    danger_level_class = get_danger_level_class(total_score)
    st.markdown(f"""
        <div class="danger-meter">
            <h2>전체 위험도 점수</h2>
            <div class="danger-score {danger_level_class}">{total_score}</div>
        </div>
    """, unsafe_allow_html=True)
    
    # 개별 패턴 분석 결과 표시
    for pattern in patterns:
        danger_level_class = get_danger_level_class(pattern['danger_level'])
        st.markdown(f"""
            <div class="analysis-card">
                <h3>🔍 발견된 패턴: {pattern['pattern']}</h3>
                <p>📊 위험도: <span class="{danger_level_class}">{pattern['danger_level']}</span></p>
                <p>📝 분석: {pattern['analysis']}</p>
                {f'<p>🔗 <a href="{pattern["url"]}" target="_blank">참고 자료</a></p>' if pattern['url'] else ''}
            </div>
        """, unsafe_allow_html=True)

def main():
    # 헤더
    st.markdown('<h1 class="main-title">⚠️ 문장 위험도 분석기 ⚠️</h1>', unsafe_allow_html=True)
    st.markdown("""
    > 💡 입력된 문장의 위험도를 분석하고 점수화하여 보여드립니다.
    """)

    # Google Sheets 연결 설정
    client = setup_google_auth()
    if not client:
        st.error("Google Sheets 연결에 실패했습니다.")
        return

    try:
        sheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1wPchxwAssBf706VuvxhGp4ESt3vj-N9RLcMaUF075ug/edit?gid=137455637#gid=137455637')
        worksheet = sheet.get_worksheet(0)
        data = worksheet.get_all_records()
    except Exception as e:
        st.error(f"스프레드시트 접근 오류: {str(e)}")
        return

    # 탭 생성
    tab1, tab2 = st.tabs(["🔍 문장 분석", "✏️ 패턴 등록"])

    with tab1:
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

    with tab2:
        st.markdown("""
        <div style='background-color: #f8f9fa; padding: 1rem; border-radius: 10px; margin-bottom: 1rem;'>
            <h4>🌟 새로운 패턴 등록</h4>
            <p style='color: #666;'>새로운 위험 패턴을 등록해주세요.</p>
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
                    list_worksheet = sheet.worksheet('DataBase')
                    list_worksheet.append_row([
                        pattern_text,
                        analysis_text,
                        url,
                        danger_level,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ])
                    st.success("✅ 패턴이 등록되었습니다!")
                    st.balloons()
                except Exception as e:
                    st.error(f"😢 패턴 등록 중 오류가 발생했습니다: {str(e)}")
            else:
                st.warning("⚠️ 패턴과 분석 내용은 필수입니다!")

if __name__ == "__main__":
    main()