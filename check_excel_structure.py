import pandas as pd
import sys

try:
    xls = pd.ExcelFile('주간회의록.xlsx')
    print('='*60)
    print('시트 목록:', xls.sheet_names)
    print('='*60)
    
    for sheet in xls.sheet_names:
        print(f'\n{"="*60}')
        print(f'시트명: {sheet}')
        print(f'{"="*60}')
        df = pd.read_excel(xls, sheet_name=sheet)
        print(f'행 수: {len(df)}, 열 수: {len(df.columns)}')
        print(f'\n컬럼명:')
        for i, col in enumerate(df.columns, 1):
            print(f'  {i}. {col}')
        
        print(f'\n첫 10행 데이터:')
        print(df.head(10).to_string())
        
        print(f'\n데이터 타입:')
        print(df.dtypes)
        
        # 11월 관련 데이터 확인
        if '11월' in sheet or '11' in sheet:
            print(f'\n*** 11월 시트 발견! ***')
            print(f'전체 데이터 샘플:')
            print(df.to_string())
        
except Exception as e:
    print(f'에러 발생: {e}')
    import traceback
    traceback.print_exc()

