import pandas as pd
import sys

try:
    xls = pd.ExcelFile('주간회의록.xlsx')
    print('시트 목록:', xls.sheet_names)
    print('\n' + '='*50)
    
    for sheet in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet)
        print(f'\n시트명: {sheet}')
        print(f'행 수: {len(df)}, 열 수: {len(df.columns)}')
        print(f'컬럼명: {list(df.columns)}')
        print(f'\n첫 5행 데이터:')
        print(df.head().to_string())
        print('\n' + '-'*50)
        
except Exception as e:
    print(f'에러 발생: {e}')
    import traceback
    traceback.print_exc()

