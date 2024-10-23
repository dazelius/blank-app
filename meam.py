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
    page_title="밈 판독기",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': "밈을 판독해 드립니다."
    }
)

# Open Graph 메타 태그 추가
st.markdown('''
    <head>
        <title>밈 판독기</title>
        <meta property="og:title" content="밈 판독기"/>
        <meta property="og:description" content="밈을 판독해 드립니다."/>
        <meta property="og:image" content="밈 판독기"/>
    </head>''', unsafe_allow_html=True)


# CSS 스타일 개선
st.markdown("""
<style>
    .main-title {
        text-align: center;
        padding: 1.5rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 15px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .stButton>button {
        width: 100%;
        background: linear-gradient(to right, #4facfe 0%, #00f2fe 100%);
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 10px;
        font-weight: 600;
        transition: transform 0.2s;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
    }
    .horizontal-scroll {
        display: flex;
        overflow-x: auto;
        padding: 1rem 0;
        gap: 1rem;
        margin-bottom: 2rem;
        white-space: nowrap;
    }

    .meme-card {
        min-width: 300px;
        max-width: 300px;
        padding: 1.5rem;
        background: white;
        border-radius: 15px;
        border: 1px solid #e1e4e8;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s;
        margin-right: 1rem;
        flex: 0 0 auto;
        display: inline-block;
        vertical-align: top;
    }

    .meme-card img {
        width: 100%;
        height: auto;
        object-fit: cover;
        border-radius: 8px;
    }
    .meme-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
    }
    .meme-card h3 {
        color: #2d3748;
        margin-bottom: 1rem;
        font-size: 1.25rem;
    }
    .meme-card p {
        color: #4a5568;
        line-height: 1.6;
        margin-bottom: 1rem;
    }
    .meme-card a {
        color: #4facfe;
        text-decoration: none;
        font-weight: 500;
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
    }
    .meme-card a:hover {
        text-decoration: underline;
    }
    .no-link {
        color: #666;
        font-style: italic;
    }
    .success-msg {
        padding: 1rem;
        background-color: #c6f6d5;
        color: #2f855a;
        border-radius: 10px;
        margin-bottom: 1rem;
        border: 1px solid #9ae6b4;
    }
    .error-msg {
        padding: 1rem;
        background-color: #fed7d7;
        color: #c53030;
        border-radius: 10px;
        margin-bottom: 1rem;
        border: 1px solid #feb2b2;
    }
    .horizontal-scroll::-webkit-scrollbar {
        height: 8px;
    }
    .horizontal-scroll::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 4px;
    }
    .horizontal-scroll::-webkit-scrollbar-thumb {
        background: #888;
        border-radius: 4px;
    }
    .horizontal-scroll::-webkit-scrollbar-thumb:hover {
        background: #555;
    }
    .stTextInput>div>div>input {
        border-radius: 10px;
    }
    .stTextArea>div>div>textarea {
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

def setup_google_auth():
    """Google Sheets API 인증 설정"""
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
        return client
    except Exception as e:
        st.error(f"인증 오류가 발생했습니다: {str(e)}")
        return None

def get_youtube_thumbnail_url(url):
    """유튜브 URL에서 썸네일 URL 추출"""
    video_id_match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    if video_id_match:
        video_id = video_id_match.group(1)
        return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
    return None

def find_matching_memes(input_text, data, threshold=0.6):
    """입력 텍스트와 일치하는 밈 찾기"""
    if not input_text.strip():
        return []
        
    found_memes = []
    input_words = input_text.lower().split()
    matched_memes = set()
    
    meme_texts = [record['text'].lower() for record in data]
    
    # 정확한 매칭 먼저 시도
    for idx, meme_text in enumerate(meme_texts):
        if any(word in meme_text for word in input_words):
            matched_memes.add(idx)
    
    # 유사도 기반 매칭
    if not matched_memes:
        for idx, meme_text in enumerate(meme_texts):
            for word in input_words:
                if len(word) > 1:  # 1글자 단어는 제외
                    score = difflib.SequenceMatcher(None, word, meme_text).ratio()
                    if score >= threshold:
                        matched_memes.add(idx)
    
    # 결과 수집
    for idx in matched_memes:
        record = data[idx]
        meme_info = {
            'meme': record['text'],
            'output': record['output'],
            'url': record['url'] if 'url' in record else '',
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        if meme_info['url'] and "youtube.com" in meme_info['url']:
            meme_info['thumbnail'] = get_youtube_thumbnail_url(meme_info['url'])
        found_memes.append(meme_info)
    
    return found_memes

def display_meme_cards(memes):
    """밈 정보를 가로 스크롤 카드 형태로 표시"""
    if not memes:
        return
    
    # 가로 스크롤을 위한 컨테이너 시작
    cards_html = '<div class="horizontal-scroll">'
    
    for meme in memes:
        url_html = f'<a href="{meme["url"]}" target="_blank">🔗 원본 보기</a>' if meme.get('url') and meme['url'].strip() else '<span class="no-link">🔗 관련 링크 없음</span>'
        
        cards_html += f"""
        <div class="meme-card">
            <h3>💭 {meme['meme']}</h3>
            <p>📝 {meme['output']}</p>
            {url_html}
            {f'<img src="{meme["thumbnail"]}" style="width:300px; margin-top:10px; border-radius:8px;">' if 'thumbnail' in meme and meme['thumbnail'] else ''}
        </div>
        """
    
    cards_html += '</div>'
    st.markdown(cards_html, unsafe_allow_html=True)

def main():
    # 헤더
    st.markdown('<h1 class="main-title">✨ 밈 판독기 ✨</h1>', unsafe_allow_html=True)
    st.markdown("""
    > 💡 밈을 모르는 당신을 위한 밈 해석기! 문장을 입력하면 관련된 밈을 찾아드립니다.
    """)

    # Google Sheets 클라이언트 설정
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
    tab1, tab2 = st.tabs(["🔍 밈 분석하기", "✏️ 밈 등록하기"])

    with tab1:
        col1, col2 = st.columns([3, 1])
        with col1:
            input_text = st.text_area(
                "분석할 문장을 입력하세요:",
                placeholder="예: 어쩔티비, 뇌절, 갈비탕 500원...",
                height=100
            )
        with col2:
            st.write("")
            st.write("")
            analyze_button = st.button("🔍 밈 분석", use_container_width=True, key="analyze")
        
        if analyze_button:
            if input_text:
                with st.spinner('🔄 밈을 찾고 있습니다...'):
                    found_memes = find_matching_memes(input_text, data)
                    if found_memes:
                        st.success(f"🎉 총 {len(found_memes)}개의 밈을 찾았습니다!")
                        display_meme_cards(found_memes)
                    else:
                        st.warning("😅 관련된 밈을 찾지 못했습니다.")
            else:
                st.warning("✍️ 문장을 입력해주세요!")

    with tab2:
        st.markdown("""
        <div style='background-color: #f8f9fa; padding: 1rem; border-radius: 10px; margin-bottom: 1rem;'>
            <h4>🌟 새로운 밈 등록하기</h4>
            <p style='color: #666;'>밈 데이터베이스를 함께 만들어가요! 새로운 밈을 등록해주세요.</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("meme_registration_form", clear_on_submit=True):
            meme_text = st.text_input(
                "🏷️ 밈 텍스트:", 
                placeholder="예: 어쩔티비"
            )
            output_text = st.text_area(
                "📝 설명:", 
                placeholder="이 밈의 의미와 사용법을 설명해주세요",
                height=100
            )
            url = st.text_input(
                "🔗 참고 URL:", 
                placeholder="유튜브 영상이나 관련 웹페이지 URL"
            )
            
            col1, col2, col3 = st.columns([1,1,1])
            with col2:
                submit_button = st.form_submit_button(
                    "✨ 밈 등록하기",
                    use_container_width=True
                )
                    
        if submit_button:
            if all([meme_text, output_text]):  # URL은 선택적으로 변경
                try:
                    # List 시트 가져오기
                    list_worksheet = sheet.worksheet('List')
                    
                    # 데이터 추가
                    list_worksheet.append_row([
                        meme_text, 
                        output_text, 
                        url, 
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ])
                    st.success("✅ 등록해주셔서 감사합니다. 검토 후에 추가됩니다!")
                    st.balloons()
                except Exception as e:
                    st.error(f"😢 밈 등록 중 오류가 발생했습니다: {str(e)}")
            else:
                st.warning("⚠️ 밈 텍스트와 설명은 필수입니다!")

if __name__ == "__main__":
    main()