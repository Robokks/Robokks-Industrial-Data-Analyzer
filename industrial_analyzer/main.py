import sys, csv
from pathlib import Path
import numpy as np
import pandas as pd
from PySide6 import QtWidgets as Q, QtCore as C
import pyqtgraph as pg
from engine import load, demo, describe, analyze, paired
from safe_export import export_table

PAGES=['Overview','Data Explorer','Signal Trends','Statistics','Thresholds','Comparison','Engineering Lab','Advanced Diagnostics','Reports & Export']
LAB=['Distribution','Process Capability','State & Events','Relationships','Stability & SPC']
ADV=['Frequency Spectrum','Signal Conditioning','Anomaly Detection','Lag & Correlation','Data Quality','Transients','Envelope & Peaks','Autocorrelation','Band Energy','Change Detection']
PARAM={'Frequency Spectrum': [('FFT sample count',512),('Hann window (1=yes)',1)],'Signal Conditioning':[('Moving window',11),('Derivative (1=yes)',0)],'Anomaly Detection':[('Z-score limit',3)],'Lag & Correlation':[('Max lag samples',40)],'Data Quality':[('Gap factor',3)],'Transients':[('Slew threshold',30)],'Envelope & Peaks':[('Peak prominence',5)],'Autocorrelation':[('Max lag',150)],'Band Energy':[('Band split Hz',2)],'Change Detection':[('Window samples',30),('Shift threshold',5)],'Distribution':[('Histogram bins',24)],'Process Capability':[('LSL',25),('USL',75),('Target',50)],'State & Events':[('Threshold',50),('Minimum duration',0)],'Stability & SPC':[('Rolling window',25),('Sigma multiplier',3)],'Thresholds':[('Lower limit',25),('Upper limit',75)],'Statistics':[('Histogram bins',24)],'Rolling Statistics':[('Window',25)],'Quality & Outliers':[('IQR multiplier',1.5)]}
COLORS=['#58e0e0','#5d8fff','#55d6a0','#ffbe67','#ff7588','#bd9cff']
STYLE='''QWidget{background:#081321;color:#e9f2fb;font:13px "Segoe UI"} QFrame#card{background:#102235;border:1px solid #294156;border-radius:12px} QPushButton{background:#1a3046;border:1px solid #365369;border-radius:8px;padding:10px;text-align:left} QPushButton:hover,QPushButton:checked{background:#1c5267;border-color:#58e0e0} QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox{background:#0d1929;border:1px solid #34506b;border-radius:6px;padding:7px} QHeaderView::section{background:#20334a;color:#b9d4e7;padding:8px;border:0} QTableWidget,QListWidget{background:#0b1726;border:1px solid #294156;alternate-background-color:#13283a;gridline-color:#294156} QTabBar::tab{background:#142d41;padding:12px;border:1px solid #35556c} QTabBar::tab:selected{background:#176c7b} QLabel#heading{font-size:27px;font-weight:bold} QLabel#micro{color:#58e0e0;font-weight:bold} QScrollArea{border:0}'''

def fmt(x):
    return f'{x:.6g}' if isinstance(x,(float,np.floating)) else str(x)
def label(s,kind=None):
    w=Q.QLabel(s); w.setTextFormat(C.Qt.TextFormat.PlainText); w.setWordWrap(True)
    if kind:w.setObjectName(kind)
    return w
def button(s,fn):
    w=Q.QPushButton(s);w.clicked.connect(fn);return w
def table(headers,rows):
    w=Q.QTableWidget(); fill(w,headers,rows); return w
def fill(w,headers,rows):
    rows=list(rows); w.clear(); w.setColumnCount(len(headers));w.setHorizontalHeaderLabels(headers);w.setRowCount(min(len(rows),10000));w.setAlternatingRowColors(True);w.setEditTriggers(Q.QAbstractItemView.EditTrigger.NoEditTriggers)
    for i,row in enumerate(rows[:10000]):
        for j,x in enumerate(row[:len(headers)]):w.setItem(i,j,Q.QTableWidgetItem(fmt(x)))
    w.horizontalHeader().setStretchLastSection(True)
def plot():
    p=pg.PlotWidget(background='#0b1726');p.showGrid(x=True,y=True,alpha=.2);p.addLegend();p.setMinimumHeight(290);return p
def draw(p,curves):
    p.clear()
    for i,(x,y,n) in enumerate(curves):
        p.plot(x,y,name=n,pen=None if n in ('Flags','XY') else pg.mkPen(COLORS[i%len(COLORS)],width=1.5),symbol='o' if n in ('Flags','XY') else None,symbolSize=5,connect='finite',autoDownsample=True)

def export(parent,headers,rows):
    path,_=Q.QFileDialog.getSaveFileName(parent,'Export','','CSV (*.csv);;Excel (*.xlsx)')
    if path:
        try:
            export_table(path,headers,rows)
        except Exception as e:Q.QMessageBox.warning(parent,'Export failed',str(e))

class Workbench(Q.QWidget):
    def __init__(self,app,tool):
        super().__init__();self.app=app;self.tool=tool;self.rows=[]; self.headers=[];v=Q.QVBoxLayout(self);v.addWidget(label(tool,'heading'));bar=Q.QHBoxLayout();v.addLayout(bar);self.a=Q.QComboBox();self.a.addItems(app.names());bar.addWidget(self.a);self.b=Q.QComboBox();self.b.addItems(app.names());self.b.setCurrentIndex(min(1,len(app.data)-1))
        if tool in ('Comparison','Relationships','Lag & Correlation'):bar.addWidget(self.b)
        self.params=[]
        for n,d in PARAM.get(tool,[]):
            col=Q.QVBoxLayout();col.addWidget(label(n));s=Q.QDoubleSpinBox();s.setRange(-1e9,1e9);s.setDecimals(4);s.setValue(d);col.addWidget(s);bar.addLayout(col);self.params.append(s)
        bar.addWidget(button('Run analysis',self.run));bar.addWidget(button('Export results',lambda:export(self,self.headers,self.rows)));self.metrics=label('Choose a channel and run analysis.');v.addWidget(self.metrics);self.p=plot();v.addWidget(self.p,1);self.tbl=table([],[]);v.addWidget(self.tbl,1)
    def run(self):
        try:
            vals=[x.value() for x in self.params]; args=dict(zip(['p','q','r'],vals));curves,m,self.rows=analyze(self.tool,self.app.data[self.a.currentIndex()],self.app.data[self.b.currentIndex()],**args);draw(self.p,curves);self.metrics.setText('   |   '.join(f'{k}: {fmt(x)}' for k,x in m.items()) or 'Analysis complete');n=max(map(len,self.rows),default=2);self.headers=['Measure / index','Value'] if n==2 else [f'Field {i+1}' for i in range(n)];fill(self.tbl,self.headers,self.rows)
        except Exception as e:self.metrics.setText('Analysis not completed: '+str(e));self.p.clear();self.rows=[];fill(self.tbl,[],[])

class App(Q.QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle('INDUSTRIAL / ANALYZER — Python Desktop');self.resize(1440,900);self.data=demo();self.source='Demo data';self.selected=set(range(4));self.page=0;root=Q.QWidget();self.setCentralWidget(root);h=Q.QHBoxLayout(root);side=Q.QVBoxLayout();h.addLayout(side);brand=label('⌁  INDUSTRIAL\n     DATA ANALYZER','heading');side.addWidget(brand);self.nav=[]
        for i,n in enumerate(PAGES):
            b=button(n,lambda _,i=i:self.show_page(i));b.setCheckable(True);b.setFixedWidth(220);side.addWidget(b);self.nav.append(b)
        side.addStretch();side.addWidget(label('OFFLINE WORKSPACE · PYTHON'));main=Q.QVBoxLayout();h.addLayout(main,1);top=Q.QHBoxLayout();main.addLayout(top);self.title=label('Analysis Overview','heading');top.addWidget(self.title,1);self.badge=label('');top.addWidget(self.badge);top.addWidget(button('＋ Open data file',self.open_file));top.addWidget(button('Reset Demo',self.reset));self.scroll=Q.QScrollArea();self.scroll.setWidgetResizable(True);main.addWidget(self.scroll,1);self.show_page(0)
    def names(self):return [c.name for c in self.data]
    def reset(self):self.data=demo();self.source='Demo data';self.selected=set(range(4));self.show_page(self.page)
    def open_file(self):
        path,_=Q.QFileDialog.getOpenFileName(self,'Open recording','','All supported (*.tdms *.txt *.csv *.xlsx *.xls *.xlsm);;All files (*)')
        if not path:return
        try:
            args={}; ext=Path(path).suffix.lower()
            if ext!='.tdms':
                if ext in ('.xlsx','.xls','.xlsm'):
                    with pd.ExcelFile(path) as f:sheets=f.sheet_names
                    sheet,ok=Q.QInputDialog.getItem(self,'Worksheet','Select sheet',sheets,0,False)
                    if not ok:return
                    args['sheet']=sheet
                else:
                    sep,ok=Q.QInputDialog.getText(self,'Text import','Delimiter (blank = automatic, \\t = tab)')
                    if not ok:return
                    args['delimiter']=sep.replace('\\t','\t') or None
                time,ok=Q.QInputDialog.getText(self,'Time base','Time column name (seconds or datetime), blank = none')
                if not ok:return
                args['time_column']=time.strip() or None
                if not time.strip():
                    fs,ok=Q.QInputDialog.getDouble(self,'Sampling rate','Hz (0 = sample index)',0,0,1e9,6)
                    if not ok:return
                    args['sample_rate']=fs or None
            data=load(path,**args)
            if not data:raise ValueError('No numeric channels found')
            self.data=data;self.source=Path(path).name;self.selected=set(range(min(4,len(data))));self.show_page(self.page)
        except Exception as e:Q.QMessageBox.warning(self,'Import failed',str(e))
    def show_page(self,i):
        self.page=i;self.title.setText(PAGES[i]);self.badge.setText(f'{self.source} · {len(self.data)} channels');[b.setChecked(j==i) for j,b in enumerate(self.nav)];w=Q.QWidget();v=Q.QVBoxLayout(w);self.scroll.setWidget(w)
        if i==0:
            v.addWidget(label('ENGINEERING INTELLIGENCE / WORKSPACE 01','micro'));v.addWidget(label('From recorded signals\nto clear decisions.','heading'));v.addWidget(label('Explore the complete dataset, inspect operating behavior and choose an investigation.'));row=Q.QHBoxLayout();v.addLayout(row)
            for n,x in [('CHANNELS DISCOVERED',len(self.data)),('MAX SAMPLES',max(len(c.y) for c in self.data)),('ACTIVE SELECTION',len(self.selected))]:
                card=Q.QFrame();card.setObjectName('card');cl=Q.QVBoxLayout(card);cl.addWidget(label(n,'micro'));cl.addWidget(label(str(x),'heading'));row.addWidget(card)
            p=plot();v.addWidget(p);draw(p,[(c.t,c.y,c.name) for c in self.data[:4]]);v.addWidget(label('Dataset information: '+self.source));v.addStretch()
        elif i==1:
            search=Q.QLineEdit();search.setPlaceholderText('Search name or index…');v.addWidget(search);lst=Q.QListWidget();v.addWidget(lst)
            def refresh():
                lst.clear()
                for j,c in enumerate(self.data):
                    if search.text().lower() not in f'{j} {c.name}'.lower():continue
                    d=describe(c.y);item=Q.QListWidgetItem(f'{j:03}   {c.name}   |   {c.unit}   |   {len(c.y)} samples   |   {fmt(d.get("Min","—"))} … {fmt(d.get("Max","—"))}');item.setData(C.Qt.ItemDataRole.UserRole,j);item.setFlags(item.flags()|C.Qt.ItemFlag.ItemIsUserCheckable);item.setCheckState(C.Qt.CheckState.Checked if j in self.selected else C.Qt.CheckState.Unchecked);lst.addItem(item)
            def changed(item):
                j=item.data(C.Qt.ItemDataRole.UserRole);self.selected.add(j) if item.checkState()==C.Qt.CheckState.Checked else self.selected.discard(j)
            lst.itemChanged.connect(changed);search.textChanged.connect(refresh);refresh();v.addWidget(button('Open signal trends',lambda:self.show_page(2)))
        elif i==2:
            v.addWidget(label('Signal Analysis Studio','heading'));bar=Q.QHBoxLayout();v.addLayout(bar);bar.addWidget(button('Browse channels',lambda:self.show_page(1)));width=Q.QComboBox();width.addItems(['100','50','25','10']);bar.addWidget(label('Window %'));bar.addWidget(width);pos=Q.QSlider(C.Qt.Orientation.Horizontal);pos.setRange(0,100);bar.addWidget(pos,1);mode=Q.QCheckBox('Two synchronized panels');mode.setChecked(True);bar.addWidget(mode);p1=plot();p2=plot();v.addWidget(p1);v.addWidget(p2);p2.setXLink(p1);readout=label('Move cursor over graph');v.addWidget(readout)
            def redraw(*_):
                cs=[]
                for j in sorted(self.selected):
                    c=self.data[j];n=max(1,int(len(c.y)*int(width.currentText())/100));start=int((len(c.y)-n)*pos.value()/100);cs.append((c.t[start:start+n],c.y[start:start+n],c.name))
                mid=(len(cs)+1)//2 if mode.isChecked() else len(cs);draw(p1,cs[:mid]);draw(p2,cs[mid:]);p2.setVisible(mode.isChecked())
            def cursor(point):
                x=p1.getPlotItem().vb.mapSceneToView(point).x();values=[]
                for j in sorted(self.selected)[:12]:
                    c=self.data[j];k=np.argmin(abs(c.t-x));values.append(f'{c.name}: {fmt(c.y[k])}')
                readout.setText(f'Cursor {x:.4g} | '+'  '.join(values))
            p1.scene().sigMouseMoved.connect(cursor);width.currentTextChanged.connect(redraw);pos.valueChanged.connect(redraw);mode.toggled.connect(redraw);redraw();v.addWidget(button('Export selected channels',self.export_selected))
        elif i==3:
            headers=['Channel','Valid','Min','Max','Mean','Median','RMS','Std Dev','Peak-to-Peak'];rows=[[c.name]+[d.get(k,np.nan) for k in headers[1:]] for c in self.data for d in [describe(c.y)]];tbl=table(headers,rows);v.addWidget(tbl);v.addWidget(button('Export all statistics',lambda:export(self,headers,rows)));tabs=Q.QTabWidget();v.addWidget(tabs);works=[]
            for t in ['Statistics','Rolling Statistics','Quality & Outliers','Segment Comparison']:
                wb=Workbench(self,t);works.append(wb);tabs.addTab(wb,t)
            def pick(row,col):
                for wb in works:wb.a.setCurrentIndex(row)
                works[tabs.currentIndex()].run()
            tbl.cellClicked.connect(pick)
        elif i in (4,5):
            v.addWidget(Workbench(self,PAGES[i]));
            if i==5:
                def matrix():
                    ids=sorted(self.selected)[:8];names=[self.data[j].name for j in ids];rows=[]
                    for j in ids:
                        row=[self.data[j].name]
                        for k in ids:
                            try:a,b=paired(self.data[j],self.data[k]);m=np.isfinite(a)&np.isfinite(b);row.append(np.corrcoef(a[m],b[m])[0,1] if m.sum()>1 else np.nan)
                            except ValueError:row.append(np.nan)
                        rows.append(row)
                    fill(mt,['Channel']+names,rows);self.matrix_data=(['Channel']+names,rows)
                self.matrix_data=([],[]);v.addWidget(button('Calculate correlation matrix (selected, max 8)',matrix));mt=table([],[]);v.addWidget(mt);v.addWidget(button('Export matrix',lambda:export(self,*self.matrix_data)))
        elif i in (6,7):
            tabs=Q.QTabWidget();v.addWidget(tabs)
            for t in LAB if i==6 else ADV:tabs.addTab(Workbench(self,t),t)
        else:
            edit=Q.QPlainTextEdit();v.addWidget(edit);edit.setPlainText('Engineering Analysis Report\nSource: '+self.source+'\n'+'\n'.join(c.name+': '+str(describe(c.y)) for j,c in enumerate(self.data) if j in self.selected));v.addWidget(button('Export selected data',self.export_selected))
            def save():
                path,_=Q.QFileDialog.getSaveFileName(self,'Save report','','Text (*.txt)');
                if path:Path(path).write_text(edit.toPlainText(),encoding='utf-8')
            v.addWidget(button('Download report TXT',save))
    def export_selected(self):
        # Long format preserves independent channel time bases.
        rows=[(c.name,c.unit,c.time_unit,t,y) for j,c in enumerate(self.data) if j in self.selected for t,y in zip(c.t,c.y)];export(self,['Channel','Unit','Time unit','Time','Value'],rows)

if __name__=='__main__':
    from v12_ui import run
    sys.exit(run())
