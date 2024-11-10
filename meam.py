import streamlit as st
import gspread
from google.oauth2 import service_account
import re
import difflib
import json
from datetime import datetime
import os
import pandas as pd
import html
import requests
from PIL import Image
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
import gc

# 전역 캐시 설정
spelling_cache = {}

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

# CSS 스타일링 (기존 CSS 코드는 유지)
st.markdown("""
<style>
    /* 기존 CSS 스타일 ... */
</style>
""", unsafe_allow_html=True)

def check_spelling(text):
    """자체 구현 맞춤법 검사 함수 - 캐시 적용"""
    try:
        # 캐시 키 생성
        cache_key = hash(text)
        if cache_key in spelling_cache:
            return spelling_cache[cache_key]
            
        # 자주 발생하는 맞춤법 오류 사전
        corrections = {
            # 기존 맞춤법 규칙 유지
        }
        
        # 초기 텍스트
        corrected_text = text
        error_count = 0
        corrections_made = []
        
        # 각 교정 규칙 적용
        for wrong, right in corrections.items():
            if wrong in corrected_text:
                count = corrected_text.count(wrong)
                if count > 0:
                    error_count += count
                    corrections_made.append((wrong, right, count))
                corrected_text = corrected_text.replace(wrong, right)
        
        result = {
            'checked': corrected_text,
            'errors': error_count,
            'corrections': corrections_made,
            'original': text
        }
        
        # 결과 캐싱
        spelling_cache[cache_key] = result
        return result
        
    except Exception as e:
        st.error(f"맞춤법 검사 중 오류 발생: {str(e)}")
        return None

def analyze_text_batch(texts, batch_idx, total_batches, source_file, column, data, spell_check_enabled=True):
    """텍스트 배치 고속 분석 - 최적화 버전"""
    batch_results = []
    
    # 텍스트 전처리를 한 번에 수행
    processed_texts = [str(text) if text is not None else "" for text in texts]
    
    # 맞춤법 검사를 배치로 처리 (활성화된 경우)
    spelling_results = {}
    if spell_check_enabled:
        for idx, text in enumerate(processed_texts):
            if text.strip():
                # 캐시 키 생성
                cache_key = hash(text)
                if cache_key not in spelling_cache:
                    spelling_cache[cache_key] = check_spelling(text)
                spelling_results[idx] = spelling_cache[cache_key]
    
    # 패턴 매칭을 배치로 처리
    for idx, text in enumerate(processed_texts):
        if not text.strip():
            continue
            
        # 패턴 매칭 수행
        found_patterns = find_matching_patterns(text, data)
        
        # 결과 저장
        for pattern in found_patterns:
            result = {
                'text': text,
                'pattern': pattern['pattern'],
                'analysis': pattern['analysis'],
                'danger_level': pattern['danger_level'],
                'url': pattern.get('url', ''),
                'match_score': pattern['match_score'],
                'source_file': source_file,
                'column': column
            }
            
            # 맞춤법 검사 결과 추가
            if idx in spelling_results and spelling_results[idx]['errors'] > 0:
                result['spelling_check'] = spelling_results[idx]
                
            batch_results.append(result)
    
    return batch_results

def process_batch_and_clear(batch_results):
    """배치 결과 처리 및 메모리 정리"""
    if batch_results:
        results = batch_results
        patterns_found = len(batch_results)
        
        # 메모리 정리
        gc.collect()
        
        return results, patterns_found
    return [], 0

def analyze_file_contents(file_content, data, spell_check_enabled=True, progress_bar=None, progress_text=None):
    """파일 내용 분석 - 최적화 버전"""
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
            def update_log(message, filename=""):
                prefix = f"[{filename}] " if filename else ""
                log_container.markdown(f"""
                    <div style="background-color: #2D2D2D; padding: 10px; border-radius: 5px; margin: 5px 0;">
                        {prefix}{message}
                    </div>
                """, unsafe_allow_html=True)

            # 파일 로드 최적화
            dfs = []
            filename = getattr(file_content, 'name', '알 수 없는 파일')
            update_log("📂 파일 로딩 및 패턴 최적화 중...", filename)
            
            # 파일 처리 로직 - 메모리 최적화
            if hasattr(file_content, 'name'):
                file_type = file_content.name.split('.')[-1].lower()
                chunk_size = 10000  # 청크 단위로 파일 읽기
                
                if file_type == 'csv':
                    for chunk in pd.read_csv(file_content, dtype=str, chunksize=chunk_size):
                        chunk['source_file'] = file_content.name
                        dfs.append(chunk)
                elif file_type in ['xlsx', 'xls']:
                    df = pd.read_excel(file_content, dtype=str)
                    df['source_file'] = file_content.name
                    dfs.append(df)
                elif file_type == 'zip':
                    with zipfile.ZipFile(file_content) as z:
                        for zip_filename in z.namelist():
                            if zip_filename.endswith(('.csv', '.xlsx', '.xls')):
                                with z.open(zip_filename) as f:
                                    if zip_filename.endswith('.csv'):
                                        for chunk in pd.read_csv(io.BytesIO(f.read()), dtype=str, chunksize=chunk_size):
                                            chunk['source_file'] = zip_filename
                                            dfs.append(chunk)
                                    else:
                                        df = pd.read_excel(io.BytesIO(f.read()), dtype=str)
                                        df['source_file'] = zip_filename
                                        dfs.append(df)

            if not dfs:
                update_log(f"⚠️ 지원하지 않는 파일 형식이거나 처리할 수 있는 파일이 없습니다.", filename)
                return None
                
            update_log(f"🔍 {len(dfs)}개의 파일을 로드했습니다.", filename)
            
            # 데이터프레임 처리 최적화
            df = pd.concat(dfs, ignore_index=True)
            del dfs  # 메모리 해제
            gc.collect()
            
            # 텍스트 컬럼 최적화
            text_columns = [col for col in df.select_dtypes(include=['object']).columns if col != 'source_file']
            
            update_log("🚀 초고속 분석 시작...", filename)

            total_patterns_found = 0
            all_results = []
            
            # 병렬 처리 설정
            batch_size = 10000
            max_workers = 4
            total_rows = df[text_columns].notna().sum().sum()
            processed_rows = 0
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                
                for col in text_columns:
                    texts = df[col].dropna().tolist()
                    source_files = df.loc[df[col].notna(), 'source_file'].tolist()
                    total_batches = (len(texts) + batch_size - 1) // batch_size
                    
                    for batch_idx in range(total_batches):
                        start_idx = batch_idx * batch_size
                        end_idx = min((batch_idx + 1) * batch_size, len(texts))
                        batch_texts = texts[start_idx:end_idx]
                        batch_sources = source_files[start_idx:end_idx]
                        
                        future = executor.submit(
                            analyze_text_batch,
                            batch_texts,
                            batch_idx,
                            total_batches,
                            batch_sources[0],
                            col,
                            data,
                            spell_check_enabled
                        )
                        futures.append((future, len(batch_texts)))
                
                # 결과 수집 및 진행률 업데이트
                for future, batch_length in futures:
                    results = future.result()
                    if results:
                        processed_results, patterns_found = process_batch_and_clear(results)
                        all_results.extend(processed_results)
                        total_patterns_found += patterns_found
                    
                    processed_rows += batch_length
                    if progress_bar is not None:
                        progress = min(processed_rows / total_rows, 1.0)
                        progress_bar.progress(progress)
                        
                    if processed_rows % (batch_size * 2) == 0:
                        elapsed_time = time.time() - start_time
                        speed = processed_rows / elapsed_time if elapsed_time > 0 else 0
                        update_log(f"""
                            📊 분석 진행 중:
                            - 처리 속도: {speed:.0f} 행/초
                            - 처리된 행: {processed_rows:,}/{total_rows:,}
                            - 발견된 패턴: {total_patterns_found:,}개
                        """, filename)
            
            # 최종 결과 정리
            if all_results:
                seen = set()
                unique_results = []
                for r in sorted(all_results, key=lambda x: (-x.get('match_score', 0), -x.get('danger_level', 0))):
                    key = (r['text'], r['pattern'], r['source_file'])
                    if key not in seen:
                        seen.add(key)
                        unique_results.append(r)
                
                total_time = time.time() - start_time
                update_log(f"""
                    ⚠️ 분석 완료:
                    - 처리 시간: {total_time:.1f}초
                    - 처리 속도: {total_rows/total_time:.0f} 행/초
                    - 총 처리된 행: {processed_rows:,}개
                    - 발견된 패턴: {total_patterns_found:,}개
                """, filename)
                
                # 메모리 정리
                gc.collect()
                
                return {
                    'total_patterns': len(unique_results),
                    'results': unique_results[:1000],
                    'filename': filename
                }
            else:
                update_log(f"✅ {filename}에서 발견된 패턴이 없습니다.")
                return None
            
        except Exception as e:
            st.error(f"'{filename}' 파일 분석 중 오류가 발생했습니다: {str(e)}")
            import traceback
            st.error(f"상세 오류: {traceback.format_exc()}")
            return None
            
    return None

# Google Sheets 관련 함수 최적화
@st.cache_data(ttl=300)
def load_sheet_data():
    """Google Sheets 데이터 로드 - 캐시 적용"""
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
        
        sheet = client.open_by_url(st.secrets["sheet_url"])
        worksheet = sheet.get_worksheet(0)
        data = worksheet.get_all_records()
        
        # 데이터 전처리
        for item in data:
            item['text'] = str(item.get('text', ''))
            item['output'] = str(item.get('output', ''))
            item['dangerlevel'] = int(item.get('dangerlevel', 0))
            
        return data
    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {str(e)}")
        return None

@st.cache_resource
def get_sheet_instance():
    """시트 인스턴스 가져오기 - 리소스 캐시 적용"""
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
        
        sheet = client.open_by_url(st.secrets["sheet_url"])
        return sheet.get_worksheet(0)
    except Exception as e:
        st.error(f"시트 연결 중 오류 발생: {str(e)}")
        return None

# 패턴 매칭 최적화 함수
@st.cache_data(ttl=3600)
def preprocess_patterns(data):
    """패턴 데이터 전처리 및 캐싱 - 최적화 버전"""
    if not data:
        st.error("데이터가 비어있습니다.")
        return {
            'short': [],
            'medium': [],
            'long': []
        }
    
    try:
        # 패턴 분류를 딕셔너리 컴프리헨션으로 최적화
        patterns = {
            'short': [],
            'medium': [],
            'long': []
        }
        
        for record in data:
            if not isinstance(record, dict) or 'text' not in record:
                continue
                
            pattern_text = str(record.get('text', '')).lower()
            if not pattern_text.strip():
                continue
                
            try:
                pattern_text_cleaned = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', pattern_text)
                pattern_words = {w for w in pattern_text_cleaned.split() if w.strip()}
                
                processed = {
                    'original': record,
                    'cleaned_text': pattern_text_cleaned,
                    'words': pattern_words,
                    'chars': set(pattern_text_cleaned),
                    'word_count': len(pattern_words),
                    'length': len(pattern_text_cleaned)
                }
                
                # 길이에 따른 분류
                if processed['length'] <= 10:
                    patterns['short'].append(processed)
                elif processed['length'] <= 30:
                    patterns['medium'].append(processed)
                else:
                    patterns['long'].append(processed)
                    
            except Exception as e:
                st.error(f"패턴 '{pattern_text}' 처리 중 오류 발생: {str(e)}")
                continue
        
        if not any(patterns.values()):
            st.warning("처리된 패턴이 없습니다. 데이터를 확인해주세요.")
        
        return patterns
        
    except Exception as e:
        st.error(f"데이터 전처리 중 오류 발생: {str(e)}")
        return {'short': [], 'medium': [], 'long': []}

def find_matching_patterns(input_text, data, threshold=0.7):
    """텍스트 패턴 매칭 - 최적화 버전"""
    if not data or not input_text:
        return []
        
    input_text = str(input_text).strip()
    if not input_text or input_text.isspace():
        return []
    
    try:
        # 전처리된 패턴 가져오기
        patterns = preprocess_patterns(data)
        
        # 입력 텍스트 전처리
        input_cleaned = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', input_text.lower())
        input_words = {w for w in input_cleaned.split() if w.strip()}
        input_chars = set(input_cleaned)
        
        # 결과 저장용 리스트
        matches = []
        
        # 각 패턴 길이별로 매칭
        for pattern_type in ['short', 'medium', 'long']:
            for pattern in patterns[pattern_type]:
                try:
                    # 빠른 필터링
                    if not (input_chars & pattern['chars']):
                        continue
                        
                    # 단어 기반 매칭
                    common_words = input_words & pattern['words']
                    if not common_words:
                        continue
                        
                    match_ratio = len(common_words) / pattern['word_count']
                    if match_ratio < threshold * 0.7:
                        continue
                    
                    # 최종 유사도 계산
                    similarity = difflib.SequenceMatcher(
                        None,
                        input_cleaned,
                        pattern['cleaned_text']
                    ).ratio()
                    
                    if similarity >= threshold:
                        record = pattern['original']
                        matches.append({
                            'pattern': record['text'],
                            'analysis': record.get('output', ''),
                            'danger_level': int(record.get('dangerlevel', 0)),
                            'url': record.get('url', ''),
                            'match_score': similarity,
                            'original_text': input_text
                        })
                        
                except Exception as e:
                    continue
        
        return sorted(matches, key=lambda x: (-x['match_score'], -x['danger_level']))
        
    except Exception as e:
        st.error(f"패턴 매칭 중 오류 발생: {str(e)}")
        return []
    
 def main():
    st.markdown('<h1 class="main-title">StringAnalysis</h1>', unsafe_allow_html=True)
    st.markdown("""
    > 💡 입력된 문장을 분석하고 점수화하여 보여드립니다.
    """)

    # 데이터 로드 및 검증
    try:
        with st.spinner('데이터를 불러오는 중...'):
            data = load_sheet_data()
            if not data:
                st.error("패턴 데이터를 불러올 수 없습니다. 구글 시트 연결을 확인해주세요.")
                return
                
            if not isinstance(data, list) or not data:
                st.error("패턴 데이터 형식이 올바르지 않습니다.")
                return
                
            # 데이터 구조 검증
            required_fields = ['text', 'output', 'dangerlevel']
            if not all(isinstance(item, dict) and all(field in item for field in required_fields) for item in data):
                st.error("패턴 데이터에 필수 필드가 누락되었습니다.")
                return
            
        # 탭 생성
        tab1, tab2, tab3 = st.tabs(["🔍 문장 분석", "✏️ 패턴 등록", "📝 맞춤법 검사"])

        with tab1:
            analysis_type = st.radio(
                "분석 유형 선택:",
                ["텍스트 직접 입력", "파일/폴더 업로드"],
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
                    spell_check = st.checkbox("맞춤법 검사 포함", value=True)
                
                if analyze_button and input_text:
                    with st.spinner('🔄 문장을 분석하고 있습니다...'):
                        # 위험도 분석
                        found_patterns = find_matching_patterns(input_text, data)
                        if found_patterns:
                            total_score = calculate_danger_score(found_patterns)
                            st.success(f"🎯 분석이 완료되었습니다! {len(found_patterns)}개의 패턴이 발견되었습니다.")
                            display_analysis_results(found_patterns, total_score)
                        else:
                            st.info("👀 특별한 위험 패턴이 발견되지 않았습니다.")
                        
                        # 맞춤법 검사
                        if spell_check:
                            with st.spinner('🔄 맞춤법 검사 중...'):
                                spelling_result = check_spelling(input_text)
                                if spelling_result:
                                    display_spelling_check(spelling_result)
            
            else:  # 파일/폴더 업로드
                st.markdown("""
                    <div style="background-color: #2D2D2D; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                        <h4>📁 파일 업로드 안내</h4>
                        <p>• 단일/다중 파일: CSV, Excel 파일 직접 업로드</p>
                        <p>• 폴더 업로드: 여러 파일을 ZIP으로 압축하여 업로드</p>
                        <p>• 지원 형식: .csv, .xlsx, .xls, .zip</p>
                    </div>
                """, unsafe_allow_html=True)
                
                uploaded_files = st.file_uploader(
                    "파일 또는 ZIP 폴더 업로드", 
                    type=['csv', 'xlsx', 'xls', 'zip'],
                    accept_multiple_files=True,
                    help="여러 파일을 한 번에 선택하거나, ZIP 파일로 압축하여 업로드하세요."
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    spell_check_files = st.checkbox("맞춤법 검사 포함", value=True)
                
                if uploaded_files:
                    if st.button("📂 파일 분석", use_container_width=True):
                        all_results = []
                        total_patterns = 0
                        
                        # 프로그레스 바와 텍스트 생성
                        progress_text = st.empty()
                        progress_bar = st.progress(0)
                        
                        try:
                            # 각 파일 처리
                            for idx, file in enumerate(uploaded_files):
                                with st.spinner(f'🔄 {file.name} 분석 중...'):
                                    analysis_result = analyze_file_contents(
                                        file, 
                                        data,
                                        spell_check_enabled=spell_check_files,
                                        progress_bar=progress_bar,
                                        progress_text=progress_text
                                    )
                                    
                                    if analysis_result and analysis_result['total_patterns'] > 0:
                                        all_results.extend(analysis_result['results'])
                                        total_patterns += analysis_result['total_patterns']
                            
                            # 분석 결과 표시
                            if total_patterns > 0:
                                st.success(f"🎯 분석이 완료되었습니다! 총 {total_patterns}개의 패턴이 발견되었습니다.")
                                
                                combined_results = {
                                    'total_patterns': total_patterns,
                                    'results': sorted(all_results, 
                                                key=lambda x: (x['danger_level'], x['match_score']), 
                                                reverse=True)[:1000]
                                }
                                display_file_analysis_results(combined_results)
                            else:
                                st.info("👀 파일에서 위험 패턴이 발견되지 않았습니다.")
                                
                        except Exception as e:
                            st.error(f"파일 분석 중 오류가 발생했습니다: {str(e)}")
                        finally:
                            # 프로그레스 바와 텍스트 제거
                            progress_bar.empty()
                            progress_text.empty()
                            
                            # 메모리 정리
                            gc.collect()

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
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("시트에 연결할 수 없습니다.")
                    except Exception as e:
                        st.error(f"😢 패턴 등록 중 오류가 발생했습니다: {str(e)}")
                else:
                    st.warning("⚠️ 패턴과 분석 내용은 필수입니다!")

        with tab3:
            st.markdown("""
                <div style='background-color: #2D2D2D; padding: 1rem; border-radius: 10px; margin-bottom: 1rem;'>
                    <h4>📝 맞춤법 검사</h4>
                    <p style='color: #E0E0E0;'>텍스트의 맞춤법을 검사합니다.</p>
                </div>
            """, unsafe_allow_html=True)
            
            spell_text = st.text_area(
                "검사할 텍스트를 입력하세요:",
                placeholder="맞춤법을 검사할 텍스트를 입력해주세요...",
                height=150
            )
            
            if st.button("✨ 맞춤법 검사", use_container_width=True):
                if spell_text:
                    with st.spinner('🔄 맞춤법을 검사하고 있습니다...'):
                        spelling_result = check_spelling(spell_text)
                        if spelling_result:
                            display_spelling_check(spelling_result)
                else:
                    st.warning("⚠️ 검사할 텍스트를 입력해주세요!")
                
    except Exception as e:
        st.error(f"애플리케이션 실행 중 오류가 발생했습니다: {str(e)}")
        return

if __name__ == "__main__":
    main()   