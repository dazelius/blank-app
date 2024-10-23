import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import difflib

# 구글 스프레드시트 인증
def authenticate_google_sheets(json_file, scope):
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(json_file, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"구글 스프레드시트 인증 오류: {e}")
        return None

# 스프레드시트에서 데이터 가져오기
def get_meme_data(sheet_url):
    try:
        sheet = client.open_by_url(sheet_url)
        worksheet = sheet.get_worksheet(0)
        return worksheet.get_all_records()
    except Exception as e:
        st.error(f"스프레드시트 데이터 가져오기 오류: {e}")
        return []

# 유사도 측정 함수
def find_best_matches(input_text, meme_texts, threshold=0.6):
    matches = []
    for meme_text in meme_texts:
        score = difflib.SequenceMatcher(None, input_text, meme_text).ratio()
        if score >= threshold:
            matches.append((meme_text, score))
    return matches

# 유튜브 썸네일 URL 추출
def get_youtube_thumbnail_url(url):
    video_id_match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    if video_id_match:
        video_id = video_id_match.group(1)
        return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
    return None

# Streamlit 앱 인터페이스 설정
st.set_page_config(page_title="밈 판독기", layout="wide")  
st.title("✨ 밈 판독기 ✨")
st.write("밈을 모르는 아재를 위한")

# 사이드바에 버튼 추가
st.sidebar.header("기능")
sidebar_option = st.sidebar.radio("선택하세요:", ["밈 분석하기", "밈 등록하기"])

# 구글 스프레드시트 인증 정보
scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
json_file_path = '/mount/src/blank-app/stellar-sunrise-439504-s3-40bbedb33c97.json'
client = authenticate_google_sheets(json_file_path, scope)

if client:
    # 스프레드시트에서 밈 데이터 가져오기
    data = get_meme_data('https://docs.google.com/spreadsheets/d/1wPchxwAssBf706VuvxhGp4ESt3vj-N9RLcMaUF075ug/edit?gid=137455637#gid=137455637')

    if sidebar_option == "밈 분석하기":
        st.subheader("문장 분석하기")
        input_text = st.text_area("문장을 입력하세요:", "")
        
        if st.button("밈 분석"):
            if input_text:
                found_memes = []
                meme_texts = [record['text'] for record in data]
                
                # 유사한 밈 찾기
                matched_memes = set()
                for meme_text in meme_texts:
                    if difflib.SequenceMatcher(None, input_text, meme_text).ratio() >= 0.6:
                        matched_memes.add(meme_text)

                # 일치하는 밈 정보 저장
                for meme_text in matched_memes:
                    for record in data:
                        if record['text'] == meme_text:
                            meme_info = {
                                'meme': record['text'],
                                'output': record['output'],
                                'url': record['url'],
                                'thumbnail': get_youtube_thumbnail_url(record['url']) if "youtube.com" in record['url'] else None
                            }
                            found_memes.append(meme_info)

                if found_memes:
                    st.subheader("탐지된 밈:")
                    for meme in found_memes:
                        meme_link = f"[**{meme['meme']}**]({meme['url']})"
                        st.markdown(f"{meme_link} - {meme['output']}")
                        if meme['thumbnail']:
                            st.image(meme['thumbnail'], width=300)
                else:
                    st.write("밈을 찾지 못했습니다.")
            else:
                st.warning("문장을 입력하세요.")

    elif sidebar_option == "밈 등록하기":
        st.subheader("밈 등록하기")
        meme_text = st.text_input("밈 텍스트 (text):")
        output_text = st.text_input("출력 텍스트 (output):")
        url = st.text_input("URL:")
        
        if st.button("등록"):
            if meme_text and output_text and url:
                new_meme = {
                    'text': meme_text,
                    'output': output_text,
                    'url': url
                }
                try:
                    worksheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1wPchxwAssBf706VuvxhGp4ESt3vj-N9RLcMaUF075ug/edit?gid=137455637#gid=137455637').get_worksheet(0)
                    worksheet.append_row([new_meme['text'], new_meme['output'], new_meme['url']])
                    st.success("밈이 성공적으로 등록되었습니다.")
                except Exception as e:
                    st.error(f"밈 등록 오류: {e}")
            else:
                st.warning("모든 필드를 입력해야 합니다.")
