"""
주간 회의록 데이터를 월별로 집계하고 시각화하는 대시보드 프로토타입
Streamlit 기반 웹 대시보드
"""

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import openpyxl

# 페이지 설정
st.set_page_config(
    page_title="주간 회의록 대시보드",
    page_icon="📊",
    layout="wide"
)

st.title("📊 주간 회의록 대시보드")
st.markdown("---")

# 로컬 파일 또는 업로드 파일 사용
import os

excel_file_path = '주간회의록.xlsx'
sales_data_path = '2025 정산서 기준 판매 데이터.xlsx'
uploaded_file = None

# 로컬 파일이 있으면 사용, 없으면 업로드 받기
if os.path.exists(excel_file_path):
    # 로컬 파일 자동 사용 (체크박스 숨김)
    uploaded_file = excel_file_path
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
        
        # 11월 시트 자동 찾기
        november_sheet = None
        for sheet in sheet_names:
            if '11월' in sheet or '11' in sheet or 'november' in sheet.lower() or 'nov' in sheet.lower():
                november_sheet = sheet
                break
        
        # 12월 시트 자동 찾기 (11월 시트가 없을 경우)
        december_sheet = None
        if not november_sheet:
            for sheet in sheet_names:
                if '12월' in sheet or '12' in sheet or 'december' in sheet.lower() or 'dec' in sheet.lower():
                    december_sheet = sheet
                    break
        
        # 시트 선택 (11월 또는 12월 시트가 있으면 기본값으로 설정)
        if november_sheet:
            # st.success(f"✅ 11월 데이터 시트 발견: **{november_sheet}**")  # 숨김
            selected_sheet = st.selectbox("시트 선택", sheet_names, index=sheet_names.index(november_sheet))
        elif december_sheet:
            # st.success(f"✅ 12월 데이터 시트 발견: **{december_sheet}**")  # 숨김
            selected_sheet = st.selectbox("시트 선택", sheet_names, index=sheet_names.index(december_sheet))
        else:
            selected_sheet = st.selectbox("시트 선택", sheet_names)
            st.info("💡 11월 또는 12월 시트를 찾지 못했습니다. 시트 이름에 '11월', '12월' 또는 '11', '12'가 포함되어 있는지 확인하세요.")
        
        df = pd.read_excel(xls, sheet_name=selected_sheet)
        
        # P열(16번째 컬럼, 인덱스 15)의 담당자 컬럼을 파트 컬럼으로 변환
        p_column_index = 15  # P열은 16번째 (0-based index: 15)
        if len(df.columns) > p_column_index:
            manager_col_p = df.columns[p_column_index]
            
            # 담당자 컬럼을 파트 컬럼으로 변환
            if manager_col_p in df.columns:
                # 담당자 이름에 따라 파트 매핑
                # 맹기열만 2파트, 나머지는 모두 1파트
                def map_to_part(manager_name):
                    manager_name = str(manager_name).strip()
                    # 맹기열인 경우 2파트
                    if '맹기열' in manager_name:
                        return '2파트'
                    # 나머지는 모두 1파트 (빈 값이 아닌 경우)
                    elif manager_name and manager_name != 'nan' and manager_name != '':
                        return '1파트'
                    # 빈 값은 그대로 반환
                    return ''
                
                df['파트'] = df[manager_col_p].astype(str).apply(map_to_part)
        
        # 11월 시트인지 확인
        is_november_sheet = '11월' in selected_sheet or '11' in selected_sheet or 'november' in selected_sheet.lower() or 'nov' in selected_sheet.lower()
        
        # 12월 시트인지 확인
        is_december_sheet = '12월' in selected_sheet or '12' in selected_sheet or 'december' in selected_sheet.lower() or 'dec' in selected_sheet.lower()
        
        # 월 표시 텍스트 결정 (12월 시트면 "12월", 11월 시트면 "11월", 아니면 기본값 "11월")
        if is_december_sheet:
            month_display = "12월"
            month_number = 12
        elif is_november_sheet:
            month_display = "11월"
            month_number = 11
        else:
            # 기본값은 11월
            month_display = "11월"
            month_number = 11
        
        # 스마트공장 시트인지 확인
        is_smart_factory = '스마트공장' in selected_sheet or 'smart' in selected_sheet.lower() or 'factory' in selected_sheet.lower()
        
        # 스마트공장 시트인 경우 업체별 상담내역 담당자 페이지 표시
        if is_smart_factory:
            st.subheader("🏭 스마트공장 업체별 상담내역 담당자")
            st.markdown("---")
            
            # 업체 컬럼 찾기
            company_columns = [col for col in df.columns if any(keyword in str(col).lower() for keyword in ['업체', 'company', '회사', '고객', 'customer', 'client'])]
            # 담당자 컬럼 찾기
            manager_columns = [col for col in df.columns if any(keyword in str(col).lower() for keyword in ['담당자', 'manager', '담당', '담당인', 'contact', '담당자명'])]
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
                # 업체별 담당자 집계
                company_manager = df.groupby([company_col, manager_col]).size().reset_index(name='상담건수')
                company_manager = company_manager.sort_values([company_col, '상담건수'], ascending=[True, False])
                
                # 업체별 요약
                company_summary = df.groupby(company_col).agg({
                    manager_col: 'count',
                }).reset_index()
                company_summary.columns = [company_col, '총상담건수']
                company_summary = company_summary.sort_values('총상담건수', ascending=False)
                
                # 통계 카드
                col_stat1, col_stat2, col_stat3 = st.columns(3)
                with col_stat1:
                    st.metric("총 업체 수", len(company_summary))
                with col_stat2:
                    st.metric("총 상담 건수", f"{company_summary['총상담건수'].sum():,}건")
                with col_stat3:
                    if manager_col:
                        unique_managers = df[manager_col].nunique()
                        st.metric("담당자 수", f"{unique_managers}명")
                
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
                
                # 테이블 표시
                display_columns = [company_col, manager_col, '상담건수']
                if consultation_col:
                    # 상담내역이 있으면 추가
                    consultation_summary = df.groupby([company_col, manager_col])[consultation_col].apply(lambda x: ' | '.join(x.dropna().astype(str).unique()[:3])).reset_index()
                    consultation_summary.columns = [company_col, manager_col, '상담내역_요약']
                    filtered_data = filtered_data.merge(consultation_summary, on=[company_col, manager_col], how='left')
                    display_columns.append('상담내역_요약')
                
                # 천단위 구분 기호 적용
                filtered_data_display = filtered_data.copy()
                filtered_data_display['상담건수'] = filtered_data_display['상담건수'].apply(lambda x: f"{x:,}건")
                
                st.dataframe(
                    filtered_data_display[display_columns],
                    use_container_width=True,
                    height=400
                )
                
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
                if '월' in df.columns:
                    df_month = df[df['월'] == month_number].copy()
                    if len(df_month) > 0:
                        st.info(f"📅 {month_display} 총판매 건수 {len(df_month)}건")
                        df = df_month
                    else:
                        st.warning(f"⚠️ 날짜 컬럼에서 {month_display} 데이터를 찾지 못했습니다. 전체 데이터를 표시합니다.")
            else:
                # 날짜 컬럼이 없으면 시트 이름으로 판단
                if november_sheet or is_december_sheet:
                    st.info(f"📊 '{selected_sheet}' 시트의 전체 데이터를 표시합니다.")
            
            # 사이드바 필터
            st.sidebar.header("필터 옵션")
            
            if '년' in df.columns:
                years = sorted(df['년'].dropna().unique())
                selected_years = st.sidebar.multiselect("년도 선택", years, default=years)
                df = df[df['년'].isin(selected_years)]
            
            # 선택된 월 데이터만 표시 중이면 월 필터는 숨김
            if '월' in df.columns:
                months = sorted(df['월'].dropna().unique())
                if month_number not in months or len(months) > 1:
                    selected_months = st.sidebar.multiselect("월 선택", months, default=months)
                    df = df[df['월'].isin(selected_months)]
                else:
                    st.sidebar.info(f"📅 {month_display} 데이터만 표시 중")
                
                # 목표 달성율 계산
                st.markdown(f"### 🎯 {month_display} 총 목표 달성 현황 <span style='font-size: 0.8em; color: #888;'>(발주서 기준)</span>", unsafe_allow_html=True)
                
                # 목표 설정 (월별로 다를 수 있음)
                if month_number == 12:
                    target_part1 = 18200000  # 12월 1파트 목표: 18,200,000원
                    target_part2 = 1000000   # 12월 2파트 목표: 1,000,000원
                else:
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
                
                # I열 찾기 (엑셀의 I열 = 9번째 컬럼, 인덱스 8)
                i_column_index = 8  # I열은 9번째 (0-based index: 8)
                i_col = None
                
                if len(df.columns) > i_column_index:
                    i_col = df.columns[i_column_index]
                else:
                    # 방법 2: 컬럼 이름으로 찾기
                    i_columns = [col for col in df.columns if any(keyword in str(col).lower() for keyword in ['업체지급금액', '지급금액', '정산금액', 'payment', 'i열'])]
                    if len(i_columns) > 0:
                        i_col = i_columns[0]
                
                # 파트 컬럼 찾기 (P열에서 생성한 '파트' 컬럼 우선 사용)
                part_columns = [col for col in df.columns if any(keyword in str(col).lower() for keyword in ['파트', 'part'])]
                part_col = None
                
                # 새로 생성한 '파트' 컬럼이 있으면 우선 사용
                if '파트' in df.columns:
                    part_col = '파트'
                elif len(part_columns) > 0:
                    part_col = part_columns[0]
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
                    
                    # 파트 컬럼이 있으면 파트별로 매출총이익 집계
                    if part_col is not None and part_col in df.columns:
                        # 파트 컬럼의 값을 문자열로 변환하고 공백 제거
                        df[part_col] = df[part_col].astype(str).str.strip()
                        
                        # NaN이나 빈 값, 'nan' 문자열 제거 후 파트별로 매출총이익 집계
                        # 파트가 비어있지 않은 데이터만 사용
                        df_with_part = df[(df[part_col] != '') & (df[part_col] != 'nan') & (df[part_col].notna())].copy()
                        
                        if len(df_with_part) > 0:
                            # 파트별로 매출총이익 집계 (groupby 사용)
                            part_summary = df_with_part.groupby(part_col)[amount_col].agg(['sum', 'count']).reset_index()
                            part_summary.columns = ['파트', '매출총이익', '건수']
                            
                            # 1파트 데이터 찾기 (1파트, part1, 1 등) - 정확한 매칭 우선
                            part1_mask_filter = (
                                (part_summary['파트'] == '1파트') |
                                (part_summary['파트'] == '1') |
                                part_summary['파트'].str.contains('1파트', na=False, regex=False, case=False) |
                                part_summary['파트'].str.contains('part1', na=False, regex=False, case=False)
                            )
                            part1_rows = part_summary[part1_mask_filter]
                            
                            if len(part1_rows) > 0:
                                part1_achieved = part1_rows['매출총이익'].sum()
                                part1_count = part1_rows['건수'].sum()
                                part1_mask = (
                                    (df[part_col] == '1파트') |
                                    (df[part_col] == '1') |
                                    df[part_col].str.contains('1파트', na=False, regex=False, case=False) |
                                    df[part_col].str.contains('part1', na=False, regex=False, case=False)
                                )
                            
                            # 2파트 데이터 찾기 (2파트, part2, 2 등) - 정확한 매칭 우선
                            part2_mask_filter = (
                                (part_summary['파트'] == '2파트') |
                                (part_summary['파트'] == '2') |
                                part_summary['파트'].str.contains('2파트', na=False, regex=False, case=False) |
                                part_summary['파트'].str.contains('part2', na=False, regex=False, case=False)
                            )
                            part2_rows = part_summary[part2_mask_filter]
                            
                            if len(part2_rows) > 0:
                                part2_achieved = part2_rows['매출총이익'].sum()
                                part2_count = part2_rows['건수'].sum()
                                part2_mask = (
                                    (df[part_col] == '2파트') |
                                    (df[part_col] == '2') |
                                    df[part_col].str.contains('2파트', na=False, regex=False, case=False) |
                                    df[part_col].str.contains('part2', na=False, regex=False, case=False)
                                )
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
                
                # 누적 달성율 섹션 (12월 첫째주)
                if month_number == 12:
                    st.subheader("📈 12월 첫째주까지 누적 달성율")
                    
                    # 12월 첫째주 목표 설정
                    weekly_target_part1 = 324410000  # 1파트 목표: 324,410,000원
                    weekly_target_part2 = 8226000    # 2파트 목표: 8,226,000원
                    
                    # 12월 첫째주 달성 이익
                    weekly_achieved_part1 = 185805000  # 1파트 달성: 185,805,000원
                    weekly_achieved_part2 = 19498000    # 2파트 달성: 19,498,000원
                    
                    # 누적 달성율 계산
                    weekly_achievement_rate_part1 = (weekly_achieved_part1 / weekly_target_part1 * 100) if weekly_target_part1 > 0 else 0
                    weekly_achievement_rate_part2 = (weekly_achieved_part2 / weekly_target_part2 * 100) if weekly_target_part2 > 0 else 0
                    
                    # 합계 계산
                    weekly_total_target = weekly_target_part1 + weekly_target_part2
                    weekly_total_achieved = weekly_achieved_part1 + weekly_achieved_part2
                    weekly_total_rate = (weekly_total_achieved / weekly_total_target * 100) if weekly_total_target > 0 else 0
                    
                    # 누적 달성율 표시
                    col_weekly1, col_weekly2, col_weekly_total = st.columns(3)
                    
                    with col_weekly1:
                        delta_weekly_part1 = weekly_achieved_part1 - weekly_target_part1
                        st.metric(
                            "1파트 누적 달성율",
                            f"{weekly_achievement_rate_part1:.1f}%",
                            delta=f"{delta_weekly_part1:,.0f}원",
                            help=f"목표: {weekly_target_part1:,}원, 달성: {weekly_achieved_part1:,}원"
                        )
                        st.caption(f"목표: {weekly_target_part1:,}원")
                        st.caption(f"달성: {weekly_achieved_part1:,}원")
                    
                    with col_weekly2:
                        delta_weekly_part2 = weekly_achieved_part2 - weekly_target_part2
                        st.metric(
                            "2파트 누적 달성율",
                            f"{weekly_achievement_rate_part2:.1f}%",
                            delta=f"{delta_weekly_part2:,.0f}원",
                            help=f"목표: {weekly_target_part2:,}원, 달성: {weekly_achieved_part2:,}원"
                        )
                        st.caption(f"목표: {weekly_target_part2:,}원")
                        st.caption(f"달성: {weekly_achieved_part2:,}원")
                    
                    with col_weekly_total:
                        delta_weekly_total = weekly_total_achieved - weekly_total_target
                        st.metric(
                            "전체 누적 달성율",
                            f"{weekly_total_rate:.1f}%",
                            delta=f"{delta_weekly_total:,.0f}원",
                            help=f"목표: {weekly_total_target:,}원, 달성: {weekly_total_achieved:,}원"
                        )
                        st.caption(f"목표: {weekly_total_target:,}원")
                        st.caption(f"달성: {weekly_total_achieved:,}원")
                    
                    # 누적 달성율 시각화 (프로그레스 바)
                    st.markdown("#### 누적 달성율 진행 상황")
                    progress_weekly_col1, progress_weekly_col2 = st.columns(2)
                    
                    with progress_weekly_col1:
                        st.markdown("**1파트**")
                        st.progress(min(weekly_achievement_rate_part1 / 100, 1.0))
                        if weekly_achievement_rate_part1 >= 100:
                            st.success(f"✅ 목표 달성! ({weekly_achievement_rate_part1:.1f}%)")
                        elif weekly_achievement_rate_part1 >= 80:
                            st.warning(f"⚠️ 목표 근접 ({weekly_achievement_rate_part1:.1f}%)")
                        else:
                            st.info(f"📊 진행 중 ({weekly_achievement_rate_part1:.1f}%)")
                    
                    with progress_weekly_col2:
                        st.markdown("**2파트**")
                        st.progress(min(weekly_achievement_rate_part2 / 100, 1.0))
                        if weekly_achievement_rate_part2 >= 100:
                            st.success(f"✅ 목표 달성! ({weekly_achievement_rate_part2:.1f}%)")
                        elif weekly_achievement_rate_part2 >= 80:
                            st.warning(f"⚠️ 목표 근접 ({weekly_achievement_rate_part2:.1f}%)")
                        else:
                            st.info(f"📊 진행 중 ({weekly_achievement_rate_part2:.1f}%)")
                    
                    st.markdown("---")
            
            st.markdown("---")
            
            # 데이터 분석 차트
            st.subheader(f"📊 {month_display} 기준 데이터 분석")
        
        # 주차 번호를 한국어로 변환하는 함수
        def week_to_korean(week_num, min_week=None):
            """주차 번호를 한국어로 변환 (예: 45 -> '{month_display} 첫째주')"""
            week_korean = ['첫째', '둘째', '셋째', '넷째', '다섯째']
            if min_week is not None:
                # 최소 주차를 기준으로 상대적 주차 계산
                relative_week = week_num - min_week
                if 0 <= relative_week < len(week_korean):
                    return f"{month_display} {week_korean[relative_week]}주"
            return f"{month_display} {week_num}주"
        
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
                df['주차_한글'] = df['주차'].apply(lambda x: week_to_korean(x, min_week))
                
                col1, col2 = st.columns(2)
                
                # 매출총이익이 숫자형이 아니면 변환
                if amount_col and amount_col in df.columns:
                    if df[amount_col].dtype == 'object':
                        df[amount_col] = pd.to_numeric(df[amount_col], errors='coerce')
                
                with col1:
                    # 주차별 데이터 (총 판매수량(i열) + 매출이익금 통합)
                    # 주차별 데이터 (한국어 주차명 사용)
                    # I열이 있으면 I열의 수량 합산, 없으면 건수 사용
                    if i_col and i_col in df.columns:
                        # I열이 숫자형이 아니면 변환
                        if df[i_col].dtype == 'object':
                            df[i_col] = pd.to_numeric(df[i_col], errors='coerce')
                        # 주차별 I열 수량 합산
                        weekly_data = df.groupby(['주차', '주차_한글'])[i_col].sum().reset_index()
                        weekly_data.columns = ['주차', '주차_한글', '총판매수량']
                        quantity_label = '총 판매수량'
                    else:
                        # I열이 없으면 건수 사용
                        weekly_data = df.groupby(['주차', '주차_한글']).size().reset_index(name='총판매수량')
                        quantity_label = '건수'
                    
                    weekly_data = weekly_data.sort_values('주차')
                    
                    # 이중 Y축 그래프 생성
                    fig_weekly = make_subplots(specs=[[{"secondary_y": True}]])
                    
                    # 총 판매수량 바 차트 (왼쪽 Y축)
                    fig_weekly.add_trace(
                        go.Bar(
                            x=weekly_data['주차_한글'],
                            y=weekly_data['총판매수량'],
                            name=quantity_label,
                            marker_color='lightblue',
                            hovertemplate=f'<b>%{{x}}</b><br>{quantity_label}: %{{y:,.0f}}<extra></extra>'
                        ),
                        secondary_y=False
                    )
                    
                    # 매출이익금 라인 차트 (오른쪽 Y축)
                    if amount_col and amount_col in df.columns:
                        weekly_profit = df.groupby(['주차', '주차_한글'])[amount_col].sum().reset_index()
                        weekly_profit.columns = ['주차', '주차_한글', '매출이익금']
                        weekly_profit = weekly_profit.sort_values('주차')
                        # 주차별 데이터와 매출이익금 데이터 병합
                        weekly_combined = weekly_data.merge(weekly_profit[['주차_한글', '매출이익금']], on='주차_한글', how='left')
                        weekly_combined['매출이익금'] = weekly_combined['매출이익금'].fillna(0)
                        
                        fig_weekly.add_trace(
                            go.Scatter(
                                x=weekly_combined['주차_한글'],
                                y=weekly_combined['매출이익금'],
                                name='매출이익금',
                                mode='lines+markers',
                                line=dict(color='green', width=3),
                                marker=dict(size=8),
                                hovertemplate='<b>%{x}</b><br>매출이익금: %{y:,.0f}원<extra></extra>'
                            ),
                            secondary_y=True
                        )
                    
                    # 레이아웃 설정
                    fig_weekly.update_layout(
                        title=f'{month_display} 주차별 총 판매수량 / 매출이익금',
                        xaxis_title="주차",
                        hovermode='x unified',
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="right",
                            x=1
                        )
                    )
                    
                    # X축 카테고리 순서 설정
                    fig_weekly.update_xaxes(
                        categoryorder='array',
                        categoryarray=weekly_data['주차_한글'].tolist()
                    )
                    
                    # Y축 레이블 설정
                    fig_weekly.update_yaxes(title_text="건수", secondary_y=False)
                    if amount_col and amount_col in df.columns:
                        fig_weekly.update_yaxes(title_text="매출이익금 (원)", secondary_y=True, tickformat=',')
                    
                    st.plotly_chart(fig_weekly, use_container_width=True)
                
                with col2:
                    # 일별 데이터 (총 판매수량(i열) + 매출이익금 통합)
                    # I열이 있으면 I열의 수량 합산, 없으면 건수 사용
                    if i_col and i_col in df.columns:
                        # I열이 숫자형이 아니면 변환
                        if df[i_col].dtype == 'object':
                            df[i_col] = pd.to_numeric(df[i_col], errors='coerce')
                        # 일별 I열 수량 합산
                        daily_data = df.groupby('일')[i_col].sum().reset_index()
                        daily_data.columns = ['일', '총판매수량']
                        quantity_label_daily = '총 판매수량'
                    else:
                        # I열이 없으면 건수 사용
                        daily_data = df.groupby('일').size().reset_index(name='총판매수량')
                        quantity_label_daily = '건수'
                    
                    # 이중 Y축 그래프 생성
                    fig_daily = make_subplots(specs=[[{"secondary_y": True}]])
                    
                    # 총 판매수량 라인 차트 (왼쪽 Y축)
                    fig_daily.add_trace(
                        go.Scatter(
                            x=daily_data['일'],
                            y=daily_data['총판매수량'],
                            name=quantity_label_daily,
                            mode='lines+markers',
                            line=dict(color='lightblue', width=3),
                            marker=dict(size=8),
                            hovertemplate=f'<b>일: %{{x}}</b><br>{quantity_label_daily}: %{{y:,.0f}}<extra></extra>'
                        ),
                        secondary_y=False
                    )
                    
                    # 매출이익금 라인 차트 (오른쪽 Y축)
                    if amount_col and amount_col in df.columns:
                        daily_profit = df.groupby('일')[amount_col].sum().reset_index()
                        daily_profit.columns = ['일', '매출이익금']
                        # 일별 데이터와 매출이익금 데이터 병합
                        daily_combined = daily_data.merge(daily_profit, on='일', how='left')
                        daily_combined['매출이익금'] = daily_combined['매출이익금'].fillna(0)
                        
                        fig_daily.add_trace(
                            go.Scatter(
                                x=daily_combined['일'],
                                y=daily_combined['매출이익금'],
                                name='매출이익금',
                                mode='lines+markers',
                                line=dict(color='green', width=3),
                                marker=dict(size=8),
                                hovertemplate='<b>일: %{x}</b><br>매출이익금: %{y:,.0f}원<extra></extra>'
                            ),
                            secondary_y=True
                        )
                    
                    # 레이아웃 설정
                    fig_daily.update_layout(
                        title=f'{month_display} 일별 총 판매수량 / 매출이익금',
                        xaxis_title="일",
                        hovermode='x unified',
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="right",
                            x=1
                        )
                    )
                    
                    # Y축 레이블 설정
                    fig_daily.update_yaxes(title_text=quantity_label_daily, secondary_y=False, tickformat=',')
                    if amount_col and amount_col in df.columns:
                        fig_daily.update_yaxes(title_text="매출이익금 (원)", secondary_y=True, tickformat=',')
                    
                    st.plotly_chart(fig_daily, use_container_width=True)
            else:
                # 날짜 정보가 없으면 전체 데이터 건수 표시
                st.info("날짜 정보가 없어 트렌드 분석을 할 수 없습니다.")
            
            # 플랫폼별 비교
            st.subheader(f"📋 플랫폼별 분석 ({month_display}) 기준")
            
            # 텍스트/카테고리 컬럼 찾기
            category_columns = df.select_dtypes(include=['object']).columns.tolist()
            # 너무 많은 고유값을 가진 컬럼 제외 (ID나 설명 컬럼 제외)
            category_columns = [col for col in category_columns 
                               if df[col].nunique() <= 50 and df[col].nunique() > 1]
            
            if len(category_columns) > 0:
                category_col = st.selectbox("분류 기준 선택", category_columns, key='category_select')
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # 큰 제목 추가
                    st.markdown("#### 📊 플랫폼별 총 판매수량")
                    
                    # 바 차트 (상위 10개)
                    # I열이 있으면 I열의 수량 합산, 없으면 건수 사용
                    if i_col and i_col in df.columns:
                        # I열이 숫자형이 아니면 변환
                        if df[i_col].dtype == 'object':
                            df[i_col] = pd.to_numeric(df[i_col], errors='coerce')
                        # 플랫폼별 I열 수량 합산
                        category_data = df.groupby(category_col)[i_col].sum().sort_values(ascending=False).head(10)
                        x_label = '총 판매수량'
                    else:
                        # I열이 없으면 건수 사용
                        category_data = df[category_col].value_counts().head(10)
                        x_label = '건수'
                    
                    fig_bar = px.bar(
                        x=category_data.values,
                        y=category_data.index,
                        orientation='h',
                        title='',  # 제목 제거 (위에 큰 제목 사용)
                        labels={'x': x_label, 'y': category_col},
                        color=category_data.values,
                        color_continuous_scale='Viridis'
                    )
                    fig_bar.update_layout(showlegend=False)
                    # 툴팁에서 컬러 정보 숨기기
                    fig_bar.update_traces(
                        hovertemplate=f'<b>%{{y}}</b><br>{x_label}: %{{x:,.0f}}<extra></extra>'
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
                
                # 플랫폼별 상세 통계 테이블
                st.markdown("#### 📊 플랫폼별 상세 통계")
                
                # 수량 컬럼 찾기
                quantity_cols = [col for col in df.columns if any(keyword in str(col).lower() for keyword in ['수량', 'quantity', 'qty'])]
                quantity_col = quantity_cols[0] if len(quantity_cols) > 0 else None
                
                # 매출기준액 컬럼 찾기
                sales_base_cols = [col for col in df.columns if any(keyword in str(col).lower() for keyword in ['매출기준액', '매출기준', 'sales base', '기준액'])]
                sales_base_col = sales_base_cols[0] if len(sales_base_cols) > 0 else None
                
                # 집계할 컬럼 준비
                agg_dict = {}
                
                # 수량 컬럼이 있으면 합계 계산
                if quantity_col and quantity_col in df.columns:
                    if df[quantity_col].dtype == 'object':
                        df[quantity_col] = pd.to_numeric(df[quantity_col], errors='coerce')
                    agg_dict['수량'] = (quantity_col, 'sum')
                
                # 매출기준액 컬럼이 있으면 합계 계산
                if sales_base_col and sales_base_col in df.columns:
                    if df[sales_base_col].dtype == 'object':
                        df[sales_base_col] = pd.to_numeric(df[sales_base_col], errors='coerce')
                    agg_dict['매출기준액'] = (sales_base_col, 'sum')
                
                # 매출총이익 컬럼이 있으면 합계 계산
                if amount_col and amount_col in df.columns:
                    if df[amount_col].dtype == 'object':
                        df[amount_col] = pd.to_numeric(df[amount_col], errors='coerce')
                    agg_dict['매출총이익'] = (amount_col, 'sum')
                
                # 플랫폼별 집계
                if len(agg_dict) > 0:
                    # pandas groupby agg 형식으로 변환
                    groupby_dict = {v[0]: v[1] for v in agg_dict.values()}
                    rename_dict = {v[0]: k for k, v in agg_dict.items()}
                    
                    category_stats = df.groupby(category_col).agg(groupby_dict).rename(columns=rename_dict)
                    
                    # 매출총이익 높은 순으로 정렬
                    if '매출총이익' in category_stats.columns:
                        category_stats = category_stats.sort_values('매출총이익', ascending=False)
                    else:
                        # 매출총이익이 없으면 첫 번째 컬럼으로 정렬
                        category_stats = category_stats.sort_values(category_stats.columns[0], ascending=False)
                    
                    # 플랫폼 컬럼을 인덱스에서 컬럼으로 변환
                    category_stats = category_stats.reset_index()
                    category_stats.columns.name = None
                    
                    # 수량 컬럼이 있으면 숫자형으로 확실히 변환 (정렬을 위해)
                    if '수량' in category_stats.columns:
                        category_stats['수량'] = pd.to_numeric(category_stats['수량'], errors='coerce')
                    
                    # 컬럼 순서 정렬: 플랫폼, 수량, 매출기준액, 매출총이익
                    column_order = [category_col]
                    if '수량' in category_stats.columns:
                        column_order.append('수량')
                    if '매출기준액' in category_stats.columns:
                        column_order.append('매출기준액')
                    if '매출총이익' in category_stats.columns:
                        column_order.append('매출총이익')
                    
                    # 나머지 컬럼도 추가
                    for col in category_stats.columns:
                        if col not in column_order:
                            column_order.append(col)
                    
                    category_stats = category_stats[column_order]
                    
                    # 표시용 포맷팅 (숫자는 숫자로 유지하여 정렬 가능하게)
                    # Streamlit column_config를 사용하여 숫자형 유지하면서 천단위 구분 기호 표시
                    column_config = {}
                    if '수량' in category_stats.columns:
                        column_config['수량'] = st.column_config.NumberColumn(
                            '수량',
                            format='%d'
                        )
                    if '매출기준액' in category_stats.columns:
                        column_config['매출기준액'] = st.column_config.NumberColumn(
                            '매출기준액',
                            format='%d'
                        )
                    if '매출총이익' in category_stats.columns:
                        column_config['매출총이익'] = st.column_config.NumberColumn(
                            '매출총이익',
                            format='%d'
                        )
                    
                    st.dataframe(
                        category_stats,
                        use_container_width=True,
                        hide_index=True,
                        column_config=column_config if column_config else None
                    )
                    
                    # 상품 등록 현황 대비 플랫폼 매출 및 판매율 분석
                    st.markdown("---")
                    st.markdown("#### 📈 상품 등록 현황 대비 플랫폼 매출 및 판매율")
                    
                    # 상품 등록 현황 데이터 (첫 번째 이미지 참고)
                    product_registration = {
                        '삼성베네포유': 1321,
                        '삼성카드몰': 1230,
                        '쿠팡': 128,
                        '로켓그로스': 3,
                        '시노텍스': 561,
                        '애터미아자': 371,
                        'LG': 1084,
                        '티딜': 578,
                        '자연이랑': 617,
                        '기아샵': 287,
                        '제이슨딜': 276,
                        '현대샵': 147,
                        '캐시딜': 674,
                        '오토앤': 14,
                        '톡스토어': 30,
                        '홈닉': 98,
                        '올웨이즈': 1364,
                        '유콕딜': 394,
                        '엔비티': 315,
                        'ESM': 369,
                        '11번가': 153,
                        '롯데온': 206,
                        '도매꾹': 3,
                        '오너클랜': 7,
                        '스마트스토어': 177,
                        '퍼스트복지몰': 888,
                        '풀무원': 891,
                        '인터엠디': 932,
                        '알리': 10,
                        '토스': 912,
                        '이제너두': 137,
                        '아이엠스쿨': 307,
                        '빌리지베이비': 307,
                        '비즈마켓': 654,
                        '웰포인트': 159,
                        '네티웰': 296,
                        '이패밀리샵': 89,
                        '지라이프': 40,
                        '바로팜': 1418,
                        '복지드림': 987,
                        '베네피아': 501,
                        'WAC': 0,
                        '현대이지웰': 7,
                        '삼아': 0
                    }
                    
                    # 플랫폼별 상세 통계와 상품 등록 현황 매칭
                    if category_col in category_stats.columns or category_col in category_stats.index.names:
                        # 인덱스가 category_col인 경우
                        if category_col in category_stats.index.names:
                            category_stats_reset = category_stats.reset_index()
                        else:
                            category_stats_reset = category_stats.copy()
                        
                        # 상품 등록 현황 컬럼 추가
                        category_stats_reset['상품등록현황'] = category_stats_reset[category_col].map(product_registration)
                        category_stats_reset['상품등록현황'] = category_stats_reset['상품등록현황'].fillna(0)
                        
                        # 상품 등록 현황 대비 플랫폼 매출 계산 (매출기준액 / 상품 등록 현황)
                        if '매출기준액' in category_stats_reset.columns:
                            category_stats_reset['등록대비매출'] = category_stats_reset.apply(
                                lambda row: (row['매출기준액'] / row['상품등록현황']) if row['상품등록현황'] > 0 else 0,
                                axis=1
                            )
                        
                        # 상품 등록 대비 판매율 계산 (판매 수량 / 상품 등록 현황 * 100)
                        if '수량' in category_stats_reset.columns:
                            category_stats_reset['등록대비판매율'] = category_stats_reset.apply(
                                lambda row: (row['수량'] / row['상품등록현황'] * 100) if row['상품등록현황'] > 0 else 0,
                                axis=1
                            )
                        
                        # 표시용 데이터 준비 (상품등록현황이 0이 아닌 것만 필터링)
                        display_stats = category_stats_reset[category_stats_reset['상품등록현황'] > 0].copy()
                        
                        if len(display_stats) > 0:
                            # 컬럼 순서 정렬
                            display_columns = [category_col, '상품등록현황']
                            if '수량' in display_stats.columns:
                                display_columns.append('수량')
                            if '매출기준액' in display_stats.columns:
                                display_columns.append('매출기준액')
                            if '등록대비매출' in display_stats.columns:
                                display_columns.append('등록대비매출')
                            if '등록대비판매율' in display_stats.columns:
                                display_columns.append('등록대비판매율')
                            if '매출총이익' in display_stats.columns:
                                display_columns.append('매출총이익')
                            
                            # 등록대비판매율 높은 순으로 정렬
                            if '등록대비판매율' in display_stats.columns:
                                display_stats = display_stats.sort_values('등록대비판매율', ascending=False)
                            elif '등록대비매출' in display_stats.columns:
                                display_stats = display_stats.sort_values('등록대비매출', ascending=False)
                            
                            # 컬럼명 한글화 (포맷팅 전에)
                            display_stats = display_stats.rename(columns={
                                category_col: '플랫폼',
                                '상품등록현황': '상품 등록 현황',
                                '수량': '판매 수량',
                                '매출기준액': '매출기준액',
                                '등록대비매출': '등록 대비 매출',
                                '등록대비판매율': '등록 대비 판매율 (%)',
                                '매출총이익': '매출총이익'
                            })
                            
                            # 숫자형 컬럼을 정수로 반올림 (정렬을 위해 숫자형 유지, Streamlit이 자동으로 천단위 구분 기호 표시)
                            display_stats_formatted = display_stats.copy()
                            
                            # 정수로 반올림할 컬럼들 (소수점 이하 반올림 처리)
                            integer_columns = ['상품 등록 현황', '판매 수량', '매출기준액', '등록 대비 매출', '매출총이익']
                            for col in integer_columns:
                                if col in display_stats_formatted.columns:
                                    # 소수점 이하 반올림 후 정수형으로 변환 (NaN 처리 포함)
                                    display_stats_formatted[col] = pd.to_numeric(
                                        display_stats_formatted[col], errors='coerce'
                                    ).round().astype('Int64')
                            
                            # 판매율만 포맷팅 (문자열로 변환)
                            if '등록 대비 판매율 (%)' in display_stats_formatted.columns:
                                display_stats_formatted['등록 대비 판매율 (%)'] = display_stats_formatted['등록 대비 판매율 (%)'].apply(
                                    lambda x: f"{x:.2f}%" if pd.notna(x) else "0.00%"
                                )
                            
                            # 컬럼 순서 재정렬
                            display_columns_renamed = []
                            if '플랫폼' in display_stats_formatted.columns:
                                display_columns_renamed.append('플랫폼')
                            if '상품 등록 현황' in display_stats_formatted.columns:
                                display_columns_renamed.append('상품 등록 현황')
                            if '판매 수량' in display_stats_formatted.columns:
                                display_columns_renamed.append('판매 수량')
                            if '매출기준액' in display_stats_formatted.columns:
                                display_columns_renamed.append('매출기준액')
                            if '등록 대비 매출' in display_stats_formatted.columns:
                                display_columns_renamed.append('등록 대비 매출')
                            if '등록 대비 판매율 (%)' in display_stats_formatted.columns:
                                display_columns_renamed.append('등록 대비 판매율 (%)')
                            if '매출총이익' in display_stats_formatted.columns:
                                display_columns_renamed.append('매출총이익')
                            
                            # Streamlit column_config를 사용하여 숫자형 유지하면서 천단위 구분 기호 표시
                            column_config_display = {}
                            if '상품 등록 현황' in display_stats_formatted.columns:
                                column_config_display['상품 등록 현황'] = st.column_config.NumberColumn(
                                    '상품 등록 현황',
                                    format='%d'
                                )
                            if '판매 수량' in display_stats_formatted.columns:
                                column_config_display['판매 수량'] = st.column_config.NumberColumn(
                                    '판매 수량',
                                    format='%d'
                                )
                            if '매출기준액' in display_stats_formatted.columns:
                                column_config_display['매출기준액'] = st.column_config.NumberColumn(
                                    '매출기준액',
                                    format='%d'
                                )
                            if '등록 대비 매출' in display_stats_formatted.columns:
                                column_config_display['등록 대비 매출'] = st.column_config.NumberColumn(
                                    '등록 대비 매출',
                                    format='%d'
                                )
                            if '매출총이익' in display_stats_formatted.columns:
                                column_config_display['매출총이익'] = st.column_config.NumberColumn(
                                    '매출총이익',
                                    format='%d'
                                )
                            
                            st.dataframe(
                                display_stats_formatted[display_columns_renamed],
                                use_container_width=True,
                                height=400,
                                hide_index=True,
                                column_config=column_config_display if column_config_display else None
                            )
                            
                            # 요약 통계
                            st.markdown("##### 📊 요약 통계")
                            summary_col1, summary_col2, summary_col3 = st.columns(3)
                            
                            with summary_col1:
                                if '등록 대비 매출' in display_stats_formatted.columns:
                                    # 숫자형 데이터에서 계산
                                    avg_sales = display_stats[display_stats['등록 대비 매출'] > 0]['등록 대비 매출'].mean()
                                    st.metric("평균 등록 대비 매출", f"{avg_sales:,.0f}원")
                            
                            with summary_col2:
                                if '등록 대비 판매율 (%)' in display_stats_formatted.columns:
                                    # 숫자형 데이터에서 계산
                                    avg_rate = display_stats[display_stats['등록 대비 판매율 (%)'] > 0]['등록 대비 판매율 (%)'].mean()
                                    st.metric("평균 등록 대비 판매율", f"{avg_rate:.2f}%")
                            
                            with summary_col3:
                                # 전체 상품 등록 현황 합계 (딕셔너리 전체 합계)
                                total_registered = sum(product_registration.values())
                                st.metric("총 상품 등록 현황", f"{total_registered:,}개")
                        else:
                            st.info("상품 등록 현황 데이터가 있는 플랫폼이 없습니다.")
                    else:
                        st.info("수량, 매출기준액, 매출총이익 컬럼을 찾을 수 없습니다.")
            else:
                st.info("분석 가능한 카테고리 컬럼을 찾지 못했습니다.")
            
            # 금주 계획 및 목표, 회의결과 및 경영자의견 입력 섹션
            st.markdown("---")
            st.markdown("---")
            st.subheader("📝 회의록 작성")
            
            # 텍스트 파싱 함수 (자동 스타일링)
            def parse_text_format(text):
                """텍스트를 파싱하여 자동으로 스타일링"""
                import re
                
                if not text:
                    return ""
                
                lines = text.split('\n')
                result = []
                
                for line in lines:
                    original_line = line
                    line = line.strip()
                    
                    # 빈 줄
                    if not line:
                        result.append('<br>')
                        continue
                    
                    # `* **텍스트**` 형식 → 빨간색 볼드 (한 줄)
                    match = re.match(r'^\*\s+\*\*(.+?)\*\*$', line)
                    if match:
                        content = match.group(1)
                        result.append(f'<div style="color: red; font-weight: bold; margin-top: 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">* {content}</div>')
                        continue
                    
                    # `* 텍스트` 형식 → 빨간색 볼드 (한 줄)
                    match = re.match(r'^\*\s+(.+)$', line)
                    if match:
                        content = match.group(1)
                        # 내부의 ** 제거 (이미 볼드 처리되므로)
                        content = content.replace('**', '')
                        result.append(f'<div style="color: red; font-weight: bold; margin-top: 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">* {content}</div>')
                        continue
                    
                    # `: 텍스트` 형식 → 일반 텍스트 (들여쓰기, 밝은 색상, 한 줄)
                    match = re.match(r'^:\s+(.+)$', line)
                    if match:
                        content = match.group(1)
                        result.append(f'<div style="margin-left: 20px; margin-top: 4px; color: #ffffff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">: {content}</div>')
                        continue
                    
                    # 일반 텍스트 (마크다운 지원, 밝은 색상, 한 줄)
                    # **볼드** 처리
                    processed_line = re.sub(r'\*\*(.+?)\*\*', r'<strong style="color: #ffffff;">\1</strong>', original_line)
                    # HTML 이스케이프는 Streamlit이 자동 처리
                    result.append(f'<div style="margin-top: 4px; color: #ffffff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{processed_line}</div>')
                
                return '\n'.join(result)
            
            # 세션 상태 초기화 (입력 내용 유지)
            # 세션 상태 초기화 (없는 경우에만)
            if 'weekly_plan' not in st.session_state:
                st.session_state.weekly_plan = ""
            if 'meeting_result' not in st.session_state:
                st.session_state.meeting_result = ""
            
            # 금주 계획 및 목표
            st.markdown("#### 💼 금주 계획 및 목표")
            # key를 사용하면 Streamlit이 자동으로 session_state에 저장하고 불러옴
            weekly_plan = st.text_area(
                "금주 계획 및 목표를 입력하세요 (복사-붙여넣기 지원)",
                value=st.session_state.weekly_plan,
                height=120,
                placeholder="예시 형식: * **코드매칭 완료** / : 각 몰별 등록",
                key='weekly_plan',
                help="`* **텍스트**` 형식은 빨간색 볼드로, `: 텍스트` 형식은 일반 텍스트로 자동 변환됩니다"
            )
            
            # 스타일링된 결과 표시
            if weekly_plan:
                parsed_plan = parse_text_format(weekly_plan)
                st.markdown(parsed_plan, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # 회의결과 및 경영자의견
            st.markdown("#### 📋 회의결과 및 경영자의견")
            # key를 사용하면 Streamlit이 자동으로 session_state에 저장하고 불러옴
            meeting_result = st.text_area(
                "회의결과 및 경영자의견을 입력하세요 (복사-붙여넣기 지원)",
                value=st.session_state.meeting_result,
                height=120,
                placeholder="예시 형식:\n* **결정사항**\n: 승인 완료\n: 다음 주 실행\n\n또는\n\n* 회의 결과\n: 경영자 의견 반영",
                key='meeting_result',
                help="`* **텍스트**` 형식은 빨간색 볼드로, `: 텍스트` 형식은 일반 텍스트로 자동 변환됩니다"
            )
            
            # 스타일링된 결과 표시
            if meeting_result:
                parsed_result = parse_text_format(meeting_result)
                st.markdown(parsed_result, unsafe_allow_html=True)
        
        # 상세 데이터 테이블 (숨김 처리)
        # st.subheader(f"📋 {month_display} 상세 데이터")
        
        # # 검색 및 필터 기능
        # col_search, col_filter = st.columns([3, 1])
        # with col_search:
        #     search_term = st.text_input("🔍 검색", "", placeholder="모든 컬럼에서 검색...")
        # with col_filter:
        #     show_rows = st.selectbox("표시 행 수", [50, 100, 200, 500, "전체"], index=1)
        
        # if search_term:
        #     # 모든 컬럼에서 검색
        #     mask = df.astype(str).apply(lambda x: x.str.contains(search_term, case=False, na=False)).any(axis=1)
        #     display_df = df[mask]
        #     st.info(f"검색 결과: {len(display_df)}건 발견")
        # else:
        #     display_df = df
        
        # # 행 수 제한
        # if isinstance(show_rows, int) and len(display_df) > show_rows:
        #     display_df = display_df.head(show_rows)
        #     st.caption(f"상위 {show_rows}건만 표시 중 (전체: {len(df)}건)")
        
        # st.dataframe(display_df, use_container_width=True, height=400)
        
        # # 다운로드 버튼
        # st.markdown("---")
        # col1, col2 = st.columns(2)
        
        # with col1:
        #     # CSV 다운로드
        #     csv = display_df.to_csv(index=False).encode('utf-8-sig')
        #     st.download_button(
        #         label="📥 CSV 다운로드",
        #         data=csv,
        #         file_name=f"주간회의록_{datetime.now().strftime('%Y%m%d')}.csv",
        #         mime="text/csv"
        #     )
        
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

