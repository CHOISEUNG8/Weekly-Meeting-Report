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

# 페이지 설정
st.set_page_config(
    page_title="주간 회의록 대시보드",
    page_icon="📊",
    layout="wide"
)

st.title("📊 주간 회의록 대시보드")
st.markdown("---")

# 메모 저장/로드 함수
MEMO_DATA_DIR = "memo_data"
if not os.path.exists(MEMO_DATA_DIR):
    os.makedirs(MEMO_DATA_DIR)

def save_memo_to_file(key, value):
    """메모를 JSON 파일로 저장"""
    try:
        file_path = os.path.join(MEMO_DATA_DIR, f"{key}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({"content": value}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"메모 저장 중 오류 발생: {str(e)}")

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
        sheet_names = xls.sheet_names
        
        # 11월 및 12월 시트 자동 찾기
        november_sheet = None
        december_sheet = None
        for sheet in sheet_names:
            if '11월' in sheet or ('11' in sheet and '월' in sheet) or 'november' in sheet.lower() or 'nov' in sheet.lower():
                november_sheet = sheet
            if '12월' in sheet or ('12' in sheet and '월' in sheet) or 'december' in sheet.lower() or 'dec' in sheet.lower():
                december_sheet = sheet
        
        # 시트 선택 (12월 시트가 있으면 기본값으로 설정, 없으면 11월 시트)
        default_sheet = december_sheet if december_sheet else november_sheet
        if default_sheet:
            selected_sheet = st.selectbox("시트 선택", sheet_names, index=sheet_names.index(default_sheet))
        else:
            selected_sheet = st.selectbox("시트 선택", sheet_names)
            st.info("💡 12월 또는 11월 시트를 찾지 못했습니다. 시트 이름에 '12월', '11월' 또는 '12', '11'이 포함되어 있는지 확인하세요.")
        
        df = pd.read_excel(xls, sheet_name=selected_sheet)
        
        # 선택된 시트에서 월 정보 추출
        selected_month = None
        if '12월' in selected_sheet or ('12' in selected_sheet and '월' in selected_sheet):
            selected_month = 12
        elif '11월' in selected_sheet or ('11' in selected_sheet and '월' in selected_sheet):
            selected_month = 11
        
        # 스마트공장 시트인지 확인
        is_smart_factory = '스마트공장' in selected_sheet or 'smart' in selected_sheet.lower() or 'factory' in selected_sheet.lower()
        
        # 스마트공장 시트인 경우 업체별 상담내역 담당자 페이지 표시
        if is_smart_factory:
            st.subheader("🏭 스마트공장 업체별 상담내역 담당자")
            st.markdown("---")
            
            # 업체 컬럼 찾기
            company_columns = [col for col in df.columns if any(keyword in str(col).lower() for keyword in ['업체', 'company', '회사', '고객', 'customer', 'client'])]
            # 담당자 컬럼 찾기 (P열 우선)
            # P열(16번째 컬럼, 인덱스 15)이 있으면 우선 사용
            manager_columns = []
            if len(df.columns) > 15:
                p_col = df.columns[15]  # P열 (16번째 컬럼)
                manager_columns.append(p_col)
            # 기존 키워드 기반 검색도 추가
            manager_columns.extend([col for col in df.columns 
                                   if any(keyword in str(col).lower() for keyword in ['담당자', 'manager', '담당', '담당인', 'contact', '담당자명'])
                                   and col not in manager_columns])
            # 상담내역 컬럼 찾기
            consultation_columns = [col for col in df.columns if any(keyword in str(col).lower() for keyword in ['상담', 'consultation', '내역', '내용', 'content', '상담내용', '상담내역'])]
            
            # 컬럼 선택 옵션 제공
            col_select1, col_select2, col_select3 = st.columns(3)
            with col_select1:
                if len(company_columns) > 0:
                    company_col = st.selectbox("업체 컬럼 선택", company_columns, key='smart_company')
                else:
                    company_col = st.selectbox("업체 컬럼 선택", [""] + list(df.columns), key='smart_company')
                    if company_col == "":
                        company_col = None
            
            with col_select2:
                if len(manager_columns) > 0:
                    manager_col = st.selectbox("담당자 컬럼 선택", manager_columns, key='smart_manager')
                else:
                    manager_col = st.selectbox("담당자 컬럼 선택", [""] + list(df.columns), key='smart_manager')
                    if manager_col == "":
                        manager_col = None
            
            with col_select3:
                if len(consultation_columns) > 0:
                    consultation_col = st.selectbox("상담내역 컬럼 선택", consultation_columns, key='smart_consultation')
                else:
                    consultation_col = st.selectbox("상담내역 컬럼 선택", [""] + list(df.columns), key='smart_consultation')
                    if consultation_col == "":
                        consultation_col = None
            
            if company_col and manager_col:
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
                
                # 담당자 컬럼을 파트로 변환
                df['파트'] = df[manager_col].apply(manager_to_part)
                
                # 업체별 파트 집계 (담당자 정보는 유지하되 파트로 그룹화)
                company_manager = df.groupby([company_col, '파트', manager_col]).size().reset_index(name='상담건수')
                company_manager = company_manager.sort_values([company_col, '파트', '상담건수'], ascending=[True, True, False])
                
                # 업체별 요약
                company_summary = df.groupby(company_col).agg({
                    manager_col: 'count',
                }).reset_index()
                company_summary.columns = [company_col, '총상담건수']
                company_summary = company_summary.sort_values('총상담건수', ascending=False)
                
                # 통계 카드
                col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                with col_stat1:
                    st.metric("총 업체 수", len(company_summary))
                with col_stat2:
                    st.metric("총 상담 건수", f"{company_summary['총상담건수'].sum():,}건")
                with col_stat3:
                    if manager_col:
                        unique_managers = df[manager_col].nunique()
                        st.metric("담당자 수", f"{unique_managers}명")
                with col_stat4:
                    # 파트별 통계
                    part_counts = df['파트'].value_counts()
                    st.metric("파트 수", f"{len(part_counts)}개")
                
                st.markdown("---")
                
                # 업체별 상담내역 담당자 테이블
                st.markdown("#### 📋 업체별 상담내역 담당자")
                
                # 검색 기능
                search_company = st.text_input("🔍 업체명 검색", "", placeholder="업체명을 입력하세요...")
                
                if search_company:
                    filtered_data = company_manager[company_manager[company_col].astype(str).str.contains(search_company, case=False, na=False)]
                    st.info(f"검색 결과: {len(filtered_data)}건")
                else:
                    filtered_data = company_manager
                
                # 테이블 표시 (파트 컬럼 포함)
                display_columns = [company_col, '파트', manager_col, '상담건수']
                if consultation_col:
                    # 상담내역이 있으면 추가
                    consultation_summary = df.groupby([company_col, '파트', manager_col])[consultation_col].apply(lambda x: ' | '.join(x.dropna().astype(str).unique()[:3])).reset_index()
                    consultation_summary.columns = [company_col, '파트', manager_col, '상담내역_요약']
                    filtered_data = filtered_data.merge(consultation_summary, on=[company_col, '파트', manager_col], how='left')
                    display_columns.append('상담내역_요약')
                
                # 천단위 구분 기호 적용
                filtered_data_display = filtered_data.copy()
                filtered_data_display['상담건수'] = filtered_data_display['상담건수'].apply(lambda x: f"{x:,}건")
                
                st.dataframe(
                    filtered_data_display[display_columns],
                    use_container_width=True,
                    height=400
                )
                
                # 파트별 통계
                st.markdown("---")
                st.markdown("#### 📊 파트별 통계")
                
                col_part1, col_part2 = st.columns(2)
                
                with col_part1:
                    # 파트별 상담건수
                    part_summary = df.groupby('파트').size().reset_index(name='상담건수')
                    part_summary = part_summary.sort_values('상담건수', ascending=False)
                    fig_parts = px.bar(
                        part_summary,
                        x='파트',
                        y='상담건수',
                        title='파트별 상담건수',
                        labels={'파트': '파트', '상담건수': '상담건수'},
                        color='상담건수',
                        color_continuous_scale='Blues'
                    )
                    fig_parts.update_layout(
                        xaxis_title="파트",
                        yaxis_title="상담건수",
                        showlegend=False
                    )
                    fig_parts.update_traces(
                        hovertemplate='<b>%{x}</b><br>상담건수: %{y}건<extra></extra>'
                    )
                    st.plotly_chart(fig_parts, use_container_width=True)
                
                with col_part2:
                    # 파트별 비율 (파이 차트)
                    part_counts = df['파트'].value_counts()
                    fig_part_pie = px.pie(
                        values=part_counts.values,
                        names=part_counts.index,
                        title='파트별 상담건수 비율',
                        hole=0.4
                    )
                    fig_part_pie.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig_part_pie, use_container_width=True)
                
                # 업체별 담당자 분포 차트
                st.markdown("---")
                st.markdown("#### 📊 업체별 담당자 분포")
                
                col_chart1, col_chart2 = st.columns(2)
                
                with col_chart1:
                    # 업체별 총 상담건수 (상위 10개)
                    top_companies = company_summary.head(10)
                    fig_companies = px.bar(
                        top_companies,
                        x=company_col,
                        y='총상담건수',
                        title='업체별 총 상담건수 (상위 10개)',
                        labels={company_col: '업체', '총상담건수': '상담건수'},
                        color='총상담건수',
                        color_continuous_scale='Blues'
                    )
                    fig_companies.update_layout(
                        xaxis_title="업체",
                        yaxis_title="상담건수",
                        showlegend=False,
                        xaxis_tickangle=-45
                    )
                    fig_companies.update_traces(
                        hovertemplate='<b>%{x}</b><br>상담건수: %{y}건<extra></extra>'
                    )
                    st.plotly_chart(fig_companies, use_container_width=True)
                
                with col_chart2:
                    # 담당자별 상담건수 (상위 10개)
                    manager_summary = df.groupby(manager_col).size().reset_index(name='상담건수')
                    manager_summary = manager_summary.sort_values('상담건수', ascending=False).head(10)
                    fig_managers = px.bar(
                        manager_summary,
                        x=manager_col,
                        y='상담건수',
                        title='담당자별 상담건수 (상위 10개)',
                        labels={manager_col: '담당자', '상담건수': '상담건수'},
                        color='상담건수',
                        color_continuous_scale='Greens'
                    )
                    fig_managers.update_layout(
                        xaxis_title="담당자",
                        yaxis_title="상담건수",
                        showlegend=False,
                        xaxis_tickangle=-45
                    )
                    fig_managers.update_traces(
                        hovertemplate='<b>%{x}</b><br>상담건수: %{y}건<extra></extra>'
                    )
                    st.plotly_chart(fig_managers, use_container_width=True)
                
                # 다운로드 버튼
                st.markdown("---")
                col_dl1, col_dl2 = st.columns(2)
                
                with col_dl1:
                    csv = filtered_data[display_columns].to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="📥 CSV 다운로드",
                        data=csv,
                        file_name=f"스마트공장_업체별상담내역_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
                
                with col_dl2:
                    from io import BytesIO
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        filtered_data[display_columns].to_excel(writer, index=False, sheet_name='업체별상담내역')
                    st.download_button(
                        label="📥 Excel 다운로드",
                        data=output.getvalue(),
                        file_name=f"스마트공장_업체별상담내역_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            
            else:
                st.warning("⚠️ 업체 컬럼과 담당자 컬럼을 선택해주세요.")
        
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
                    st.info(f"📊 '{selected_sheet}' 시트의 전체 데이터를 표시합니다.")
            else:
                # 날짜 컬럼이 없으면 시트 이름으로 판단
                if selected_month is not None:
                    st.info(f"📊 '{selected_sheet}' 시트의 전체 데이터를 표시합니다.")
            
            # 사이드바 필터
            st.sidebar.header("필터 옵션")
        
        # 회의결과 및 경영자의견 메모장 추가 (사이드바 - 주차별)
        month_label_sidebar = f"{selected_month}월" if selected_month is not None else "월"
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"#### 📝 {month_label_sidebar} 회의결과 및 경영자의견")
        
        # 주차를 올바른 순서로 정렬하는 함수
        def sort_weeks_korean_sidebar(weeks):
            """주차를 첫째주, 둘째주, 셋째주, 넷째주 순서로 정렬"""
            week_order = {'첫째': 1, '둘째': 2, '셋째': 3, '넷째': 4, '다섯째': 5}
            def get_week_number(week_str):
                for key, value in week_order.items():
                    if key in week_str:
                        return value
                return 999  # 알 수 없는 주차는 마지막에
            return sorted(weeks, key=get_week_number)
        
        # 주차 정보 계산 (사이드바에서 사용하기 위해)
        sidebar_weeks = []
        if len(date_columns) > 0:
            date_col = date_columns[0]
            df_temp = df.copy()
            df_temp[date_col] = pd.to_datetime(df_temp[date_col], errors='coerce')
            df_temp['주차'] = df_temp[date_col].dt.isocalendar().week
            min_week = df_temp['주차'].min() if len(df_temp) > 0 else None
            
            # 주차 번호를 한국어로 변환하는 함수
            def week_to_korean_sidebar(week_num, min_week=None, month=None):
                week_korean = ['첫째', '둘째', '셋째', '넷째', '다섯째']
                month_label = f"{month}월" if month is not None else "월"
                if min_week is not None:
                    relative_week = week_num - min_week
                    if 0 <= relative_week < len(week_korean):
                        return f"{month_label} {week_korean[relative_week]}주"
                return f"{month_label} {week_num}주"
            
            df_temp['주차_한글'] = df_temp['주차'].apply(lambda x: week_to_korean_sidebar(x, min_week, selected_month))
            sidebar_weeks = sort_weeks_korean_sidebar(df_temp['주차_한글'].unique().tolist())
        
        # 주차별 회의결과 및 경영자의견
        if len(sidebar_weeks) > 0:
            # 사이드바와 메인 페이지 동기화를 위한 키 (selected_month를 직접 사용)
            month_key = f"{selected_month}월" if selected_month is not None else "월"
            sidebar_week_select_key = f"sidebar_week_select_{month_key}"
            main_week_select_key = f"main_week_select_{month_key}"
            
            # 주차 선택 (사이드바와 메인 페이지 동기화)
            # 메인 페이지에서 선택한 주차가 있으면 그것을 사용, 없으면 첫 번째 주차
            if main_week_select_key in st.session_state and st.session_state[main_week_select_key] in sidebar_weeks:
                # 메인 페이지에서 선택한 주차 사용
                default_index = sidebar_weeks.index(st.session_state[main_week_select_key])
            elif sidebar_week_select_key in st.session_state and st.session_state[sidebar_week_select_key] in sidebar_weeks:
                # 사이드바에서 이전에 선택한 주차 사용
                default_index = sidebar_weeks.index(st.session_state[sidebar_week_select_key])
            else:
                default_index = 0
            
            selected_week_sidebar = st.sidebar.selectbox(
                "주차 선택", 
                sidebar_weeks, 
                key=sidebar_week_select_key,
                index=default_index
            )
            
            # 선택된 주차의 회의결과 메모 키
            meeting_memo_key_sidebar = f"meeting_memo_{month_label_sidebar}_{selected_week_sidebar}"
            
            # 주차별로 독립적인 session_state 키 사용 (주차가 변경되면 항상 파일에서 불러오기)
            current_week_state_key_sidebar = f"current_week_sidebar_{meeting_memo_key_sidebar}"
            if current_week_state_key_sidebar not in st.session_state or st.session_state.get(f"last_selected_week_sidebar_{month_label_sidebar}") != selected_week_sidebar:
                # 주차가 변경되었거나 처음 로드하는 경우 파일에서 불러오기
                loaded_memo_sidebar = load_memo_from_file(meeting_memo_key_sidebar)
                st.session_state[meeting_memo_key_sidebar] = loaded_memo_sidebar if loaded_memo_sidebar else ""
                st.session_state[current_week_state_key_sidebar] = True
                st.session_state[f"last_selected_week_sidebar_{month_label_sidebar}"] = selected_week_sidebar
            
            # 회의결과 메모 입력
            meeting_memo_text_sidebar = st.sidebar.text_area(
                f"{selected_week_sidebar} 회의결과 및 경영자의견을 입력하세요",
                value=st.session_state.get(meeting_memo_key_sidebar, ""),
                height=200,
                placeholder=f"{selected_week_sidebar} 회의결과 및 경영자의견을 작성하세요. 내용은 자동으로 저장됩니다.",
                key=f"meeting_memo_input_sidebar_{month_label_sidebar}_{selected_week_sidebar}"
            )
            
            # 회의결과 메모 저장 (입력 시마다 자동 저장)
            if meeting_memo_text_sidebar != st.session_state.get(meeting_memo_key_sidebar, ""):
                st.session_state[meeting_memo_key_sidebar] = meeting_memo_text_sidebar
                save_memo_to_file(meeting_memo_key_sidebar, meeting_memo_text_sidebar)
                st.sidebar.success(f"✅ {selected_week_sidebar} 회의결과가 저장되었습니다.", icon="💾")
            
            # 저장된 회의결과 메모 표시 (입력창과 별도로)
            if st.session_state.get(meeting_memo_key_sidebar, ""):
                with st.sidebar.expander(f"📋 저장된 {selected_week_sidebar} 회의결과 및 경영자의견 보기", expanded=False):
                    meeting_memo_display_sidebar = st.session_state[meeting_memo_key_sidebar].replace('\n', '<br>')
                    st.sidebar.markdown(meeting_memo_display_sidebar, unsafe_allow_html=True)
            
            # 모든 주차별 회의결과 요약 보기
            st.sidebar.markdown("---")
            st.sidebar.markdown("#### 📊 주차별 회의결과 요약")
            meeting_summary_sidebar = {}
            for week in sidebar_weeks:
                week_key = f"meeting_memo_{month_label_sidebar}_{week}"
                # 파일에서 불러오기
                loaded_week_memo = load_memo_from_file(week_key)
                if loaded_week_memo:
                    meeting_summary_sidebar[week] = loaded_week_memo
                elif week_key in st.session_state and st.session_state[week_key]:
                    meeting_summary_sidebar[week] = st.session_state[week_key]
            
            if meeting_summary_sidebar:
                # 정렬된 주차 순서로 표시
                for week in sidebar_weeks:
                    if week in meeting_summary_sidebar:
                        content = meeting_summary_sidebar[week]
                        with st.sidebar.expander(f"📝 {week} 회의결과", expanded=False):
                            week_display = content.replace('\n', '<br>')
                            st.sidebar.markdown(week_display, unsafe_allow_html=True)
            else:
                st.sidebar.info("아직 작성된 주차별 회의결과가 없습니다.")
            
            # 주차별 경영진 회의록 요약 추가
            st.sidebar.markdown("---")
            st.sidebar.markdown("#### 📋 주차별 경영진 회의록 요약")
            executive_meeting_summary = {}
            for week in sidebar_weeks:
                week_key = f"executive_meeting_{month_label_sidebar}_{week}"
                # 파일에서 불러오기
                loaded_executive_meeting = load_memo_from_file(week_key)
                if loaded_executive_meeting:
                    executive_meeting_summary[week] = loaded_executive_meeting
            
            if executive_meeting_summary:
                # 정렬된 주차 순서로 표시
                for week in sidebar_weeks:
                    if week in executive_meeting_summary:
                        content = executive_meeting_summary[week]
                        # 내용 요약 (첫 100자만 표시)
                        summary = content[:100] + "..." if len(content) > 100 else content
                        with st.sidebar.expander(f"📋 {week} 경영진 회의록", expanded=False):
                            week_display = content.replace('\n', '<br>')
                            st.sidebar.markdown(week_display, unsafe_allow_html=True)
            else:
                st.sidebar.info("아직 작성된 주차별 경영진 회의록이 없습니다.")
        else:
            # 주차 정보가 없으면 월별로 표시
            meeting_memo_key_sidebar = f"meeting_memo_{month_label_sidebar}"
            # 파일에서 메모 불러오기
            if meeting_memo_key_sidebar not in st.session_state:
                loaded_memo_sidebar = load_memo_from_file(meeting_memo_key_sidebar)
                if loaded_memo_sidebar:
                    st.session_state[meeting_memo_key_sidebar] = loaded_memo_sidebar
                else:
                    st.session_state[meeting_memo_key_sidebar] = ""
            
            # 회의결과 메모 입력
            meeting_memo_text_sidebar = st.sidebar.text_area(
                "회의결과 및 경영자의견을 입력하세요",
                value=st.session_state.get(meeting_memo_key_sidebar, ""),
                height=200,
                placeholder="회의결과 및 경영자의견을 작성하세요. 내용은 자동으로 저장됩니다.",
                key=f"meeting_memo_input_sidebar_{month_label_sidebar}"
            )
            
            # 회의결과 메모 저장 (입력 시마다 자동 저장)
            if meeting_memo_text_sidebar != st.session_state.get(meeting_memo_key_sidebar, ""):
                st.session_state[meeting_memo_key_sidebar] = meeting_memo_text_sidebar
                save_memo_to_file(meeting_memo_key_sidebar, meeting_memo_text_sidebar)
                st.sidebar.success("✅ 회의결과가 저장되었습니다.", icon="💾")
            
            # 저장된 회의결과 메모 표시 (입력창과 별도로)
            if st.session_state.get(meeting_memo_key_sidebar, ""):
                with st.sidebar.expander("📋 저장된 회의결과 및 경영자의견 보기", expanded=False):
                    meeting_memo_display_sidebar = st.session_state[meeting_memo_key_sidebar].replace('\n', '<br>')
                    st.sidebar.markdown(meeting_memo_display_sidebar, unsafe_allow_html=True)
        
        if '년' in df.columns:
            years = sorted(df['년'].dropna().unique())
            selected_years = st.sidebar.multiselect("년도 선택", years, default=years)
            df = df[df['년'].isin(selected_years)]
        
        # 선택된 월 데이터만 표시 중이면 월 필터는 숨김
        if '월' in df.columns:
            months = sorted(df['월'].dropna().unique())
            if selected_month is not None and selected_month in months and len(months) == 1:
                st.sidebar.info(f"📅 {selected_month}월 데이터만 표시 중")
            else:
                selected_months = st.sidebar.multiselect("월 선택", months, default=months)
                df = df[df['월'].isin(selected_months)]
            
            # 선택된 월 목표 달성율 계산
            month_label = f"{selected_month}월" if selected_month is not None else "월"
            st.subheader(f"🎯 {month_label} 목표 달성 현황")
            
            # 목표 설정
            target_part1 = 17000000  # 1파트 목표: 17,000,000원
            target_part2 = 1000000   # 2파트 목표: 1,000,000원
            
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
        
        if amount_col is not None:
            # 금액 컬럼이 숫자형이 아니면 변환 시도
            if df[amount_col].dtype == 'object':
                df[amount_col] = pd.to_numeric(df[amount_col], errors='coerce')
            
            if part_col is not None:
                # 파트 컬럼이 있는 경우
                # 1파트 데이터 필터링 (1, 1파트, part1 등)
                part1_mask = (
                    df[part_col].astype(str).str.contains('1파트|part1|^1$', na=False, regex=True) |
                    (df[part_col].astype(str).str.strip() == '1')
                )
                if part1_mask.any():
                    part1_achieved = df[part1_mask][amount_col].sum()
                    part1_count = part1_mask.sum()
                
                # 2파트 데이터 필터링 (2, 2파트, part2 등)
                part2_mask = (
                    df[part_col].astype(str).str.contains('2파트|part2|^2$', na=False, regex=True) |
                    (df[part_col].astype(str).str.strip() == '2')
                )
                if part2_mask.any():
                    part2_achieved = df[part2_mask][amount_col].sum()
                    part2_count = part2_mask.sum()
            else:
                # 파트 컬럼이 없는 경우, 전체 데이터를 확인
                # 사용자가 직접 입력하거나, 다른 방법으로 구분
                with st.expander("💡 파트 컬럼이 없습니다. 수동으로 분할하세요."):
                    total_amount = df[amount_col].sum()
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
        if amount_col is not None and '월' in df.columns and selected_month is not None and selected_month in df['월'].values:
            total_profit = part1_achieved + part2_achieved
            total_count = len(df)
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
        
        # 선택된 월 데이터 분석 차트
        month_label = f"{selected_month}월" if selected_month is not None else "월"
        st.subheader(f"📊 {month_label} 데이터 분석")
        
        # 주차 번호를 한국어로 변환하는 함수
        def week_to_korean(week_num, min_week=None, month=None):
            """주차 번호를 한국어로 변환 (예: 45 -> '11월 첫째주' 또는 '12월 첫째주')"""
            week_korean = ['첫째', '둘째', '셋째', '넷째', '다섯째']
            month_label = f"{month}월" if month is not None else "월"
            if min_week is not None:
                # 최소 주차를 기준으로 상대적 주차 계산
                relative_week = week_num - min_week
                if 0 <= relative_week < len(week_korean):
                    return f"{month_label} {week_korean[relative_week]}주"
            return f"{month_label} {week_num}주"
        
        # 주간별 또는 일별 트렌드 (날짜 컬럼이 있는 경우)
        if '년월' in df.columns or len(date_columns) > 0:
            if len(date_columns) > 0:
                date_col = date_columns[0]
                # 주간별 집계
                df['주차'] = df[date_col].dt.isocalendar().week
                df['일'] = df[date_col].dt.day
                
                # 선택된 월의 최소 주차 번호 찾기 (첫째주 기준)
                min_week = df['주차'].min() if len(df) > 0 else None
                
                # 주차를 한국어로 변환
                df['주차_한글'] = df['주차'].apply(lambda x: week_to_korean(x, min_week, selected_month))
                
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
                            showgrid=False  # 오른쪽 Y축 그리드선 비활성화
                        )
                        month_label = f"{selected_month}월" if selected_month is not None else "월"
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
                            showgrid=False  # 오른쪽 Y축 그리드선 비활성화
                        )
                        month_label = f"{selected_month}월" if selected_month is not None else "월"
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
        
        # 플랫폼별 비교
        month_label = f"{selected_month}월" if selected_month is not None else "월"
        st.subheader(f"📋 플랫폼별 분석 ({month_label})")
        
        # 텍스트/카테고리 컬럼 찾기
        category_columns = df.select_dtypes(include=['object']).columns.tolist()
        # 너무 많은 고유값을 가진 컬럼 제외 (ID나 설명 컬럼 제외)
        category_columns = [col for col in category_columns 
                           if df[col].nunique() <= 50 and df[col].nunique() > 1]
        
        if len(category_columns) > 0:
            category_col = st.selectbox("분류 기준 선택", category_columns, key='category_select')
            
            # 총 판매수량 분석 섹션 제목 추가
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
            
    
        
        # 상세 데이터 테이블
        month_label = f"{selected_month}월" if selected_month is not None else "월"
        st.subheader(f"📋 {month_label} 상세 데이터")
        
        # 검색 및 필터 기능
        col_search, col_filter = st.columns([3, 1])
        with col_search:
            search_term = st.text_input("🔍 검색", "", placeholder="모든 컬럼에서 검색...")
        with col_filter:
            show_rows = st.selectbox("표시 행 수", [50, 100, 200, 500, "전체"], index=1)
        
        if search_term:
            # 모든 컬럼에서 검색
            mask = df.astype(str).apply(lambda x: x.str.contains(search_term, case=False, na=False)).any(axis=1)
            display_df = df[mask]
            st.info(f"검색 결과: {len(display_df)}건 발견")
        else:
            display_df = df
        
        # 행 수 제한
        if isinstance(show_rows, int) and len(display_df) > show_rows:
            display_df = display_df.head(show_rows)
            st.caption(f"상위 {show_rows}건만 표시 중 (전체: {len(df)}건)")
        
        st.dataframe(display_df, use_container_width=True, height=400)
        
        # 다운로드 버튼
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        with col1:
            # CSV 다운로드
            csv = display_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 CSV 다운로드",
                data=csv,
                file_name=f"주간회의록_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        
        with col2:
            # Excel 다운로드
            from io import BytesIO
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                display_df.to_excel(writer, index=False, sheet_name='데이터')
            st.download_button(
                label="📥 Excel 다운로드",
                data=output.getvalue(),
                file_name=f"주간회의록_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        # 메모장 기능 추가 (파트별로 구분)
        st.markdown("---")
        st.markdown(f"#### 📝 {month_label} 계획 (파트별)")
        
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
                placeholder="1파트 메모를 작성하세요. 내용은 자동으로 저장됩니다.",
                key=f"memo_input_{month_label}_part1"
            )
            
            # 1파트 메모 저장 (입력 시마다 자동 저장)
            if memo_text_part1 != st.session_state.get(memo_key_part1, ""):
                st.session_state[memo_key_part1] = memo_text_part1
                save_memo_to_file(memo_key_part1, memo_text_part1)
                st.success("✅ 1파트 메모가 저장되었습니다.", icon="💾")
            
            # 저장된 1파트 메모 표시
            if st.session_state.get(memo_key_part1, ""):
                with st.expander("📋 저장된 1파트 메모 보기", expanded=False):
                    memo_display_part1 = st.session_state[memo_key_part1].replace('\n', '<br>')
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
                placeholder="2파트 메모를 작성하세요. 내용은 자동으로 저장됩니다.",
                key=f"memo_input_{month_label}_part2"
            )
            
            # 2파트 메모 저장 (입력 시마다 자동 저장)
            if memo_text_part2 != st.session_state.get(memo_key_part2, ""):
                st.session_state[memo_key_part2] = memo_text_part2
                save_memo_to_file(memo_key_part2, memo_text_part2)
                st.success("✅ 2파트 메모가 저장되었습니다.", icon="💾")
            
            # 저장된 2파트 메모 표시
            if st.session_state.get(memo_key_part2, ""):
                with st.expander("📋 저장된 2파트 메모 보기", expanded=False):
                    memo_display_part2 = st.session_state[memo_key_part2].replace('\n', '<br>')
                    st.markdown(memo_display_part2, unsafe_allow_html=True)
        
        # 주차별 경영진 회의록 추가
        st.markdown("---")
        st.markdown(f"#### 📋 {month_label} 주차별 경영진 회의록")
        
        # 주차를 올바른 순서로 정렬하는 함수
        def sort_weeks_korean(weeks):
            """주차를 첫째주, 둘째주, 셋째주, 넷째주 순서로 정렬"""
            week_order = {'첫째': 1, '둘째': 2, '셋째': 3, '넷째': 4, '다섯째': 5}
            def get_week_number(week_str):
                for key, value in week_order.items():
                    if key in week_str:
                        return value
                return 999  # 알 수 없는 주차는 마지막에
            return sorted(weeks, key=get_week_number)
        
        # 주차 정보가 있는 경우
        if '주차_한글' in df.columns:
            # 고유한 주차 목록 가져오기 (올바른 순서로 정렬)
            unique_weeks = sort_weeks_korean(df['주차_한글'].unique().tolist())
            
            if len(unique_weeks) > 0:
                # 사이드바와 메인 페이지 동기화를 위한 키 (selected_month를 직접 사용)
                month_key = f"{selected_month}월" if selected_month is not None else "월"
                sidebar_week_select_key = f"sidebar_week_select_{month_key}"
                main_week_select_key = f"main_week_select_{month_key}"
                
                # 주차 선택 (사이드바와 메인 페이지 동기화)
                # 사이드바에서 선택한 주차가 있으면 그것을 사용, 없으면 첫 번째 주차
                if sidebar_week_select_key in st.session_state and st.session_state[sidebar_week_select_key] in unique_weeks:
                    # 사이드바에서 선택한 주차 사용 (우선순위)
                    default_index = unique_weeks.index(st.session_state[sidebar_week_select_key])
                elif main_week_select_key in st.session_state and st.session_state[main_week_select_key] in unique_weeks:
                    # 메인 페이지에서 이전에 선택한 주차 사용
                    default_index = unique_weeks.index(st.session_state[main_week_select_key])
                else:
                    default_index = 0
                
                selected_week = st.selectbox("주차 선택", unique_weeks, key=main_week_select_key, index=default_index)
                
                # 선택된 주차의 회의록 키
                meeting_key = f"executive_meeting_{month_label}_{selected_week}"
                
                # 주차별로 독립적인 session_state 키 사용 (주차가 변경되면 항상 파일에서 불러오기)
                current_week_state_key = f"current_week_{meeting_key}"
                if current_week_state_key not in st.session_state or st.session_state.get(f"last_selected_week_{month_label}") != selected_week:
                    # 주차가 변경되었거나 처음 로드하는 경우 파일에서 불러오기
                    loaded_meeting = load_memo_from_file(meeting_key)
                    st.session_state[meeting_key] = loaded_meeting if loaded_meeting else ""
                    st.session_state[current_week_state_key] = True
                    st.session_state[f"last_selected_week_{month_label}"] = selected_week
                
                # 주차별 경영진 회의록 입력
                meeting_text = st.text_area(
                    f"{selected_week} 경영진 회의록을 입력하세요",
                    value=st.session_state.get(meeting_key, ""),
                    height=200,
                    placeholder=f"{selected_week} 경영진 회의록을 작성하세요. 내용은 자동으로 저장됩니다.",
                    key=f"meeting_input_{month_label}_{selected_week}"
                )
                
                # 회의록 저장 (입력 시마다 자동 저장)
                if meeting_text != st.session_state.get(meeting_key, ""):
                    st.session_state[meeting_key] = meeting_text
                    save_memo_to_file(meeting_key, meeting_text)
                    st.success(f"✅ {selected_week} 경영진 회의록이 저장되었습니다.", icon="💾")
                
                # 저장된 회의록 표시
                if st.session_state[meeting_key]:
                    with st.expander(f"📋 저장된 {selected_week} 경영진 회의록 보기", expanded=False):
                        meeting_display = st.session_state[meeting_key].replace('\n', '<br>')
                        st.markdown(meeting_display, unsafe_allow_html=True)
                
                # 모든 주차별 회의록 요약 보기
                st.markdown("---")
                st.markdown("#### 📊 주차별 회의록 요약")
                meeting_summary = {}
                for week in unique_weeks:
                    week_key = f"executive_meeting_{month_label}_{week}"
                    # 파일에서 불러오기
                    loaded_week_meeting = load_memo_from_file(week_key)
                    if loaded_week_meeting:
                        meeting_summary[week] = loaded_week_meeting
                    elif week_key in st.session_state and st.session_state[week_key]:
                        meeting_summary[week] = st.session_state[week_key]
                
                # 선택된 주차를 추적하여 주차 변경 시 자동으로 열리도록 함
                summary_selected_week_key = f"summary_selected_week_{month_label}"
                if summary_selected_week_key not in st.session_state:
                    st.session_state[summary_selected_week_key] = selected_week
                
                # 주차가 변경되었는지 확인
                week_changed = st.session_state[summary_selected_week_key] != selected_week
                if week_changed:
                    st.session_state[summary_selected_week_key] = selected_week
                
                if meeting_summary:
                    # 선택된 주차의 회의록을 먼저 표시하고 자동으로 열기
                    # 주차가 변경되었거나 처음 로드하는 경우 expanded=True
                    if selected_week in meeting_summary:
                        content = meeting_summary[selected_week]
                        # 선택된 주차는 항상 expanded=True (주차 변경 시 자동으로 열림)
                        with st.expander(f"📝 {selected_week} 회의록", expanded=True):
                            week_display = content.replace('\n', '<br>')
                            st.markdown(week_display, unsafe_allow_html=True)
                    
                    # 나머지 주차의 회의록 표시 (선택된 주차 제외)
                    # 정렬된 순서로 표시하되, 선택된 주차는 제외
                    for week in unique_weeks:
                        if week in meeting_summary and week != selected_week:
                            content = meeting_summary[week]
                            # 선택되지 않은 주차는 expanded=False
                            with st.expander(f"📝 {week} 회의록", expanded=False):
                                week_display = content.replace('\n', '<br>')
                                st.markdown(week_display, unsafe_allow_html=True)
                else:
                    st.info("아직 작성된 주차별 회의록이 없습니다.")
            else:
                st.info("주차 정보를 찾을 수 없습니다.")
        else:
            st.info("주차 정보가 없어 주차별 회의록을 작성할 수 없습니다. 날짜 정보가 포함된 데이터를 업로드해주세요.")
        
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

