import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import difflib
import requests  # 썸네일 가져오기 위해 추가
import os
import json

# 구글 스프레드시트 인증
scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']

# 환경 변수에서 JSON 문자열을 읽고 파싱
creds_json = os.getenv('GOOGLE_SHEET_CREDENTIALS')
creds_dict = json.loads(creds_json)

creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# 스프레드시트 열기
sheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1wPchxwAssBf706VuvxhGp4ESt3vj-N9RLcMaUF075ug/edit?gid=137455637#gid=137455637')
worksheet = sheet.get_worksheet(0)

# 스프레드시트에서 밈 데이터를 가져오기
data = worksheet.get_all_records()

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
        thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
        return thumbnail_url
    return None

# Streamlit 앱 인터페이스
st.set_page_config(page_title="밈 판독기", layout="wide")  # 페이지 설정

st.title("✨ 밈 판독기 ✨")
st.write("밈을 모르는 아재를 위한 판독기입니다.")

# 사이드바에 버튼 추가
st.sidebar.header("기능")
sidebar_option = st.sidebar.radio("선택하세요:", ["밈 분석하기", "밈 등록하기"])

if sidebar_option == "밈 분석하기":
    st.subheader("문장 분석하기")
    input_text = st.text_area("문장을 입력하세요:", "")
    
    if st.button("밈 분석"):
        if input_text:
            found_memes = []
            meme_texts = [record['text'] for record in data]
            
            # 입력된 문장을 단어 단위로 분리
            input_words = input_text.split()
            matched_memes = set()  # 중복된 밈을 방지하기 위해 집합 사용
            
            # 모든 밈 텍스트에 대해 확인
            for meme_text in meme_texts:
                for word in input_words:
                    score = difflib.SequenceMatcher(None, word, meme_text).ratio()
                    if score >= 0.6:
                        matched_memes.add(meme_text)  # 중복을 방지하기 위해 set에 추가
            
            # 일치하는 밈 정보 저장
            for meme_text in matched_memes:
                for record in data:
                    if record['text'] == meme_text:
                        meme_info = {
                            'meme': record['text'],
                            'output': record['output'],
                            'url': record['url']
                        }
                        # 유튜브 링크라면 썸네일 URL 추가
                        if "youtube.com" in record['url']:
                            meme_info['thumbnail'] = get_youtube_thumbnail_url(record['url'])
                        found_memes.append(meme_info)

            if found_memes:
                st.subheader("탐지된 밈:")
                for meme in found_memes:
                    # 밈 텍스트를 밑줄 긋고 볼드체로 표시, 클릭 시 URL로 연결
                    meme_link = f"[**{meme['meme']}**]({meme['url']})"
                    st.markdown(f"{meme_link} - {meme['output']}")
                    
                    # 썸네일 이미지 표시
                    if 'thumbnail' in meme:
                        st.image(meme['thumbnail'], width=300)
            else:
                st.write("밈을 찾지 못했습니다.")
        else:
            st.write("문장을 입력하세요.")

elif sidebar_option == "밈 등록하기":
    st.subheader("밈 등록하기")
    meme_text = st.text_input("밈 텍스트 (text):")
    output_text = st.text_input("출력 텍스트 (output):")
    url = st.text_input("URL:")
    
    if st.button("등록"):
        if meme_text and output_text and url:
            # 새 밈 정보 추가
            new_meme = {
                'text': meme_text,
                'output': output_text,
                'url': url
            }
            # 스프레드시트에 새 밈 추가
            worksheet.append_row([new_meme['text'], new_meme['output'], new_meme['url']])
            st.success("밈이 성공적으로 등록되었습니다.")
        else:
            st.warning("모든 필드를 입력해야 합니다.")
