"""Escape spreadsheet formulas in untrusted text and replace output atomically."""
import os
import tempfile
from pathlib import Path
import pandas as pd

def safe_cell(value):
    if isinstance(value,str) and (value.lstrip().startswith(('=','+','-','@')) or value.startswith(('\t','\r','\n'))):
        return "'"+value
    return value

def export_table(path,headers,rows):
    path=Path(path)
    if path.suffix.lower() not in ('.csv','.xlsx'):
        raise ValueError('Choose CSV or XLSX extension')
    frame=pd.DataFrame(([safe_cell(v) for v in row] for row in rows),columns=[safe_cell(x) for x in headers])
    fd,tmp=tempfile.mkstemp(suffix=path.suffix,dir=path.parent)
    os.close(fd)
    try:
        if path.suffix.lower()=='.xlsx': frame.to_excel(tmp,index=False,engine='openpyxl')
        else: frame.to_csv(tmp,index=False)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
