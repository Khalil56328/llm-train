# -*- coding: utf-8 -*-
"""临时脚本：将功能点 xlsx 完整内容导出为 utf-8 文本"""
import glob, os
import pandas as pd

os.chdir(os.path.dirname(os.path.abspath(__file__)))
c = r'd:\work\project\20260806\docs\训推平台功能点.xlsx'
xl = pd.ExcelFile(c)
with open('_xlsx_dump.txt', 'w', encoding='utf-8') as f:
    for s in xl.sheet_names:
        df = xl.parse(s, header=None)
        f.write('==== SHEET: %s shape: %s\n' % (s, df.shape))
        f.write(df.to_string(max_rows=500, max_cols=20))
        f.write('\n')
print('done')
