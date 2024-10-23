import streamlit as st
import gspread
from google.oauth2 import service_account
import re
import difflib
import json
from datetime import datetime

# 페이지 설정
st.set_page_config(
    page_title="밈 판독기",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS 스타일 추가
st.markdown("""
<style>
    .main-title {
        text-align: center;
        padding: 1rem;
        background: linear-gradient(45deg, #FF6B6B, #4ECDC4);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
        background-color: #4ECDC4;
        color: white;
    }
    .meme-card {
        padding: 1rem;
        background-color: #f8f9fa;
        border-radius: 10px;
        margin-bottom: 1rem;
        border: 1px solid #dee2e6;
    }
    .success-msg {
        padding: 1rem;
        background-color: #d4edda;
        color: #155724;
        border-radius: 5px;
        margin-bottom: 1rem;
    }
    .error-msg {
        padding: 1rem;
        background-color: #f8d7da;
        color: #721c24;
        border-radius: 5px;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

def setup_google_auth():
    """Google Sheets API 인증 설정"""
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
    
    try:
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
            'url': record['url'],
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        if "youtube.com" in record['url']:
            meme_info['thumbnail'] = get_youtube_thumbnail_url(record['url'])
        found_memes.append(meme_info)
    
    return found_memes

def display_meme_card(meme):
    """밈 정보를 카드 형태로 표시"""
    with st.container():
        st.markdown(f"""
        <div class="meme-card">
            <h3>{meme['meme']}</h3>
            <p>{meme['output']}</p>
            <a href="{meme['url']}" target="_blank">원본 보기 🔗</a>
        </div>
        """, unsafe_allow_html=True)
        
        if 'thumbnail' in meme:
            st.image(meme['thumbnail'], width=300, use_column_width=True)

def main():
    # 헤더
    st.markdown('<h1 class="main-title">✨ 밈 판독기 ✨</h1>', unsafe_allow_html=True)
    st.markdown("""
    > 밈을 모르는 당신을 위한 밈 해석기! 문장을 입력하면 관련된 밈을 찾아드립니다.
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
    tab1, tab2 = st.tabs(["📝 밈 분석하기", "➕ 밈 등록하기"])

    with tab1:
        col1, col2 = st.columns([3, 1])
        with col1:
            input_text = st.text_area(
                "분석할 문장을 입력하세요:",
                placeholder="예: 어쩔티비",
                height=100
            )
        with col2:
            st.write("")
            st.write("")
            if st.button("🔍 밈 분석", use_container_width=True):
                if input_text:
                    with st.spinner('밈을 찾고 있습니다...'):
                        found_memes = find_matching_memes(input_text, data)
                        
                        if found_memes:
                            st.success(f"총 {len(found_memes)}개의 밈을 찾았습니다!")
                            for meme in found_memes:
                                display_meme_card(meme)
                        else:
                            st.warning("😅 관련된 밈을 찾지 못했습니다.")
                else:
                    st.warning("문장을 입력해주세요!")

    with tab2:
        with st.form("meme_registration_form"):
            st.subheader("새로운 밈 등록하기")
            meme_text = st.text_input("밈 텍스트:", placeholder="예: 어쩔티비")
            output_text = st.text_input("설명:", placeholder="어쩔티비의 의미와 사용법을 설명해주세요")
            url = st.text_input("참고 URL:", placeholder="유튜브 영상이나 관련 웹페이지 URL")
            
            submit_button = st.form_submit_button("✨ 밈 등록하기")
            
            if submit_button:
                if all([meme_text, output_text, url]):
                    try:
                        worksheet.append_row([
                            meme_text, 
                            output_text, 
                            url, 
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        ])
                        st.success("✅ 밈이 성공적으로 등록되었습니다!")
                        st.balloons()
                    except Exception as e:
                        st.error(f"밈 등록 중 오류가 발생했습니다: {str(e)}")
                else:
                    st.warning("모든 필드를 입력해주세요!")

if __name__ == "__main__":
    main()