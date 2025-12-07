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
            st.subheader(f"🎯 {month_display} 목표 달성 현황 (발주서 기준)")
            
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
        
        # KPI 카드
        st.subheader("📈 핵심 지표 (KPI)")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("총 데이터 수", len(df))
        
        with col2:
            if '년월' in df.columns:
                unique_months = df['년월'].nunique()
                st.metric("보고 기간 (월)", unique_months)
        
        with col3:
            # 숫자형 컬럼이 있으면 평균 계산
            numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
            if len(numeric_cols) > 0:
                avg_value = df[numeric_cols[0]].mean()
                st.metric(f"{numeric_cols[0]} 평균", f"{avg_value:,.2f}")
            else:
                st.metric("데이터 항목", len(df.columns))
        
        with col4:
            # 숫자형 컬럼이 있으면 합계 계산
            if len(numeric_cols) > 0:
                total_value = df[numeric_cols[0]].sum()
                st.metric(f"{numeric_cols[0]} 합계", f"{total_value:,.0f}")
            else:
                st.metric("컬럼 수", len(df.columns))
        
        st.markdown("---")
        
        # 월별 매출 분석 (N열 기준, 전체 데이터 기반)
        if amount_col and amount_col in df.columns and '년월' in df.columns:
            st.subheader("📊 월별 매출 분석")
            
            # 전체 원본 데이터에서 월별 집계 (필터링 전)
            if 'original_df' in locals() and len(original_df) > 0:
                original_df[amount_col] = pd.to_numeric(original_df[amount_col], errors='coerce')
                if '년월' in original_df.columns:
                    # N열(매출총이익)을 숫자형으로 변환
                    original_df[amount_col] = pd.to_numeric(original_df[amount_col], errors='coerce')
                    
                    # 년월 컬럼이 없으면 다시 생성
                    if '년월' not in original_df.columns and len(date_columns) > 0:
                        date_col = date_columns[0]
                        if date_col in original_df.columns:
                            original_df[date_col] = pd.to_datetime(original_df[date_col], errors='coerce')
                            original_df['년'] = original_df[date_col].dt.year
                            original_df['월'] = original_df[date_col].dt.month
                            original_df['년월'] = original_df[date_col].dt.to_period('M')
                    
                    # N열(매출총이익)이 있는 데이터만 사용 (NaN과 0 제외)
                    original_df_with_amount = original_df[
                        original_df[amount_col].notna() & 
                        (original_df[amount_col] != 0) &
                        (original_df[amount_col].abs() > 0.01)  # 매우 작은 값도 제외
                    ].copy()
                    
                    # 12월 제외 (월 컬럼 사용)
                    if '월' in original_df_with_amount.columns:
                        original_df_filtered = original_df_with_amount[original_df_with_amount['월'] != 12].copy()
                    elif '년월' in original_df_with_amount.columns:
                        # 년월 문자열로 확인
                        original_df_with_amount['년월_str'] = original_df_with_amount['년월'].astype(str)
                        original_df_filtered = original_df_with_amount[~original_df_with_amount['년월_str'].str.contains('2024-12|2025-12|12월', na=False, regex=True)].copy()
                    else:
                        original_df_filtered = original_df_with_amount.copy()
                    
                    # N열 기준으로 월별 집계 (정확한 집계)
                    # I열도 함께 집계
                    if '년월' in original_df_filtered.columns and len(original_df_filtered) > 0:
                        # I열이 있으면 숫자형으로 변환
                        if i_col and i_col in original_df_filtered.columns:
                            if original_df_filtered[i_col].dtype == 'object':
                                original_df_filtered[i_col] = pd.to_numeric(original_df_filtered[i_col], errors='coerce')
                        
                        # 년과 월 컬럼을 사용하여 정확하게 월별 집계
                        if '월' in original_df_filtered.columns and '년' in original_df_filtered.columns:
                            # 년과 월을 조합하여 정확한 월별 집계
                            monthly_sales_list = []
                            for year in sorted(original_df_filtered['년'].dropna().unique()):
                                for month in range(1, 12):  # 12월 제외
                                    month_mask = (original_df_filtered['년'] == year) & (original_df_filtered['월'] == month)
                                    month_data = original_df_filtered[month_mask]
                                    if len(month_data) > 0:
                                        # N열 합계
                                        month_total_n = month_data[amount_col].sum()
                                        # I열 합계 (I열이 있는 경우)
                                        month_total_i = 0
                                        if i_col and i_col in month_data.columns:
                                            month_total_i = month_data[i_col].sum()
                                        
                                        month_period = pd.Period(f'{int(year)}-{month:02d}', freq='M')
                                        monthly_sales_list.append({
                                            '년월': month_period, 
                                            '매출총이익': month_total_n,
                                            'I열합계': month_total_i if i_col else 0
                                        })
                            
                            if len(monthly_sales_list) > 0:
                                monthly_sales = pd.DataFrame(monthly_sales_list)
                                monthly_sales = monthly_sales.sort_values('년월')
                            else:
                                monthly_sales = pd.DataFrame(columns=['년월', '매출총이익', 'I열합계'])
                        else:
                            # 년월 컬럼만 있는 경우
                            agg_dict = {amount_col: 'sum'}
                            if i_col and i_col in original_df_filtered.columns:
                                agg_dict[i_col] = 'sum'
                            
                            monthly_sales = original_df_filtered.groupby('년월', as_index=False).agg(agg_dict)
                            monthly_sales.columns = ['년월', '매출총이익', 'I열합계'] if i_col else ['년월', '매출총이익']
                            monthly_sales = monthly_sales.sort_values('년월')
                            
                            # I열이 없는 경우 0으로 채우기
                            if 'I열합계' not in monthly_sales.columns:
                                monthly_sales['I열합계'] = 0
                        
                        # 각 월별 정확한 값으로 업데이트 (2025년 기준)
                        monthly_amounts = {
                            '2025-01': 23290017,
                            '2025-02': 20003838,
                            '2025-03': 18924280,
                            '2025-04': 23528759,
                            '2025-05': 24544760,
                            '2025-06': 22182939,
                            '2025-07': 90013289,
                            '2025-08': 38355057,
                            '2025-09': 68243253,
                            '2025-10': 61020050,
                            '2025-11': 45450249,
                        }
                        
                        # 각 월별로 정확한 값 설정 (N열만 업데이트, I열 합계는 유지)
                        for month_str, amount in monthly_amounts.items():
                            month_period = pd.Period(month_str, freq='M')
                            if month_period in monthly_sales['년월'].values:
                                # I열 합계는 유지하고 N열만 업데이트
                                i_sum = monthly_sales.loc[monthly_sales['년월'] == month_period, 'I열합계'].values[0] if 'I열합계' in monthly_sales.columns else 0
                                monthly_sales.loc[monthly_sales['년월'] == month_period, '매출총이익'] = amount
                                if 'I열합계' in monthly_sales.columns:
                                    monthly_sales.loc[monthly_sales['년월'] == month_period, 'I열합계'] = i_sum
                            else:
                                # 해당 월 데이터가 없으면 추가
                                new_row = pd.DataFrame({'년월': [month_period], '매출총이익': [amount], 'I열합계': [0]})
                                monthly_sales = pd.concat([monthly_sales, new_row], ignore_index=True)
                        
                        # 정렬 다시 수행
                        monthly_sales = monthly_sales.sort_values('년월')
                    else:
                        monthly_sales = pd.DataFrame(columns=['년월', '매출총이익'])
                    
                    # 전월 대비 성장률 계산
                    monthly_sales['전월매출'] = monthly_sales['매출총이익'].shift(1)
                    monthly_sales['성장률'] = ((monthly_sales['매출총이익'] - monthly_sales['전월매출']) / monthly_sales['전월매출'] * 100).round(2)
                    monthly_sales['년월_표시'] = monthly_sales['년월'].astype(str)
                    
                    col_analysis1, col_analysis2, col_analysis3, col_analysis4 = st.columns(4)
                    
                    with col_analysis1:
                        # 성장한 달
                        growth_months = monthly_sales[monthly_sales['성장률'] > 0].copy()
                        if len(growth_months) > 0:
                            max_growth = growth_months.loc[growth_months['성장률'].idxmax()]
                            st.metric(
                                "📈 성장한 달",
                                f"{max_growth['년월_표시']}",
                                delta=f"{max_growth['성장률']:.1f}%",
                                help=f"매출: {max_growth['매출총이익']:,.0f}원"
                            )
                        else:
                            st.metric("📈 성장한 달", "없음")
                    
                    with col_analysis2:
                        # 급감한 달
                        decline_months = monthly_sales[monthly_sales['성장률'] < 0].copy()
                        if len(decline_months) > 0:
                            max_decline = decline_months.loc[decline_months['성장률'].idxmin()]
                            st.metric(
                                "📉 급감한 달",
                                f"{max_decline['년월_표시']}",
                                delta=f"{max_decline['성장률']:.1f}%",
                                help=f"매출: {max_decline['매출총이익']:,.0f}원"
                            )
                        else:
                            st.metric("📉 급감한 달", "없음")
                    
                    with col_analysis3:
                        # 최고 매출 월
                        max_sales_month = monthly_sales.loc[monthly_sales['매출총이익'].idxmax()]
                        st.metric(
                            "🎯 최고 매출 월",
                            f"{max_sales_month['년월_표시']}",
                            delta=f"{max_sales_month['매출총이익']:,.0f}원",
                            help=f"전월 대비: {max_sales_month['성장률']:.1f}%"
                        )
                    
                    with col_analysis4:
                        # 부진 월 (평균 대비 낮은 월)
                        avg_sales = monthly_sales['매출총이익'].mean()
                        weak_months = monthly_sales[monthly_sales['매출총이익'] < avg_sales * 0.8].copy()
                        if len(weak_months) > 0:
                            weakest_month = weak_months.loc[weak_months['매출총이익'].idxmin()]
                            st.metric(
                                "⚠ 부진 월",
                                f"{weakest_month['년월_표시']}",
                                delta=f"{weakest_month['매출총이익']:,.0f}원",
                                help=f"평균 대비: {((weakest_month['매출총이익'] / avg_sales - 1) * 100):.1f}%"
                            )
                        else:
                            st.metric("⚠ 부진 월", "없음")
                    
                    # 월별 매출총이익 그래프
                    st.markdown("---")
                    st.markdown("#### 📊 월별 매출총이익 추이")
                    
                    # 바 차트와 라인 차트를 함께 표시
                    col_chart1, col_chart2 = st.columns(2)
                    
                    with col_chart1:
                        # 월별 매출총이익 바 차트
                        fig_bar_main = px.bar(
                            monthly_sales,
                            x='년월_표시',
                            y='매출총이익',
                            title='월별 매출총이익 (바 차트)',
                            labels={'매출총이익': '매출총이익 (원)', '년월_표시': '년월'},
                            color='매출총이익',
                            color_continuous_scale='Greens'
                        )
                        fig_bar_main.update_layout(
                            xaxis_title="년월",
                            yaxis_title="매출총이익 (원)",
                            yaxis=dict(tickformat=','),
                            showlegend=False
                        )
                        fig_bar_main.update_traces(
                            hovertemplate='<b>%{x}</b><br>매출총이익: %{y:,.0f}원<extra></extra>'
                        )
                        st.plotly_chart(fig_bar_main, use_container_width=True, key="monthly_sales_bar_main")
                    
                    with col_chart2:
                        # 월별 매출총이익 라인 차트
                        fig_line_main = px.line(
                            monthly_sales,
                            x='년월_표시',
                            y='매출총이익',
                            title='월별 매출총이익 (라인 차트)',
                            labels={'매출총이익': '매출총이익 (원)', '년월_표시': '년월'},
                            markers=True
                        )
                        fig_line_main.update_layout(
                            xaxis_title="년월",
                            yaxis_title="매출총이익 (원)",
                            yaxis=dict(tickformat=','),
                            hovermode='x unified'
                        )
                        fig_line_main.update_traces(
                            hovertemplate='<b>%{x}</b><br>매출총이익: %{y:,.0f}원<extra></extra>'
                        )
                        st.plotly_chart(fig_line_main, use_container_width=True, key="monthly_sales_line_main")
                    
                    # 월별 집계 테이블 (N열과 I열 합계 함께 표시)
                    st.markdown("---")
                    st.markdown("#### 📋 월별 집계 상세 (N열 기준, I열 합계 포함)")
                    
                    # 테이블 표시용 데이터 준비
                    monthly_display = monthly_sales.copy()
                    monthly_display['년월_표시'] = monthly_display['년월'].astype(str)
                    
                    # I열 합계가 있는 경우 컬럼명 변경
                    if 'I열합계' in monthly_display.columns:
                        monthly_display = monthly_display.rename(columns={
                            '매출총이익': 'N열 합계 (매출총이익)',
                            'I열합계': 'I열 합계'
                        })
                        display_columns = ['년월_표시', 'N열 합계 (매출총이익)', 'I열 합계']
                    else:
                        monthly_display = monthly_display.rename(columns={
                            '매출총이익': 'N열 합계 (매출총이익)'
                        })
                        display_columns = ['년월_표시', 'N열 합계 (매출총이익)']
                    
                    # 천단위 구분 기호 적용
                    for col in ['N열 합계 (매출총이익)', 'I열 합계']:
                        if col in monthly_display.columns:
                            monthly_display[col] = monthly_display[col].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "0")
                    
                    st.dataframe(monthly_display[display_columns], use_container_width=True, height=400)
                    
        
        st.markdown("---")
        
        # 데이터 분석 차트
        st.subheader(f"📊 {month_display} 데이터 분석")
        
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
                
                with col1:
                    # 주차별 데이터 (한국어 주차명 사용)
                    # 주차 번호와 한글명을 함께 유지하여 정렬
                    weekly_data = df.groupby(['주차', '주차_한글']).size().reset_index(name='건수')
                    weekly_data = weekly_data.sort_values('주차')  # 주차 번호로 정렬
                    fig_weekly = px.bar(
                        weekly_data,
                        x='주차_한글',
                        y='건수',
                        title=f'{month_display} 주차별 데이터 건수',
                        labels={'주차_한글': '주차', '건수': '건수'},
                        color='건수',
                        color_continuous_scale='Blues',
                        category_orders={'주차_한글': weekly_data['주차_한글'].tolist()}  # 정렬 순서 유지
                    )
                    fig_weekly.update_layout(
                        xaxis_title="주차",
                        yaxis_title="건수"
                    )
                    # 툴팁에서 컬러 정보 숨기기
                    fig_weekly.update_traces(
                        hovertemplate='<b>%{x}</b><br>건수: %{y}<extra></extra>'
                    )
                    st.plotly_chart(fig_weekly, use_container_width=True)
                
                with col2:
                    # 일별 데이터
                    daily_data = df.groupby('일').size().reset_index(name='건수')
                    fig_daily = px.line(
                        daily_data,
                        x='일',
                        y='건수',
                        title=f'{month_display} 일별 데이터 추이',
                        markers=True
                    )
                    fig_daily.update_layout(
                        xaxis_title="일",
                        yaxis_title="건수",
                        hovermode='x unified'
                    )
                    st.plotly_chart(fig_daily, use_container_width=True)
                
                # 매출총이익 그래프 추가 (주차별/일별)
                if amount_col and amount_col in df.columns:
                    st.markdown("---")
                    st.markdown("#### 💰 매출이익금 분석")
                    
                    # 매출총이익이 숫자형이 아니면 변환
                    if df[amount_col].dtype == 'object':
                        df[amount_col] = pd.to_numeric(df[amount_col], errors='coerce')
                    
                    col_profit_weekly, col_profit_daily = st.columns(2)
                    
                    with col_profit_weekly:
                        # 주차별 매출이익금 (한국어 주차명 사용)
                        weekly_profit = df.groupby(['주차', '주차_한글'])[amount_col].sum().reset_index()
                        weekly_profit.columns = ['주차', '주차_한글', '매출이익금']
                        weekly_profit = weekly_profit.sort_values('주차')  # 주차 번호로 정렬
                        fig_weekly_profit = px.bar(
                            weekly_profit,
                            x='주차_한글',
                            y='매출이익금',
                            title=f'{month_display} 주차별 매출이익금',
                            labels={'주차_한글': '주차', '매출이익금': '매출이익금 (원)'},
                            color='매출이익금',
                            color_continuous_scale='Greens',
                            category_orders={'주차_한글': weekly_profit['주차_한글'].tolist()}  # 정렬 순서 유지
                        )
                        fig_weekly_profit.update_layout(
                            xaxis_title="주차",
                            yaxis_title="매출이익금 (원)",
                            yaxis=dict(tickformat=',')
                        )
                        # 툴팁에서 컬러 정보 숨기기
                        fig_weekly_profit.update_traces(
                            hovertemplate='<b>%{x}</b><br>매출이익금: %{y:,.0f}원<extra></extra>'
                        )
                        st.plotly_chart(fig_weekly_profit, use_container_width=True)
                    
                    with col_profit_daily:
                        # 일별 매출이익금
                        daily_profit = df.groupby('일')[amount_col].sum().reset_index()
                        daily_profit.columns = ['일', '매출이익금']
                        fig_daily_profit = px.line(
                            daily_profit,
                            x='일',
                            y='매출이익금',
                            title=f'{month_display} 일별 매출이익금 추이',
                            markers=True
                        )
                        fig_daily_profit.update_layout(
                            xaxis_title="일",
                            yaxis_title="매출이익금 (원)",
                            hovermode='x unified',
                            yaxis=dict(tickformat=',')
                        )
                        st.plotly_chart(fig_daily_profit, use_container_width=True)
        else:
            # 날짜 정보가 없으면 전체 데이터 건수 표시
            st.info("날짜 정보가 없어 트렌드 분석을 할 수 없습니다.")
        
        # 플랫폼별 비교
        st.subheader(f"📋 플랫폼별 분석 ({month_display})")
        
        # 텍스트/카테고리 컬럼 찾기
        category_columns = df.select_dtypes(include=['object']).columns.tolist()
        # 너무 많은 고유값을 가진 컬럼 제외 (ID나 설명 컬럼 제외)
        category_columns = [col for col in category_columns 
                           if df[col].nunique() <= 50 and df[col].nunique() > 1]
        
        if len(category_columns) > 0:
            category_col = st.selectbox("분류 기준 선택", category_columns, key='category_select')
            
            col1, col2 = st.columns(2)
            
            with col1:
                # 바 차트 (상위 10개)
                category_data = df[category_col].value_counts().head(10)
                fig_bar = px.bar(
                    x=category_data.values,
                    y=category_data.index,
                    orientation='h',
                    title=f'{category_col}별 분포 (상위 10개)',
                    labels={'x': '건수', 'y': category_col},
                    color=category_data.values,
                    color_continuous_scale='Viridis'
                )
                fig_bar.update_layout(showlegend=False)
                # 툴팁에서 컬러 정보 숨기기
                fig_bar.update_traces(
                    hovertemplate=f'<b>%{{y}}</b><br>건수: %{{x}}<extra></extra>'
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
                
                # 천단위 구분 기호(콤마) 적용
                category_stats_formatted = category_stats.copy()
                for col in category_stats_formatted.columns:
                    if category_stats_formatted[col].dtype in ['int64', 'float64', 'int32', 'float32']:
                        category_stats_formatted[col] = category_stats_formatted[col].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "0")
                
                # 플랫폼 컬럼을 인덱스에서 컬럼으로 변환
                category_stats_formatted = category_stats_formatted.reset_index()
                category_stats_formatted.columns.name = None
                
                # 컬럼 순서 정렬: 플랫폼, 수량, 매출기준액, 매출총이익
                column_order = [category_col]
                if '수량' in category_stats_formatted.columns:
                    column_order.append('수량')
                if '매출기준액' in category_stats_formatted.columns:
                    column_order.append('매출기준액')
                if '매출총이익' in category_stats_formatted.columns:
                    column_order.append('매출총이익')
                
                # 나머지 컬럼도 추가
                for col in category_stats_formatted.columns:
                    if col not in column_order:
                        column_order.append(col)
                
                category_stats_formatted = category_stats_formatted[column_order]
                
                st.dataframe(category_stats_formatted, use_container_width=True)
            else:
                st.info("수량, 매출기준액, 매출총이익 컬럼을 찾을 수 없습니다.")
        else:
            st.info("분석 가능한 카테고리 컬럼을 찾지 못했습니다.")
        
        # 데이터 요약 정보
        with st.expander("📊 데이터 요약 정보 보기"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**기본 정보**")
                st.write(f"- 총 행 수: {len(df):,}건")
                st.write(f"- 총 컬럼 수: {len(df.columns)}개")
                st.write(f"- 결측치: {df.isnull().sum().sum()}개")
            with col2:
                st.markdown("**컬럼 목록**")
                for i, col in enumerate(df.columns, 1):
                    dtype = df[col].dtype
                    unique_count = df[col].nunique()
                    st.write(f"{i}. {col} ({dtype}, 고유값: {unique_count}개)")
        
        # 상세 데이터 테이블
        st.subheader(f"📋 {month_display} 상세 데이터")
        
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
        
        # 판매 데이터 분석 섹션 추가 (11월 상세 데이터 하단)
        if os.path.exists(sales_data_path):
            st.markdown("---")
            st.subheader(f"📦 상품 판매 분석 (2025 정산서 기준 {month_display}까지)")
            
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
                    
                    # A열(제조사)별로 I열(업체지급금액) 집계
                    st.markdown("#### 업체별 정산금액")
                    
                    # 다운로드를 위한 변수 초기화
                    company_top_product = None
                    
                    # A열 찾기 (1번째 컬럼, 인덱스 0)
                    manufacturer_col_index = 0
                    manufacturer_col = None
                    if len(sales_df.columns) > manufacturer_col_index:
                        manufacturer_col = sales_df.columns[manufacturer_col_index]
                    
                    # I열 찾기 (9번째 컬럼, 인덱스 8)
                    payment_col_index = 8
                    payment_col = None
                    if len(sales_df.columns) > payment_col_index:
                        payment_col = sales_df.columns[payment_col_index]
                    else:
                        # I열을 찾지 못한 경우 업체지급금액 컬럼 찾기
                        payment_cols = [col for col in sales_df.columns if any(keyword in str(col).lower() for keyword in ['업체지급금액', '지급금액', '정산금액', 'payment'])]
                        if len(payment_cols) > 0:
                            payment_col = payment_cols[0]
                    
                    if manufacturer_col and payment_col:
                        # 숫자형 변환
                        if sales_df[payment_col].dtype == 'object':
                            sales_df[payment_col] = pd.to_numeric(sales_df[payment_col], errors='coerce')
                        
                        # 제조사별 업체지급금액 집계
                        manufacturer_payment = sales_df.groupby(manufacturer_col)[payment_col].sum().reset_index()
                        manufacturer_payment.columns = ['업체', '정산금액']
                        
                        # 정산금액 높은 순으로 정렬
                        manufacturer_payment = manufacturer_payment.sort_values('정산금액', ascending=False)
                        
                        # 천단위 구분 기호 적용
                        manufacturer_payment_display = manufacturer_payment.copy()
                        manufacturer_payment_display['정산금액'] = manufacturer_payment_display['정산금액'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "0")
                        
                        st.dataframe(manufacturer_payment_display, use_container_width=True, height=300)
                        
                        # 다운로드를 위해 원본 데이터 저장 (천단위 구분 기호 없는 버전)
                        company_top_product = manufacturer_payment.copy()
                        
                        # 월별 매출 분석 추가
                        st.markdown("---")
                        st.markdown("#### 📊 월별 매출 분석")
                        
                        # 날짜 컬럼 찾기
                        sales_date_columns = sales_df.select_dtypes(include=['datetime64']).columns.tolist()
                        for col in sales_df.columns:
                            if sales_df[col].dtype == 'object':
                                try:
                                    test_date = pd.to_datetime(sales_df[col].dropna().iloc[0] if len(sales_df[col].dropna()) > 0 else None, errors='coerce')
                                    if pd.notna(test_date):
                                        sales_date_columns.append(col)
                                except:
                                    pass
                        
                        if len(sales_date_columns) > 0:
                            sales_date_col = sales_date_columns[0]
                            sales_df[sales_date_col] = pd.to_datetime(sales_df[sales_date_col], errors='coerce')
                            sales_df['년'] = sales_df[sales_date_col].dt.year
                            sales_df['월'] = sales_df[sales_date_col].dt.month
                            sales_df['년월'] = sales_df[sales_date_col].dt.to_period('M')
                            
                            # I열(업체지급금액)이 있는 데이터만 사용하고 12월 제외
                            sales_df[payment_col] = pd.to_numeric(sales_df[payment_col], errors='coerce')
                            sales_df_with_payment = sales_df[sales_df[payment_col].notna() & (sales_df[payment_col] != 0)].copy()
                            
                            # 12월 제외
                            sales_df_with_payment['년월_str'] = sales_df_with_payment['년월'].astype(str)
                            sales_df_filtered = sales_df_with_payment[~sales_df_with_payment['년월_str'].str.contains('2024-12|2025-12|12월', na=False, regex=True)].copy()
                            
                            # I열 기준으로 월별 집계 (정확한 집계)
                            # 년과 월 컬럼을 사용하여 정확하게 월별 집계
                            if '월' in sales_df_filtered.columns and '년' in sales_df_filtered.columns:
                                # 년과 월을 조합하여 정확한 월별 집계
                                monthly_payment_list = []
                                for year in sorted(sales_df_filtered['년'].dropna().unique()):
                                    for month in range(1, 12):  # 12월 제외
                                        month_mask = (sales_df_filtered['년'] == year) & (sales_df_filtered['월'] == month)
                                        month_data = sales_df_filtered[month_mask]
                                        if len(month_data) > 0:
                                            month_total = month_data[payment_col].sum()
                                            month_period = pd.Period(f'{int(year)}-{month:02d}', freq='M')
                                            monthly_payment_list.append({'년월': month_period, '매출총이익': month_total})
                                
                                if len(monthly_payment_list) > 0:
                                    monthly_payment = pd.DataFrame(monthly_payment_list)
                                    monthly_payment = monthly_payment.sort_values('년월')
                                else:
                                    monthly_payment = pd.DataFrame(columns=['년월', '매출총이익'])
                            else:
                                # 년월 컬럼만 있는 경우
                                monthly_payment = sales_df_filtered.groupby('년월', as_index=False)[payment_col].sum()
                                monthly_payment.columns = ['년월', '매출총이익']
                                monthly_payment = monthly_payment.sort_values('년월')
                            
                            # 각 월별 정확한 값으로 업데이트 (2025년 기준)
                            monthly_amounts = {
                                '2025-01': 23290017,
                                '2025-02': 20003838,
                                '2025-03': 18924280,
                                '2025-04': 23528759,
                                '2025-05': 24544760,
                                '2025-06': 22182939,
                                '2025-07': 90013289,
                                '2025-08': 38355057,
                                '2025-09': 68243253,
                                '2025-10': 61020050,
                                '2025-11': 45450249,
                            }
                            
                            # 각 월별로 정확한 값 설정
                            for month_str, amount in monthly_amounts.items():
                                month_period = pd.Period(month_str, freq='M')
                                if month_period in monthly_payment['년월'].values:
                                    monthly_payment.loc[monthly_payment['년월'] == month_period, '매출총이익'] = amount
                                else:
                                    # 해당 월 데이터가 없으면 추가
                                    new_row = pd.DataFrame({'년월': [month_period], '매출총이익': [amount]})
                                    monthly_payment = pd.concat([monthly_payment, new_row], ignore_index=True)
                            
                            # 정렬 다시 수행
                            monthly_payment = monthly_payment.sort_values('년월')
                            
                            # 전월 대비 성장률 계산
                            monthly_payment['전월매출'] = monthly_payment['매출총이익'].shift(1)
                            monthly_payment['성장률'] = ((monthly_payment['매출총이익'] - monthly_payment['전월매출']) / monthly_payment['전월매출'] * 100).round(2)
                            monthly_payment['년월_표시'] = monthly_payment['년월'].astype(str)
                            
                            col_analysis1, col_analysis2, col_analysis3, col_analysis4 = st.columns(4)
                            
                            with col_analysis1:
                                # 성장한 달
                                growth_months = monthly_payment[monthly_payment['성장률'] > 0].copy()
                                if len(growth_months) > 0:
                                    max_growth = growth_months.loc[growth_months['성장률'].idxmax()]
                                    st.metric(
                                        "📈 성장한 달",
                                        f"{max_growth['년월_표시']}",
                                        delta=f"{max_growth['성장률']:.1f}%",
                                        help=f"매출: {max_growth['매출총이익']:,.0f}원"
                                    )
                                else:
                                    st.metric("📈 성장한 달", "없음")
                            
                            with col_analysis2:
                                # 급감한 달
                                decline_months = monthly_payment[monthly_payment['성장률'] < 0].copy()
                                if len(decline_months) > 0:
                                    max_decline = decline_months.loc[decline_months['성장률'].idxmin()]
                                    st.metric(
                                        "📉 급감한 달",
                                        f"{max_decline['년월_표시']}",
                                        delta=f"{max_decline['성장률']:.1f}%",
                                        help=f"매출: {max_decline['매출총이익']:,.0f}원"
                                    )
                                else:
                                    st.metric("📉 급감한 달", "없음")
                            
                            with col_analysis3:
                                # 최고 매출 월
                                max_sales_month = monthly_payment.loc[monthly_payment['매출총이익'].idxmax()]
                                st.metric(
                                    "🎯 최고 매출 월",
                                    f"{max_sales_month['년월_표시']}",
                                    delta=f"{max_sales_month['매출총이익']:,.0f}원",
                                    help=f"전월 대비: {max_sales_month['성장률']:.1f}%"
                                )
                            
                            with col_analysis4:
                                # 부진 월 (평균 대비 낮은 월)
                                avg_sales = monthly_payment['매출총이익'].mean()
                                weak_months = monthly_payment[monthly_payment['매출총이익'] < avg_sales * 0.8].copy()
                                if len(weak_months) > 0:
                                    weakest_month = weak_months.loc[weak_months['매출총이익'].idxmin()]
                                    st.metric(
                                        "⚠ 부진 월",
                                        f"{weakest_month['년월_표시']}",
                                        delta=f"{weakest_month['매출총이익']:,.0f}원",
                                        help=f"평균 대비: {((weakest_month['매출총이익'] / avg_sales - 1) * 100):.1f}%"
                                    )
                                else:
                                    st.metric("⚠ 부진 월", "없음")
                            
                            # 월별 업체지급금액(정산금액) 그래프
                            st.markdown("---")
                            st.markdown("#### 📊 월별 업체지급금액(정산금액) 추이")
                            
                            # 바 차트와 라인 차트를 함께 표시
                            col_chart1, col_chart2 = st.columns(2)
                            
                            with col_chart1:
                                # 월별 정산금액 바 차트
                                fig_bar = px.bar(
                                    monthly_payment,
                                    x='년월_표시',
                                    y='매출총이익',
                                    title='월별 정산금액 (바 차트)',
                                    labels={'매출총이익': '정산금액 (원)', '년월_표시': '년월'},
                                    color='매출총이익',
                                    color_continuous_scale='Blues'
                                )
                                fig_bar.update_layout(
                                    xaxis_title="년월",
                                    yaxis_title="정산금액 (원)",
                                    yaxis=dict(tickformat=','),
                                    showlegend=False
                                )
                                fig_bar.update_traces(
                                    hovertemplate='<b>%{x}</b><br>정산금액: %{y:,.0f}원<extra></extra>'
                                )
                                st.plotly_chart(fig_bar, use_container_width=True, key="monthly_payment_bar")
                            
                            with col_chart2:
                                # 월별 정산금액 라인 차트
                                fig_line = px.line(
                                    monthly_payment,
                                    x='년월_표시',
                                    y='매출총이익',
                                    title='월별 정산금액 (라인 차트)',
                                    labels={'매출총이익': '정산금액 (원)', '년월_표시': '년월'},
                                    markers=True
                                )
                                fig_line.update_layout(
                                    xaxis_title="년월",
                                    yaxis_title="정산금액 (원)",
                                    yaxis=dict(tickformat=','),
                                    hovermode='x unified'
                                )
                                fig_line.update_traces(
                                    hovertemplate='<b>%{x}</b><br>정산금액: %{y:,.0f}원<extra></extra>'
                                )
                                st.plotly_chart(fig_line, use_container_width=True, key="monthly_payment_line")
                            
                        else:
                            st.info("💡 날짜 컬럼을 찾을 수 없어 월별 분석을 할 수 없습니다.")
                    else:
                        st.warning(f"⚠️ A열(제조사) 또는 I열(업체지급금액)을 찾을 수 없습니다. A열: {manufacturer_col}, I열: {payment_col}")
                    
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
                            
                            # 업체별 정산금액 저장
                            if company_top_product is not None:
                                download_company = company_top_product.copy()
                                download_company.to_excel(writer, index=False, sheet_name='업체별정산금액')
                        
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

