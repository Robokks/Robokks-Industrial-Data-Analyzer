"""Stream exports, escape formula injection, and atomically replace destinations."""
import csv
import math
import os
import tempfile
from pathlib import Path
import numpy as np

def safe_cell(value):
    if isinstance(value,np.generic):value=value.item()
    if isinstance(value,float) and not math.isfinite(value):return None
    if isinstance(value,str) and (value.lstrip().startswith(('=','+','-','@')) or value.startswith(('\t','\r','\n'))):
        return "'"+value
    return value

def export_table(path,headers,rows):
    path=Path(path)
    if path.suffix.lower() not in ('.csv','.xlsx'):
        raise ValueError('Choose CSV or XLSX extension')
    headers=[safe_cell(x) for x in headers]
    def records():
        for row in rows:
            clean=[safe_cell(v) for v in row]
            if len(clean)!=len(headers):raise ValueError('Export row width does not match headers')
            yield clean
    fd,tmp=tempfile.mkstemp(suffix=path.suffix,dir=path.parent)
    os.close(fd)
    try:
        if path.suffix.lower()=='.csv':
            with open(tmp,'w',newline='',encoding='utf-8') as f:
                writer=csv.writer(f);writer.writerow(headers);writer.writerows(records())
        else:
            from openpyxl import Workbook
            if len(headers)>16384:raise ValueError('Excel column limit exceeded; choose CSV')
            book=Workbook(write_only=True);sheet=book.create_sheet('Measurements');sheet.append(headers)
            try:
                for i,row in enumerate(records(),start=2):
                    if i>1048576:raise ValueError('Excel row limit exceeded; choose CSV')
                    sheet.append(row)
                book.save(tmp)
            finally:
                if not sheet.closed:sheet.close()
                book.close()
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
