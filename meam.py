import streamlit as st
import gspread
from google.oauth2 import service_account
import re
import difflib
from datetime import datetime

# ... (이전 인증 및 설정 코드는 동일) ...

def display_meme_card(meme):
    """밈 정보를 카드 형태로 표시"""
    st.markdown(f"""
    <div class="meme-card">
        <h3>💭 {meme['meme']}</h3>
        <p>📝 {meme['output']}</p>
        {'<a href="' + meme['url'] + '" target="_blank">🔗 원본 보기</a>' if meme['url'] and meme['url'].strip() else '<span class="no-link">🔗 관련 링크 없음</span>'}
    </div>
    """, unsafe_allow_html=True)
    
    if 'thumbnail' in meme and meme['thumbnail']:
        st.image(meme['thumbnail'], width=200)

def main():
    # CSS 스타일 추가
    st.markdown("""
    <style>
    /* 기존 스타일 유지 */
    .horizontal-scroll {
        display: flex;
        overflow-x: auto;
        padding: 1rem 0;
        gap: 1rem;
        margin-bottom: 2rem;
    }
    .meme-card {
        min-width: 300px;
        max-width: 300px;
        padding: 1rem;
        background: white;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-right: 1rem;
        flex: 0 0 auto;
    }
    .no-link {
        color: #666;
        font-style: italic;
    }
    /* 스크롤바 스타일링 */
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
    </style>
    """, unsafe_allow_html=True)

    # 헤더
    st.markdown('<h1 class="main-title">✨ 밈 판독기 ✨</h1>', unsafe_allow_html=True)
    
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
            analyze_button = st.button("🔍 밈 분석", use_container_width=True)

        if analyze_button and input_text:
            with st.spinner('🔄 밈을 찾고 있습니다...'):
                found_memes = find_matching_memes(input_text, data)
                
                if found_memes:
                    st.success(f"🎉 총 {len(found_memes)}개의 밈을 찾았습니다!")
                    # 수평 스크롤 컨테이너 시작
                    st.markdown('<div class="horizontal-scroll">', unsafe_allow_html=True)
                    for meme in found_memes:
                        display_meme_card(meme)
                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.warning("😅 관련된 밈을 찾지 못했습니다.")
        elif analyze_button:
            st.warning("✍️ 문장을 입력해주세요!")

    # 밈 등록 탭 (이전과 동일)
    with tab2:
        # ... (이전 코드와 동일) ...

if __name__ == "__main__":
    main()