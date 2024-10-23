import streamlit as st
import pandas as pd
import json
import time
from datetime import datetime
import io
import base64
from openai import OpenAI

# 페이지 설정
st.set_page_config(
    page_title="Excel 다국어 번역기",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 스타일 적용
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        height: 50px;
        margin-top: 20px;
    }
    .reportview-container {
        background-color: #f0f2f6;
    }
    .css-1d391kg {
        padding: 1rem;
    }
    .stProgress > div > div > div > div {
        background-color: #00cc00;
    }
    </style>
""", unsafe_allow_html=True)

# API 키 초기화
if 'api_key' not in st.session_state:
    st.session_state.api_key = ""  # 빈 문자열로 초기화

def translate_batch(texts, target_language, client):
    """배치 번역 함수"""
    try:
        language_contexts = {
            'en_US': {
                'name': 'English',
                'rules': ['Keep UI terms consistent', 'Use gaming industry standard terms']
            },
            'ja_JP': {
                'name': '日本語',
                'rules': ['Use proper gaming terminology', 'Maintain correct keigo level']
            },
            'zh_CN': {
                'name': '简体中文',
                'rules': ['Use simplified Chinese characters', 'Follow mainland China gaming terms']
            },
            'zh_TW': {
                'name': '繁體中文',
                'rules': ['Use traditional Chinese characters', 'Follow Taiwan gaming terms']
            }
        }

        context = language_contexts.get(target_language, {})
        
        prompt = f"""
당신은 전문 게임 현지화 번역가입니다. 다음 텍스트들을 {context.get('name', target_language)}로 번역해주세요.

번역 규칙:
1. 게임 UI/UX 용어의 일관성을 엄격히 유지하세요
2. 원문의 의미를 정확하게 유지하세요
3. 게임 산업 표준 용어를 사용하세요
4. 각 문장을 독립적으로 번역하세요
5. 줄바꿈과 특수문자를 유지하세요
{' '.join(context.get('rules', []))}

번역할 텍스트 목록:
{json.dumps(texts, ensure_ascii=False)}

JSON 배열 형식으로만 응답하세요.
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert game localization translator."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
            temperature=0.3
        )

        content = response.choices[0].message.content.strip()
        
        try:
            # JSON 형식 추출
            start_idx = content.find('[')
            end_idx = content.rfind(']') + 1
            json_content = content[start_idx:end_idx]
            translations = json.loads(json_content)
            
            if len(translations) != len(texts):
                raise ValueError(f"번역 결과 수가 일치하지 않습니다: 입력 {len(texts)}개, 출력 {len(translations)}개")
                
            return translations
        except json.JSONDecodeError:
            return [f"JSON 파싱 오류: {content[:100]}..."] * len(texts)
            
    except Exception as e:
        print(f"Translation error: {str(e)}")
        return [f"Error: {str(e)}"] * len(texts)

def process_excel(df, text_column, progress_bar, status_text):
    """엑셀 파일 처리"""
    client = OpenAI(api_key=st.session_state.api_key)
    
    # 결과 데이터프레임 초기화
    result_df = pd.DataFrame(index=df.index)
    result_df['원문'] = df[text_column]
    
    # 빈 값 처리
    df[text_column] = df[text_column].fillna('')
    
    # 번역할 텍스트 준비 (인덱스 유지)
    texts_with_index = [(idx, text) for idx, text in enumerate(df[text_column]) if text.strip()]
    indices, texts = zip(*texts_with_index) if texts_with_index else ([], [])
    
    total_texts = len(texts)
    batch_size = 20
    
    # 번역 언어 설정
    languages = {
        'English': 'en_US',
        'Japanese': 'ja_JP',
        'Chinese(Simplified)': 'zh_CN',
        'Chinese(Traditional)': 'zh_TW'
    }

    # 각 언어별 번역
    for i, (lang_name, lang_code) in enumerate(languages.items()):
        translations_dict = {}
        
        for j in range(0, total_texts, batch_size):
            batch_texts = list(texts[j:j+batch_size])
            batch_indices = list(indices[j:j+batch_size])
            
            # 진행률 계산
            progress = (j + (i * total_texts)) / (total_texts * len(languages))
            progress_bar.progress(min(1.0, progress))
            status_text.text(f"번역 중: {lang_name} - {j}/{total_texts}")
            
            # 배치 번역
            batch_translations = translate_batch(batch_texts, lang_code, client)
            
            # 인덱스와 번역 결과 매핑
            for idx, trans in zip(batch_indices, batch_translations):
                translations_dict[idx] = trans
            
            time.sleep(0.5)  # API 레이트 리밋 방지
        
        # 전체 데이터프레임 크기에 맞게 번역 결과 배열 생성
        translations_array = [""] * len(df)
        for idx, trans in translations_dict.items():
            translations_array[idx] = trans
        
        result_df[lang_name] = translations_array
    
    progress_bar.progress(1.0)
    return result_df

def get_table_download_link(df):
    """다운로드 링크 생성"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    excel_data = output.getvalue()
    b64 = base64.b64encode(excel_data).decode()
    filename = f"translated_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">📥 번역 결과 다운로드</a>'

def find_text_column(df):
    """텍스트 열 찾기"""
    # 우선순위: Text > 한글 열 > 첫 번째 열
    for col in df.columns:
        if 'text' in str(col).lower():
            return col
    
    for col in df.columns:
        # 한글이 포함된 열 찾기
        if any('\u3131' <= c <= '\u318F' or '\uAC00' <= c <= '\uD7A3' for c in str(col)):
            return col
    
    return df.columns[0]

def main():
    st.title("🌐 Excel 다국어 번역기")
    
    # 사이드바 설정
    with st.sidebar:
        st.subheader("⚙️ 설정")
        api_key = st.text_input("OpenAI API Key", value=st.session_state.api_key, type="password")
        st.session_state.api_key = api_key
        
        st.markdown("""
        ### 📝 사용 방법
        1. Excel 파일을 업로드하세요
        2. 번역할 열이 자동으로 선택됩니다
        3. 번역 시작 버튼을 클릭하세요
        
        ### 🌍 지원 언어
        - English (en_US)
        - Japanese (ja_JP)
        - Chinese Simplified (zh_CN)
        - Chinese Traditional (zh_TW)
        """)
    
    # 메인 영역
    uploaded_file = st.file_uploader(
        "Excel 파일을 업로드하세요 (.xlsx)",
        type=['xlsx']
    )
    
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
        text_column = find_text_column(df)
        st.info(f"'{text_column}' 열이 번역 대상으로 선택되었습니다.")
        
        if st.button("번역 시작"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            with st.spinner('번역 처리 중...'):
                result_df = process_excel(
                    df, text_column, progress_bar, status_text
                )
                
                st.success("✅ 번역이 완료되었습니다!")
                
                # 결과 표시
                st.subheader("번역 결과")
                st.dataframe(result_df, height=400)
                st.markdown(get_table_download_link(result_df), unsafe_allow_html=True)
                
                # 통계
                st.subheader("📊 번역 통계")
                col1, col2 = st.columns(2)
                with col1:
                    total_items = len([x for x in result_df['원문'] if str(x).strip()])
                    st.metric("번역된 항목", total_items)
                with col2:
                    st.metric("지원 언어", "4개")
    else:
        st.info("👆 Excel 파일을 업로드해주세요.")

if __name__ == "__main__":
    main()