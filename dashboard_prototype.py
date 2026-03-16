"""
주간 회의록 데이터를 월별로 집계하고 시각화하는 대시보드 프로토타입
Streamlit 기반 웹 대시보드
"""

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import openpyxl
import json
import os
import html
import time
import shutil

# 페이지 설정
st.set_page_config(
    page_title="주간 회의록 대시보드",
    page_icon="📊",
    layout="wide"
)

st.title("📊 주간 회의록 대시보드")

# 상단 고정 메뉴 구현
st.markdown("""
    <style>
    .stApp {
        margin-top: 50px;
    }
    .nav-container {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        background-color: white;
        padding: 10px 0;
        z-index: 999;
        border-bottom: 1px solid #ddd;
        display: flex;
        justify-content: center;
        gap: 20px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    .nav-item {
        text-decoration: none;
        color: #31333F;
        font-weight: 600;
        padding: 5px 15px;
        border-radius: 5px;
        transition: background-color 0.3s;
    }
    .nav-item:hover {
        background-color: #f0f2f6;
        color: #ff4b4b;
    }
    /* 앵커 위치 조정을 위한 스타일 */
    .anchor {
        display: block;
        position: relative;
        top: -100px;
        visibility: hidden;
    }
    </style>
    
    <div class="nav-container">
        <a class="nav-item" href="#section_target">📊 통계/현황</a>
        <a class="nav-item" href="#section_sales">📦 상품 분석</a>
        <a class="nav-item" href="#section_data_analysis">📈 데이터 분석</a>
        <a class="nav-item" href="#section_plans">📝 파트별 계획</a>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# 메모 저장/로드 함수 (스크립트 위치 기준 절대 경로 사용 → 서버 재시작/실행 위치와 무관하게 데이터 유지)
_script_dir = os.path.dirname(os.path.abspath(__file__))
MEMO_DATA_DIR = os.path.join(_script_dir, "memo_data")
if not os.path.exists(MEMO_DATA_DIR):
    os.makedirs(MEMO_DATA_DIR)

# 주차 계산 함수 (지난주 금요일 ~ 이번주 목요일 기준)
def get_custom_week(date):
    """지난주 금요일 ~ 이번주 목요일 기준으로 주차 계산
    예: 12월 5일(금) ~ 12월 11일(목)까지가 하나의 주차
    
    기준: 지난주 금요일부터 이번주 목요일까지가 하나의 주차
    - 금요일: 해당 주차의 시작일
    - 토요일~목요일: 같은 주차
    """
    if pd.isna(date):
        return None
    
    # 날짜의 요일 (0=월요일, 4=금요일, 6=일요일)
    weekday = date.weekday()
    
    # 해당 주차의 기준 금요일 찾기 (지난주 금요일)
    # 금요일(4)이면 그 날이 기준, 그 외에는 가장 가까운 이전 금요일
    if weekday == 4:  # 금요일
        base_friday = date
    elif weekday == 5:  # 토요일
        base_friday = date - pd.Timedelta(days=1)
    elif weekday == 6:  # 일요일
        base_friday = date - pd.Timedelta(days=2)
    else:  # 월(0), 화(1), 수(2), 목(3)
        # 월요일이면 3일 전 금요일, 화요일이면 4일 전 금요일, 수요일이면 5일 전 금요일, 목요일이면 6일 전 금요일
        base_friday = date - pd.Timedelta(days=weekday + 3)
    
    # 해당 월의 첫 번째 금요일 찾기
    first_day_of_month = base_friday.replace(day=1)
    first_weekday = first_day_of_month.weekday()
    
    # 첫 번째 금요일 계산
    if first_weekday <= 4:  # 월~금
        days_to_first_friday = 4 - first_weekday
    else:  # 토~일
        days_to_first_friday = 4 - first_weekday + 7
    
    first_friday = first_day_of_month + pd.Timedelta(days=days_to_first_friday)
    
    # 주차 번호 계산 (해당 월의 몇 번째 주차인지)
    if base_friday < first_friday:
        # 기준 금요일이 해당 월의 첫 번째 금요일보다 이전이면 이전 달의 마지막 주차
        # 이전 달의 마지막 금요일을 찾아서 계산
        prev_month_last_day = first_day_of_month - pd.Timedelta(days=1)
        prev_month_first_day = prev_month_last_day.replace(day=1)
        prev_first_weekday = prev_month_first_day.weekday()
        
        if prev_first_weekday <= 4:
            prev_days_to_first_friday = 4 - prev_first_weekday
        else:
            prev_days_to_first_friday = 4 - prev_first_weekday + 7
        
        prev_first_friday = prev_month_first_day + pd.Timedelta(days=prev_days_to_first_friday)
        week_number = ((base_friday - prev_first_friday).days // 7) + 1
    else:
        week_number = ((base_friday - first_friday).days // 7) + 1
    
    return week_number

# 주차별 날짜 범위 계산 함수 (지난주 금요일 ~ 이번주 목요일)
def get_week_date_range(week_num, month, min_week, year=None):
    """주차 번호에 해당하는 날짜 범위 반환 (지난주 금요일 ~ 이번주 목요일)"""
    if week_num is None or min_week is None:
        return None, None
    
    # 년도가 없으면 현재 년도 사용
    if year is None:
        year = 2024
    
    # 해당 월의 첫 번째 금요일 찾기
    first_day_of_month = pd.Timestamp(year=year, month=month, day=1)
    first_weekday = first_day_of_month.weekday()
    
    if first_weekday <= 4:  # 월~금
        days_to_first_friday = 4 - first_weekday
    else:  # 토~일
        days_to_first_friday = 4 - first_weekday + 7
    
    first_friday = first_day_of_month + pd.Timedelta(days=days_to_first_friday)
    
    # 주차 번호에 해당하는 금요일 계산
    relative_week = week_num - min_week
    base_friday = first_friday + pd.Timedelta(days=relative_week * 7)
    
    # 해당 주차의 시작일 (금요일)과 종료일 (목요일)
    start_date = base_friday  # 금요일
    end_date = base_friday + pd.Timedelta(days=6)  # 목요일
    
    return start_date, end_date

def get_base_friday(date):
    """주어진 날짜가 속한 주차의 기준 금요일 반환"""
    if pd.isna(date):
        return None

    weekday = date.weekday()
    if weekday == 4:  # 금요일
        return date
    if weekday == 5:  # 토요일
        return date - pd.Timedelta(days=1)
    if weekday == 6:  # 일요일
        return date - pd.Timedelta(days=2)
    # 월(0)~목(3): 가장 가까운 이전 금요일
    return date - pd.Timedelta(days=weekday + 3)

def get_month_week_label(date, selected_month):
    """시작일(금요일) 기준으로 선택 월의 n째주 라벨 반환"""
    if pd.isna(date) or selected_month is None:
        return None

    base_friday = get_base_friday(date)
    if base_friday is None or base_friday.month != selected_month:
        return None

    first_day = pd.Timestamp(year=base_friday.year, month=selected_month, day=1)
    days_to_prev_friday = (first_day.weekday() - 4) % 7
    first_week_start = first_day - pd.Timedelta(days=days_to_prev_friday)
    week_idx = int(((base_friday - first_week_start).days // 7) + 1)

    week_korean = ['첫째', '둘째', '셋째', '넷째', '다섯째']
    if 1 <= week_idx <= len(week_korean):
        return f"{selected_month}월 {week_korean[week_idx - 1]}주"
    return None

def save_memo_to_file(key, value):
    """메모를 JSON 파일로 저장 (원본 포맷 보존, 원자적 쓰기로 안전하게 저장)"""
    try:
        # 빈 값으로 저장하려 할 때 기존 파일이 있으면 경고하고 저장하지 않음 (데이터 손실 방지)
        file_path = os.path.join(MEMO_DATA_DIR, f"{key}.json")
        if not value or not value.strip():
            # 빈 값인데 기존 파일이 있고 내용이 있다면 저장하지 않음
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                        existing_content = existing_data.get("content", "")
                        if existing_content and existing_content.strip():
                            # 기존 내용이 있는데 빈 값으로 덮어쓰려 하면 저장하지 않음
                            return
                except:
                    pass  # 파일 읽기 실패 시 계속 진행
        
        # 임시 파일 경로 생성
        temp_file_path = file_path + ".tmp"
        
        # 원본 텍스트 포맷을 완벽하게 보존하기 위해 ensure_ascii=False 사용
        # 임시 파일에 먼저 저장 (원자적 쓰기)
        with open(temp_file_path, 'w', encoding='utf-8') as f:
            json.dump({"content": value}, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())  # 디스크에 강제로 쓰기
        
        # 임시 파일을 원본 파일로 안전하게 교체 (원자적 연산)
        if os.path.exists(file_path):
            # 백업 파일 생성 (데이터 손실 방지)
            backup_file_path = file_path + ".backup"
            try:
                shutil.copy2(file_path, backup_file_path)
            except:
                pass  # 백업 실패해도 계속 진행
        
        # Windows에서는 rename이 원자적이지 않을 수 있으므로, 존재하는 파일은 삭제 후 rename
        if os.path.exists(file_path):
            os.remove(file_path)
        os.rename(temp_file_path, file_path)
        
    except Exception as e:
        st.error(f"메모 저장 중 오류 발생: {str(e)}")
        # 임시 파일이 남아있으면 정리
        try:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
        except:
            pass

def load_memo_from_file(key):
    """JSON 파일에서 메모 불러오기"""
    try:
        file_path = os.path.join(MEMO_DATA_DIR, f"{key}.json")
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("content", "")
    except Exception as e:
        pass
    return ""

# 로컬 파일 또는 업로드 파일 사용

excel_file_path = '주간회의록.xlsx'
sales_data_path = '2025 정산서 기준 판매 데이터.xlsx'
uploaded_file = None

# 로컬 파일이 있으면 사용, 없으면 업로드 받기
if os.path.exists(excel_file_path):
    use_local = st.checkbox("로컬 파일 사용 (주간회의록.xlsx)", value=True)
    if use_local:
        uploaded_file = excel_file_path
    else:
        uploaded_file = st.file_uploader("주간 회의록 엑셀 파일 업로드", type=['xlsx', 'xls'])
else:
    uploaded_file = st.file_uploader("주간 회의록 엑셀 파일 업로드", type=['xlsx', 'xls'])

if uploaded_file is not None:
    try:
        # 엑셀 파일 읽기
        if isinstance(uploaded_file, str):
            # 로컬 파일
            xls = pd.ExcelFile(uploaded_file)
        else:
            # 업로드된 파일
            xls = pd.ExcelFile(uploaded_file)
        
        # 시트 목록 확인
        sheet_names = [sheet for sheet in xls.sheet_names if not ('스마트공장' in sheet or 'smart' in sheet.lower() or 'factory' in sheet.lower())]
        
        # 현재 날짜 확인
        today = pd.Timestamp.now()
        current_month = today.month
        current_year = today.year
        
        # 1월 시트, 11월 및 12월 시트 자동 찾기
        january_sheet = None
        november_sheet = None
        december_sheet = None
        for sheet in sheet_names:
            sheet_lower = sheet.lower()
            # 2026년 1월 또는 1월 시트 찾기 (11월, 12월과 구분)
            if (('2026' in sheet and '1월' in sheet) or 
                ('1월' in sheet and '11' not in sheet and '12' not in sheet) or
                ('january' in sheet_lower or 'jan' in sheet_lower) and 'nov' not in sheet_lower and 'dec' not in sheet_lower):
                january_sheet = sheet
            if '11월' in sheet or ('11' in sheet and '월' in sheet) or 'november' in sheet_lower or 'nov' in sheet_lower:
                november_sheet = sheet
            if '12월' in sheet or ('12' in sheet and '월' in sheet) or 'december' in sheet_lower or 'dec' in sheet_lower:
                december_sheet = sheet
        
        # 시트 선택 기본값 설정
        # 2026년 2월 raw 시트가 있으면 우선 선택, 없으면 첫 번째 시트 사용
        default_sheet_index = 0
        for idx, sheet in enumerate(sheet_names):
            sheet_lower = sheet.lower()
            if (
                '2026' in sheet
                and ('2월' in sheet or 'february' in sheet_lower or 'feb' in sheet_lower)
                and 'raw' in sheet_lower
            ):
                default_sheet_index = idx
                break
        if len(sheet_names) > 0:
            selected_sheet = st.selectbox("시트 선택", sheet_names, index=default_sheet_index)
        else:
            st.error("⚠️ 사용 가능한 시트가 없습니다.")
            selected_sheet = None
        
        if selected_sheet is None:
            st.stop()
        
        df = pd.read_excel(xls, sheet_name=selected_sheet)
        is_raw_selected_sheet = 'raw' in selected_sheet.lower()
        
        # 선택된 시트에서 월 정보 추출
        selected_month = None
        if '1월' in selected_sheet and '11' not in selected_sheet and '12' not in selected_sheet:
            selected_month = 1
        elif '2월' in selected_sheet or 'february' in selected_sheet.lower() or 'feb' in selected_sheet.lower():
            selected_month = 2
        elif '3월' in selected_sheet or ('3' in selected_sheet and '월' in selected_sheet):
            selected_month = 3
        elif '12월' in selected_sheet or ('12' in selected_sheet and '월' in selected_sheet):
            selected_month = 12
        elif '11월' in selected_sheet or ('11' in selected_sheet and '월' in selected_sheet):
            selected_month = 11
        
        # 스마트공장 시트인지 확인
        is_smart_factory = False
        
        # 스마트공장 시트인 경우 업체별 상담내역 담당자 페이지 표시
        if is_smart_factory:
            # ... (기존 코드 생략) ...
            pass
        
        # 일반 시트인 경우 기존 로직 실행
        if not is_smart_factory:
            # 11월 데이터 필터링 (날짜 컬럼이 있는 경우)
            original_df = df.copy()
            
            # 데이터 전처리 (날짜 컬럼 찾기)
            date_columns = df.select_dtypes(include=['datetime64']).columns.tolist()
            
            # 날짜 형식의 문자열 컬럼도 찾기
            for col in df.columns:
                if df[col].dtype == 'object':
                    try:
                        test_date = pd.to_datetime(df[col].dropna().iloc[0], errors='coerce')
                        if pd.notna(test_date):
                            date_columns.append(col)
                    except:
                        pass
            
            # 날짜 컬럼이 있으면 처리
            if len(date_columns) > 0:
                date_col = date_columns[0]
                df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
                df['년'] = df[date_col].dt.year
                df['월'] = df[date_col].dt.month
                df['년월'] = df[date_col].dt.to_period('M')

                # raw 시트는 B열(주문월)을 월 기준으로 우선 반영
                order_month_series = None
                if len(df.columns) > 1:
                    b_col = df.columns[1]  # B열
                    order_month_series = pd.to_numeric(df[b_col], errors='coerce')
                    if order_month_series.between(1, 12).sum() > 0:
                        df['주문월'] = order_month_series
                        if is_raw_selected_sheet:
                            df['월'] = order_month_series
                
                # 선택된 월 데이터만 필터링 (11월 또는 12월)
                if '월' in df.columns and selected_month is not None:
                    df_filtered = df[df['월'] == selected_month].copy()
                    if len(df_filtered) > 0:
                        df = df_filtered
                        # 총 매출이익금은 나중에 계산 후 표시
                    else:
                        st.warning(f"⚠️ 날짜 컬럼에서 {selected_month}월 데이터를 찾지 못했습니다. 전체 데이터를 표시합니다.")
                elif selected_month is None:
                    # 시트 이름에서 월을 찾지 못한 경우 전체 데이터 표시
                    # st.info(f"📊 '{selected_sheet}' 시트의 전체 데이터를 표시합니다.")  # 숨김 처리
                    pass
            else:
                # 날짜 컬럼이 없으면 시트 이름으로 판단
                if selected_month is not None:
                    # st.info(f"📊 '{selected_sheet}' 시트의 전체 데이터를 표시합니다.")  # 숨김 처리
                    pass
            
            # 사이드바 필터
            st.sidebar.header("필터 옵션")
        
        # 주차 정보 계산 (사이드바에서 경영진 회의록 사용하기 위해)
        # selected_month가 None인 경우 데이터에서 월 추출
        month_for_sidebar_temp = selected_month
        if month_for_sidebar_temp is None and len(df) > 0 and '월' in df.columns:
            unique_months = sorted(df['월'].dropna().unique())
            if len(unique_months) == 1:
                month_for_sidebar_temp = int(unique_months[0])
        month_label_sidebar = f"{month_for_sidebar_temp}월" if month_for_sidebar_temp is not None else "월"
        
        # 주차를 역순으로 정렬하는 함수 (다섯째주 → 첫째주)
        def sort_weeks_korean_sidebar(weeks):
            """주차를 다섯째주, 넷째주, 셋째주, 둘째주, 첫째주 순서로 정렬"""
            week_order = {'첫째': 1, '둘째': 2, '셋째': 3, '넷째': 4, '다섯째': 5}
            def get_week_number(week_str):
                for key, value in week_order.items():
                    if key in week_str:
                        return value
                return 999  # 알 수 없는 주차는 마지막에
            # 역순으로 정렬 (다섯째주가 먼저)
            return sorted(weeks, key=get_week_number, reverse=True)
        
        # 주차 정보 계산 (사이드바에서 사용하기 위해)
        sidebar_weeks = []
        # selected_month가 None인 경우 데이터에서 월 추출 (블록 밖에서도 사용하기 위해 먼저 계산)
        month_for_sidebar = selected_month
        if month_for_sidebar is None and len(df) > 0 and '월' in df.columns:
            unique_months = sorted(df['월'].dropna().unique())
            if len(unique_months) == 1:
                month_for_sidebar = int(unique_months[0])
        
        if len(date_columns) > 0:
            date_col = date_columns[0]
            df_temp = df.copy()
            df_temp[date_col] = pd.to_datetime(df_temp[date_col], errors='coerce')
            # 지난주 금요일 ~ 이번주 목요일 기준으로 주차 계산
            df_temp['주차'] = df_temp[date_col].apply(get_custom_week)
            min_week = df_temp['주차'].min() if len(df_temp) > 0 and df_temp['주차'].notna().any() else None
            max_week = df_temp['주차'].max() if len(df_temp) > 0 and df_temp['주차'].notna().any() else None
            
            # 주차 번호를 한국어로 변환하는 함수
            def week_to_korean_sidebar(week_num, min_week=None, month=None, max_week=None):
                week_korean = ['첫째', '둘째', '셋째', '넷째', '다섯째']
                month_label = f"{month}월" if month is not None else "월"
                if min_week is not None:
                    relative_week = week_num - min_week
                    # 다섯째주는 실제 데이터에 존재할 때만 표시 (relative_week이 4인 경우만)
                    if 0 <= relative_week < len(week_korean):
                        # 다섯째주(relative_week=4)인 경우, max_week을 확인하여 실제로 존재하는지 체크
                        if relative_week == 4:
                            # max_week이 min_week + 4 이상이어야 다섯째주가 존재
                            if max_week is not None and max_week >= min_week + 4:
                                return f"{month_label} {week_korean[relative_week]}주"
                            else:
                                # 다섯째주가 존재하지 않으면 None 반환 (표시하지 않음)
                                return None
                        else:
                            return f"{month_label} {week_korean[relative_week]}주"
                return f"{month_label} {week_num}주"
            
            if selected_month is not None:
                # 선택 월에서는 입력 데이터 날짜를 기반으로 실제 주차를 자동 생성
                df_temp['주차_한글'] = df_temp[date_col].apply(lambda x: get_month_week_label(x, selected_month))
                sidebar_weeks_all = [w for w in df_temp['주차_한글'].unique().tolist() if w is not None]
                sidebar_weeks = sort_weeks_korean_sidebar(sidebar_weeks_all)
            else:
                df_temp['주차_한글'] = df_temp['주차'].apply(lambda x: week_to_korean_sidebar(x, min_week, month_for_sidebar, max_week))
                # None 값 제거 (다섯째주가 존재하지 않는 경우)
                sidebar_weeks_all = [w for w in df_temp['주차_한글'].unique().tolist() if w is not None]
                sidebar_weeks = sort_weeks_korean_sidebar(sidebar_weeks_all)
        
        # 주차별 경영진 회의록 입력 및 요약
        if len(sidebar_weeks) > 0:
            # 사이드바와 메인 페이지 동기화를 위한 키 (month_for_sidebar 사용)
            month_key = f"{month_for_sidebar}월" if month_for_sidebar is not None else "월"
            sidebar_week_select_key = f"sidebar_week_select_{month_key}"
            main_week_select_key = f"main_week_select_{month_key}"
            
            # 오늘 날짜를 기반으로 현재 주차 계산
            today = pd.Timestamp.now()
            current_week_num = get_custom_week(today)
            current_week_korean = None
            if selected_month is not None:
                current_week_korean = get_month_week_label(today, selected_month)
            elif current_week_num is not None and min_week is not None:
                current_week_korean = week_to_korean_sidebar(current_week_num, min_week, month_for_sidebar)
            
            # 주차 선택 (사이드바와 메인 페이지 동기화)
            # 우선순위: 1) 메인 페이지 선택, 2) 사이드바 이전 선택, 3) 오늘 날짜 기준 주차, 4) 첫 번째 주차
            if main_week_select_key in st.session_state and st.session_state[main_week_select_key] in sidebar_weeks:
                # 메인 페이지에서 선택한 주차 사용
                default_index = sidebar_weeks.index(st.session_state[main_week_select_key])
            elif sidebar_week_select_key in st.session_state and st.session_state[sidebar_week_select_key] in sidebar_weeks:
                # 사이드바에서 이전에 선택한 주차 사용
                default_index = sidebar_weeks.index(st.session_state[sidebar_week_select_key])
            elif current_week_korean and current_week_korean in sidebar_weeks:
                # 오늘 날짜 기준 주차 사용
                default_index = sidebar_weeks.index(current_week_korean)
            else:
                default_index = 0
            
            selected_week_sidebar = st.sidebar.selectbox(
                "주차 선택", 
                sidebar_weeks, 
                key=sidebar_week_select_key,
                index=default_index
            )
            
            # 주차별 경영진 회의록 입력 및 요약
            st.sidebar.markdown("---")
            st.sidebar.markdown("#### 📋 주차별 경영진 회의록")
            
            # 메인 페이지와 동일한 month_label 사용 (키 일치를 위해)
            month_label_for_meeting = f"{selected_month}월" if selected_month is not None else "월"
            
            # 선택된 주차의 경영진 회의록 키
            executive_meeting_key_sidebar = f"executive_meeting_{month_label_for_meeting}_{selected_week_sidebar}"
            
            # 입력창의 키 (주차별로 고정되어 주차 변경 시 자동으로 새 입력창 생성)
            executive_input_key = f"executive_meeting_input_sidebar_{month_label_for_meeting}_{selected_week_sidebar}"
            
            # 주차별로 독립적인 session_state 키 사용 (주차가 변경되면 항상 파일에서 불러오기)
            current_week_state_key_executive = f"current_week_sidebar_executive_{executive_meeting_key_sidebar}"
            last_selected_week_key = f"last_selected_week_sidebar_executive_{month_label_for_meeting}"
            
            # 주차 변경 감지 및 이전 주차 데이터 저장
            if last_selected_week_key in st.session_state and st.session_state[last_selected_week_key] != selected_week_sidebar:
                # 주차가 변경되었으므로 이전 주차의 데이터를 파일에 저장
                previous_week_sidebar = st.session_state[last_selected_week_key]
                previous_executive_meeting_key = f"executive_meeting_{month_label_for_meeting}_{previous_week_sidebar}"
                previous_executive_input_key = f"executive_meeting_input_sidebar_{month_label_for_meeting}_{previous_week_sidebar}"
                
                # 이전 주차의 경영진 회의록 저장 (입력창 내용 우선 확인)
                previous_executive_meeting = ""
                if previous_executive_input_key in st.session_state:
                    # 입력창의 내용이 있으면 우선 사용
                    previous_executive_meeting = st.session_state[previous_executive_input_key]
                elif previous_executive_meeting_key in st.session_state:
                    # 입력창 내용이 없으면 session_state 확인
                    previous_executive_meeting = st.session_state[previous_executive_meeting_key]
                
                # 빈 값이 아닐 때만 저장
                if previous_executive_meeting and previous_executive_meeting.strip():
                    save_memo_to_file(previous_executive_meeting_key, previous_executive_meeting)
            
            # 주차가 변경되었는지 확인
            if current_week_state_key_executive not in st.session_state or st.session_state.get(last_selected_week_key) != selected_week_sidebar:
                # 주차가 변경되었거나 처음 로드하는 경우 파일에서 불러오기
                loaded_executive_meeting = load_memo_from_file(executive_meeting_key_sidebar)
                if loaded_executive_meeting:
                    st.session_state[executive_meeting_key_sidebar] = loaded_executive_meeting
                    # 입력창의 session_state도 업데이트
                    st.session_state[executive_input_key] = loaded_executive_meeting
                else:
                    # 파일에서 불러온 값이 없으면 session_state에 빈 값으로 설정하지 않음
                    # 대신 빈 문자열로 초기화하되, 나중에 저장할 때는 빈 값 저장 방지 로직이 작동함
                    if executive_meeting_key_sidebar not in st.session_state:
                        st.session_state[executive_meeting_key_sidebar] = ""
                    # 입력창의 session_state도 초기화
                    if executive_input_key not in st.session_state:
                        st.session_state[executive_input_key] = ""
                st.session_state[current_week_state_key_executive] = True
                st.session_state[last_selected_week_key] = selected_week_sidebar
            else:
                # 주차가 변경되지 않았지만 파일에 최신 데이터가 있을 수 있으므로 확인
                if executive_meeting_key_sidebar not in st.session_state or not st.session_state.get(executive_meeting_key_sidebar):
                    loaded_executive_meeting = load_memo_from_file(executive_meeting_key_sidebar)
                    if loaded_executive_meeting:
                        st.session_state[executive_meeting_key_sidebar] = loaded_executive_meeting
                        # 입력창의 session_state도 업데이트
                        if executive_input_key not in st.session_state:
                            st.session_state[executive_input_key] = loaded_executive_meeting
            
            # 입력창이 처음 생성될 때 초기값 설정
            if executive_input_key not in st.session_state:
                # 파일에서 최신 내용 확인
                latest_from_file = load_memo_from_file(executive_meeting_key_sidebar)
                if latest_from_file:
                    st.session_state[executive_input_key] = latest_from_file
                    st.session_state[executive_meeting_key_sidebar] = latest_from_file
                else:
                    st.session_state[executive_input_key] = st.session_state.get(executive_meeting_key_sidebar, "")
            
            executive_meeting_text_sidebar = st.sidebar.text_area(
                f"{selected_week_sidebar} 경영진 회의록을 입력하세요",
                height=150,
                placeholder=f"{selected_week_sidebar} 경영진 회의록을 작성하세요.\n\n💡 팁: '저장' 버튼을 눌러야 데이터가 보존됩니다.",
                key=executive_input_key
            )
            
            # 명시적 저장 버튼
            if st.sidebar.button(f"💾 {selected_week_sidebar} 회의록 저장", key=f"save_btn_executive_{selected_week_sidebar}"):
                if executive_meeting_text_sidebar and executive_meeting_text_sidebar.strip():
                    st.session_state[executive_meeting_key_sidebar] = executive_meeting_text_sidebar
                    save_memo_to_file(executive_meeting_key_sidebar, executive_meeting_text_sidebar)
                    st.sidebar.success(f"✅ {selected_week_sidebar} 경영진 회의록이 저장되었습니다.")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.sidebar.warning("⚠️ 저장할 내용이 없습니다.")
            
            # 저장된 경영진 회의록 표시
            if st.session_state.get(executive_meeting_key_sidebar, ""):
                with st.sidebar.expander(f"📋 저장된 {selected_week_sidebar} 경영진 회의록 보기", expanded=False):
                    executive_display = st.session_state[executive_meeting_key_sidebar].replace('\n', '<br>')
                    st.sidebar.markdown(executive_display, unsafe_allow_html=True)
            
            # 모든 주차별 경영진 회의록 요약 보기 (현재 선택된 주차 제외)
            st.sidebar.markdown("---")
            st.sidebar.markdown("#### 📋 주차별 경영진 회의록 요약")
            executive_meeting_summary = {}
            
            # 모든 주차의 회의록을 파일에서 불러와서 session_state에 저장 (요약 표시를 위해)
            # 매번 파일에서 확인하여 최신 데이터 보장
            for week in sidebar_weeks:
                # 현재 선택된 주차는 제외 (위에서 이미 표시됨)
                if week == selected_week_sidebar:
                    continue
                    
                week_key = f"executive_meeting_{month_label_for_meeting}_{week}"
                # 파일에서 불러오기 (항상 최신 데이터 확인)
                loaded_executive_meeting = load_memo_from_file(week_key)
                if loaded_executive_meeting:
                    # 파일에 데이터가 있으면 session_state에 저장하고 요약에 추가
                    st.session_state[week_key] = loaded_executive_meeting
                    executive_meeting_summary[week] = loaded_executive_meeting
                elif week_key in st.session_state and st.session_state[week_key]:
                    # 파일에 없지만 session_state에 있으면 사용 (새로 작성 중인 경우)
                    executive_meeting_summary[week] = st.session_state[week_key]
            
            if executive_meeting_summary:
                # 정렬된 주차 순서로 표시 (현재 선택된 주차 제외)
                for week in sidebar_weeks:
                    if week == selected_week_sidebar:
                        continue  # 현재 선택된 주차는 제외
                    if week in executive_meeting_summary:
                        content = executive_meeting_summary[week]
                        # 내용 요약 (첫 100자만 표시)
                        summary = content[:100] + "..." if len(content) > 100 else content
                        with st.sidebar.expander(f"📋 {week} 경영진 회의록", expanded=False):
                            week_display = content.replace('\n', '<br>')
                            st.sidebar.markdown(week_display, unsafe_allow_html=True)
        else:
            # 주차 정보가 없으면 경영진 회의록만 표시
            st.sidebar.info("주차 정보가 없어 주차별 경영진 회의록을 작성할 수 없습니다.")
        
        if '년' in df.columns:
            years = sorted(df['년'].dropna().unique())
            # 년도 선택 필터 숨김 (기본값으로 모든 년도 선택)
            selected_years = years
            df = df[df['년'].isin(selected_years)]

        # 목표 달성 계산용 월 기준 컬럼 결정
        # 우선순위: B열(주문월) -> 기존 월 컬럼
        order_month_col = None
        target_month_series = None
        if len(df.columns) > 1:
            order_month_col = df.columns[1]  # B열
            target_month_series = pd.to_numeric(df[order_month_col], errors='coerce')
            # 주문월로 보기 어려운 데이터면 기존 월 컬럼 사용
            valid_month_count = target_month_series.between(1, 12).sum()
            if valid_month_count == 0:
                target_month_series = None
        if target_month_series is None and '월' in df.columns:
            target_month_series = pd.to_numeric(df['월'], errors='coerce')
        
        # 선택된 월 데이터만 표시 중이면 월 필터는 숨김
        if '월' in df.columns:
            months = sorted(df['월'].dropna().unique())
            if selected_month is not None and selected_month in months and len(months) == 1:
                st.sidebar.info(f"📅 {selected_month}월 데이터만 표시 중")
            else:
                selected_months = st.sidebar.multiselect("월 선택", months, default=months)
                df = df[df['월'].isin(selected_months)]
            
            # 선택된 월 목표 달성율 계산
            # month_label 설정: selected_month가 있으면 사용, 없으면 필터링된 데이터에서 월 추출
            if selected_month is not None:
                month_label = f"{selected_month}월"
            elif len(df) > 0 and '월' in df.columns:
                # 필터링된 데이터에서 고유한 월 추출 (하나의 월만 있는 경우)
                unique_months = sorted(df['월'].dropna().unique())
                if len(unique_months) == 1:
                    month_label = f"{int(unique_months[0])}월"
                elif len(selected_months) == 1:
                    month_label = f"{int(selected_months[0])}월"
                else:
                    month_label = "월"
            else:
                month_label = "월"
            st.markdown('<span id="section_target" class="anchor"></span>', unsafe_allow_html=True)
            st.subheader(f"🎯 {month_label} 목표 달성 현황")
            
            # 목표 설정 (년도별, 월별)
            # 2025년도 목표액 (기본값)
            target_part1_2025 = 17000000  # 1파트 목표: 17,000,000원
            target_part2_2025 = 1000000   # 2파트 목표: 1,000,000원
            
            # 2026년도 1파트 월별 목표액
            target_part1_2026_monthly = {
                1: 32000000,   # 1월: 32,000,000원
                2: 40000000,   # 2월: 40,000,000원
                3: 44000000,   # 3월: 44,000,000원
                4: 32000000,   # 4월: 32,000,000원
                5: 40000000,   # 5월: 40,000,000원
                6: 29000000,   # 6월: 29,000,000원
                7: 33000000,   # 7월: 33,000,000원
                8: 36000000,   # 8월: 36,000,000원
                9: 40000000,   # 9월: 40,000,000원
                10: 29000000,  # 10월: 29,000,000원
                11: 24000000,  # 11월: 24,000,000원
                12: 24000000   # 12월: 24,000,000원
            }
            
            # 2026년도 2파트 월별 목표액
            target_part2_2026_monthly = {
                1: 2000000,   # 1월: 2,000,000원
                2: 2000000,   # 2월: 2,000,000원
                3: 2000000,   # 3월: 2,000,000원
                4: 4000000,   # 4월: 4,000,000원
                5: 5000000,   # 5월: 5,000,000원
                6: 5000000,   # 6월: 5,000,000원
                7: 6000000,   # 7월: 6,000,000원
                8: 7000000,   # 8월: 7,000,000원
                9: 11000000,  # 9월: 11,000,000원
                10: 9000000,  # 10월: 9,000,000원
                11: 8000000,  # 11월: 8,000,000원
                12: 9000000   # 12월: 9,000,000원
            }
            
            # 년도 추출
            year = None
            if '년' in df.columns and len(df) > 0:
                unique_years = sorted(df['년'].dropna().unique())
                if len(unique_years) == 1:
                    year = int(unique_years[0])
                elif len(selected_years) == 1:
                    year = int(selected_years[0])
            
            # 월 추출
            month_num = None
            if selected_month is not None:
                month_num = selected_month
            elif len(df) > 0 and target_month_series is not None:
                unique_months = sorted(target_month_series.dropna().astype(int).unique())
                if len(unique_months) == 1:
                    month_num = int(unique_months[0])
                elif len(selected_months) == 1:
                    month_num = int(selected_months[0])
            
            # 년도와 월에 따라 목표액 설정
            if year == 2026 and month_num is not None:
                # 2026년도: 월별 목표액 사용
                target_part1 = target_part1_2026_monthly.get(month_num, target_part1_2025)
                target_part2 = target_part2_2026_monthly.get(month_num, target_part2_2025)
            else:
                # 2025년도 또는 년도/월 정보가 없는 경우: 기본값 사용
                target_part1 = target_part1_2025
                target_part2 = target_part2_2025
            
            # N열 찾기 (엑셀의 N열 = 14번째 컬럼, 인덱스 13)
        # 방법 1: 컬럼 인덱스로 N열 찾기 (14번째 컬럼)
        n_column_index = 13  # N열은 14번째 (0-based index: 13)
        amount_col = None
        
        if len(df.columns) > n_column_index:
            amount_col = df.columns[n_column_index]
        else:
            # 방법 2: 컬럼 이름으로 찾기
            amount_columns = [col for col in df.columns if any(keyword in str(col).lower() for keyword in ['금액', 'amount', '매출', '매출액', '수익', 'revenue', '매출총이익'])]
            if len(amount_columns) > 0:
                amount_col = amount_columns[0]
            else:
                with st.expander("⚠️ N열을 찾지 못했습니다. 수동으로 선택해주세요."):
                    amount_col = st.selectbox("금액 컬럼 선택 (N열)", [""] + list(df.columns), key='amount_col')
                    if amount_col == "":
                        amount_col = None
        
        # P열의 담당자 컬럼을 파트로 변환
        # P열(16번째 컬럼, 인덱스 15)을 담당자 컬럼으로 사용
        manager_col_for_part = None
        if len(df.columns) > 15:
            manager_col_for_part = df.columns[15]  # P열 (16번째 컬럼)
        
        # 담당자를 파트로 변환하는 함수
        def manager_to_part(manager_name):
            """담당자 이름을 파트로 변환
            - 맹기열 → 2파트
            - 박진성, 아름벌, 최승영 및 나머지 모든 담당자 → 1파트
            """
            if pd.isna(manager_name) or manager_name == '':
                return '1파트'
            
            manager_str = str(manager_name).strip()
            
            # 맹기열 → 2파트
            if '맹기열' in manager_str:
                return '2파트'
            
            # 나머지 모든 담당자 → 1파트 (박진성, 아름벌, 최승영 포함)
            return '1파트'
        
        # 파트 컬럼 찾기 (기존 파트 컬럼이 있는지 먼저 확인)
        part_columns = [col for col in df.columns if any(keyword in str(col).lower() for keyword in ['파트', 'part'])]
        part_col = None
        
        if len(part_columns) > 0:
            part_col = part_columns[0]
        elif manager_col_for_part is not None:
            # P열의 담당자 컬럼이 있으면 파트로 변환
            df['파트'] = df[manager_col_for_part].apply(manager_to_part)
            part_col = '파트'
        else:
            with st.expander("⚠️ 파트 컬럼을 자동으로 찾지 못했습니다. 수동으로 선택해주세요."):
                part_col = st.selectbox("파트 컬럼 선택", [""] + list(df.columns), key='part_col')
                if part_col == "":
                    part_col = None
        
        # 파트별 금액 집계
        part1_achieved = 0
        part2_achieved = 0
        part1_mask = None
        part2_mask = None
        part1_count = 0
        part2_count = 0

        # 목표 달성 계산 시 월 기준(B열 주문월 우선)으로 데이터 재필터링
        df_target = df.copy()
        if target_month_series is not None:
            if selected_month is not None:
                target_mask = target_month_series == selected_month
                if target_mask.any():
                    df_target = df[target_mask].copy()
            elif 'selected_months' in locals() and len(selected_months) == 1:
                target_mask = target_month_series == int(selected_months[0])
                if target_mask.any():
                    df_target = df[target_mask].copy()
        
        if amount_col is not None:
            # 금액 컬럼이 숫자형이 아니면 변환 시도
            if df_target[amount_col].dtype == 'object':
                df_target[amount_col] = pd.to_numeric(df_target[amount_col], errors='coerce')
            
            if part_col is not None:
                # 파트 컬럼이 있는 경우
                # 1파트 데이터 필터링 (1, 1파트, part1 등)
                part1_mask = (
                    df_target[part_col].astype(str).str.contains('1파트|part1|^1$', na=False, regex=True) |
                    (df_target[part_col].astype(str).str.strip() == '1')
                )
                if part1_mask.any():
                    part1_achieved = df_target[part1_mask][amount_col].sum()
                    part1_count = part1_mask.sum()
                
                # 2파트 데이터 필터링 (2, 2파트, part2 등)
                part2_mask = (
                    df_target[part_col].astype(str).str.contains('2파트|part2|^2$', na=False, regex=True) |
                    (df_target[part_col].astype(str).str.strip() == '2')
                )
                if part2_mask.any():
                    part2_achieved = df_target[part2_mask][amount_col].sum()
                    part2_count = part2_mask.sum()
            else:
                # 파트 컬럼이 없는 경우, 전체 데이터를 확인
                # 사용자가 직접 입력하거나, 다른 방법으로 구분
                with st.expander("💡 파트 컬럼이 없습니다. 수동으로 분할하세요."):
                    total_amount = df_target[amount_col].sum()
                    st.write(f"전체 N열 합계: {total_amount:,.0f}원")
                    part1_ratio = st.slider("1파트 비율 (%)", 0, 100, 90, key='part1_ratio')
                    part1_achieved = total_amount * (part1_ratio / 100)
                    part2_achieved = total_amount * ((100 - part1_ratio) / 100)
        
        # 디버깅 정보 (기본적으로 숨김)
        with st.expander("🔍 파트별 요약 보기", expanded=False):
            st.write(f"**1파트 달성 금액:** {part1_achieved:,.0f}원")
            st.write(f"**2파트 달성 금액:** {part2_achieved:,.0f}원")
            if part_col:
                st.write(f"**1파트 데이터 건수:** {part1_count}건")
                st.write(f"**2파트 데이터 건수:** {part2_count}건")
        
        # 선택된 월 총 매출이익금 표시 (1파트 + 2파트 합계)
        if amount_col is not None and selected_month is not None:
            total_profit = part1_achieved + part2_achieved
            total_count = len(df_target)
            col_info1, col_info2 = st.columns(2)
            with col_info1:
                st.info(f"📅 {selected_month}월 총 판매 수량 {total_count:,}건")
            with col_info2:
                st.info(f"💰 {selected_month}월 총 매출이익금 {total_profit:,.0f}원")
        
        # 달성율 계산
        achievement_rate_part1 = (part1_achieved / target_part1 * 100) if target_part1 > 0 else 0
        achievement_rate_part2 = (part2_achieved / target_part2 * 100) if target_part2 > 0 else 0
        
        # 달성율 표시
        col_part1, col_part2, col_total = st.columns(3)
        
        with col_part1:
            delta_part1 = part1_achieved - target_part1
            st.metric(
                "1파트 달성율",
                f"{achievement_rate_part1:.1f}%",
                delta=f"{delta_part1:,.0f}원",
                help=f"목표: {target_part1:,}원, 달성: {part1_achieved:,.0f}원"
            )
            st.caption(f"목표: {target_part1:,}원")
            st.caption(f"달성: {part1_achieved:,.0f}원")
        
        with col_part2:
            delta_part2 = part2_achieved - target_part2
            st.metric(
                "2파트 달성율",
                f"{achievement_rate_part2:.1f}%",
                delta=f"{delta_part2:,.0f}원",
                help=f"목표: {target_part2:,}원, 달성: {part2_achieved:,.0f}원"
            )
            st.caption(f"목표: {target_part2:,}원")
            st.caption(f"달성: {part2_achieved:,.0f}원")
        
        with col_total:
            total_target = target_part1 + target_part2
            total_achieved = part1_achieved + part2_achieved
            total_rate = (total_achieved / total_target * 100) if total_target > 0 else 0
            delta_total = total_achieved - total_target
            st.metric(
                "전체 달성율",
                f"{total_rate:.1f}%",
                delta=f"{delta_total:,.0f}원",
                help=f"목표: {total_target:,}원, 달성: {total_achieved:,.0f}원"
            )
            st.caption(f"목표: {total_target:,}원")
            st.caption(f"달성: {total_achieved:,.0f}원")
        
        # 달성율 시각화 (프로그레스 바)
        st.markdown("#### 달성율 진행 상황")
        progress_col1, progress_col2 = st.columns(2)
        
        with progress_col1:
            st.markdown("**1파트**")
            st.progress(min(achievement_rate_part1 / 100, 1.0))
            if achievement_rate_part1 >= 100:
                st.success(f"✅ 목표 달성! ({achievement_rate_part1:.1f}%)")
            elif achievement_rate_part1 >= 80:
                st.warning(f"⚠️ 목표 근접 ({achievement_rate_part1:.1f}%)")
            else:
                st.info(f"📊 진행 중 ({achievement_rate_part1:.1f}%)")
        
        with progress_col2:
            st.markdown("**2파트**")
            st.progress(min(achievement_rate_part2 / 100, 1.0))
            if achievement_rate_part2 >= 100:
                st.success(f"✅ 목표 달성! ({achievement_rate_part2:.1f}%)")
            elif achievement_rate_part2 >= 80:
                st.warning(f"⚠️ 목표 근접 ({achievement_rate_part2:.1f}%)")
            else:
                st.info(f"📊 진행 중 ({achievement_rate_part2:.1f}%)")
        
        st.markdown("---")
        
        # 월간 KPI 요약
        # st.markdown('<span id="section_stats" class="anchor"></span>', unsafe_allow_html=True)
        st.subheader("📊 월간 KPI 요약")
        
        # J열 찾기 (총 매출, 10번째 컬럼, 인덱스 9)
        j_column_index = 9  # J열은 10번째 (0-based index: 9)
        revenue_col = None
        if len(df.columns) > j_column_index:
            revenue_col = df.columns[j_column_index]
        else:
            st.warning("⚠️ J열(총 매출)을 찾을 수 없습니다.")
        
        # K열 찾기 (매출원가, 11번째 컬럼, 인덱스 10)
        k_column_index = 10  # K열은 11번째 (0-based index: 10)
        cost_col = None
        if len(df.columns) > k_column_index:
            cost_col = df.columns[k_column_index]
        else:
            st.warning("⚠️ K열(매출원가)을 찾을 수 없습니다.")
        
        # N열 찾기 (매출총이익, 14번째 컬럼, 인덱스 13) - 이미 amount_col로 찾았을 수 있음
        n_column_index = 13  # N열은 14번째 (0-based index: 13)
        profit_col = None
        if len(df.columns) > n_column_index:
            profit_col = df.columns[n_column_index]
        else:
            # amount_col이 이미 N열이면 사용
            if amount_col is not None:
                profit_col = amount_col
        
        # 데이터 타입 변환 및 집계
        total_revenue = None
        total_cost = None
        total_profit = None
        profit_rate = None
        
        if revenue_col is not None:
            if df[revenue_col].dtype == 'object':
                df[revenue_col] = pd.to_numeric(df[revenue_col], errors='coerce')
            total_revenue = df[revenue_col].sum()
        
        if cost_col is not None:
            if df[cost_col].dtype == 'object':
                df[cost_col] = pd.to_numeric(df[cost_col], errors='coerce')
            total_cost = df[cost_col].sum()
        
        if profit_col is not None:
            if df[profit_col].dtype == 'object':
                df[profit_col] = pd.to_numeric(df[profit_col], errors='coerce')
            total_profit = df[profit_col].sum()
        
        # 이익률 계산: 1 - (K열 합계 / J열 합계)
        if total_revenue is not None and total_revenue > 0 and total_cost is not None:
            cost_ratio = total_cost / total_revenue
            profit_rate = (1 - cost_ratio) * 100  # 백분율로 변환
        
        # KPI 표시
        col_kpi1, col_kpi2 = st.columns(2)
        
        with col_kpi1:
            if total_revenue is not None:
                st.markdown(f"**총 매출:** {total_revenue:,.0f}원")
            else:
                st.markdown("**총 매출:** 데이터 없음")
            
            if total_cost is not None:
                st.markdown(f"**매출원가:** {total_cost:,.0f}원")
            else:
                st.markdown("**매출원가:** 데이터 없음")
        
        with col_kpi2:
            if total_profit is not None:
                st.markdown(f"**매출총이익(GP):** {total_profit:,.0f}원")
            else:
                st.markdown("**매출총이익(GP):** 데이터 없음")
            
            if profit_rate is not None:
                st.markdown(f"**이익률(GP%):** {profit_rate:.1f}%")
            else:
                st.markdown("**이익률(GP%):** 계산 불가")
        
        st.markdown("---")
        
        # 전체 플랫폼 매출이익금 그래프 (주차별) 표시 여부
        hide_platform_profit_charts = True
        if not hide_platform_profit_charts:
            st.subheader("📈 전체 플랫폼 매출이익금")
        
        try:
            # 연도별 주차 계산 함수 (1년을 52주로 나누기)
            def get_year_week(date, year):
                """해당 연도의 주차 계산 (1월 1일부터 시작, 1주차~52주차)
                연초부터 시작하는 주차 계산
                """
                if pd.isna(date):
                    return None
                
                # 해당 연도의 1월 1일
                year_start = pd.Timestamp(year, 1, 1)
                
                # 1월 1일이 속한 주의 월요일 찾기 (주차는 월요일부터 시작)
                year_start_weekday = year_start.weekday()  # 0=월요일, 6=일요일
                first_week_monday = year_start - pd.Timedelta(days=year_start_weekday)
                
                # 해당 날짜가 속한 주의 월요일 찾기
                date_weekday = date.weekday()
                date_monday = date - pd.Timedelta(days=date_weekday)
                
                # 주차 계산 (1주차부터 시작)
                days_diff = (date_monday - first_week_monday).days
                week_number = (days_diff // 7) + 1
                
                # 연초 처리: 1월 1일 이전이면 전년도 마지막 주차로 처리하지 않음 (해당 연도 1주차로 처리)
                if week_number < 1:
                    week_number = 1
                
                # 52주를 넘지 않도록 제한
                if week_number > 52:
                    week_number = 52
                
                return week_number
            
            def week_to_month_label(year, week_number):
                """연도와 주차(1~52)를 받아 'X월 Y주차' 문자열 반환"""
                year_start = pd.Timestamp(year, 1, 1)
                year_start_weekday = year_start.weekday()
                first_week_monday = year_start - pd.Timedelta(days=year_start_weekday)
                week_monday = first_week_monday + pd.Timedelta(days=(week_number - 1) * 7)
                month = week_monday.month
                day_of_month = week_monday.day
                week_in_month = (day_of_month - 1) // 7 + 1
                return f"{month}월 {week_in_month}주차"
            
            def get_month_week_ranges(year):
                """연도별로 월(1~12)마다 해당하는 주차 범위 [x0, x1] 리스트 반환. x는 주차(1~52) 기준."""
                year_start = pd.Timestamp(year, 1, 1)
                year_start_weekday = year_start.weekday()
                first_week_monday = year_start - pd.Timedelta(days=year_start_weekday)
                month_ranges = []  # [(month, x0, x1), ...]
                for week_num in range(1, 53):
                    week_monday = first_week_monday + pd.Timedelta(days=(week_num - 1) * 7)
                    month = week_monday.month
                    if not month_ranges or month_ranges[-1][0] != month:
                        month_ranges.append([month, week_num, week_num])
                    else:
                        month_ranges[-1][2] = week_num
                return [(m, x0, x1) for m, x0, x1 in month_ranges]
            
            # 전년도 매출 비교.xlsx 사용: 주문일(날짜), 매출총이익, 구분 → 4개 그래프 (컬럼 이름 우선, 인덱스 보조)
            compare_path = os.path.join(_script_dir, "전년도 매출 비교.xlsx")
            if not os.path.exists(compare_path):
                compare_path = "전년도 매출 비교.xlsx"
            compare_df = None
            date_col_compare = None
            profit_col_compare = None
            gubun_col = None
            
            if os.path.exists(compare_path):
                try:
                    xls_compare = pd.ExcelFile(compare_path)
                    # 첫 시트 사용 (시트가 여러 개면 첫 시트; 필요 시 sheet_names에서 특정 시트 선택 가능)
                    compare_df = pd.read_excel(xls_compare, sheet_name=xls_compare.sheet_names[0])
                    cols = compare_df.columns
                    # 컬럼 이름으로 찾기 (공백/대소문자 무시)
                    def find_col(name_candidates, index_fallback):
                        for c in cols:
                            c_str = str(c).strip().lower()
                            for n in name_candidates:
                                if n in c_str or c_str in n:
                                    return c
                        return cols[index_fallback] if len(cols) > index_fallback else None
                    date_col_compare = find_col(['주문일', '날짜', 'date', '일자'], 4)
                    profit_col_compare = find_col(['매출총이익', '매출이익', '이익', 'profit'], 12)
                    # O열 구분: 헤더 '구분' 또는 이름에 '구분' 포함, 없으면 O열(15번째, 인덱스 14) 사용
                    gubun_col = None
                    for c in cols:
                        s = str(c).strip()
                        if s == '구분' or '구분' in s:
                            gubun_col = c
                            break
                    if gubun_col is None and len(cols) > 14:
                        gubun_col = cols[14]  # O열
                    if gubun_col is None:
                        gubun_col = find_col(['플랫폼', 'category', 'gubun'], 14)
                    if date_col_compare and profit_col_compare:
                        compare_df[date_col_compare] = pd.to_datetime(compare_df[date_col_compare], errors='coerce')
                        compare_df[profit_col_compare] = pd.to_numeric(compare_df[profit_col_compare], errors='coerce')
                        compare_df['_년'] = compare_df[date_col_compare].dt.year
                        compare_df['_주차'] = compare_df.apply(lambda r: get_year_week(r[date_col_compare], int(r['_년'])) if pd.notna(r[date_col_compare]) and pd.notna(r['_년']) else None, axis=1)
                        compare_df = compare_df[compare_df['_주차'].notna()]
                        compare_df = compare_df[compare_df['_년'].isin([2025, 2026])]
                        if gubun_col is not None:
                            compare_df[gubun_col] = compare_df[gubun_col].astype(str).str.strip()
                except Exception as e:
                    st.warning(f"⚠️ 전년도 매출 비교.xlsx 로드 중 오류: {str(e)}")
                    compare_df = None
            
            def build_weekly_from_compare(구분_목록=None):
                """구분_목록이 None이면 전체, 리스트면 해당 구분만 필터 후 주차별 합산"""
                w25 = {}
                w26 = {}
                if compare_df is None or len(compare_df) == 0:
                    return w25, w26
                sub = compare_df.copy()
                if 구분_목록 is not None and gubun_col is not None:
                    sub = sub[sub[gubun_col].isin(구분_목록)]
                if len(sub) == 0:
                    return w25, w26
                agg = sub.groupby(['_년', '_주차'])[profit_col_compare].sum().reset_index()
                for _, row in agg.iterrows():
                    yr, wk = int(row['_년']), int(row['_주차'])
                    g = row[profit_col_compare]
                    if yr == 2025:
                        w25[wk] = w25.get(wk, 0) + g
                    elif yr == 2026:
                        w26[wk] = w26.get(wk, 0) + g
                return w25, w26
            
            def draw_compare_chart(weekly_2025, weekly_2026, chart_title):
                weeks = list(range(2, 53))
                data_2025 = [weekly_2025.get(w, 0) for w in weeks]
                data_2026 = [weekly_2026.get(w, 0) for w in weeks]
                fig = go.Figure()
                # 데이터 없어도 2025/2026 막대는 항상 추가해 4개 그래프가 모두 보이도록 함
                fig.add_trace(go.Bar(x=weeks, y=data_2025, name='2025', marker_color='#1f77b4', text=[f'{week_to_month_label(2025, w)} {x:,.0f} 원' if x > 0 else '' for w, x in zip(weeks, data_2025)], textposition='outside', hovertemplate='%{text}<extra></extra>'))
                fig.add_trace(go.Bar(x=weeks, y=data_2026, name='2026', marker_color='#808080', text=[f'{week_to_month_label(2026, w)} {x:,.0f} 원' if x > 0 else '' for w, x in zip(weeks, data_2026)], textposition='outside', hovertemplate='%{text}<extra></extra>'))
                month_ranges = get_month_week_ranges(2025)
                visible_month_ranges = [(m, max(x0, 2), x1) for m, x0, x1 in month_ranges if x1 >= 2]
                shapes = []
                for i, (month, x0, x1) in enumerate(visible_month_ranges):
                    fill_color = 'rgba(200, 220, 240, 0.35)' if i % 2 == 0 else 'rgba(230, 235, 245, 0.5)'
                    shapes.append(dict(type='rect', xref='x', yref='paper', x0=x0 - 0.5, x1=x1 + 0.5, y0=0, y1=1, fillcolor=fill_color, line=dict(width=0), layer='below'))
                for month, x0, x1 in visible_month_ranges:
                    shapes.append(dict(type='line', xref='x', yref='paper', x0=x1 + 0.5, x1=x1 + 0.5, y0=0, y1=1, line=dict(color='rgba(180, 190, 200, 0.7)', width=1), layer='below'))
                shapes.append(dict(type='line', xref='x', yref='paper', x0=1.5, x1=1.5, y0=0, y1=1, line=dict(color='rgba(180, 190, 200, 0.7)', width=1), layer='below'))
                tickvals = [(x0 + x1) / 2 for month, x0, x1 in visible_month_ranges]
                ticktext = [f'{month}월' for month, x0, x1 in visible_month_ranges]
                fig.update_layout(title=chart_title, xaxis_title='주차', yaxis_title='매출이익금 (원)', barmode='group', shapes=shapes, xaxis=dict(tickmode='array', tickvals=tickvals, ticktext=ticktext, range=[1.5, 52.5], showgrid=False, ticklen=4), yaxis=dict(tickformat=',.0f'), height=500, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                st.plotly_chart(fig, use_container_width=True)
            
            if not hide_platform_profit_charts and compare_df is not None and len(compare_df) > 0 and date_col_compare and profit_col_compare:
                # O열 구분 값으로 4개 그래프 생성 (1.전체 2.삼성몰 3.타 폐쇄몰 4.2파트)
                if gubun_col is not None:
                    구분_그래프_목록 = [
                        (None, '전체 매출이익금'),           # 1. 전체 그래프 (필터 없음)
                        (['삼성몰'], '삼성몰 매출이익금'),   # 2. 삼성몰 그래프
                        (['타 폐쇄몰'], '타 폐쇄몰 매출이익금'),  # 3. 타 폐쇄몰 그래프
                        (['2파트'], '2파트 매출이익금'),     # 4. 2파트 그래프
                    ]
                    for idx, (구분_필터, 차트_제목) in enumerate(구분_그래프_목록):
                        w25, w26 = build_weekly_from_compare(구분_필터)
                        draw_compare_chart(w25, w26, 차트_제목)
                        total_25 = sum(w25.values())
                        total_26 = sum(w26.values())
                        st.markdown(f"**{차트_제목}** · 2025년 합계: **{total_25:,.0f}원**  |  2026년 합계: **{total_26:,.0f}원**")
                        if idx == 0:
                            st.caption("※ 발주서 기준 금액이며, 반품/취소는 반영되지 않았습니다.")
                        st.markdown("---")
                else:
                    # 구분 컬럼 없으면 전체만 표시
                    w25, w26 = build_weekly_from_compare(None)
                    draw_compare_chart(w25, w26, '전체 매출이익금')
                    total_25 = sum(w25.values())
                    total_26 = sum(w26.values())
                    st.markdown(f"**전체 매출이익금** · 2025년 합계: **{total_25:,.0f}원**  |  2026년 합계: **{total_26:,.0f}원**")
                    st.caption("발주서 기준 금액이며, 반품/취소는 반영되지 않았습니다.")
                    st.caption("💡 O열 '구분' 컬럼이 있으면 전체·삼성몰·타 폐쇄몰·2파트 4개 그래프가 표시됩니다.")
            elif not hide_platform_profit_charts:
                if not os.path.exists(compare_path):
                    st.info("💡 '전년도 매출 비교.xlsx' 파일을 스크립트와 같은 폴더에 넣어주세요.")
                else:
                    st.info("💡 전년도 매출 비교.xlsx에서 주문일(날짜), 매출총이익 컬럼을 확인해주세요.")
            
        
        except Exception as e:
            if not hide_platform_profit_charts:
                st.warning(f"⚠️ 전년도 매출이익금 추이 그래프 생성 중 오류 발생: {str(e)}")
        
        st.markdown("---")

        # 엑셀 로우 데이터 기반 상품 분석
        st.markdown('<span id="section_sales" class="anchor"></span>', unsafe_allow_html=True)
        st.subheader("📦 상품 분석")

        # 상품코드 컬럼 찾기
        product_code_col = None
        product_code_keywords = ['상품코드', 'product', 'code', '코드', '상품', '제품코드', '상품 코드', '제품 코드']
        for col in df.columns:
            col_str = str(col).lower()
            if any(keyword in col_str for keyword in product_code_keywords) and '상품명' not in col_str and '상품이름' not in col_str:
                product_code_col = col
                break

        # 상품코드 컬럼을 찾지 못한 경우 C열(인덱스 2) 또는 D열(인덱스 3) 시도
        if product_code_col is None:
            if len(df.columns) > 2:
                product_code_col = df.columns[2]  # C열
            elif len(df.columns) > 3:
                product_code_col = df.columns[3]  # D열

        # 상품명 컬럼 찾기
        product_name_col = None
        product_name_keywords = ['상품명', 'product name', '품명', 'name', '제품명', '상품이름']
        for col in df.columns:
            col_str = str(col).lower()
            if any(keyword in col_str for keyword in product_name_keywords):
                product_name_col = col
                break

        # 판매 수량 컬럼 찾기
        sales_qty_col = None
        sales_qty_keywords = ['판매수량', '판매 수량', '수량', 'quantity', 'qty', '판매량', 'sales', 'quantity']
        for col in df.columns:
            col_str = str(col).lower()
            if any(keyword in col_str for keyword in sales_qty_keywords):
                sales_qty_col = col
                break

        # 판매 수량 컬럼을 찾지 못한 경우 I열(인덱스 8) 시도
        if sales_qty_col is None:
            i_column_index = 8  # I열은 9번째 (0-based index: 8)
            if len(df.columns) > i_column_index:
                sales_qty_col = df.columns[i_column_index]

        # 매출이익금 컬럼 찾기 (amount_col 사용)
        profit_col = amount_col if amount_col is not None else None

        # 상품 분석이 가능한지 확인
        if product_code_col and sales_qty_col:
            # 데이터 타입 변환
            if df[sales_qty_col].dtype == 'object':
                df[sales_qty_col] = pd.to_numeric(df[sales_qty_col], errors='coerce')
            if profit_col and df[profit_col].dtype == 'object':
                df[profit_col] = pd.to_numeric(df[profit_col], errors='coerce')

            # 1. 많이 판매된 상품 TOP 10 (판매수량 기준)
            st.markdown("#### 🏆 많이 판매된 상품 TOP 10")
            product_sales_qty = df.groupby(product_code_col)[sales_qty_col].sum().reset_index()
            product_sales_qty.columns = ['상품코드', '총판매수량']
            product_sales_qty = product_sales_qty.sort_values('총판매수량', ascending=False).head(10)

            # 상품명 추가
            if product_name_col:
                product_name_mapping = df.groupby(product_code_col)[product_name_col].apply(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else x.iloc[0]).to_dict()
                product_sales_qty['상품명'] = product_sales_qty['상품코드'].map(product_name_mapping)
                product_sales_qty['상품명'] = product_sales_qty['상품명'].fillna(product_sales_qty['상품코드'])
                display_cols = ['상품명', '총판매수량']
            else:
                product_sales_qty['상품명'] = product_sales_qty['상품코드']
                display_cols = ['상품명', '총판매수량']

            # 표시용 데이터 포맷팅
            product_sales_qty_display = product_sales_qty.copy()
            product_sales_qty_display['총판매수량'] = product_sales_qty_display['총판매수량'].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "0")

            st.dataframe(product_sales_qty_display[display_cols], use_container_width=True, hide_index=True)

            # 2. 대량으로 판매된 상품 (개별 판매수량이 큰 상품들)
            st.markdown("#### 📦 대량 판매 상품 TOP 10")
            # 개별 거래에서 판매수량이 큰 것들만 필터링 (예: 100개 이상)
            large_qty_threshold = 10  # 임계값 설정
            large_qty_products = df[df[sales_qty_col] >= large_qty_threshold].copy()

            if len(large_qty_products) > 0:
                large_qty_summary = large_qty_products.groupby(product_code_col)[sales_qty_col].sum().reset_index()
                large_qty_summary.columns = ['상품코드', '총판매수량']
                large_qty_summary = large_qty_summary.sort_values('총판매수량', ascending=False).head(10)

                # 상품명 추가
                if product_name_col:
                    large_qty_summary['상품명'] = large_qty_summary['상품코드'].map(product_name_mapping)
                    large_qty_summary['상품명'] = large_qty_summary['상품명'].fillna(large_qty_summary['상품코드'])
                    display_cols = ['상품명', '총판매수량']
                else:
                    large_qty_summary['상품명'] = large_qty_summary['상품코드']
                    display_cols = ['상품명', '총판매수량']

                # 표시용 데이터 포맷팅
                large_qty_display = large_qty_summary.copy()
                large_qty_display['총판매수량'] = large_qty_display['총판매수량'].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "0")
                
                # 순위 추가
                large_qty_display.insert(0, '순위', range(1, len(large_qty_display) + 1))
                display_cols = ['순위'] + display_cols

                # 데이터프레임 높이 설정 (행 수에 따라 동적 조정, 최소 10행 표시)
                num_rows = len(large_qty_display)
                height = max(300, num_rows * 35 + 100)  # 각 행당 35px + 헤더 100px
                
                # 순위 컬럼 좌측 정렬을 위한 CSS 스타일
                st.markdown("""
                <style>
                .stDataFrame table thead th:first-child,
                .stDataFrame table tbody td:first-child {
                    text-align: left !important;
                }
                div[data-testid="stDataFrame"] table thead th:first-child,
                div[data-testid="stDataFrame"] table tbody td:first-child {
                    text-align: left !important;
                }
                </style>
                """, unsafe_allow_html=True)
                
                st.dataframe(
                    large_qty_display[display_cols], 
                    use_container_width=True, 
                    hide_index=True,
                    height=height
                )
                
                # 실제 표시된 상품 수 정보
                if num_rows < 10:
                    st.caption(f"※ 총 {num_rows}개의 상품이 표시되었습니다.")
            else:
                st.info(f"판매수량 {large_qty_threshold}개 이상인 상품이 없습니다.")

            # 3. 매출이익금이 높은 상품 TOP 10
            if profit_col:
                st.markdown("#### 💰 매출이익금이 높은 상품 TOP 10")
                product_profit = df.groupby(product_code_col)[profit_col].sum().reset_index()
                product_profit.columns = ['상품코드', '총매출이익금']
                product_profit = product_profit.sort_values('총매출이익금', ascending=False).head(10)

                # 상품명 추가
                if product_name_col:
                    product_profit['상품명'] = product_profit['상품코드'].map(product_name_mapping)
                    product_profit['상품명'] = product_profit['상품명'].fillna(product_profit['상품코드'])
                    display_cols = ['상품명', '총매출이익금']
                else:
                    product_profit['상품명'] = product_profit['상품코드']
                    display_cols = ['상품명', '총매출이익금']

                # 표시용 데이터 포맷팅
                product_profit_display = product_profit.copy()
                product_profit_display['총매출이익금'] = product_profit_display['총매출이익금'].apply(lambda x: f"{x:,.0f}원" if pd.notna(x) else "0원")

                st.dataframe(product_profit_display[display_cols], use_container_width=True, hide_index=True)
            else:
                st.warning("⚠️ 매출이익금 컬럼을 찾을 수 없어 매출이익금 분석을 할 수 없습니다.")

        else:
            st.warning("⚠️ 상품코드 또는 판매수량 컬럼을 찾을 수 없어 상품 분석을 할 수 없습니다.")

        st.markdown('<span id="section_data_analysis" class="anchor"></span>', unsafe_allow_html=True)
        st.markdown("---")
        
        # 선택된 월 데이터 분석 차트
        # month_label 설정: selected_month가 있으면 사용, 없으면 필터링된 데이터에서 월 추출
        if selected_month is not None:
            month_label = f"{selected_month}월"
        elif len(df) > 0 and '월' in df.columns:
            # 필터링된 데이터에서 고유한 월 추출 (하나의 월만 있는 경우)
            unique_months = sorted(df['월'].dropna().unique())
            if len(unique_months) == 1:
                month_label = f"{int(unique_months[0])}월"
            else:
                month_label = "월"
        else:
            month_label = "월"
        st.subheader(f"📊 {month_label} 데이터 분석")
        
        # 주차 번호를 한국어로 변환하는 함수
        def week_to_korean(week_num, min_week=None, month=None, max_week=None):
            """주차 번호를 한국어로 변환 (예: 45 -> '11월 첫째주' 또는 '12월 첫째주')"""
            week_korean = ['첫째', '둘째', '셋째', '넷째', '다섯째']
            month_label = f"{month}월" if month is not None else "월"
            if min_week is not None:
                # 최소 주차를 기준으로 상대적 주차 계산
                relative_week = week_num - min_week
                if 0 <= relative_week < len(week_korean):
                    # 다섯째주는 실제 데이터에 존재할 때만 표시 (relative_week이 4인 경우만)
                    if relative_week == 4:
                        # max_week이 min_week + 4 이상이어야 다섯째주가 존재
                        if max_week is not None and max_week >= min_week + 4:
                            return f"{month_label} {week_korean[relative_week]}주"
                        else:
                            # 다섯째주가 존재하지 않으면 None 반환 (표시하지 않음)
                            return None
                    else:
                        return f"{month_label} {week_korean[relative_week]}주"
            return f"{month_label} {week_num}주"
        
        # 주간별 또는 일별 트렌드 (날짜 컬럼이 있는 경우)
        if '년월' in df.columns or len(date_columns) > 0:
            if len(date_columns) > 0:
                date_col = date_columns[0]
                # 주간별 집계 (지난주 금요일 ~ 이번주 목요일 기준)
                df['주차'] = df[date_col].apply(get_custom_week)
                df['일'] = df[date_col].dt.day
                
                # 선택된 월의 최소 주차 번호 찾기 (첫째주 기준)
                min_week = df['주차'].min() if len(df) > 0 and df['주차'].notna().any() else None
                max_week = df['주차'].max() if len(df) > 0 and df['주차'].notna().any() else None
                
                # selected_month가 None인 경우 데이터에서 월 추출
                month_for_week_label = selected_month
                if month_for_week_label is None and len(df) > 0 and '월' in df.columns:
                    unique_months = sorted(df['월'].dropna().unique())
                    if len(unique_months) == 1:
                        month_for_week_label = int(unique_months[0])
                
                if selected_month is not None:
                    # 선택 월에서는 입력 데이터 날짜를 기준으로 실제 n째주 라벨을 자동 반영
                    df['주차_한글'] = df[date_col].apply(lambda x: get_month_week_label(x, selected_month))
                else:
                    # selected_month가 없을 때만 기존 상대 주차 라벨 방식 사용
                    df['주차_한글'] = df['주차'].apply(lambda x: week_to_korean(x, min_week, month_for_week_label, max_week))

                # None 값 제거 (선택 월 기준에 맞지 않는 주차 포함)
                df = df[df['주차_한글'].notna()]
                
                # 주차 산출 내역 표시
                if min_week is not None and '주차_한글' in df.columns:
                    st.markdown("#### 📅 주차 산출 내역")
                    st.info("**산출 기준:** 지난주 금요일 ~ 이번주 목요일까지")
                    
                    # 고유한 주차 목록 가져오기
                    unique_weeks = df[df['주차'].notna()]['주차'].unique()
                    unique_weeks_sorted = sorted(unique_weeks)
                    
                    # 주차별 날짜 범위 표시
                    week_info_list = []
                    # 년도 추출
                    year = None
                    if '년' in df.columns and len(df) > 0:
                        year = int(df['년'].dropna().iloc[0]) if df['년'].notna().any() else None
                    
                    # selected_month가 None인 경우 기본값 사용 (데이터에서 추출하거나 현재 월)
                    month_for_calculation = selected_month
                    if month_for_calculation is None:
                        if '월' in df.columns and len(df) > 0:
                            month_for_calculation = int(df['월'].dropna().iloc[0]) if df['월'].notna().any() else None
                        if month_for_calculation is None:
                            month_for_calculation = pd.Timestamp.now().month
                    
                    today_date = pd.Timestamp.now().normalize()
                    if selected_month is not None:
                        # 선택 월 주차는 시작일(금요일) 기준 월에만 반영
                        # 예: 2026-02-27(금) ~ 2026-03-05(목)은 2월로 반영하고 3월에서는 제외
                        display_year = year if year is not None else pd.Timestamp.now().year
                        first_day = pd.Timestamp(year=display_year, month=selected_month, day=1)
                        days_to_prev_friday = (first_day.weekday() - 4) % 7
                        first_week_start = first_day - pd.Timedelta(days=days_to_prev_friday)
                        week_korean_labels = ['첫째', '둘째', '셋째', '넷째', '다섯째']

                        for idx in range(5):
                            start_date = first_week_start + pd.Timedelta(days=idx * 7)
                            end_date = start_date + pd.Timedelta(days=6)

                            # 시작일(금요일)이 선택 월인 구간만 해당 월 주차로 표시
                            if start_date.month != selected_month:
                                continue
                            # 해당 주차 종료일(목요일)이 지난 후에만 표기
                            if today_date <= end_date.normalize():
                                continue

                            weekdays_kr = ['월', '화', '수', '목', '금', '토', '일']
                            start_weekday_kr = weekdays_kr[start_date.weekday()]
                            end_weekday_kr = weekdays_kr[end_date.weekday()]

                            week_info_list.append({
                                '주차': f"{selected_month}월 {week_korean_labels[idx]}주",
                                '시작일': start_date.strftime('%Y-%m-%d') + f' ({start_weekday_kr})',
                                '종료일': end_date.strftime('%Y-%m-%d') + f' ({end_weekday_kr})',
                                '기간': f"{start_date.strftime('%m/%d')} ~ {end_date.strftime('%m/%d')}"
                            })
                    else:
                        for week_num in unique_weeks_sorted:
                            start_date, end_date = get_week_date_range(week_num, month_for_calculation, min_week, year)
                            if start_date and end_date:
                                # 해당 주차 종료일(목요일)이 지난 후에만 표기
                                if today_date <= end_date.normalize():
                                    continue
                                # 시작일(금요일)의 월을 기준으로 주차 레이블 결정
                                start_month = start_date.month

                                # 시작일이 선택된 월과 다르면 해당 주차는 제외 (다른 월에서 표시되어야 함)
                                if selected_month is not None and start_month != selected_month:
                                    continue  # 이 주차는 제외하고 다음 주차로

                                # 시작일이 선택된 월과 같으면 기존 레이블 사용
                                week_korean = df[df['주차'] == week_num]['주차_한글'].iloc[0] if len(df[df['주차'] == week_num]) > 0 else f"{month_label} {week_num}주"

                                # 요일을 한국어로 변환
                                weekdays_kr = ['월', '화', '수', '목', '금', '토', '일']
                                start_weekday_kr = weekdays_kr[start_date.weekday()]
                                end_weekday_kr = weekdays_kr[end_date.weekday()]

                                week_info_list.append({
                                    '주차': week_korean,
                                    '시작일': start_date.strftime('%Y-%m-%d') + f' ({start_weekday_kr})',
                                    '종료일': end_date.strftime('%Y-%m-%d') + f' ({end_weekday_kr})',
                                    '기간': f"{start_date.strftime('%m/%d')} ~ {end_date.strftime('%m/%d')}"
                                })
                    
                    if week_info_list:
                        week_info_df = pd.DataFrame(week_info_list)
                        st.dataframe(week_info_df[['주차', '기간', '시작일', '종료일']], use_container_width=True, hide_index=True)
                    
                    st.markdown("---")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # 주차별 총 판매수량과 매출이익금 통합 그래프
                    weekly_data = df.groupby(['주차', '주차_한글']).size().reset_index(name='건수')
                    weekly_data = weekly_data.sort_values('주차')
                    
                    # 매출이익금이 있으면 함께 표시
                    if amount_col and amount_col in df.columns:
                        if df[amount_col].dtype == 'object':
                            df[amount_col] = pd.to_numeric(df[amount_col], errors='coerce')
                        weekly_profit = df.groupby(['주차', '주차_한글'])[amount_col].sum().reset_index()
                        weekly_profit.columns = ['주차', '주차_한글', '매출이익금']
                        weekly_profit = weekly_profit.sort_values('주차')
                        weekly_combined = weekly_data.merge(weekly_profit, on=['주차', '주차_한글'], how='left')
                        
                        # 이중 Y축 그래프 생성
                        from plotly.subplots import make_subplots
                        fig_weekly = make_subplots(specs=[[{"secondary_y": True}]])
                        
                        # 파스텔 톤 colorscale 정의
                        pastel_blue = [[0, '#E8F4F8'], [0.5, '#B8E6F5'], [1, '#87CEEB']]
                        pastel_green = [[0, '#E8F5E9'], [0.5, '#C8E6C9'], [1, '#A5D6A7']]
                        
                        # 총 판매수량 바 차트 (왼쪽 Y축) - 파스텔 톤 적용
                        fig_weekly.add_trace(
                            go.Bar(
                                x=weekly_combined['주차_한글'],
                                y=weekly_combined['건수'],
                                name='총 판매수량',
                                marker=dict(
                                    color=weekly_combined['건수'],
                                    colorscale=pastel_blue,
                                    showscale=True,
                                    colorbar=dict(
                                        title=dict(text="총 판매수량", side="right"),
                                        x=1.25,
                                        len=0.35,
                                        y=0.7,
                                        yanchor='middle',
                                        thickness=15
                                    )
                                ),
                                hovertemplate='<b>%{x}</b><br>총 판매수량: %{y}<extra></extra>'
                            ),
                            secondary_y=False,
                        )
                        
                        # 매출이익금 라인 차트 (오른쪽 Y축) - 파스텔 톤 적용
                        fig_weekly.add_trace(
                            go.Scatter(
                                x=weekly_combined['주차_한글'],
                                y=weekly_combined['매출이익금'],
                                name='매출이익금',
                                mode='lines+markers',
                                line=dict(color='#A5D6A7', width=3),
                                marker=dict(
                                    size=8,
                                    color=weekly_combined['매출이익금'],
                                    colorscale=pastel_green,
                                    showscale=True,
                                    colorbar=dict(
                                        title=dict(text="매출이익금", side="right"),
                                        x=1.25,
                                        len=0.35,
                                        y=0.25,
                                        yanchor='middle',
                                        thickness=15
                                    )
                                ),
                                hovertemplate='<b>%{x}</b><br>매출이익금: %{y:,.0f}원<extra></extra>'
                            ),
                            secondary_y=True,
                        )
                        
                        fig_weekly.update_xaxes(
                            title_text="주차",
                            title_font=dict(size=16, color='black', family='Arial Black'),
                            categoryorder='array',
                            categoryarray=weekly_combined['주차_한글'].tolist(),
                            showgrid=False  # 세로 보조 눈금선 숨김
                        )
                        fig_weekly.update_yaxes(
                            title_text="총 판매수량",
                            secondary_y=False,
                            showgrid=True
                        )
                        fig_weekly.update_yaxes(
                            title_text="매출이익금 (원)",
                            secondary_y=True,
                            tickformat=',',
                            showgrid=False,  # 오른쪽 Y축 그리드선 비활성화
                            showticklabels=False  # 보조 Y축 눈금선 제거
                        )
                        # month_label 설정: selected_month가 있으면 사용, 없으면 필터링된 데이터에서 월 추출
                        if selected_month is not None:
                            month_label = f"{selected_month}월"
                        elif len(df) > 0 and '월' in df.columns:
                            unique_months = sorted(df['월'].dropna().unique())
                            if len(unique_months) == 1:
                                month_label = f"{int(unique_months[0])}월"
                            else:
                                month_label = "월"
                        else:
                            month_label = "월"
                        fig_weekly.update_layout(
                            title=f'{month_label} 주차별 총 판매수량 및 매출이익금',
                            hovermode='x unified',
                            showlegend=True,
                            legend=dict(
                                x=0.02,
                                y=0.98,
                                xanchor='left',
                                yanchor='top',
                                bgcolor='rgba(255,255,255,0.8)',
                                bordercolor='rgba(0,0,0,0.2)',
                                borderwidth=1
                            ),
                            margin=dict(r=250)  # 오른쪽 마진 대폭 증가 (컬러바 공간 확보)
                        )
                    else:
                        # 매출이익금이 없으면 총 판매수량만 표시
                        month_label = f"{selected_month}월" if selected_month is not None else "월"
                        fig_weekly = px.bar(
                            weekly_data,
                            x='주차_한글',
                            y='건수',
                            title=f'{month_label} 주차별 총 판매수량',
                            labels={'주차_한글': '주차', '건수': '총 판매수량'},
                            color='건수',
                            color_continuous_scale='Blues',
                            category_orders={'주차_한글': weekly_data['주차_한글'].tolist()}
                        )
                        fig_weekly.update_layout(
                            xaxis_title="주차",
                            yaxis_title="총 판매수량"
                        )
                        fig_weekly.update_traces(
                            hovertemplate='<b>%{x}</b><br>총 판매수량: %{y}<extra></extra>'
                        )
                    
                    st.plotly_chart(fig_weekly, use_container_width=True)
                
                with col2:
                    # 일별 총 판매수량과 매출이익금 통합 그래프
                    daily_data = df.groupby('일').size().reset_index(name='건수')
                    
                    # 매출이익금이 있으면 함께 표시
                    if amount_col and amount_col in df.columns:
                        if df[amount_col].dtype == 'object':
                            df[amount_col] = pd.to_numeric(df[amount_col], errors='coerce')
                        daily_profit = df.groupby('일')[amount_col].sum().reset_index()
                        daily_profit.columns = ['일', '매출이익금']
                        daily_combined = daily_data.merge(daily_profit, on='일', how='left')
                        
                        # 이중 Y축 그래프 생성
                        from plotly.subplots import make_subplots
                        fig_daily = make_subplots(specs=[[{"secondary_y": True}]])
                        
                        # 파스텔 톤 colorscale 정의
                        pastel_blue = [[0, '#E8F4F8'], [0.5, '#B8E6F5'], [1, '#87CEEB']]
                        pastel_green = [[0, '#E8F5E9'], [0.5, '#C8E6C9'], [1, '#A5D6A7']]
                        
                        # 총 판매수량 라인 차트 (왼쪽 Y축) - 파스텔 톤 적용
                        fig_daily.add_trace(
                            go.Scatter(
                                x=daily_combined['일'],
                                y=daily_combined['건수'],
                                name='총 판매수량',
                                mode='lines+markers',
                                line=dict(color='#87CEEB', width=2),
                                marker=dict(
                                    size=6,
                                    color=daily_combined['건수'],
                                    colorscale=pastel_blue,
                                    showscale=True,
                                    colorbar=dict(
                                        title=dict(text="총 판매수량", side="right"),
                                        x=1.25,
                                        len=0.35,
                                        y=0.7,
                                        yanchor='middle',
                                        thickness=15
                                    )
                                ),
                                hovertemplate='<b>일: %{x}</b><br>총 판매수량: %{y}<extra></extra>'
                            ),
                            secondary_y=False,
                        )
                        
                        # 매출이익금 라인 차트 (오른쪽 Y축) - 파스텔 톤 적용
                        fig_daily.add_trace(
                            go.Scatter(
                                x=daily_combined['일'],
                                y=daily_combined['매출이익금'],
                                name='매출이익금',
                                mode='lines+markers',
                                line=dict(color='#A5D6A7', width=2),
                                marker=dict(
                                    size=6,
                                    color=daily_combined['매출이익금'],
                                    colorscale=pastel_green,
                                    showscale=True,
                                    colorbar=dict(
                                        title=dict(text="매출이익금", side="right"),
                                        x=1.25,
                                        len=0.35,
                                        y=0.25,
                                        yanchor='middle',
                                        thickness=15
                                    )
                                ),
                                hovertemplate='<b>일: %{x}</b><br>매출이익금: %{y:,.0f}원<extra></extra>'
                            ),
                            secondary_y=True,
                        )
                        
                        fig_daily.update_xaxes(
                            title_text="일",
                            title_font=dict(size=16, color='black', family='Arial Black'),
                            showgrid=False  # 세로 보조 눈금선 숨김
                        )
                        fig_daily.update_yaxes(
                            title_text="총 판매수량",
                            secondary_y=False,
                            showgrid=True
                        )
                        fig_daily.update_yaxes(
                            title_text="매출이익금 (원)",
                            secondary_y=True,
                            tickformat=',',
                            showgrid=False,  # 오른쪽 Y축 그리드선 비활성화
                            showticklabels=False  # 보조 Y축 눈금선 제거
                        )
                        # month_label 설정: selected_month가 있으면 사용, 없으면 필터링된 데이터에서 월 추출
                        if selected_month is not None:
                            month_label = f"{selected_month}월"
                        elif len(df) > 0 and '월' in df.columns:
                            unique_months = sorted(df['월'].dropna().unique())
                            if len(unique_months) == 1:
                                month_label = f"{int(unique_months[0])}월"
                            else:
                                month_label = "월"
                        else:
                            month_label = "월"
                        fig_daily.update_layout(
                            title=f'{month_label} 일별 총 판매수량 및 매출이익금 추이',
                            hovermode='x unified',
                            showlegend=True,
                            legend=dict(
                                x=0.02,
                                y=0.98,
                                xanchor='left',
                                yanchor='top',
                                bgcolor='rgba(255,255,255,0.8)',
                                bordercolor='rgba(0,0,0,0.2)',
                                borderwidth=1
                            ),
                            margin=dict(r=250)  # 오른쪽 마진 대폭 증가 (컬러바 공간 확보)
                        )
                    else:
                        # 매출이익금이 없으면 총 판매수량만 표시
                        month_label = f"{selected_month}월" if selected_month is not None else "월"
                        fig_daily = px.line(
                            daily_data,
                            x='일',
                            y='건수',
                            title=f'{month_label} 일별 총 판매수량 추이',
                            markers=True
                        )
                        fig_daily.update_layout(
                            xaxis_title="일",
                            yaxis_title="총 판매수량",
                            hovermode='x unified'
                        )
                    
                    st.plotly_chart(fig_daily, use_container_width=True)
        else:
            # 날짜 정보가 없으면 전체 총 판매수량 표시
            st.info("날짜 정보가 없어 트렌드 분석을 할 수 없습니다.")
        
        # 플랫폼별 성과 분석
        st.subheader("📊 플랫폼별 성과")
        
        # A열 찾기 (플랫폼, 1번째 컬럼, 인덱스 0)
        platform_col = None
        if len(df.columns) > 0:
            platform_col = df.columns[0]  # A열 (1번째 컬럼)
        
        # I열 찾기 (판매 수량, 9번째 컬럼, 인덱스 8)
        i_column_index = 8  # I열은 9번째 (0-based index: 8)
        sales_qty_col = None
        if len(df.columns) > i_column_index:
            sales_qty_col = df.columns[i_column_index]
        
        # O열 찾기 (이익률, 15번째 컬럼, 인덱스 14)
        o_column_index = 14  # O열은 15번째 (0-based index: 14)
        profit_rate_col = None
        if len(df.columns) > o_column_index:
            profit_rate_col = df.columns[o_column_index]
        
        if platform_col is not None and revenue_col is not None:
            # 플랫폼별 집계
            platform_summary = df.groupby(platform_col).agg({
                revenue_col: 'sum',  # 매출 (J열)
            }).reset_index()
            platform_summary.columns = ['플랫폼', '매출']
            
            # I열 합계 추가 (최다 판매 판단용)
            if sales_qty_col is not None:
                if df[sales_qty_col].dtype == 'object':
                    df[sales_qty_col] = pd.to_numeric(df[sales_qty_col], errors='coerce')
                sales_qty_sum = df.groupby(platform_col)[sales_qty_col].sum().reset_index()
                sales_qty_sum.columns = ['플랫폼', '판매수량']
                # merge 전에 판매수량을 숫자형으로 확실히 변환
                sales_qty_sum['판매수량'] = pd.to_numeric(sales_qty_sum['판매수량'], errors='coerce').fillna(0).astype(int)
                platform_summary = platform_summary.merge(sales_qty_sum, on='플랫폼', how='left')
                # merge 후에도 다시 한 번 숫자형으로 변환 (안전장치)
                platform_summary['판매수량'] = pd.to_numeric(platform_summary['판매수량'], errors='coerce').fillna(0).astype(int)
            
            # O열 이익률 추가
            if profit_rate_col is not None:
                if df[profit_rate_col].dtype == 'object':
                    df[profit_rate_col] = pd.to_numeric(df[profit_rate_col], errors='coerce')
                # 플랫폼별 평균 이익률 계산
                profit_rate_avg = df.groupby(platform_col)[profit_rate_col].mean().reset_index()
                profit_rate_avg.columns = ['플랫폼', '이익률']
                platform_summary = platform_summary.merge(profit_rate_avg, on='플랫폼', how='left')
            else:
                # O열이 없으면 매출과 매출원가로 이익률 계산
                if cost_col is not None:
                    platform_cost = df.groupby(platform_col)[cost_col].sum().reset_index()
                    platform_cost.columns = ['플랫폼', '매출원가']
                    platform_summary = platform_summary.merge(platform_cost, on='플랫폼', how='left')
                    platform_summary['이익률'] = ((platform_summary['매출'] - platform_summary['매출원가']) / platform_summary['매출'] * 100).round(2)
                    platform_summary = platform_summary.drop('매출원가', axis=1)
            
            # 비고 컬럼 초기화
            platform_summary['비고'] = ''
            
            # 최다 판매 플랫폼 찾기 (I열 합계가 가장 높은 플랫폼)
            if sales_qty_col is not None and '판매수량' in platform_summary.columns:
                max_sales_platform = platform_summary.loc[platform_summary['판매수량'].idxmax(), '플랫폼']
                platform_summary.loc[platform_summary['플랫폼'] == max_sales_platform, '비고'] += '최다 판매 / '
            
            # 수수료 높은 플랫폼 찾기 (매출 대비 비용 비율이 높은 플랫폼)
            if cost_col is not None:
                platform_cost = df.groupby(platform_col)[cost_col].sum().reset_index()
                platform_cost.columns = ['플랫폼', '매출원가']
                platform_summary_with_cost = platform_summary.merge(platform_cost, on='플랫폼', how='left')
                platform_summary_with_cost['수수료율'] = (platform_summary_with_cost['매출원가'] / platform_summary_with_cost['매출'] * 100).round(2)
                max_fee_platform = platform_summary_with_cost.loc[platform_summary_with_cost['수수료율'].idxmax(), '플랫폼']
                platform_summary.loc[platform_summary['플랫폼'] == max_fee_platform, '비고'] += '수수료 높음 / '
            
            # 이익률 우수 플랫폼 찾기 (O열 이익률이 가장 높은 플랫폼)
            if '이익률' in platform_summary.columns:
                max_profit_rate_platform = platform_summary.loc[platform_summary['이익률'].idxmax(), '플랫폼']
                platform_summary.loc[platform_summary['플랫폼'] == max_profit_rate_platform, '비고'] += '이익률 우수'
            
            # 비고 컬럼의 끝 '/' 제거
            platform_summary['비고'] = platform_summary['비고'].str.rstrip(' / ')
            
            # 표시용 데이터 준비
            platform_display = platform_summary.copy()
            platform_display['매출'] = platform_display['매출'].apply(lambda x: f"{x:,.0f}원" if pd.notna(x) else "0원")
            if '판매수량' in platform_display.columns:
                platform_display['판매수량'] = platform_display['판매수량'].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "0")
            if '이익률' in platform_display.columns:
                def format_profit_rate(x):
                    if pd.notna(x) and x != 0:
                        # 값이 1 미만이면 100을 곱해서 백분율로 변환
                        if abs(float(x)) < 1:
                            return f"{float(x) * 100:.1f}%"
                        else:
                            return f"{float(x):.1f}%"
                    else:
                        return "0%"
                platform_display['이익률'] = platform_display['이익률'].apply(format_profit_rate)
            
            # 표시 컬럼 선택
            display_cols = ['플랫폼', '매출']
            if '이익률' in platform_display.columns:
                display_cols.append('이익률')
            if '판매수량' in platform_display.columns:
                display_cols.append('판매수량')
            display_cols.append('비고')
            
            # 정렬 전에 숫자형 컬럼을 명시적으로 숫자형으로 변환 (안전장치)
            # 모든 숫자 컬럼에 대해 동일한 방식으로 처리
            if '판매수량' in platform_summary.columns:
                # 판매수량도 매출/이익률과 동일한 방식으로 처리
                if platform_summary['판매수량'].dtype == 'object' or str(platform_summary['판매수량'].dtype).startswith('string'):
                    # 문자열인 경우 숫자로 변환 (콤마, 공백 제거)
                    platform_summary['판매수량'] = platform_summary['판매수량'].astype(str).str.replace(',', '').str.replace(' ', '').str.replace('원', '')
                platform_summary['판매수량'] = pd.to_numeric(platform_summary['판매수량'], errors='coerce').fillna(0)
            
            if '이익률' in platform_summary.columns:
                # 이익률도 문자열일 수 있으므로 처리
                if platform_summary['이익률'].dtype == 'object' or str(platform_summary['이익률'].dtype).startswith('string'):
                    # 문자열인 경우 숫자로 변환 (% 제거)
                    platform_summary['이익률'] = platform_summary['이익률'].astype(str).str.replace('%', '').str.replace(',', '').str.replace(' ', '')
                platform_summary['이익률'] = pd.to_numeric(platform_summary['이익률'], errors='coerce').fillna(0)
            
            if '매출' in platform_summary.columns:
                # 매출도 문자열일 수 있으므로 처리
                if platform_summary['매출'].dtype == 'object' or str(platform_summary['매출'].dtype).startswith('string'):
                    # 문자열인 경우 숫자로 변환 (원, 콤마, 공백 제거)
                    platform_summary['매출'] = platform_summary['매출'].astype(str).str.replace('원', '').str.replace(',', '').str.replace(' ', '')
                platform_summary['매출'] = pd.to_numeric(platform_summary['매출'], errors='coerce').fillna(0)
            
            # 정렬 옵션
            sort_option = st.selectbox("정렬 기준", ['매출 높은 순', '이익률 높은 순', '판매수량 높은 순'], key='platform_sort')
            
            # 모든 정렬 옵션에 대해 동일한 방식으로 처리 (nlargest 사용)
            platform_summary_sorted = platform_summary.copy()
            
            if sort_option == '매출 높은 순':
                # 매출을 숫자형으로 확실히 변환
                platform_summary_sorted['매출'] = pd.to_numeric(platform_summary_sorted['매출'], errors='coerce').fillna(0)
                # nlargest를 사용하여 숫자 기준 정렬 보장
                platform_summary_sorted = platform_summary_sorted.nlargest(len(platform_summary_sorted), '매출').reset_index(drop=True)
            elif sort_option == '이익률 높은 순' and '이익률' in platform_summary_sorted.columns:
                # 이익률을 숫자형으로 확실히 변환
                platform_summary_sorted['이익률'] = pd.to_numeric(platform_summary_sorted['이익률'], errors='coerce').fillna(0)
                # nlargest를 사용하여 숫자 기준 정렬 보장
                platform_summary_sorted = platform_summary_sorted.nlargest(len(platform_summary_sorted), '이익률').reset_index(drop=True)
            elif sort_option == '판매수량 높은 순' and '판매수량' in platform_summary_sorted.columns:
                # 판매수량을 숫자형으로 확실히 변환 (매출/이익률과 동일한 방식)
                # 문자열인 경우 숫자로 변환
                if platform_summary_sorted['판매수량'].dtype == 'object' or str(platform_summary_sorted['판매수량'].dtype).startswith('string'):
                    platform_summary_sorted['판매수량'] = platform_summary_sorted['판매수량'].astype(str).str.replace(',', '').str.replace(' ', '').str.replace('원', '')
                
                # 판매수량을 숫자형으로 변환
                platform_summary_sorted['판매수량'] = pd.to_numeric(platform_summary_sorted['판매수량'], errors='coerce').fillna(0)
                
                # 정렬 전 판매수량 값 확인 및 디버깅
                # 판매수량 기준으로 직접 정렬 (nlargest 대신 sort_values 사용하여 더 확실하게)
                platform_summary_sorted = platform_summary_sorted.sort_values('판매수량', ascending=False, na_position='last', kind='mergesort').reset_index(drop=True)
                
                # 정렬 후 판매수량이 숫자형인지 확인
                platform_summary_sorted['판매수량'] = pd.to_numeric(platform_summary_sorted['판매수량'], errors='coerce').fillna(0)
                
                # 정렬 순서 검증: 내림차순이어야 함
                sales_qty_values = platform_summary_sorted['판매수량'].values
                if len(sales_qty_values) > 1:
                    is_descending = all(sales_qty_values[i] >= sales_qty_values[i+1] for i in range(len(sales_qty_values)-1))
                    if not is_descending:
                        # 정렬이 제대로 안 되었다면 다시 정렬 (nlargest 사용)
                        platform_summary_sorted = platform_summary_sorted.nlargest(len(platform_summary_sorted), '판매수량').reset_index(drop=True)
                        platform_summary_sorted['판매수량'] = pd.to_numeric(platform_summary_sorted['판매수량'], errors='coerce').fillna(0)
            else:
                platform_summary_sorted = platform_summary_sorted.reset_index(drop=True)
            
            # 정렬된 데이터 표시 (순서 유지하면서 문자열로 변환)
            # 정렬된 순서를 명시적으로 유지하기 위해 인덱스를 리셋한 복사본 사용
            platform_display_sorted = platform_summary_sorted.copy()
            platform_display_sorted = platform_display_sorted.reset_index(drop=True)
            
            # 정렬된 순서를 보존하기 위해 인덱스 순서대로 문자열 변환
            # 매출을 문자열로 변환 (순서는 이미 정렬됨)
            매출_formatted = []
            for idx in platform_display_sorted.index:
                val = platform_display_sorted.loc[idx, '매출']
                if pd.notna(val) and val != 0:
                    매출_formatted.append(f"{float(val):,.0f}원")
                else:
                    매출_formatted.append("0원")
            platform_display_sorted['매출'] = 매출_formatted
            
            # 판매수량을 문자열로 변환 (숫자형에서 직접 변환하여 순서 유지)
            if '판매수량' in platform_display_sorted.columns:
                # 판매수량이 숫자형인지 확인하고, 아니면 숫자형으로 변환
                if platform_display_sorted['판매수량'].dtype == 'object' or str(platform_display_sorted['판매수량'].dtype).startswith('string'):
                    platform_display_sorted['판매수량'] = pd.to_numeric(platform_display_sorted['판매수량'], errors='coerce').fillna(0)
                
                # 판매수량 정렬인 경우 정렬 순서를 명시적으로 보존
                if sort_option == '판매수량 높은 순':
                    # 판매수량 값들을 숫자형으로 변환하여 정렬 순서 확인
                    sales_qty_numeric = pd.to_numeric(platform_display_sorted['판매수량'], errors='coerce').fillna(0).values
                    # 내림차순인지 확인
                    if len(sales_qty_numeric) > 1:
                        is_descending = all(sales_qty_numeric[i] >= sales_qty_numeric[i+1] for i in range(len(sales_qty_numeric)-1))
                        if not is_descending:
                            # 정렬이 제대로 안 되었다면 다시 정렬
                            platform_display_sorted = platform_display_sorted.sort_values('판매수량', ascending=False, na_position='last', kind='mergesort').reset_index(drop=True)
                            platform_display_sorted['판매수량'] = pd.to_numeric(platform_display_sorted['판매수량'], errors='coerce').fillna(0)
                
                # 정렬된 순서를 완전히 보존하기 위해 iloc로 순서대로 변환
                sales_qty_formatted = []
                # 판매수량 값을 먼저 숫자형으로 확실히 변환
                platform_display_sorted['판매수량'] = pd.to_numeric(platform_display_sorted['판매수량'], errors='coerce').fillna(0)
                # 정렬된 순서대로 문자열로 변환
                for i in range(len(platform_display_sorted)):
                    val = platform_display_sorted.iloc[i]['판매수량']
                    # 숫자형인지 확인하고 변환
                    if pd.notna(val) and pd.notnull(val):
                        try:
                            num_val = float(val)
                            if num_val != 0:
                                sales_qty_formatted.append(f"{int(num_val):,}")
                            else:
                                sales_qty_formatted.append("0")
                        except (ValueError, TypeError):
                            sales_qty_formatted.append("0")
                    else:
                        sales_qty_formatted.append("0")
                # 판매수량 컬럼을 문자열 리스트로 교체 (순서 보존)
                platform_display_sorted['판매수량'] = sales_qty_formatted
            
            # 이익률을 문자열로 변환 (소수점 한 자리로 표시, 예: 79.8%)
            if '이익률' in platform_display_sorted.columns:
                이익률_formatted = []
                for idx in platform_display_sorted.index:
                    val = platform_display_sorted.loc[idx, '이익률']
                    if pd.notna(val) and val != 0:
                        # 값이 1 미만이면 100을 곱해서 백분율로 변환 (0.798 -> 79.8%)
                        # 값이 1 이상이면 그대로 사용 (79.8 -> 79.8%)
                        if abs(float(val)) < 1:
                            val_display = float(val) * 100
                        else:
                            val_display = float(val)
                        이익률_formatted.append(f"{val_display:.1f}%")
                    else:
                        이익률_formatted.append("0%")
                platform_display_sorted['이익률'] = 이익률_formatted
            
            # 테이블 표시 (정렬된 순서 그대로 표시)
            # 정렬된 순서를 명시적으로 보존하기 위해 인덱스를 재설정
            display_data = platform_display_sorted[display_cols].copy()
            display_data = display_data.reset_index(drop=True)
            
            # 판매수량 정렬인 경우 정렬 순서를 명시적으로 보존
            if sort_option == '판매수량 높은 순' and '판매수량' in display_data.columns:
                # 정렬 순서를 보존하기 위해 순서 번호 컬럼 추가
                display_data['_display_order'] = range(len(display_data))
                # 순서 번호로 정렬하여 정렬 순서 보장 (이미 정렬되어 있지만 확실히 하기 위해)
                display_data = display_data.sort_values('_display_order', ascending=True).reset_index(drop=True)
                # 순서 번호 컬럼 제거
                display_data = display_data.drop('_display_order', axis=1)
            
            # 인덱스를 0부터 시작하도록 설정 (정렬 순서 보존)
            display_data.index = range(len(display_data))
            
            # Streamlit dataframe 표시 (정렬된 순서 유지)
            # 판매수량 정렬인 경우 정렬 순서를 명시적으로 보존하기 위해 순서 번호를 인덱스로 사용
            st.dataframe(display_data, use_container_width=True, height=400, hide_index=True)
        else:
            st.warning("⚠️ 플랫폼 컬럼(A열) 또는 매출 컬럼(J열)을 찾을 수 없습니다.")
        
        st.markdown("---")

        # 삼성(베네포유+카드몰) vs 타 폐쇄몰 vs 2파트 폐쇄몰 매출이익금 비교 (플랫폼별 분석 섹션 위)
        if amount_col is not None and len(df) > 0:
            # 플랫폼 컬럼(A열) 찾기
            platform_col_for_group = df.columns[0] if len(df.columns) > 0 else None

            # 파트 컬럼 확인/생성 (플랫폼별 분석 섹션과 동일 로직)
            part_col_for_group = None
            part_columns_for_group = [col for col in df.columns if any(keyword in str(col).lower() for keyword in ['파트', 'part'])]
            manager_columns_for_group = [
                col for col in df.columns
                if any(keyword in str(col).lower() for keyword in ['담당자', 'manager', '담당', '담당인', 'contact', '담당자명'])
            ]

            if part_columns_for_group:
                part_col_for_group = part_columns_for_group[0]
            elif manager_columns_for_group:
                def manager_to_part_for_group(manager_name):
                    """담당자 이름을 파트로 변환"""
                    if pd.isna(manager_name):
                        return '1파트'
                    manager_str = str(manager_name).strip()
                    # 맹기열 → 2파트
                    if '맹기열' in manager_str:
                        return '2파트'
                    # 나머지 모든 담당자 → 1파트
                    return '1파트'

                manager_col_for_part_group = manager_columns_for_group[0]
                if '파트' not in df.columns:
                    df['파트'] = df[manager_col_for_part_group].apply(manager_to_part_for_group)
                part_col_for_group = '파트'

            if platform_col_for_group is not None:
                profit_col_for_group = amount_col
                if df[profit_col_for_group].dtype == 'object':
                    df[profit_col_for_group] = pd.to_numeric(df[profit_col_for_group], errors='coerce')

                platform_series = df[platform_col_for_group].astype(str)
                platform_norm = platform_series.str.replace(' ', '', regex=False).str.lower()

                # 삼성 베네포유 / 삼성 카드몰 매칭 (공백 제거 후 비교)
                samsung_keys = ['삼성베네포유', '베네포유', '삼성카드몰', '카드몰']
                samsung_mask = platform_norm.apply(lambda x: any(k in x for k in samsung_keys))

                samsung_profit = df.loc[samsung_mask, profit_col_for_group].sum(skipna=True)

                if part_col_for_group and part_col_for_group in df.columns:
                    part_norm = df[part_col_for_group].astype(str).str.replace(' ', '', regex=False)
                    one_part_mask = part_norm.str.contains('1파트', na=False, regex=False)
                    two_part_mask = part_norm.str.contains('2파트', na=False, regex=False)
                    other_mall_profit_1part = df.loc[one_part_mask & (~samsung_mask), profit_col_for_group].sum(skipna=True)
                    other_mall_profit_2part = df.loc[two_part_mask & (~samsung_mask), profit_col_for_group].sum(skipna=True)
                    group_note = None
                else:
                    # 파트 컬럼이 없으면 "나머지 몰"을 전체 기준으로 계산
                    other_mall_profit_1part = df.loc[~samsung_mask, profit_col_for_group].sum(skipna=True)
                    other_mall_profit_2part = 0.0
                    group_note = "※ 파트 컬럼을 찾지 못해 ‘나머지 몰’은 전체 기준으로 집계했습니다."

                compare_df = pd.DataFrame({
                    '구분': ['삼성(베네포유+카드몰)', '타 폐쇄몰', '2파트 폐쇄몰'],
                    '매출이익금': [
                        float(samsung_profit) if pd.notna(samsung_profit) else 0.0,
                        float(other_mall_profit_1part) if pd.notna(other_mall_profit_1part) else 0.0,
                        float(other_mall_profit_2part) if pd.notna(other_mall_profit_2part) else 0.0
                    ]
                })

                fig_profit_compare = px.bar(
                    compare_df,
                    x='구분',
                    y='매출이익금',
                    text='매출이익금',
                    title=f'{month_label} 매출이익금 비교 (삼성 vs 타 폐쇄몰 vs 2파트 폐쇄몰)',
                    color='구분',
                    color_discrete_map={
                        '삼성(베네포유+카드몰)': '#87CEEB',  # 파스텔 블루
                        '타 폐쇄몰': '#A5D6A7',              # 파스텔 그린
                        '2파트 폐쇄몰': '#FFB6C1'             # 파스텔 핑크
                    }
                )
                fig_profit_compare.update_traces(
                    texttemplate='%{text:,.0f}원',
                    textposition='outside',
                    hovertemplate='<b>%{x}</b><br>매출이익금: %{y:,.0f}원<extra></extra>'
                )
                fig_profit_compare.update_layout(
                    yaxis_title="매출이익금 (원)",
                    xaxis_title="",
                    showlegend=False,
                    margin=dict(t=60, r=20, b=40, l=20)
                )
                fig_profit_compare.update_yaxes(tickformat=',')

                st.plotly_chart(fig_profit_compare, use_container_width=True)
                if group_note:
                    st.info(group_note)
            else:
                st.warning("⚠️ 플랫폼 컬럼(A열)을 찾을 수 없어 '삼성 vs 타 폐쇄몰 vs 2파트 폐쇄몰' 비교를 표시할 수 없습니다.")
        else:
            st.info("매출이익금(N열) 데이터가 없어 '삼성 vs 타 폐쇄몰 vs 2파트 폐쇄몰' 비교를 표시할 수 없습니다.")

        # 플랫폼별 비교
        # month_label 설정: selected_month가 있으면 사용, 없으면 필터링된 데이터에서 월 추출
        if selected_month is not None:
            month_label = f"{selected_month}월"
        elif len(df) > 0 and '월' in df.columns:
            unique_months = sorted(df['월'].dropna().unique())
            if len(unique_months) == 1:
                month_label = f"{int(unique_months[0])}월"
            else:
                month_label = "월"
        else:
            month_label = "월"
        st.subheader(f"📋 플랫폼별 분석 ({month_label})")
        
        # 파트 컬럼 확인 및 생성
        part_col = None
        part_columns = [col for col in df.columns if any(keyword in str(col).lower() for keyword in ['파트', 'part'])]
        manager_columns = [col for col in df.columns 
                          if any(keyword in str(col).lower() for keyword in ['담당자', 'manager', '담당', '담당인', 'contact', '담당자명'])]
        
        # 파트 컬럼이 없으면 담당자 컬럼에서 파트 생성
        if not part_columns and manager_columns:
            def manager_to_part(manager_name):
                """담당자 이름을 파트로 변환"""
                if pd.isna(manager_name):
                    return '1파트'
                manager_str = str(manager_name).strip()
                # 맹기열 → 2파트
                if '맹기열' in manager_str:
                    return '2파트'
                # 나머지 모든 담당자 → 1파트
                return '1파트'
            
            manager_col_for_part = manager_columns[0]
            df['파트'] = df[manager_col_for_part].apply(manager_to_part)
            part_col = '파트'
        elif part_columns:
            part_col = part_columns[0]
        
        # 텍스트/카테고리 컬럼 찾기
        category_columns = df.select_dtypes(include=['object']).columns.tolist()
        # 너무 많은 고유값을 가진 컬럼 제외 (ID나 설명 컬럼 제외)
        category_columns = [col for col in category_columns 
                           if df[col].nunique() <= 50 and df[col].nunique() > 1]
        
        if len(category_columns) > 0:
            category_col = st.selectbox("분류 기준 선택", category_columns, key='category_select')
            
            # 파트별 분석 (전체, 1파트, 2파트)
            if part_col and part_col in df.columns:
                # 파트별 탭 생성
                part_tabs_analysis = st.tabs(["전체", "1파트", "2파트"])
                
                for tab_idx, part_name in enumerate(["전체", "1파트", "2파트"]):
                    with part_tabs_analysis[tab_idx]:
                        # 파트별 데이터 필터링
                        if part_name == "전체":
                            df_part = df.copy()
                        else:
                            df_part = df[df[part_col].astype(str).str.contains(part_name.replace('파트', ''), na=False, regex=False)]
                        
                        if len(df_part) == 0:
                            st.info(f"{part_name} 데이터가 없습니다.")
                            continue
                        
                        # 플랫폼별 판매수량과 매출이익금 통합 그래프
                        st.markdown(f"#### 📊 {part_name} 플랫폼별 판매수량 및 매출이익금 분석")
                        
                        # 플랫폼별 판매수량 집계
                        platform_qty = df_part.groupby(category_col).size().sort_values(ascending=False).head(10)
                        
                        # 플랫폼별 매출이익금 집계
                        if amount_col and amount_col in df_part.columns:
                            if df_part[amount_col].dtype == 'object':
                                df_part[amount_col] = pd.to_numeric(df_part[amount_col], errors='coerce')
                            platform_profit = df_part.groupby(category_col)[amount_col].sum().sort_values(ascending=False).head(10)
                            
                            # 공통 플랫폼 찾기
                            common_platforms_set = set(platform_qty.index) & set(platform_profit.index)
                            if len(common_platforms_set) > 0:
                                # 매출이익금 기준으로 정렬 (높은 순서부터)
                                common_platforms = sorted(
                                    common_platforms_set,
                                    key=lambda p: platform_profit.get(p, 0),
                                    reverse=True
                                )
                                
                                # 이중 Y축 그래프 생성
                                from plotly.subplots import make_subplots
                                fig_combined = make_subplots(specs=[[{"secondary_y": True}]])
                                
                                # 삼성베네포유 플랫폼 확인
                                samsung_keywords = ['삼성베네포유', '베네포유', 'beneforyou', 'samsung']
                                samsung_platforms = [p for p in common_platforms if any(kw.lower() in str(p).lower() for kw in samsung_keywords)]
                                other_platforms = [p for p in common_platforms if p not in samsung_platforms]
                                
                                # 삼성베네포유를 제외한 플랫폼들의 매출이익금 최대값 계산
                                other_profit_values = [platform_profit.get(p, 0) for p in other_platforms]
                                max_other_profit = max(other_profit_values) if len(other_profit_values) > 0 else 0
                                
                                # 매출이익금 바 차트 (왼쪽 Y축)
                                # 삼성베네포유와 다른 플랫폼을 구분하여 색상 지정
                                profit_colors = []
                                for p in common_platforms:
                                    if any(kw.lower() in str(p).lower() for kw in samsung_keywords):
                                        profit_colors.append('#FF6B6B')  # 빨간색 (삼성베네포유)
                                    else:
                                        profit_colors.append('#32CD32')  # 초록색 (기타)
                                
                                fig_combined.add_trace(
                                    go.Bar(
                                        x=common_platforms,
                                        y=[platform_profit.get(p, 0) for p in common_platforms],
                                        name='매출이익금',
                                        marker_color=profit_colors,
                                        hovertemplate='<b>%{x}</b><br>매출이익금: %{y:,.0f}원<extra></extra>'
                                    ),
                                    secondary_y=False
                                )
                                
                                # 판매수량 라인 차트 (오른쪽 Y축)
                                fig_combined.add_trace(
                                    go.Scatter(
                                        x=common_platforms,
                                        y=[platform_qty.get(p, 0) for p in common_platforms],
                                        name='판매수량',
                                        mode='lines+markers',
                                        marker=dict(size=10, color='#87CEEB'),
                                        line=dict(width=3, color='#87CEEB'),
                                        hovertemplate='<b>%{x}</b><br>판매수량: %{y}건<extra></extra>'
                                    ),
                                    secondary_y=True
                                )
                                
                                # 레이아웃 설정
                                fig_combined.update_layout(
                                    title=f'{part_name} 플랫폼별 판매수량 및 매출이익금 (상위 {len(common_platforms)}개)',
                                    xaxis_title=category_col,
                                    hovermode='x unified',
                                    height=500,
                                    # 그리드 라인 설정
                                    xaxis=dict(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)'),
                                    yaxis=dict(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)'),
                                    yaxis2=dict(showgrid=False)  # 오른쪽 Y축은 그리드 라인 제거
                                )
                                
                                # Y축 설정 - 삼성베네포유를 제외한 플랫폼들의 차이를 잘 보이도록 범위 조정
                                if len(samsung_platforms) > 0 and max_other_profit > 0:
                                    # 삼성베네포유가 있고 다른 플랫폼들도 있는 경우
                                    # Y축 범위를 다른 플랫폼들의 최대값 기준으로 설정 (약간의 여유 공간 추가)
                                    yaxis_range = [0, max_other_profit * 1.2]  # 20% 여유 공간
                                else:
                                    # 삼성베네포유가 없거나 다른 플랫폼이 없는 경우 전체 범위 사용
                                    yaxis_range = None
                                
                                fig_combined.update_yaxes(
                                    title_text="매출이익금 (원)",
                                    tickformat=',',
                                    secondary_y=False,
                                    showgrid=True,
                                    gridwidth=1,
                                    gridcolor='rgba(128,128,128,0.2)',
                                    nticks=6,  # 눈금 개수 제한
                                    range=yaxis_range  # Y축 범위 설정
                                )
                                fig_combined.update_yaxes(
                                    title_text="판매수량 (건)",
                                    secondary_y=True,
                                    showgrid=False,  # 오른쪽 Y축은 그리드 라인 제거
                                    showticklabels=False,  # 보조 Y축 눈금선 제거
                                    nticks=6  # 눈금 개수 제한
                                )
                                
                                st.plotly_chart(fig_combined, use_container_width=True)
                            else:
                                st.warning("판매수량과 매출이익금 데이터가 있는 공통 플랫폼이 없습니다.")
                        else:
                            # 매출이익금이 없으면 판매수량만 표시
                            st.markdown("#### 📊 플랫폼별 판매수량 분석")
                            fig_qty = px.bar(
                                x=platform_qty.index,
                                y=platform_qty.values,
                                title=f'{part_name} {category_col}별 판매수량 (상위 10개)',
                                labels={'x': category_col, 'y': '판매수량 (건)'},
                                color=platform_qty.values,
                                color_continuous_scale='Blues'
                            )
                            fig_qty.update_layout(
                                xaxis_title=category_col,
                                yaxis_title="판매수량 (건)",
                                showlegend=False
                            )
                            st.plotly_chart(fig_qty, use_container_width=True)
            else:
                # 파트 정보가 없으면 기존 방식으로 표시
                st.markdown("#### 📊 플랫폼별 총 판매수량 분석")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # 바 차트 (상위 10개)
                    category_data = df[category_col].value_counts().head(10)
                    
                    # 플랫폼별 정렬 순서 지정 (부분 일치 허용)
                    priority_order = ['삼성베네포유', '삼성카드몰', '애터미아자', '캐시딜', '복지드림']
                    
                    # 우선순위 플랫폼과 나머지 플랫폼 분리 (부분 일치로 찾기)
                    priority_platforms = []
                    other_platforms = []
                    
                    # 실제 데이터의 플랫폼 이름과 우선순위 이름 매칭
                    for priority_name in priority_order:
                        for platform in category_data.index:
                            if priority_name in str(platform) or str(platform) in priority_name:
                                if platform not in priority_platforms:
                                    priority_platforms.append(platform)
                                    break
                    
                    for platform in category_data.index:
                        if platform not in priority_platforms:
                            other_platforms.append(platform)
                    
                    # 우선순위 플랫폼을 먼저, 나머지는 판매수량 순으로 정렬
                    sorted_platforms = priority_platforms + sorted(other_platforms, key=lambda x: category_data[x], reverse=True)
                    
                    # 차트에서 상단에 우선순위 플랫폼이 오도록 역순으로 정렬
                    sorted_platforms_reversed = sorted_platforms[::-1]
                    
                    # 정렬된 순서대로 데이터 재구성
                    category_data_sorted = category_data.reindex(sorted_platforms_reversed)
                    
                    fig_bar = px.bar(
                        x=category_data_sorted.values,
                        y=category_data_sorted.index,
                        orientation='h',
                        title=f'{category_col}별 분포 (상위 10개)',
                        labels={'x': '총 판매수량', 'y': category_col},
                        color=category_data_sorted.values,
                        color_continuous_scale='Viridis'
                    )
                    # Y축 순서를 반대로 설정하여 상단에 우선순위 플랫폼이 오도록
                    fig_bar.update_layout(
                        showlegend=False,
                        yaxis={'categoryorder': 'array', 'categoryarray': sorted_platforms_reversed}
                    )
                    # 툴팁에서 컬러 정보 숨기기
                    fig_bar.update_traces(
                        hovertemplate=f'<b>%{{y}}</b><br>총 판매수량: %{{x}}<extra></extra>'
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)
                
                with col2:
                    # 파이 차트 (상위 8개)
                    top_data = df[category_col].value_counts().head(8)
                    others_count = df[category_col].value_counts().iloc[8:].sum() if len(df[category_col].value_counts()) > 8 else 0
                    
                    if others_count > 0:
                        top_data['기타'] = others_count
                    
                    fig_pie = px.pie(
                        values=top_data.values,
                        names=top_data.index,
                        title=f'{category_col}별 비율',
                        hole=0.4  # 도넛 차트 스타일
                    )
                    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig_pie, use_container_width=True)
                
                # 매출총이익 그래프 추가
                if amount_col and amount_col in df.columns:
                    st.markdown("---")
                    st.markdown("#### 💰 플랫폼별 매출이익금 분석")
                    
                    # 매출총이익이 숫자형이 아니면 변환
                    if df[amount_col].dtype == 'object':
                        df[amount_col] = pd.to_numeric(df[amount_col], errors='coerce')
                    
                    # 플랫폼별 매출총이익 집계
                    platform_profit = df.groupby(category_col)[amount_col].sum().sort_values(ascending=False).head(10)
                    
                    col_profit1, col_profit2 = st.columns(2)
                    
                    with col_profit1:
                        # 플랫폼별 매출이익금 바 차트 (세로)
                        fig_profit_bar = px.bar(
                            x=platform_profit.index,
                            y=platform_profit.values,
                            title=f'{category_col}별 매출이익금 (상위 10개)',
                            labels={'x': category_col, 'y': '매출이익금 (원)'},
                            color=platform_profit.values,
                            color_continuous_scale='Greens'
                        )
                        fig_profit_bar.update_layout(
                            xaxis_title=category_col,
                            yaxis_title="매출이익금 (원)",
                            showlegend=False,
                            yaxis=dict(tickformat=',')
                        )
                        # Y축 값에 천단위 구분 기호 적용
                        fig_profit_bar.update_yaxes(tickformat=',')
                        # 툴팁에서 컬러 정보 숨기기
                        fig_profit_bar.update_traces(
                            hovertemplate=f'<b>%{{x}}</b><br>매출이익금: %{{y:,.0f}}원<extra></extra>'
                        )
                        st.plotly_chart(fig_profit_bar, use_container_width=True)
                    
                    with col_profit2:
                        # 플랫폼별 매출이익금 파이 차트
                        top_profit = platform_profit.head(8)
                        others_profit = platform_profit.iloc[8:].sum() if len(platform_profit) > 8 else 0
                        
                        if others_profit > 0:
                            top_profit = top_profit.copy()
                            top_profit['기타'] = others_profit
                        
                        fig_profit_pie = px.pie(
                            values=top_profit.values,
                            names=top_profit.index,
                            title=f'{category_col}별 매출이익금 비율',
                            hole=0.4
                        )
                        fig_profit_pie.update_traces(
                            textposition='inside',
                            textinfo='percent+label',
                            hovertemplate='<b>%{label}</b><br>매출이익금: %{value:,.0f}원<br>비율: %{percent}<extra></extra>'
                        )
                        st.plotly_chart(fig_profit_pie, use_container_width=True)
            
    
        
        # 상세 데이터 테이블 (숨김 처리)
        # month_label = f"{selected_month}월" if selected_month is not None else "월"
        # st.subheader(f"📋 {month_label} 상세 데이터")
        # 
        # # 검색 및 필터 기능
        # col_search, col_filter = st.columns([3, 1])
        # with col_search:
        #     search_term = st.text_input("🔍 검색", "", placeholder="모든 컬럼에서 검색...")
        # with col_filter:
        #     show_rows = st.selectbox("표시 행 수", [50, 100, 200, 500, "전체"], index=1)
        # 
        # if search_term:
        #     # 모든 컬럼에서 검색
        #     mask = df.astype(str).apply(lambda x: x.str.contains(search_term, case=False, na=False)).any(axis=1)
        #     display_df = df[mask]
        #     st.info(f"검색 결과: {len(display_df)}건 발견")
        # else:
        #     display_df = df
        # 
        # # 행 수 제한
        # if isinstance(show_rows, int) and len(display_df) > show_rows:
        #     display_df = display_df.head(show_rows)
        #     st.caption(f"상위 {show_rows}건만 표시 중 (전체: {len(df)}건)")
        # 
        # st.dataframe(display_df, use_container_width=True, height=400)
        
        # 핵심 매출 기여 상품 분석 (삼성베네포유 플랫폼 기준)
        st.markdown('<span id="section_sales" class="anchor"></span>', unsafe_allow_html=True)
        st.markdown("---")
        st.markdown("#### 💎 핵심 매출 기여 상품 분석")
        
        # 2025년 판매분석 시트 찾기 (우선순위)
        sales_analysis_sheet = None
        for sheet in sheet_names:
            if '2025' in sheet and ('판매분석' in sheet or '판매' in sheet and '분석' in sheet):
                sales_analysis_sheet = sheet
                break
        
        # 2025년 판매분석 시트가 있으면 우선 사용
        df_analysis_base = None
        if sales_analysis_sheet:
            try:
                df_sales_analysis = pd.read_excel(xls, sheet_name=sales_analysis_sheet)
                if len(df_sales_analysis) > 0:
                    df_analysis_base = df_sales_analysis.copy()
            except Exception as e:
                st.warning(f"⚠️ 2025년 판매분석 시트({sales_analysis_sheet})를 로드하는 중 오류 발생: {str(e)}")
                df_analysis_base = None
        
        # 2025년 판매분석 시트가 없거나 로드 실패한 경우 기존 방식 사용
        if df_analysis_base is None or len(df_analysis_base) == 0:
            # 11월, 12월, 1월, 2월, 3월 시트 찾기 및 합산
            # raw 시트가 있으면 raw 우선 사용
            november_sheet = None
            december_sheet = None
            january_sheet = None
            february_sheet = None
            march_sheet = None
            november_sheet_non_raw = None
            december_sheet_non_raw = None
            january_sheet_non_raw = None
            february_sheet_non_raw = None
            march_sheet_non_raw = None
            for sheet in sheet_names:
                sheet_lower = sheet.lower()
                is_raw_sheet = 'raw' in sheet_lower
                if '11월' in sheet or ('11' in sheet and '월' in sheet) or 'november' in sheet_lower or 'nov' in sheet_lower:
                    if is_raw_sheet and november_sheet is None:
                        november_sheet = sheet
                    elif (not is_raw_sheet) and november_sheet_non_raw is None:
                        november_sheet_non_raw = sheet
                if '12월' in sheet or ('12' in sheet and '월' in sheet) or 'december' in sheet_lower or 'dec' in sheet_lower:
                    if is_raw_sheet and december_sheet is None:
                        december_sheet = sheet
                    elif (not is_raw_sheet) and december_sheet_non_raw is None:
                        december_sheet_non_raw = sheet
                if '1월' in sheet or ('1' in sheet and '월' in sheet and '11' not in sheet and '12' not in sheet) or 'january' in sheet_lower or 'jan' in sheet_lower:
                    if is_raw_sheet and january_sheet is None:
                        january_sheet = sheet
                    elif (not is_raw_sheet) and january_sheet_non_raw is None:
                        january_sheet_non_raw = sheet
                if '2월' in sheet or 'february' in sheet_lower or 'feb' in sheet_lower:
                    if is_raw_sheet and february_sheet is None:
                        february_sheet = sheet
                    elif (not is_raw_sheet) and february_sheet_non_raw is None:
                        february_sheet_non_raw = sheet
                if '3월' in sheet or ('3' in sheet and '월' in sheet) or 'march' in sheet_lower or 'mar' in sheet_lower:
                    if is_raw_sheet and march_sheet is None:
                        march_sheet = sheet
                    elif (not is_raw_sheet) and march_sheet_non_raw is None:
                        march_sheet_non_raw = sheet

            # raw가 없으면 non-raw로 fallback
            if november_sheet is None:
                november_sheet = november_sheet_non_raw
            if december_sheet is None:
                december_sheet = december_sheet_non_raw
            if january_sheet is None:
                january_sheet = january_sheet_non_raw
            if february_sheet is None:
                february_sheet = february_sheet_non_raw
            if march_sheet is None:
                march_sheet = march_sheet_non_raw
            
            # 11월, 12월, 1월, 2월, 3월 시트를 모두 로드하여 합산
            df_combined = pd.DataFrame()
            loaded_sheets = []
            
            for month_name, sheet_name in [("11월", november_sheet), ("12월", december_sheet), ("1월", january_sheet), ("2월", february_sheet), ("3월", march_sheet)]:
                if sheet_name:
                    try:
                        df_month = pd.read_excel(xls, sheet_name=sheet_name)
                        if len(df_month) > 0:
                            df_combined = pd.concat([df_combined, df_month], ignore_index=True)
                            loaded_sheets.append(month_name)
                    except Exception as e:
                        st.warning(f"⚠️ {month_name} 시트({sheet_name})를 로드하는 중 오류 발생: {str(e)}")
            
            # 합산된 데이터가 있으면 사용, 없으면 기존 df 사용
            if len(df_combined) > 0:
                df_analysis_base = df_combined.copy()
            else:
                df_analysis_base = df.copy()
        
        # 2025년 판매분석 시트인지 확인
        is_sales_analysis_sheet = sales_analysis_sheet is not None
        
        # 상품코드 컬럼 찾기 (일반적으로 C열 또는 D열 근처)
        product_code_col = None
        product_code_keywords = ['상품코드', 'product', 'code', '코드', '상품', '제품코드', '상품 코드', '제품 코드']
        if df_analysis_base is not None and len(df_analysis_base) > 0:
            for idx, col in enumerate(df_analysis_base.columns):
                col_str = str(col).lower()
                if any(keyword in col_str for keyword in product_code_keywords) and '상품명' not in col_str and '상품이름' not in col_str:
                    product_code_col = col
                    break
            
            # 상품코드 컬럼을 찾지 못한 경우 C열(인덱스 2) 또는 D열(인덱스 3) 시도
            if product_code_col is None:
                if len(df_analysis_base.columns) > 2:
                    product_code_col = df_analysis_base.columns[2]  # C열
                elif len(df_analysis_base.columns) > 3:
                    product_code_col = df_analysis_base.columns[3]  # D열
            
            # 판매 수량 컬럼 찾기
            sales_qty_col = None
            sales_qty_keywords = ['판매수량', '판매 수량', '수량', 'quantity', 'qty', '판매량', 'sales', 'quantity']
            for idx, col in enumerate(df_analysis_base.columns):
                col_str = str(col).lower()
                if any(keyword in col_str for keyword in sales_qty_keywords):
                    sales_qty_col = col
                    break
            
            # 판매 수량 컬럼을 찾지 못한 경우 I열(인덱스 8) 시도
            if sales_qty_col is None:
                i_column_index = 8  # I열은 9번째 (0-based index: 8)
                if len(df_analysis_base.columns) > i_column_index:
                    sales_qty_col = df_analysis_base.columns[i_column_index]
        
        # 날짜 컬럼 찾기 (분기별 필터링용)
        date_col = None
        if df_analysis_base is not None and len(df_analysis_base) > 0 and is_sales_analysis_sheet:
            date_keywords = ['날짜', 'date', 'Date', 'DATE', '일자', '거래일', '판매일', '주문일']
            for col in df_analysis_base.columns:
                col_str = str(col).lower()
                if any(keyword in col_str for keyword in date_keywords):
                    date_col = col
                    break
            
            # 날짜 컬럼을 찾지 못한 경우 datetime 타입 컬럼 찾기
            if date_col is None:
                date_columns = df_analysis_base.select_dtypes(include=['datetime64']).columns.tolist()
                if len(date_columns) > 0:
                    date_col = date_columns[0]
                else:
                    # 문자열 형식의 날짜 컬럼 찾기
                    for col in df_analysis_base.columns:
                        if df_analysis_base[col].dtype == 'object':
                            try:
                                test_date = pd.to_datetime(df_analysis_base[col].dropna().iloc[0] if len(df_analysis_base[col].dropna()) > 0 else None, errors='coerce')
                                if pd.notna(test_date):
                                    date_col = col
                                    break
                            except:
                                pass
        
        # 기간 선택 옵션
        period_options = ["전체"]
        if date_col and df_analysis_base is not None and len(df_analysis_base) > 0:
            # 날짜 컬럼을 datetime으로 변환
            df_analysis_base[date_col] = pd.to_datetime(df_analysis_base[date_col], errors='coerce')
            df_analysis_base = df_analysis_base[df_analysis_base[date_col].notna()].copy()
            
            # 년, 월, 분기 컬럼 추가
            df_analysis_base['년'] = df_analysis_base[date_col].dt.year
            df_analysis_base['월'] = df_analysis_base[date_col].dt.month
            df_analysis_base['분기'] = df_analysis_base['월'].apply(lambda x: (x - 1) // 3 + 1)
            
            # 2025년 데이터만 필터링
            df_2025 = df_analysis_base[df_analysis_base['년'] == 2025].copy()
            if len(df_2025) > 0:
                available_quarters = sorted(df_2025['분기'].unique())
                for q in available_quarters:
                    period_options.append(f"2025년 {q}분기")
        
        # 기간 및 분석 기준 선택
        col1, col2 = st.columns(2)
        with col1:
            selected_period = st.selectbox("기간 선택", period_options, key='period_select')
        with col2:
            analysis_criteria = st.selectbox("분석 기준 선택", ["판매수량", "매출이익금", "매출액"], key='analysis_criteria_select')
        
        # 선택된 기간에 따라 데이터 필터링
        df_analysis = None
        if df_analysis_base is not None and len(df_analysis_base) > 0:
            if selected_period == "전체":
                df_analysis = df_analysis_base.copy()
            elif "분기" in selected_period:
                # 분기 추출 (예: "2025년 1분기" -> 1)
                quarter_num = int(selected_period.split("분기")[0].split()[-1])
                df_analysis = df_analysis_base[(df_analysis_base['년'] == 2025) & (df_analysis_base['분기'] == quarter_num)].copy()
            else:
                df_analysis = df_analysis_base.copy()
        
        # 2025년 판매분석 시트인 경우: 상품 코드 기준으로 직접 집계 (플랫폼 필터링 없음)
        if is_sales_analysis_sheet and product_code_col and sales_qty_col and df_analysis is not None and len(df_analysis) > 0:
            # 판매수량이 숫자형이 아니면 변환
            if df_analysis[sales_qty_col].dtype == 'object':
                df_analysis[sales_qty_col] = pd.to_numeric(df_analysis[sales_qty_col], errors='coerce')
            
            # 매출액 컬럼 찾기
            revenue_col = None
            revenue_keywords = ['매출액', '매출금액', '판매금액', 'revenue', 'sales_amount', 'amount']
            for col in df_analysis.columns:
                col_str = str(col).lower()
                if any(keyword in col_str for keyword in revenue_keywords) and '이익' not in col_str:
                    revenue_col = col
                    break
            
            # 매출액 컬럼을 찾지 못한 경우 J열(인덱스 9) 시도
            if revenue_col is None:
                j_column_index = 9  # J열은 10번째 (0-based index: 9)
                if len(df_analysis.columns) > j_column_index:
                    revenue_col = df_analysis.columns[j_column_index]

            # 매출이익금 컬럼 찾기
            profit_col = None
            profit_keywords = ['매출이익금', '이익금', 'profit', 'Profit', 'PROFIT', '매출이익', '이익', '수익', '수익금', 'GP', 'gp']
            for col in df_analysis.columns:
                col_str = str(col).lower()
                if any(keyword in col_str for keyword in profit_keywords):
                    profit_col = col
                    break
            
            # 매출이익금 컬럼을 찾지 못한 경우 N열(인덱스 13) 시도
            if profit_col is None:
                n_column_index = 13  # N열은 14번째 (0-based index: 13)
                if len(df_analysis.columns) > n_column_index:
                    profit_col = df_analysis.columns[n_column_index]

            # 데이터 타입 변환 (매출액, 매출이익금)
            if revenue_col and df_analysis[revenue_col].dtype == 'object':
                df_analysis[revenue_col] = pd.to_numeric(df_analysis[revenue_col], errors='coerce')
            if profit_col and df_analysis[profit_col].dtype == 'object':
                df_analysis[profit_col] = pd.to_numeric(df_analysis[profit_col], errors='coerce')

            # 상품코드별 집계
            agg_dict = {sales_qty_col: 'sum'}
            if revenue_col:
                agg_dict[revenue_col] = 'sum'
            if profit_col:
                agg_dict[profit_col] = 'sum'
            
            product_sales = df_analysis.groupby(product_code_col).agg(agg_dict).reset_index()
            
            # 컬럼명 정리
            rename_dict = {product_code_col: '상품코드', sales_qty_col: '판매수량'}
            if revenue_col:
                rename_dict[revenue_col] = '매출액'
            if profit_col:
                rename_dict[profit_col] = '매출이익금'
            product_sales = product_sales.rename(columns=rename_dict)
            
            # 선택된 기준에 따라 정렬
            sort_col = analysis_criteria
            if sort_col not in product_sales.columns:
                sort_col = '판매수량'
            product_sales = product_sales.sort_values(sort_col, ascending=False)
            
            # 업체명 컬럼 찾기
            company_col = None
            company_keywords = ['업체', '제조사', 'company', 'manufacturer', 'maker', '회사', '고객', 'customer', '제조업체']
            for col in df_analysis.columns:
                col_str = str(col).lower()
                if any(keyword in col_str for keyword in company_keywords):
                    company_col = col
                    break
            
            # 업체명 컬럼을 찾지 못한 경우 B열(인덱스 1) 시도
            if company_col is None and len(df_analysis.columns) > 1:
                company_col = df_analysis.columns[1]  # B열
            
            # 업체명 추가 (있는 경우)
            if company_col:
                # 상품코드별 가장 많이 나타나는 업체명 사용
                company_mapping = df_analysis.groupby(product_code_col)[company_col].apply(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else x.iloc[0]).to_dict()
                product_sales['업체명'] = product_sales['상품코드'].map(company_mapping)
                product_sales['업체명'] = product_sales['업체명'].fillna('미확인')
            else:
                product_sales['업체명'] = '미확인'
            
            # 상품명 컬럼 찾기 (있는 경우)
            product_name_col = None
            product_name_keywords = ['상품명', 'product name', '품명', 'name', '제품명', '상품이름']
            for col in df_analysis.columns:
                col_str = str(col).lower()
                if any(keyword in col_str for keyword in product_name_keywords):
                    product_name_col = col
                    break
            
            # 상품명 추가 (있는 경우)
            if product_name_col:
                # 상품코드별 첫 번째 상품명 사용
                product_name_mapping = df_analysis.groupby(product_code_col)[product_name_col].first().to_dict()
                product_sales['상품명'] = product_sales['상품코드'].map(product_name_mapping)
                product_sales['상품명'] = product_sales['상품명'].fillna(product_sales['상품코드'])
            
            # 표시 컬럼 설정
            display_cols = ['업체명', '상품코드']
            if '상품명' in product_sales.columns:
                display_cols.append('상품명')
            display_cols.append('판매수량')
            if '매출액' in product_sales.columns:
                display_cols.append('매출액')
            if '매출이익금' in product_sales.columns:
                display_cols.append('매출이익금')
            
            # 표시용 데이터 준비
            product_sales_display = product_sales.copy()
            product_sales_display['판매수량'] = product_sales_display['판매수량'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "0")
            if '매출액' in product_sales_display.columns:
                product_sales_display['매출액'] = product_sales_display['매출액'].apply(
                    lambda x: f"{int(x):,}" if pd.notna(x) and not pd.isna(x) else "0"
                )
            if '매출이익금' in product_sales_display.columns:
                product_sales_display['매출이익금'] = product_sales_display['매출이익금'].apply(
                    lambda x: f"{int(x):,}" if pd.notna(x) and not pd.isna(x) else "0"
                )
            
            period_label = selected_period if selected_period != "전체" else "2025.01 ~ 현재 누적"
            st.info(f"📊 {period_label} 상품코드별 {analysis_criteria} 분석 (총 {len(product_sales)}개 상품)")
            st.dataframe(product_sales_display[display_cols], use_container_width=True, height=400, hide_index=True)
        
        # 기존 방식: 플랫폼 필터링 후 집계
        elif not is_sales_analysis_sheet and df_analysis is not None and len(df_analysis) > 0:
            # A열 찾기 (플랫폼, 1번째 컬럼, 인덱스 0)
            platform_col = None
            if len(df_analysis.columns) > 0:
                platform_col = df_analysis.columns[0]  # A열 (1번째 컬럼)
            
            if platform_col and sales_qty_col and product_code_col:
                # 삼성베네포유 플랫폼 필터링
                samsung_beneforyou_keywords = ['삼성베네포유', '베네포유', 'beneforyou', 'samsung']
                df_samsung = df_analysis[df_analysis[platform_col].astype(str).str.contains('|'.join(samsung_beneforyou_keywords), case=False, na=False, regex=True)]
                
                if len(df_samsung) > 0:
                    # 데이터 타입 변환
                    if df_samsung[sales_qty_col].dtype == 'object':
                        df_samsung[sales_qty_col] = pd.to_numeric(df_samsung[sales_qty_col], errors='coerce')
                    
                    # 매출액 컬럼 찾기
                    revenue_col = None
                    revenue_keywords = ['매출액', '매출금액', '판매금액', 'revenue', 'sales_amount', 'amount']
                    for col in df_samsung.columns:
                        col_str = str(col).lower()
                        if any(keyword in col_str for keyword in revenue_keywords) and '이익' not in col_str:
                            revenue_col = col
                            break
                    if revenue_col is None:
                        j_column_index = 9
                        if len(df_samsung.columns) > j_column_index:
                            revenue_col = df_samsung.columns[j_column_index]

                    # 매출이익금 컬럼 찾기
                    profit_col = None
                    profit_keywords = ['매출이익금', '이익금', 'profit', 'Profit', 'PROFIT', '매출이익', '이익', '수익', '수익금', 'GP', 'gp']
                    for col in df_samsung.columns:
                        col_str = str(col).lower()
                        if any(keyword in col_str for keyword in profit_keywords):
                            profit_col = col
                            break
                    if profit_col is None:
                        n_column_index = 13
                        if len(df_samsung.columns) > n_column_index:
                            profit_col = df_samsung.columns[n_column_index]

                    # 데이터 타입 변환 (매출액, 매출이익금)
                    if revenue_col and df_samsung[revenue_col].dtype == 'object':
                        df_samsung[revenue_col] = pd.to_numeric(df_samsung[revenue_col], errors='coerce')
                    if profit_col and df_samsung[profit_col].dtype == 'object':
                        df_samsung[profit_col] = pd.to_numeric(df_samsung[profit_col], errors='coerce')

                    # 상품코드별 집계
                    agg_dict = {sales_qty_col: 'sum'}
                    if revenue_col:
                        agg_dict[revenue_col] = 'sum'
                    if profit_col:
                        agg_dict[profit_col] = 'sum'
                    
                    product_sales = df_samsung.groupby(product_code_col).agg(agg_dict).reset_index()
                    
                    # 컬럼명 정리
                    rename_dict = {product_code_col: '상품코드', sales_qty_col: '판매수량'}
                    if revenue_col:
                        rename_dict[revenue_col] = '매출액'
                    if profit_col:
                        rename_dict[profit_col] = '매출이익금'
                    product_sales = product_sales.rename(columns=rename_dict)
                    
                    # 선택된 기준에 따라 정렬
                    sort_col = analysis_criteria
                    if sort_col not in product_sales.columns:
                        sort_col = '판매수량'
                    product_sales = product_sales.sort_values(sort_col, ascending=False)
                    
                    # 업체명 컬럼 찾기
                    company_col = None
                    company_keywords = ['업체', '제조사', 'company', 'manufacturer', 'maker', '회사', '고객', 'customer', '제조업체']
                    for col in df_analysis.columns:
                        col_str = str(col).lower()
                        if any(keyword in col_str for keyword in company_keywords):
                            company_col = col
                            break
                    
                    # 업체명 컬럼을 찾지 못한 경우 B열(인덱스 1) 시도
                    if company_col is None and len(df_analysis.columns) > 1:
                        company_col = df_analysis.columns[1]  # B열
                    
                    # 업체명 추가 (있는 경우)
                    if company_col:
                        # 상품코드별 가장 많이 나타나는 업체명 사용
                        company_mapping = df_samsung.groupby(product_code_col)[company_col].apply(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else x.iloc[0]).to_dict()
                        product_sales['업체명'] = product_sales['상품코드'].map(company_mapping)
                        product_sales['업체명'] = product_sales['업체명'].fillna('미확인')
                    else:
                        product_sales['업체명'] = '미확인'
                    
                    # 상품명 컬럼 찾기 (있는 경우)
                    product_name_col = None
                    product_name_keywords = ['상품명', 'product name', '품명', 'name', '제품명', '상품이름']
                    for col in df_analysis.columns:
                        col_str = str(col).lower()
                        if any(keyword in col_str for keyword in product_name_keywords):
                            product_name_col = col
                            break
                    
                    # 상품명 추가 (있는 경우)
                    if product_name_col:
                        # 상품코드별 첫 번째 상품명 사용
                        product_name_mapping = df_samsung.groupby(product_code_col)[product_name_col].first().to_dict()
                        product_sales['상품명'] = product_sales['상품코드'].map(product_name_mapping)
                        product_sales['상품명'] = product_sales['상품명'].fillna(product_sales['상품코드'])
                    
                    # 표시 컬럼 설정
                    display_cols = ['업체명', '상품코드']
                    if '상품명' in product_sales.columns:
                        display_cols.append('상품명')
                    display_cols.append('판매수량')
                    if '매출액' in product_sales.columns:
                        display_cols.append('매출액')
                    if '매출이익금' in product_sales.columns:
                        display_cols.append('매출이익금')
                    
                    # 표시용 데이터 준비
                    product_sales_display = product_sales.copy()
                    product_sales_display['판매수량'] = product_sales_display['판매수량'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "0")
                    if '매출액' in product_sales_display.columns:
                        product_sales_display['매출액'] = product_sales_display['매출액'].apply(
                            lambda x: f"{int(x):,}" if pd.notna(x) and not pd.isna(x) else "0"
                        )
                    if '매출이익금' in product_sales_display.columns:
                        product_sales_display['매출이익금'] = product_sales_display['매출이익금'].apply(
                            lambda x: f"{int(x):,}" if pd.notna(x) and not pd.isna(x) else "0"
                        )
                    
                    period_label = selected_period if selected_period != "전체" else "2025.01 ~ 현재 누적"
                    st.info(f"📊 {period_label} 삼성베네포유 플랫폼 기준 상품코드별 {analysis_criteria} 분석 (총 {len(product_sales)}개 상품)")
                    st.dataframe(product_sales_display[display_cols], use_container_width=True, height=400, hide_index=True)
                else:
                    st.warning("⚠️ 삼성베네포유 플랫폼 데이터를 찾을 수 없습니다.")
            else:
                missing_cols = []
                if not platform_col:
                    missing_cols.append("플랫폼 컬럼(A열)")
                if not sales_qty_col:
                    missing_cols.append("판매수량 컬럼")
                if not product_code_col:
                    missing_cols.append("상품코드 컬럼")
                st.warning(f"⚠️ {', '.join(missing_cols)}을(를) 찾을 수 없습니다.")
        else:
            missing_cols = []
            if not sales_qty_col:
                missing_cols.append("판매수량 컬럼")
            if not product_code_col:
                missing_cols.append("상품코드 컬럼")
            st.warning(f"⚠️ {', '.join(missing_cols)}을(를) 찾을 수 없습니다.")
        
        # 다운로드 버튼 (숨김 처리)
        # st.markdown("---")
        # col1, col2 = st.columns(2)
        # 
        # with col1:
        #     # CSV 다운로드
        #     csv = display_df.to_csv(index=False).encode('utf-8-sig')
        #     st.download_button(
        #         label="📥 CSV 다운로드",
        #         data=csv,
        #         file_name=f"주간회의록_{datetime.now().strftime('%Y%m%d')}.csv",
        #         mime="text/csv"
        #     )
        # 
        # with col2:
        #     # Excel 다운로드
        #     from io import BytesIO
        #     output = BytesIO()
        #     with pd.ExcelWriter(output, engine='openpyxl') as writer:
        #         display_df.to_excel(writer, index=False, sheet_name='데이터')
        #     st.download_button(
        #         label="📥 Excel 다운로드",
        #         data=output.getvalue(),
        #         file_name=f"주간회의록_{datetime.now().strftime('%Y%m%d')}.xlsx",
        #         mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        #     )
        
        # 메모장 기능 추가 (파트별로 구분, 주차별 저장)
        st.markdown('<span id="section_plans" class="anchor"></span>', unsafe_allow_html=True)
        st.markdown("---")
        st.markdown(f"#### 📝 {month_label} 계획 (파트별)")
        
        # 주차를 올바른 순서로 정렬하는 함수
        def sort_weeks_korean_for_part(weeks):
            """주차를 첫째주, 둘째주, 셋째주, 넷째주 순서로 정렬"""
            week_order = {'첫째': 1, '둘째': 2, '셋째': 3, '넷째': 4, '다섯째': 5}
            def get_week_number(week_str):
                for key, value in week_order.items():
                    if key in week_str:
                        return value
                return 999  # 알 수 없는 주차는 마지막에
            return sorted(weeks, key=get_week_number)
        
        # 주차 정보가 있는 경우 주차별로 저장
        if '주차_한글' in df.columns:
            # 고유한 주차 목록 가져오기 (올바른 순서로 정렬)
            unique_weeks = sort_weeks_korean_for_part(df['주차_한글'].unique().tolist())
            
            if len(unique_weeks) > 0:
                # 사이드바와 메인 페이지 동기화를 위한 키 (month_label 사용)
                month_key = month_label  # month_label은 이미 데이터에서 월을 추출해서 설정됨
                sidebar_week_select_key = f"sidebar_week_select_{month_key}"
                part_week_select_key = f"part_week_select_{month_key}"
                
                # 주차 선택 (사이드바와 메인 페이지 동기화)
                # 사이드바에서 선택한 주차가 있으면 그것을 사용, 없으면 첫 번째 주차
                if sidebar_week_select_key in st.session_state and st.session_state[sidebar_week_select_key] in unique_weeks:
                    # 사이드바에서 선택한 주차 사용 (우선순위)
                    default_index = unique_weeks.index(st.session_state[sidebar_week_select_key])
                elif part_week_select_key in st.session_state and st.session_state[part_week_select_key] in unique_weeks:
                    # 파트 메모에서 이전에 선택한 주차 사용
                    default_index = unique_weeks.index(st.session_state[part_week_select_key])
                else:
                    default_index = 0
                
                selected_week_part = st.selectbox("주차 선택", unique_weeks, key=part_week_select_key, index=default_index)
                
                # 주차 변경 감지 및 이전 주차 데이터 저장
                last_week_key = f"last_selected_week_part_{month_label}"
                if last_week_key in st.session_state and st.session_state[last_week_key] != selected_week_part:
                    # 주차가 변경되었으므로 이전 주차의 데이터를 파일에 저장
                    previous_week = st.session_state[last_week_key]
                    previous_memo_key_part1 = f"memo_{month_label}_{previous_week}_part1"
                    previous_memo_key_part2 = f"memo_{month_label}_{previous_week}_part2"
                    previous_input_key_part1 = f"memo_input_{month_label}_{previous_week}_part1"
                    previous_input_key_part2 = f"memo_input_{month_label}_{previous_week}_part2"
                    
                    # 이전 주차의 1파트 메모 저장 (입력창 내용 우선 확인)
                    previous_memo_part1 = ""
                    if previous_input_key_part1 in st.session_state:
                        # 입력창의 내용이 있으면 우선 사용
                        previous_memo_part1 = st.session_state[previous_input_key_part1]
                    elif previous_memo_key_part1 in st.session_state:
                        # 입력창 내용이 없으면 session_state 확인
                        previous_memo_part1 = st.session_state[previous_memo_key_part1]
                    
                    # 빈 값이 아닐 때만 저장
                    if previous_memo_part1 and previous_memo_part1.strip():
                        save_memo_to_file(previous_memo_key_part1, previous_memo_part1)
                    
                    # 이전 주차의 2파트 메모 저장 (입력창 내용 우선 확인)
                    previous_memo_part2 = ""
                    if previous_input_key_part2 in st.session_state:
                        # 입력창의 내용이 있으면 우선 사용
                        previous_memo_part2 = st.session_state[previous_input_key_part2]
                    elif previous_memo_key_part2 in st.session_state:
                        # 입력창 내용이 없으면 session_state 확인
                        previous_memo_part2 = st.session_state[previous_memo_key_part2]
                    
                    # 빈 값이 아닐 때만 저장
                    if previous_memo_part2 and previous_memo_part2.strip():
                        save_memo_to_file(previous_memo_key_part2, previous_memo_part2)
                
                # 파트별 메모 탭 생성
                part_tabs = st.tabs(["1파트", "2파트"])
                
                # 1파트 메모
                with part_tabs[0]:
                    memo_key_part1 = f"memo_{month_label}_{selected_week_part}_part1"
                    
                    # 주차별로 독립적인 session_state 키 사용 (주차가 변경되면 항상 파일에서 불러오기)
                    current_week_state_key_part1 = f"current_week_{memo_key_part1}"
                    if current_week_state_key_part1 not in st.session_state or st.session_state.get(f"last_selected_week_part_{month_label}") != selected_week_part:
                        # 주차가 변경되었거나 처음 로드하는 경우 파일에서 불러오기
                        loaded_memo = load_memo_from_file(memo_key_part1)
                        if loaded_memo:
                            st.session_state[memo_key_part1] = loaded_memo
                        elif selected_month == 12 and selected_week_part == unique_weeks[0]:
                            # 12월 첫째주 계획 메모 기본값 설정 (1파트)
                            default_memo_part1 = """★ 업무 진행 현황

* 교육 이수진행 (최승영 / 장지웅) 완료
: 장지웅 프로는 추가로 교육필요한 인증서가 있어 추가 교육진행중

* 메가존 제안서 승인완료 상품 등록 (오가닉K + 2)

* 애터미 특가구좌 진행
: 미고가 제품 진행 (월 화 수) - 1+1 귀걸이 목걸이 쥬얼리 2세트
: 에스씨컴퍼니 떡 + 미고가 정수리가발 (목) 진행
: 소노스퀘어 이불 셋트 (토) 진행
: 미고가 쥬얼리세트 2종 (일요일) 진행

*이제너두 운영관련 MD와 협의
: 상품 등록수 늘리기 (E-카탈로그형식으로 상시제품보다가 특판 문의 들어올수 있음)
: 공지사항에 기재되는 특판 및 행사건 최대한 저렴하게 진행 요청
: 공지사항 행사건 처리 잘해주면 그다음 특판제안 관련 받을수 있을수 있음
: 상시매출도 높아야 특판 기회 가능성 있음
: 기존에 특판기업들이 있기때문에 그 기업들보다 저렴하게 진행해야 추후 진행가능
  (너무많은 제안서가 들어오기떄문에 기존 특판기업에 의존도 95%) 

*전문 특판업체 필요성
: 특판의 경우 전문적으로 진행하는 회사들이 존재하여 상품 의뢰할 기업 찾기
: 자체적으로 진행하기에는 특판구조에 맞지않는 제품들이 대다수 (상위 브랜드 제품의 보유사항)
: 특판이 존재하는 폐쇄몰 기준 특판 진행할수 있는 매출 및 상품수 확보할때까지만 의뢰 예정

*신규제품 상품 관련 정리
: 맥널티 일농 / 디에스엠 (최저가 안맞아서 제안서 다시 요청)
: 소셜빈은 제품 상세페이지 부터 진행되어야 함
  (제품 300개 정도 - 정상가 대비 75%공급가 : 최저가는 따로 조사 예정)
: 닥터엠 생수의경우 복지몰의 중복코드가 있어서 정리 요청 및 단가 인하 요청
: 순창성가정식품 많은제품 모두 제안 요청
   고추장 된장 등 면세제품 과세제품으로 1월1일부터 변경예정이어서 
   해당제품들 모두 상품 내리고 다시 올려야함
: 위랩 신규제품 제안 요청 진행 / 최저가에 맞추어 가격설정 요청

---------------------------------------------------------------------------------------------------------------------------------

* 설 명절 제안서 관련 이슈
: 자체 가상 취합일정 - 12/19
: 실제 삼성 취합일정 - 12/17 오전 11시까지
: 다시 일정관련하여 메일 재발송 진행 - 중요업체는 유선으로 재촉 진행

* 애터미 추가 특가 상품 제안예정
: 쿠첸 밥솥 특가 예정 + 업체 특가 요청 진행

* 한화 복지몰 마사지기 상품 제안 
: 누가의료기 선정하여 요청 하였고,
금액 확인 후 상품 제안 예정

* 올웨이지 미팅 요청
: 판매 활성화를 위해 미팅 요청 진행
: 메일로 주요 상품군 전달 진행

* PNS로지스틱스 (말레이시아 물류파트너)
 : 간략하게 스마트공장 리스트 및 진행제품 카테고리 정리해서 
   신동인 팀장에게 공유 진행

*홈페이지 관련 모니터링
비즈마켓
https://www.bizmarket.com/
제이슨그룹
https://jasongroup.co.kr/
엘슈퍼비젼
https://elsupervision.com/default/
"""
                            st.session_state[memo_key_part1] = default_memo_part1
                            save_memo_to_file(memo_key_part1, default_memo_part1)
                        else:
                            # 파일에서 불러온 값이 없고 기본값도 없으면 session_state에 빈 값으로 설정하지 않음
                            # 대신 빈 문자열로 초기화하되, 나중에 저장할 때는 빈 값 저장 방지 로직이 작동함
                            if memo_key_part1 not in st.session_state:
                                st.session_state[memo_key_part1] = ""
                        st.session_state[current_week_state_key_part1] = True
                        st.session_state[f"last_selected_week_part_{month_label}"] = selected_week_part
                    
                    # 1파트 메모 입력
                    memo_text_part1 = st.text_area(
                        f"1파트 메모를 입력하세요 ({selected_week_part})",
                        value=st.session_state.get(memo_key_part1, ""),
                        height=200,
                        placeholder=f"1파트 메모를 작성하세요 ({selected_week_part}).\n\n💡 팁: '저장' 버튼을 눌러야 데이터가 보존됩니다.",
                        key=f"memo_input_{month_label}_{selected_week_part}_part1"
                    )
                    
                    # 명시적 저장 버튼
                    if st.button(f"💾 {selected_week_part} 1파트 계획 저장", key=f"save_btn_part1_{selected_week_part}"):
                        if memo_text_part1 and memo_text_part1.strip():
                            st.session_state[memo_key_part1] = memo_text_part1
                            save_memo_to_file(memo_key_part1, memo_text_part1)
                            st.success(f"✅ {selected_week_part} 1파트 계획이 저장되었습니다.")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.warning("⚠️ 저장할 내용이 없습니다.")
                    
                    # 저장된 1파트 메모 표시 (원본 포맷 보존, 입력 영역과 동일한 스타일)
                    if st.session_state.get(memo_key_part1, ""):
                        with st.expander(f"📋 저장된 {selected_week_part} 1파트 메모 보기", expanded=False):
                            # 입력 영역과 동일한 스타일로 표시 (일반 폰트, 줄바꿈 보존)
                            memo_content = html.escape(st.session_state[memo_key_part1])
                            # 줄바꿈을 <br>로 변환
                            memo_content = memo_content.replace('\n', '<br>')
                            # 입력 영역과 동일한 스타일 적용
                            memo_display_part1 = f"<div style='white-space: pre-wrap; font-family: inherit; line-height: 1.5; padding: 0.5rem;'>{memo_content}</div>"
                            st.markdown(memo_display_part1, unsafe_allow_html=True)
                
                # 2파트 메모
                with part_tabs[1]:
                    memo_key_part2 = f"memo_{month_label}_{selected_week_part}_part2"
                    
                    # 주차별로 독립적인 session_state 키 사용 (주차가 변경되면 항상 파일에서 불러오기)
                    current_week_state_key_part2 = f"current_week_{memo_key_part2}"
                    if current_week_state_key_part2 not in st.session_state or st.session_state.get(f"last_selected_week_part_{month_label}") != selected_week_part:
                        # 주차가 변경되었거나 처음 로드하는 경우 파일에서 불러오기
                        loaded_memo = load_memo_from_file(memo_key_part2)
                        if loaded_memo:
                            st.session_state[memo_key_part2] = loaded_memo
                        else:
                            # 파일에서 불러온 값이 없으면 session_state에 빈 값으로 설정하지 않음
                            # 대신 빈 문자열로 초기화하되, 나중에 저장할 때는 빈 값 저장 방지 로직이 작동함
                            if memo_key_part2 not in st.session_state:
                                st.session_state[memo_key_part2] = ""
                        st.session_state[current_week_state_key_part2] = True
                        st.session_state[f"last_selected_week_part_{month_label}"] = selected_week_part
                    
                    # 2파트 메모 입력
                    memo_text_part2 = st.text_area(
                        f"2파트 메모를 입력하세요 ({selected_week_part})",
                        value=st.session_state.get(memo_key_part2, ""),
                        height=200,
                        placeholder=f"2파트 메모를 작성하세요 ({selected_week_part}).\n\n💡 팁: '저장' 버튼을 눌러야 데이터가 보존됩니다.",
                        key=f"memo_input_{month_label}_{selected_week_part}_part2"
                    )
                    
                    # 명시적 저장 버튼
                    if st.button(f"💾 {selected_week_part} 2파트 계획 저장", key=f"save_btn_part2_{selected_week_part}"):
                        if memo_text_part2 and memo_text_part2.strip():
                            st.session_state[memo_key_part2] = memo_text_part2
                            save_memo_to_file(memo_key_part2, memo_text_part2)
                            st.success(f"✅ {selected_week_part} 2파트 계획이 저장되었습니다.")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.warning("⚠️ 저장할 내용이 없습니다.")
                    
                    # 저장된 2파트 메모 표시 (원본 포맷 보존, 입력 영역과 동일한 스타일)
                    if st.session_state.get(memo_key_part2, ""):
                        with st.expander(f"📋 저장된 {selected_week_part} 2파트 메모 보기", expanded=False):
                            # 입력 영역과 동일한 스타일로 표시 (일반 폰트, 줄바꿈 보존)
                            memo_content = html.escape(st.session_state[memo_key_part2])
                            # 줄바꿈을 <br>로 변환
                            memo_content = memo_content.replace('\n', '<br>')
                            # 입력 영역과 동일한 스타일 적용
                            memo_display_part2 = f"<div style='white-space: pre-wrap; font-family: inherit; line-height: 1.5; padding: 0.5rem;'>{memo_content}</div>"
                            st.markdown(memo_display_part2, unsafe_allow_html=True)
            else:
                st.info("주차 정보를 찾을 수 없습니다.")
        else:
            # 주차 정보가 없는 경우 기존 방식으로 월별 저장 (하위 호환성 유지)
            st.info("⚠️ 주차 정보가 없어 월별로 저장됩니다. 날짜 정보가 포함된 데이터를 업로드하면 주차별로 저장됩니다.")
            
            # 파트별 메모 탭 생성
            part_tabs = st.tabs(["1파트", "2파트"])
            
            # 1파트 메모
            with part_tabs[0]:
                memo_key_part1 = f"memo_{month_label}_part1"
                # 파일에서 메모 불러오기
                if memo_key_part1 not in st.session_state:
                    loaded_memo = load_memo_from_file(memo_key_part1)
                    if loaded_memo:
                        st.session_state[memo_key_part1] = loaded_memo
                    elif selected_month == 12:
                        # 12월 계획 메모 기본값 설정 (1파트)
                        default_memo_part1 = """★ 업무 진행 현황

* 교육 이수진행 (최승영 / 장지웅) 완료
: 장지웅 프로는 추가로 교육필요한 인증서가 있어 추가 교육진행중

* 메가존 제안서 승인완료 상품 등록 (오가닉K + 2)

* 애터미 특가구좌 진행
: 미고가 제품 진행 (월 화 수) - 1+1 귀걸이 목걸이 쥬얼리 2세트
: 에스씨컴퍼니 떡 + 미고가 정수리가발 (목) 진행
: 소노스퀘어 이불 셋트 (토) 진행
: 미고가 쥬얼리세트 2종 (일요일) 진행

*이제너두 운영관련 MD와 협의
: 상품 등록수 늘리기 (E-카탈로그형식으로 상시제품보다가 특판 문의 들어올수 있음)
: 공지사항에 기재되는 특판 및 행사건 최대한 저렴하게 진행 요청
: 공지사항 행사건 처리 잘해주면 그다음 특판제안 관련 받을수 있을수 있음
: 상시매출도 높아야 특판 기회 가능성 있음
: 기존에 특판기업들이 있기때문에 그 기업들보다 저렴하게 진행해야 추후 진행가능
  (너무많은 제안서가 들어오기떄문에 기존 특판기업에 의존도 95%) 

*전문 특판업체 필요성
: 특판의 경우 전문적으로 진행하는 회사들이 존재하여 상품 의뢰할 기업 찾기
: 자체적으로 진행하기에는 특판구조에 맞지않는 제품들이 대다수 (상위 브랜드 제품의 보유사항)
: 특판이 존재하는 폐쇄몰 기준 특판 진행할수 있는 매출 및 상품수 확보할때까지만 의뢰 예정

*신규제품 상품 관련 정리
: 맥널티 일농 / 디에스엠 (최저가 안맞아서 제안서 다시 요청)
: 소셜빈은 제품 상세페이지 부터 진행되어야 함
  (제품 300개 정도 - 정상가 대비 75%공급가 : 최저가는 따로 조사 예정)
: 닥터엠 생수의경우 복지몰의 중복코드가 있어서 정리 요청 및 단가 인하 요청
: 순창성가정식품 많은제품 모두 제안 요청
   고추장 된장 등 면세제품 과세제품으로 1월1일부터 변경예정이어서 
   해당제품들 모두 상품 내리고 다시 올려야함
: 위랩 신규제품 제안 요청 진행 / 최저가에 맞추어 가격설정 요청

---------------------------------------------------------------------------------------------------------------------------------

* 설 명절 제안서 관련 이슈
: 자체 가상 취합일정 - 12/19
: 실제 삼성 취합일정 - 12/17 오전 11시까지
: 다시 일정관련하여 메일 재발송 진행 - 중요업체는 유선으로 재촉 진행

* 애터미 추가 특가 상품 제안예정
: 쿠첸 밥솥 특가 예정 + 업체 특가 요청 진행

* 한화 복지몰 마사지기 상품 제안 
: 누가의료기 선정하여 요청 하였고,
금액 확인 후 상품 제안 예정

* 올웨이지 미팅 요청
: 판매 활성화를 위해 미팅 요청 진행
: 메일로 주요 상품군 전달 진행

* PNS로지스틱스 (말레이시아 물류파트너)
 : 간략하게 스마트공장 리스트 및 진행제품 카테고리 정리해서 
   신동인 팀장에게 공유 진행

*홈페이지 관련 모니터링
비즈마켓
https://www.bizmarket.com/
제이슨그룹
https://jasongroup.co.kr/
엘슈퍼비젼
https://elsupervision.com/default/
"""
                        st.session_state[memo_key_part1] = default_memo_part1
                        save_memo_to_file(memo_key_part1, default_memo_part1)
                    else:
                        st.session_state[memo_key_part1] = ""
                
                # 1파트 메모 입력
                memo_text_part1 = st.text_area(
                    "1파트 메모를 입력하세요",
                    value=st.session_state.get(memo_key_part1, ""),
                    height=200,
                    placeholder="1파트 메모를 작성하세요.\n\n💡 팁: '저장' 버튼을 눌러야 데이터가 보존됩니다.",
                    key=f"memo_input_{month_label}_part1"
                )
                
                # 명시적 저장 버튼
                if st.button("💾 1파트 계획 저장", key=f"save_btn_part1_no_week_{month_label}"):
                    if memo_text_part1 and memo_text_part1.strip():
                        st.session_state[memo_key_part1] = memo_text_part1
                        save_memo_to_file(memo_key_part1, memo_text_part1)
                        st.success("✅ 1파트 계획이 저장되었습니다.")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.warning("⚠️ 저장할 내용이 없습니다.")
                
                # 저장된 1파트 메모 표시 (원본 포맷 보존, 입력 영역과 동일한 스타일)
                if st.session_state.get(memo_key_part1, ""):
                    with st.expander("📋 저장된 1파트 메모 보기", expanded=False):
                        # 입력 영역과 동일한 스타일로 표시 (일반 폰트, 줄바꿈 보존)
                        memo_content = html.escape(st.session_state[memo_key_part1])
                        # 줄바꿈을 <br>로 변환
                        memo_content = memo_content.replace('\n', '<br>')
                        # 입력 영역과 동일한 스타일 적용
                        memo_display_part1 = f"<div style='white-space: pre-wrap; font-family: inherit; line-height: 1.5; padding: 0.5rem;'>{memo_content}</div>"
                        st.markdown(memo_display_part1, unsafe_allow_html=True)
            
            # 2파트 메모
            with part_tabs[1]:
                memo_key_part2 = f"memo_{month_label}_part2"
                # 파일에서 메모 불러오기
                if memo_key_part2 not in st.session_state:
                    loaded_memo = load_memo_from_file(memo_key_part2)
                    if loaded_memo:
                        st.session_state[memo_key_part2] = loaded_memo
                    else:
                        st.session_state[memo_key_part2] = ""
                
                # 2파트 메모 입력
                memo_text_part2 = st.text_area(
                    "2파트 메모를 입력하세요",
                    value=st.session_state.get(memo_key_part2, ""),
                    height=200,
                    placeholder="2파트 메모를 작성하세요.\n\n💡 팁: '저장' 버튼을 눌러야 데이터가 보존됩니다.",
                    key=f"memo_input_{month_label}_part2"
                )
                
                # 명시적 저장 버튼
                if st.button("💾 2파트 계획 저장", key=f"save_btn_part2_no_week_{month_label}"):
                    if memo_text_part2 and memo_text_part2.strip():
                        st.session_state[memo_key_part2] = memo_text_part2
                        save_memo_to_file(memo_key_part2, memo_text_part2)
                        st.success("✅ 2파트 계획이 저장되었습니다.")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.warning("⚠️ 저장할 내용이 없습니다.")
                
                # 저장된 2파트 메모 표시 (원본 포맷 보존, 입력 영역과 동일한 스타일)
                if st.session_state.get(memo_key_part2, ""):
                    with st.expander("📋 저장된 2파트 메모 보기", expanded=False):
                        # 입력 영역과 동일한 스타일로 표시 (일반 폰트, 줄바꿈 보존)
                        memo_content = html.escape(st.session_state[memo_key_part2])
                        # 줄바꿈을 <br>로 변환
                        memo_content = memo_content.replace('\n', '<br>')
                        # 입력 영역과 동일한 스타일 적용
                        memo_display_part2 = f"<div style='white-space: pre-wrap; font-family: inherit; line-height: 1.5; padding: 0.5rem;'>{memo_content}</div>"
                        st.markdown(memo_display_part2, unsafe_allow_html=True)
        
        # 주차별 경영진 회의록 추가 (숨김 처리)
        # st.markdown('<span id="section_meeting" class="anchor"></span>', unsafe_allow_html=True)
        # st.markdown("---")
        # st.markdown(f"#### 📋 {month_label} 주차별 경영진 회의록")
        # 
        # # 주차를 올바른 순서로 정렬하는 함수
        # def sort_weeks_korean(weeks):
        #     """주차를 첫째주, 둘째주, 셋째주, 넷째주 순서로 정렬"""
        #     week_order = {'첫째': 1, '둘째': 2, '셋째': 3, '넷째': 4, '다섯째': 5}
        #     def get_week_number(week_str):
        #         for key, value in week_order.items():
        #             if key in week_str:
        #                 return value
        #         return 999  # 알 수 없는 주차는 마지막에
        #     return sorted(weeks, key=get_week_number)
        # 
        # # 주차 정보가 있는 경우
        # if '주차_한글' in df.columns:
        #     # 고유한 주차 목록 가져오기 (올바른 순서로 정렬)
        #     unique_weeks = sort_weeks_korean(df['주차_한글'].unique().tolist())
        #     
        #     if len(unique_weeks) > 0:
        #         # 사이드바와 메인 페이지 동기화를 위한 키 (selected_month를 직접 사용)
        #         month_key = f"{selected_month}월" if selected_month is not None else "월"
        #         sidebar_week_select_key = f"sidebar_week_select_{month_key}"
        #         main_week_select_key = f"main_week_select_{month_key}"
        #         
        #         # 주차 선택 (사이드바와 메인 페이지 동기화)
        #         # 사이드바에서 선택한 주차가 있으면 그것을 사용, 없으면 첫 번째 주차
        #         if sidebar_week_select_key in st.session_state and st.session_state[sidebar_week_select_key] in unique_weeks:
        #             # 사이드바에서 선택한 주차 사용 (우선순위)
        #             default_index = unique_weeks.index(st.session_state[sidebar_week_select_key])
        #         elif main_week_select_key in st.session_state and st.session_state[main_week_select_key] in unique_weeks:
        #             # 메인 페이지에서 이전에 선택한 주차 사용
        #             default_index = unique_weeks.index(st.session_state[main_week_select_key])
        #         else:
        #             default_index = 0
        #         
        #         selected_week = st.selectbox("주차 선택", unique_weeks, key=main_week_select_key, index=default_index)
        #         
        #         # 모든 주차의 회의록을 미리 파일에서 불러와서 session_state에 저장 (요약 표시를 위해)
        #         all_weeks_loaded_key = f"all_weeks_loaded_{month_label}"
        #         if all_weeks_loaded_key not in st.session_state:
        #             for week in unique_weeks:
        #                 week_key = f"executive_meeting_{month_label}_{week}"
        #                 # session_state에 없으면 파일에서 불러오기
        #                 if week_key not in st.session_state or not st.session_state.get(week_key):
        #                     loaded_week_meeting = load_memo_from_file(week_key)
        #                     if loaded_week_meeting:
        #                         st.session_state[week_key] = loaded_week_meeting
        #             st.session_state[all_weeks_loaded_key] = True
        #         
        #         # 선택된 주차의 회의록 키
        #         meeting_key = f"executive_meeting_{month_label}_{selected_week}"
        #         
        #         # 주차별로 독립적인 session_state 키 사용 (주차가 변경되면 항상 파일에서 불러오기)
        #         current_week_state_key = f"current_week_{meeting_key}"
        #         if current_week_state_key not in st.session_state or st.session_state.get(f"last_selected_week_{month_label}") != selected_week:
        #             # 주차가 변경되었거나 처음 로드하는 경우 파일에서 불러오기
        #             loaded_meeting = load_memo_from_file(meeting_key)
        #             st.session_state[meeting_key] = loaded_meeting if loaded_meeting else ""
        #             st.session_state[current_week_state_key] = True
        #             st.session_state[f"last_selected_week_{month_label}"] = selected_week
        #         
        #         # 주차별 경영진 회의록 입력
        #         meeting_text = st.text_area(
        #             f"{selected_week} 경영진 회의록을 입력하세요",
        #             value=st.session_state.get(meeting_key, ""),
        #             height=200,
        #             placeholder=f"{selected_week} 경영진 회의록을 작성하세요. 내용은 자동으로 저장됩니다.",
        #             key=f"meeting_input_{month_label}_{selected_week}"
        #         )
        #         
        #         # 회의록 저장 (입력 시마다 자동 저장)
        #         if meeting_text != st.session_state.get(meeting_key, ""):
        #             st.session_state[meeting_key] = meeting_text
        #             save_memo_to_file(meeting_key, meeting_text)
        #             st.success(f"✅ {selected_week} 경영진 회의록이 저장되었습니다.", icon="💾")
        #         
        #         # 저장된 회의록 표시
        #         if st.session_state[meeting_key]:
        #             with st.expander(f"📋 저장된 {selected_week} 경영진 회의록 보기", expanded=False):
        #                 meeting_display = st.session_state[meeting_key].replace('\n', '<br>')
        #                 st.markdown(meeting_display, unsafe_allow_html=True)
        #         
        #         # 모든 주차별 회의록 요약 보기
        #         st.markdown("---")
        #         st.markdown("#### 📊 주차별 회의록 요약")
        #         meeting_summary = {}
        #         for week in unique_weeks:
        #             week_key = f"executive_meeting_{month_label}_{week}"
        #             # session_state에 있으면 우선 사용 (최신 데이터), 없으면 파일에서 불러오기
        #             if week_key in st.session_state and st.session_state[week_key]:
        #                 meeting_summary[week] = st.session_state[week_key]
        #             else:
        #                 # 파일에서 불러오기
        #                 loaded_week_meeting = load_memo_from_file(week_key)
        #                 if loaded_week_meeting:
        #                     meeting_summary[week] = loaded_week_meeting
        #                     # session_state에도 저장하여 다음에 빠르게 접근
        #                     st.session_state[week_key] = loaded_week_meeting
        #         
        #         # 선택된 주차를 추적하여 주차 변경 시 자동으로 열리도록 함
        #         summary_selected_week_key = f"summary_selected_week_{month_label}"
        #         if summary_selected_week_key not in st.session_state:
        #             st.session_state[summary_selected_week_key] = selected_week
        #         
        #         # 주차가 변경되었는지 확인
        #         week_changed = st.session_state[summary_selected_week_key] != selected_week
        #         if week_changed:
        #             st.session_state[summary_selected_week_key] = selected_week
        #         
        #         if meeting_summary:
        #             # 선택된 주차의 회의록을 먼저 표시하고 자동으로 열기
        #             # 주차가 변경되었거나 처음 로드하는 경우 expanded=True
        #             if selected_week in meeting_summary:
        #                 content = meeting_summary[selected_week]
        #                 # 선택된 주차는 항상 expanded=True (주차 변경 시 자동으로 열림)
        #                 with st.expander(f"📝 {selected_week} 회의록", expanded=True):
        #                     week_display = content.replace('\n', '<br>')
        #                     st.markdown(week_display, unsafe_allow_html=True)
        #             
        #             # 나머지 주차의 회의록 표시 (선택된 주차 제외)
        #             # 정렬된 순서로 표시하되, 선택된 주차는 제외
        #             for week in unique_weeks:
        #                 if week in meeting_summary and week != selected_week:
        #                     content = meeting_summary[week]
        #                     # 선택되지 않은 주차는 expanded=False
        #                     with st.expander(f"📝 {week} 회의록", expanded=False):
        #                         week_display = content.replace('\n', '<br>')
        #                         st.markdown(week_display, unsafe_allow_html=True)
        #         else:
        #             st.info("아직 작성된 주차별 회의록이 없습니다.")
        #     else:
        #         st.info("주차 정보를 찾을 수 없습니다.")
        # else:
        #     st.info("주차 정보가 없어 주차별 회의록을 작성할 수 없습니다. 날짜 정보가 포함된 데이터를 업로드해주세요.")
        
        # 판매 데이터 분석 섹션 추가 (선택된 월 상세 데이터 하단) - 숨김
        if False and os.path.exists(sales_data_path):
            st.markdown("---")
            month_label = f"{selected_month}월" if selected_month is not None else "월"
            st.subheader(f"📦 상품 판매 분석 (2025 정산서 기준 {month_label}까지)")
            
            try:
                sales_xls = pd.ExcelFile(sales_data_path)
                sales_sheet = st.selectbox("판매 데이터 시트 선택", sales_xls.sheet_names, key='sales_sheet')
                sales_df = pd.read_excel(sales_xls, sheet_name=sales_sheet)
                
                # 컬럼 찾기
                company_cols = [col for col in sales_df.columns 
                               if any(kw in str(col).lower() for kw in ['업체', 'company', '회사', '고객', 'customer', '제조사', 'manufacturer', 'maker'])
                               and '지급금액' not in str(col)
                               and '금액' not in str(col)]
                product_cols = [col for col in sales_df.columns 
                               if any(kw in str(col).lower() for kw in ['상품', 'product', '코드', 'code', '상품코드'])
                               and '상품명' not in str(col)
                               and '코드별' not in str(col)]
                product_name_cols = [col for col in sales_df.columns if any(kw in str(col).lower() for kw in ['상품명', 'product name', '품명', 'name', '제품명', '상품이름'])]
                quantity_cols = [col for col in sales_df.columns 
                                if any(kw in str(col).lower() for kw in ['수량', 'quantity', '판매', 'sales', 'qty']) 
                                and '코드별' not in str(col)
                                and '상품코드' not in str(col)
                                and '상품명' not in str(col)]
                
                col_select1, col_select2, col_select3, col_select4 = st.columns(4)
                with col_select1:
                    if company_cols:
                        company_col = st.selectbox("업체 컬럼", company_cols, key='sales_company')
                    else:
                        company_col = st.selectbox("업체 컬럼", [""] + list(sales_df.columns), key='sales_company')
                        if company_col == "":
                            company_col = None
                
                with col_select2:
                    if product_cols:
                        product_col = st.selectbox("상품코드 컬럼", product_cols, key='sales_product')
                    else:
                        product_col = st.selectbox("상품코드 컬럼", [""] + list(sales_df.columns), key='sales_product')
                        if product_col == "":
                            product_col = None
                
                with col_select3:
                    if product_name_cols:
                        product_name_col = st.selectbox("상품명 컬럼", product_name_cols, key='sales_product_name')
                    else:
                        product_name_col = st.selectbox("상품명 컬럼", [""] + list(sales_df.columns), key='sales_product_name')
                        if product_name_col == "":
                            product_name_col = None
                
                with col_select4:
                    if quantity_cols:
                        quantity_col = st.selectbox("판매 수량 컬럼", quantity_cols, key='sales_quantity')
                    else:
                        quantity_col = st.selectbox("판매 수량 컬럼", [""] + list(sales_df.columns), key='sales_quantity')
                        if quantity_col == "":
                            quantity_col = None
                
                if company_col and product_col and quantity_col:
                    # 수량 컬럼이 숫자형이 아니면 변환
                    if sales_df[quantity_col].dtype == 'object':
                        sales_df[quantity_col] = pd.to_numeric(sales_df[quantity_col], errors='coerce')
                    
                    # 상품코드와 상품명 매핑 생성
                    if product_name_col:
                        product_mapping = sales_df[[product_col, product_name_col]].drop_duplicates()
                        product_mapping = product_mapping.set_index(product_col)[product_name_col].to_dict()
                    else:
                        product_mapping = {}
                        st.warning("⚠️ 상품명 컬럼이 없어 상품코드로 표시됩니다.")
                    
                    # 상품코드별 제조사 매핑 생성 (원본 업체 컬럼 사용)
                    # 같은 상품코드에 여러 업체가 있을 수 있으므로, 가장 많이 나타나는 업체를 사용
                    manufacturer_mapping = {}
                    for product_code in sales_df[product_col].unique():
                        product_rows = sales_df[sales_df[product_col] == product_code]
                        if len(product_rows) > 0:
                            # 해당 상품코드에 가장 많이 나타나는 업체를 제조사로 사용
                            company_counts = product_rows[company_col].value_counts()
                            if len(company_counts) > 0:
                                manufacturer_mapping[product_code] = company_counts.index[0]
                    
                    # 1. 업체별로 판매가 가장 많이 된 상품코드
                    st.markdown("#### 1️⃣ 업체별 최다 판매 상품")
                    
                    # "코드별 판매수량" 컬럼이 있는지 확인 (이미 집계된 값일 수 있음)
                    code_sales_col = None
                    for col in sales_df.columns:
                        if '코드별' in str(col) and '판매' in str(col) and '수량' in str(col):
                            code_sales_col = col
                            break
                    
                    # 판매 수량 컬럼이 "코드별 판매수량"인 경우와 일반 수량 컬럼인 경우 구분
                    if '코드별' in str(quantity_col) or code_sales_col:
                        # "코드별 판매수량" 컬럼 사용 (이미 집계된 값)
                        use_col = code_sales_col if code_sales_col else quantity_col
                        if sales_df[use_col].dtype == 'object':
                            sales_df[use_col] = pd.to_numeric(sales_df[use_col], errors='coerce')
                    else:
                        # 일반 수량 컬럼도 숫자형으로 변환
                        if sales_df[quantity_col].dtype == 'object':
                            sales_df[quantity_col] = pd.to_numeric(sales_df[quantity_col], errors='coerce')
                        use_col = quantity_col
                    
                    # 상품코드별로 제조사 정보 추가 (원본 업체 컬럼 기반)
                    # 상품코드별로 가장 많이 나타나는 업체를 제조사로 사용
                    if len(manufacturer_mapping) > 0:
                        sales_df['제조사'] = sales_df[product_col].map(manufacturer_mapping)
                        # 매핑되지 않은 경우 원본 company_col 사용
                        sales_df['제조사'] = sales_df['제조사'].fillna(sales_df[company_col])
                    else:
                        # 매핑이 없는 경우 원본 company_col 사용
                        sales_df['제조사'] = sales_df[company_col]
                    
                    # 제조사별, 상품코드별로 첫 번째 값 사용 (중복 제거, 합산하지 않음)
                    company_product_sales = sales_df.groupby(['제조사', product_col])[use_col].first().reset_index()
                    company_product_sales.columns = ['제조사', product_col, '판매수량_집계']
                    
                    # 제조사별로 판매수량이 가장 큰 상품 하나만 찾기
                    company_top_product = company_product_sales.groupby('제조사').apply(
                        lambda x: x.loc[x['판매수량_집계'].idxmax()]
                    ).reset_index(drop=True)
                    company_top_product = company_top_product.rename(columns={'판매수량_집계': quantity_col})
                    
                    # 컬럼명 변경 (실제 컬럼명 사용)
                    company_top_product = company_top_product.rename(columns={'제조사': '업체', product_col: '상품코드_원본', quantity_col: '판매수량_원본'})
                    
                    # 상품명 추가
                    if product_mapping:
                        company_top_product['상품명'] = company_top_product['상품코드_원본'].map(product_mapping)
                        company_top_product['상품명'] = company_top_product['상품명'].fillna(company_top_product['상품코드_원본'])
                        display_cols = ['업체', '상품명', '판매수량']
                    else:
                        company_top_product['상품코드'] = company_top_product['상품코드_원본']
                        display_cols = ['업체', '상품코드', '판매수량']
                    
                    company_top_product_display = company_top_product.copy()
                    company_top_product_display['판매수량'] = company_top_product_display['판매수량_원본'].apply(lambda x: f"{int(x):,}")
                    st.dataframe(company_top_product_display[display_cols], use_container_width=True, height=300)
                    
                    # 2. 중복 제거하여 전체 상품별 판매 수량 (2539가지)
                    st.markdown("---")
                    st.markdown("#### 2️⃣ 전체 상품별 판매 수량 (중복 제거)")
                    
                    # 상품코드별 총 판매 수량 집계 (상품코드로 집계하되 표시는 상품명)
                    # "코드별 판매수량" 컬럼이 이미 집계된 값인지 확인
                    code_sales_col = None
                    for col in sales_df.columns:
                        if '코드별' in str(col) and '판매' in str(col) and '수량' in str(col):
                            code_sales_col = col
                            break
                    
                    # 상품코드와 제조사 매핑 생성 (원본 업체 컬럼 기반)
                    # 같은 상품코드에 여러 업체가 있을 수 있으므로, 가장 많이 나타나는 업체를 사용
                    company_mapping = {}
                    for product_code in sales_df[product_col].unique():
                        product_rows = sales_df[sales_df[product_col] == product_code]
                        if len(product_rows) > 0:
                            # 해당 상품코드에 가장 많이 나타나는 업체를 제조사로 사용
                            company_counts = product_rows[company_col].value_counts()
                            if len(company_counts) > 0:
                                company_mapping[product_code] = company_counts.index[0]
                    
                    # 매핑이 비어있으면 fallback으로 원본 매핑 사용
                    if len(company_mapping) == 0:
                        fallback_mapping = sales_df[[product_col, company_col]].drop_duplicates()
                        company_mapping = fallback_mapping.set_index(product_col)[company_col].to_dict()
                    
                    if code_sales_col and code_sales_col != quantity_col:
                        # "코드별 판매수량" 컬럼이 있으면 이를 우선 사용 (이미 집계된 값)
                        st.info(f"💡 '{code_sales_col}' 컬럼을 사용하여 집계합니다.")
                        if sales_df[code_sales_col].dtype == 'object':
                            sales_df[code_sales_col] = pd.to_numeric(sales_df[code_sales_col], errors='coerce')
                        
                        # 상품코드별로 첫 번째 값 사용 (중복 제거)
                        product_sales = sales_df.groupby(product_col)[code_sales_col].first().reset_index()
                        product_sales.columns = ['상품코드', '총판매수량']
                    else:
                        # 일반 수량 컬럼 사용 (합산)
                        product_sales = sales_df.groupby(product_col)[quantity_col].sum().reset_index()
                        product_sales.columns = ['상품코드', '총판매수량']
                    
                    product_sales = product_sales.sort_values('총판매수량', ascending=False)
                    
                    # 제조사 추가
                    product_sales['제조사'] = product_sales['상품코드'].map(company_mapping)
                    product_sales['제조사'] = product_sales['제조사'].fillna('미확인')
                    
                    # 상품명 추가
                    if product_mapping:
                        product_sales['상품명'] = product_sales['상품코드'].map(product_mapping)
                        product_sales['상품명'] = product_sales['상품명'].fillna(product_sales['상품코드'])
                    
                    # 표시용 데이터 준비
                    product_sales_display = product_sales.copy()
                    product_sales_display['총판매수량'] = product_sales_display['총판매수량'].apply(lambda x: f"{int(x):,}")
                    
                    st.info(f"📊 총 {len(product_sales)}가지 상품 (중복 제거)")
                    
                    # 검색 기능 (상품명 또는 상품코드로 검색)
                    search_product = st.text_input("🔍 상품명/상품코드 검색", "", placeholder="상품명 또는 상품코드를 입력하세요...", key='search_product')
                    
                    if search_product:
                        if product_mapping:
                            # 상품명과 상품코드 모두에서 검색
                            mask = (
                                product_sales['상품명'].astype(str).str.contains(search_product, case=False, na=False) |
                                product_sales['상품코드'].astype(str).str.contains(search_product, case=False, na=False)
                            )
                        else:
                            mask = product_sales['상품코드'].astype(str).str.contains(search_product, case=False, na=False)
                        
                        filtered_products = product_sales[mask]
                        st.info(f"검색 결과: {len(filtered_products)}건")
                        display_products = filtered_products.copy()
                        display_products['총판매수량'] = display_products['총판매수량'].apply(lambda x: f"{int(x):,}")
                        
                        if product_mapping:
                            display_cols = ['제조사', '상품명', '총판매수량']
                        else:
                            display_cols = ['제조사', '상품코드', '총판매수량']
                        
                        st.dataframe(display_products[display_cols], use_container_width=True, height=400)
                    else:
                        # 상위 100개만 표시
                        top_100 = product_sales.head(100)
                        top_100_display = top_100.copy()
                        top_100_display['총판매수량'] = top_100_display['총판매수량'].apply(lambda x: f"{int(x):,}")
                        
                        if product_mapping:
                            display_cols = ['제조사', '상품명', '총판매수량']
                        else:
                            display_cols = ['제조사', '상품코드', '총판매수량']
                        
                        st.dataframe(top_100_display[display_cols], use_container_width=True, height=400)
                        st.caption(f"상위 100개만 표시 (전체: {len(product_sales)}개)")
                    
                    # 3. 가장 많이 판매된 상품
                    st.markdown("---")
                    st.markdown("#### 3️⃣ 가장 많이 판매된 상품 TOP 10")
                    
                    top_10_products = product_sales.head(10).copy()
                    
                    # TOP 10 테이블
                    top_10_display = top_10_products.copy()
                    top_10_display['순위'] = range(1, len(top_10_display) + 1)
                    top_10_display['총판매수량'] = top_10_display['총판매수량'].apply(lambda x: f"{int(x):,}")
                    
                    if product_mapping:
                        display_cols = ['순위', '제조사', '상품명', '총판매수량']
                    else:
                        display_cols = ['순위', '제조사', '상품코드', '총판매수량']
                    
                    st.dataframe(top_10_display[display_cols], use_container_width=True)
                    
                    # 다운로드 버튼
                    st.markdown("---")
                    col_dl1, col_dl2 = st.columns(2)
                    
                    with col_dl1:
                        # 다운로드용 데이터 준비 (상품명 포함)
                        download_data = product_sales.copy()
                        if product_mapping:
                            download_data = download_data[['상품코드', '상품명', '총판매수량']]
                        else:
                            download_data = download_data[['상품코드', '총판매수량']]
                        
                        csv = download_data.to_csv(index=False).encode('utf-8-sig')
                        st.download_button(
                            label="📥 전체 상품 판매수량 CSV 다운로드",
                            data=csv,
                            file_name=f"상품_판매수량_{datetime.now().strftime('%Y%m%d')}.csv",
                            mime="text/csv"
                        )
                    
                    with col_dl2:
                        from io import BytesIO
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            # 상품명 포함하여 저장
                            if product_mapping:
                                download_product = product_sales[['상품코드', '상품명', '총판매수량']].copy()
                            else:
                                download_product = product_sales[['상품코드', '총판매수량']].copy()
                            download_product.to_excel(writer, index=False, sheet_name='상품별판매수량')
                            
                            # 업체별 최다 판매 상품도 상품명 포함 (상품코드도 함께 저장)
                            download_company = company_top_product.copy()
                            if product_mapping:
                                download_company['상품코드'] = download_company['상품코드_원본']
                                download_company = download_company[['업체', '상품명', '상품코드', '판매수량_원본']]
                                download_company.columns = ['업체', '상품명', '상품코드', '판매수량']
                            else:
                                download_company['상품코드'] = download_company['상품코드_원본']
                                download_company = download_company[['업체', '상품코드', '판매수량_원본']]
                                download_company.columns = ['업체', '상품코드', '판매수량']
                            download_company.to_excel(writer, index=False, sheet_name='업체별최다판매상품')
                        
                        st.download_button(
                            label="📥 Excel 다운로드",
                            data=output.getvalue(),
                            file_name=f"상품_판매분석_{datetime.now().strftime('%Y%m%d')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                
                else:
                    st.warning("⚠️ 업체, 상품코드, 판매 수량 컬럼을 모두 선택해주세요.")
            
            except Exception as e:
                st.error(f"판매 데이터 처리 중 오류 발생: {str(e)}")
                st.info("파일 구조를 확인하고 코드를 수정해주세요.")
        
    except Exception as e:
        st.error(f"파일 처리 중 오류 발생: {str(e)}")
        st.info("파일 구조를 확인하고 코드를 수정해주세요.")
else:
    st.info("👆 엑셀 파일을 업로드하여 대시보드를 시작하세요.")
    
    st.markdown("---")
    st.subheader("사용 방법")
    st.markdown("""
    1. **파일 업로드**: 주간 회의록 엑셀 파일을 업로드합니다.
    2. **시트 선택**: 여러 시트가 있는 경우 원하는 시트를 선택합니다.
    3. **필터 적용**: 사이드바에서 년도, 월 등을 필터링합니다.
    4. **데이터 분석**: 다양한 그래프와 차트로 데이터를 분석합니다.
    5. **다운로드**: 분석 결과를 CSV 또는 Excel로 다운로드합니다.
    """)

