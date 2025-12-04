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
        
        # 11월 시트 자동 찾기
        november_sheet = None
        for sheet in sheet_names:
            if '11월' in sheet or '11' in sheet or 'november' in sheet.lower() or 'nov' in sheet.lower():
                november_sheet = sheet
                break
        
        # 시트 선택 (11월 시트가 있으면 기본값으로 설정)
        if november_sheet:
            st.success(f"✅ 11월 데이터 시트 발견: **{november_sheet}**")
            selected_sheet = st.selectbox("시트 선택", sheet_names, index=sheet_names.index(november_sheet))
        else:
            selected_sheet = st.selectbox("시트 선택", sheet_names)
            st.info("💡 11월 시트를 찾지 못했습니다. 시트 이름에 '11월' 또는 '11'이 포함되어 있는지 확인하세요.")
        
        df = pd.read_excel(xls, sheet_name=selected_sheet)
        
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
            
            # 11월 데이터만 필터링
            if '월' in df.columns:
                df_november = df[df['월'] == 11].copy()
                if len(df_november) > 0:
                    st.info(f"📅 날짜 컬럼에서 11월 데이터 {len(df_november)}건을 찾았습니다.")
                    df = df_november
                else:
                    st.warning("⚠️ 날짜 컬럼에서 11월 데이터를 찾지 못했습니다. 전체 데이터를 표시합니다.")
        else:
            # 날짜 컬럼이 없으면 시트 이름으로 판단
            if november_sheet:
                st.info(f"📊 '{selected_sheet}' 시트의 전체 데이터를 표시합니다.")
        
        # 사이드바 필터
        st.sidebar.header("필터 옵션")
        
        if '년' in df.columns:
            years = sorted(df['년'].dropna().unique())
            selected_years = st.sidebar.multiselect("년도 선택", years, default=years)
            df = df[df['년'].isin(selected_years)]
        
        # 11월 데이터만 표시 중이면 월 필터는 숨김
        if '월' in df.columns:
            months = sorted(df['월'].dropna().unique())
            if 11 not in months or len(months) > 1:
                selected_months = st.sidebar.multiselect("월 선택", months, default=months)
                df = df[df['월'].isin(selected_months)]
            else:
                st.sidebar.info("📅 11월 데이터만 표시 중")
        
        # 11월 목표 달성율 계산
        st.subheader("🎯 11월 목표 달성 현황")
        
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
        
        # 파트 컬럼 찾기
        part_columns = [col for col in df.columns if any(keyword in str(col).lower() for keyword in ['파트', 'part'])]
        part_col = None
        
        if len(part_columns) > 0:
            part_col = part_columns[0]
        else:
            with st.expander("⚠️ 파트 컬럼을 자동으로 찾지 못했습니다. 수동으로 선택해주세요."):
                part_col = st.selectbox("파트 컬럼 선택", [""] + list(df.columns), key='part_col')
                if part_col == "":
                    part_col = None
        
        # 컬럼 정보를 간단히 표시 (expander로 숨김)
        with st.expander("📊 사용 중인 컬럼 정보", expanded=False):
            if amount_col:
                st.write(f"💰 금액 컬럼: **{amount_col}** (N열)")
            if part_col:
                st.write(f"📋 파트 컬럼: **{part_col}**")
        
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
        with st.expander("🔍 상세 정보 보기", expanded=False):
            st.write("**데이터 샘플:**")
            if part_col and amount_col:
                st.dataframe(df[[part_col, amount_col]].head(10))
            elif amount_col:
                st.dataframe(df[[amount_col]].head(10))
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
        
        # 11월 데이터 분석 차트
        st.subheader("📊 11월 데이터 분석")
        
        # 주간별 또는 일별 트렌드 (날짜 컬럼이 있는 경우)
        if '년월' in df.columns or len(date_columns) > 0:
            if len(date_columns) > 0:
                date_col = date_columns[0]
                # 주간별 집계
                df['주차'] = df[date_col].dt.isocalendar().week
                df['일'] = df[date_col].dt.day
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # 주차별 데이터
                    weekly_data = df.groupby('주차').size().reset_index(name='건수')
                    fig_weekly = px.bar(
                        weekly_data,
                        x='주차',
                        y='건수',
                        title='11월 주차별 데이터 건수',
                        labels={'주차': '주차', '건수': '건수'},
                        color='건수',
                        color_continuous_scale='Blues'
                    )
                    st.plotly_chart(fig_weekly, use_container_width=True)
                
                with col2:
                    # 일별 데이터
                    daily_data = df.groupby('일').size().reset_index(name='건수')
                    fig_daily = px.line(
                        daily_data,
                        x='일',
                        y='건수',
                        title='11월 일별 데이터 추이',
                        markers=True
                    )
                    fig_daily.update_layout(
                        xaxis_title="일",
                        yaxis_title="건수",
                        hovermode='x unified'
                    )
                    st.plotly_chart(fig_daily, use_container_width=True)
        else:
            # 날짜 정보가 없으면 전체 데이터 건수 표시
            st.info("날짜 정보가 없어 트렌드 분석을 할 수 없습니다.")
        
        # 플랫폼별 비교
        st.subheader("📋 플랫폼별 분석 (11월)")
        
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
            
            # 플랫폼별 상세 통계 테이블
            st.markdown("#### 📊 플랫폼별 상세 통계")
            category_stats = df.groupby(category_col).agg({
                col: ['count', 'mean'] if df[col].dtype in ['int64', 'float64'] else 'count'
                for col in df.select_dtypes(include=['int64', 'float64']).columns[:3]  # 숫자형 컬럼 상위 3개만
            }).round(0).astype(int)  # 소수점 이하 반올림하여 정수로 변환
            
            # 천단위 구분 기호(콤마) 적용
            category_stats_formatted = category_stats.copy()
            # MultiIndex 컬럼인 경우와 일반 컬럼인 경우 모두 처리
            if isinstance(category_stats_formatted.columns, pd.MultiIndex):
                # MultiIndex 컬럼 처리
                for col in category_stats_formatted.columns:
                    if category_stats_formatted[col].dtype in ['int64', 'float64', 'int32', 'float32']:
                        category_stats_formatted[col] = category_stats_formatted[col].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "")
            else:
                # 일반 컬럼 처리
                for col in category_stats_formatted.columns:
                    if category_stats_formatted[col].dtype in ['int64', 'float64', 'int32', 'float32']:
                        category_stats_formatted[col] = category_stats_formatted[col].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "")
            
            st.dataframe(category_stats_formatted, use_container_width=True)
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
        st.subheader("📋 11월 상세 데이터")
        
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

