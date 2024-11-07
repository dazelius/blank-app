import streamlit as st
import pandas as pd
import json
import time
from datetime import datetime
import io
import os
import base64
from openai import OpenAI
import traceback
from difflib import SequenceMatcher
from konlpy.tag import Okt
import numpy as np

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
    div[data-baseweb="notification"] {
        display: none;
    }
    </style>
""", unsafe_allow_html=True)

class KoreanTextSimilarity:
    def __init__(self):
        self.okt = Okt()
        
    def preprocess_text(self, text):
        """텍스트 전처리: 형태소 분석 및 정규화"""
        # 형태소 분석
        morphs = self.okt.morphs(text, stem=True)
        # 공백 제거 및 소문자 변환
        normalized = [m.strip().lower() for m in morphs if m.strip()]
        return normalized
    
    def calculate_similarity(self, text1, text2):
        """한국어 텍스트 유사도 계산"""
        # 기본 문자열 유사도
        base_similarity = SequenceMatcher(None, text1, text2).ratio()
        
        # 형태소 기반 유사도
        processed1 = self.preprocess_text(text1)
        processed2 = self.preprocess_text(text2)
        
        # 공통 형태소 비율 계산
        common_morphs = set(processed1) & set(processed2)
        total_morphs = set(processed1) | set(processed2)
        morph_similarity = len(common_morphs) / len(total_morphs) if total_morphs else 0
        
        # 형태소 시퀀스 유사도
        seq_similarity = SequenceMatcher(None, ' '.join(processed1), ' '.join(processed2)).ratio()
        
        # 최종 유사도 점수 계산 (가중치 적용)
        final_similarity = (base_similarity * 0.3 + 
                          morph_similarity * 0.4 + 
                          seq_similarity * 0.3)
        
        return final_similarity * 100  # 백분율로 변환
    
    def check_similarity_threshold(self, text1, text2, threshold=50):
        """임계값 기반 유사도 검사"""
        similarity = self.calculate_similarity(text1, text2)
        return similarity >= threshold, similarity

def filter_similar_texts(search_text, text_list, threshold=50):
    """유사한 텍스트 필터링"""
    similarity_checker = KoreanTextSimilarity()
    similar_texts = []
    
    for text in text_list:
        is_similar, similarity = similarity_checker.check_similarity_threshold(
            search_text, text, threshold
        )
        if is_similar:
            similar_texts.append({
                'text': text,
                'similarity': similarity
            })
    
    # 유사도 순으로 정렬
    similar_texts.sort(key=lambda x: x['similarity'], reverse=True)
    return similar_texts

def init_session_state():
    """세션 상태 초기화"""
    if 'api_key' not in st.session_state:
        try:
            # secrets.toml 파일에서 API 키 읽기 시도
            st.session_state.api_key = st.secrets.get("OPENAI_API_KEY", "")
        except Exception as e:
            # 환경 변수에서 API 키 읽기 시도
            st.session_state.api_key = os.getenv("OPENAI_API_KEY", "")
            
        # API 키 검증
        if not st.session_state.api_key:
            st.error("⚠️ OpenAI API 키가 설정되지 않았습니다.")
            st.info("""
            💡 다음 두 가지 방법 중 하나로 API 키를 설정해주세요:
            1. `.streamlit/secrets.toml` 파일에 추가:
               ```toml
               OPENAI_API_KEY = "your-api-key-here"
               ```
            2. 환경 변수로 설정:
               ```bash
               export OPENAI_API_KEY="your-api-key-here"
               ```
            """)
            st.stop()

def handle_error(func):
    """에러 처리 데코레이터"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_details = traceback.format_exc()
            print(f"Error in {func.__name__}: {error_details}")
            return [f"번역 중 오류 발생"] * len(args[0]) if args else None
    return wrapper

@handle_error
def translate_batch(texts, target_language, client):
    """배치 번역 함수"""
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
        },
        'pt_BR': {
            'name': 'Português',
            'rules': [
                'Use Brazilian Portuguese conventions',
                'Follow gaming industry standard terms in Portuguese',
                'Maintain consistent formality level'
            ]
        },
        'es_ES': {
            'name': 'Español',
            'rules': [
                'Use neutral Spanish terms when possible',
                'Follow gaming industry standard terms in Spanish',
                'Maintain consistent formality level'
            ]
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
5. 문화적 맥락을 고려하세요
{' '.join(context.get('rules', []))}

번역할 텍스트 목록:
{json.dumps(texts, ensure_ascii=False)}

JSON 배열 형식으로만 응답하세요.
"""

    for attempt in range(3):  # 최대 3번 재시도
        try:
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
            
            # JSON 형식 추출 및 검증
            start_idx = content.find('[')
            end_idx = content.rfind(']') + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("JSON 형식이 올바르지 않습니다")
                
            json_content = content[start_idx:end_idx]
            translations = json.loads(json_content)
            
            if len(translations) != len(texts):
                raise ValueError(f"번역 결과 수가 일치하지 않습니다: 입력 {len(texts)}개, 출력 {len(translations)}개")
                
            return translations
            
        except Exception as e:
            if attempt == 2:  # 마지막 시도에서 실패
                print(f"Translation error after 3 attempts: {str(e)}")
                return [f"번역 실패: {str(e)}"] * len(texts)
            time.sleep(2)  # 재시도 전 대기

@handle_error
def process_excel(df, text_column, progress_bar, status_text):
    """엑셀 파일 처리"""
    try:
        client = OpenAI(api_key=st.session_state.api_key)
        
        # 결과 데이터프레임 초기화
        result_df = pd.DataFrame(index=df.index)
        result_df['원문'] = df[text_column]
        
        # 빈 값 처리
        df[text_column] = df[text_column].fillna('')
        
        # 번역할 텍스트 준비 (인덱스 유지)
        texts_with_index = [(idx, text) for idx, text in enumerate(df[text_column]) if text.strip()]
        if not texts_with_index:
            st.warning("번역할 텍스트가 없습니다.")
            return df
            
        indices, texts = zip(*texts_with_index)
        
        total_texts = len(texts)
        batch_size = 20
        
        # 번역 언어 설정
        languages = {
            'English': 'en_US',
            'Japanese': 'ja_JP',
            'Chinese(Simplified)': 'zh_CN',
            'Chinese(Traditional)': 'zh_TW',
            'Portuguese': 'pt_BR',
            'Spanish': 'es_ES'
        }

        for i, (lang_name, lang_code) in enumerate(languages.items()):
            translations_dict = {}
            
            for j in range(0, total_texts, batch_size):
                batch_texts = list(texts[j:j+batch_size])
                batch_indices = list(indices[j:j+batch_size])
                
                # 진행률 계산
                progress = (j + (i * total_texts)) / (total_texts * len(languages))
                progress_bar.progress(min(0.99, progress))  # 1.0에서 오류 방지
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
        
    except Exception as e:
        st.error(f"처리 중 오류가 발생했습니다: {str(e)}")
        return None

def get_table_download_link(df):
    """다운로드 링크 생성"""
    try:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        excel_data = output.getvalue()
        b64 = base64.b64encode(excel_data).decode()
        filename = f"translated_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">📥 번역 결과 다운로드</a>'
    except Exception as e:
        st.error(f"파일 생성 중 오류가 발생했습니다: {str(e)}")
        return None

def find_text_column(df):
    """텍스트 열 찾기"""
    for col in df.columns:
        if 'text' in str(col).lower():
            return col
    
    for col in df.columns:
        if any('\u3131' <= c <= '\u318F' or '\uAC00' <= c <= '\uD7A3' for c in str(col)):
            return col
    
    return df.columns[0]

def main():
    st.title("🌐 Excel 다국어 번역기")
    
    # 세션 상태 초기화
    init_session_state()
    
    # 사이드바 설정
    with st.sidebar:
        st.subheader("📋 사용 방법")
        st.markdown("""
        1. Excel 파일을 업로드하세요
        2. 번역할 열이 자동으로 선택됩니다
        3. 번역 시작 버튼을 클릭하세요
        
        ### 🌍 지원 언어
        - English (en_US)
        - Japanese (ja_JP)
        - Chinese Simplified (zh_CN)
        - Chinese Traditional (zh_TW)
        - Portuguese (pt_BR)
        - Spanish (es_ES)
        """)
    
    # 메인 영역
    uploaded_file = st.file_uploader(
        "Excel 파일을 업로드하세요 (.xlsx)",
        type=['xlsx']
    )
    
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            text_column = find_text_column(df)
            st.info(f"'{text_column}' 열이 번역 대상으로 선택되었습니다.")
            
            # 검색 기능 추가
            search_text = st.text_input("텍스트 검색 (유사도 기반)")
            if search_text:
                texts = df[text_column].dropna().tolist()
                similar_texts = filter_similar_texts(search_text, texts)
                
                if similar_texts:
                    st.subheader("유사한 텍스트")
                    for item in similar_texts:
                        st.write(f"- {item['text']} (유사도: {item['similarity']:.2f}%)")
                else:
                    st.info("유사한 텍스트를 찾지 못했습니다.")
            
            if st.button("번역 시작"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                with st.spinner('번역 처리 중...'):
                    result_df = process_excel(
                        df, text_column, progress_bar, status_text
                    )
                    
                    if result_df is not None:
                        st.success("✅ 번역이 완료되었습니다!")
                        
                        # 결과 표시
                        st.subheader("번역 결과")
                        st.dataframe(result_df, height=400)
                        
                        # 다운로드 링크
                        download_link = get_table_download_link(result_df)
                        if download_link:
                            st.markdown(download_link, unsafe_allow_html=True)
                        
                        # 통계
                        st.subheader("📊 번역 통계")
                        col1, col2 = st.columns(2)
                        with col1:
                            total_items = len([x for x in result_df['원문'] if str(x).strip()])
                            st.metric("번역된 항목", total_items)
                        with col2:
                            st.metric("지원 언어", "6개")
                    
        except Exception as e:
            st.error(f"파일 처리 중 오류가 발생했습니다: {str(e)}")
            
    else:
        st.info("👆 Excel 파일을 업로드해주세요.")

if __name__ == "__main__":
    main()