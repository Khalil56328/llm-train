# -*- coding: utf-8 -*-
"""临时脚本：读取功能点 xlsx 全部内容并打印"""
import glob, os, sys
import pandas as pd

os.chdir(os.path.dirname(os.path.abspath(__file__)))
cands = glob.glob(r'd:\work\project\20260806\docs\*.xlsx')
print('FOUND:', cands)
for c in cands:
    xl = pd.ExcelFile(c)
    print('SHEETS:', xl.sheet_names)
    for s in xl.sheet_names:
        df = xl.parse(s, header=None)
        print('==== SHEET:', s, 'shape:', df.shape)
        print(df.to_string(max_rows=200, max_cols=20))
