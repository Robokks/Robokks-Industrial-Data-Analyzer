"""Native V12.2 presentation layer; no HTML, JavaScript, or WebView."""
import sys
import logging
import time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import signal, stats
from PySide6 import QtWidgets as Q, QtCore as C, QtGui as G
import pyqtgraph as pg
from main import App as LegacyApp, PAGES, LAB, ADV, PARAM, fmt, label, button, table, fill, export
from engine import Channel, describe, analyze, paired, events
from access import AccessStore, Session, ROLES, MATRIX
import ui_theme as theme
from performance import preview_indices, nearest_index, cursor_measurement

TITLES = ["Analysis Overview","Data Explorer","Signal Trend Workspace","Statistical Analysis","Threshold Analysis","Signal Comparison","Engineering Analysis Lab","Advanced Signal Diagnostics","Reports & Export"]
ICONS = ["▦","▤","⌁","▥","⚑","⇄","◈","✧","▣"]
PALETTE = ["#4dd9e8","#ffbe67","#8e95ff","#55d6a0","#ff7588","#cb91ef","#78b6ff","#f4d35e"]
STYLE = """
QWidget {color:#e9f2fb;font:14px 'Segoe UI';}
QMainWindow,QDialog,QWidget#workspace,QWidget#page,QScrollArea>QWidget>QWidget{background:#081321;}
QFrame#sidebar{background:#0a1828;border-right:1px solid #294156;}
QFrame#card{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #142337,stop:1 #101c2d);border:1px solid #294156;border-radius:13px;}
QFrame#hero{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #163b52,stop:.65 #122a43,stop:1 #153e4b);border:1px solid #325873;border-radius:18px;}
QFrame#metric{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #142a40,stop:1 #0e1f30);border:1px solid #294156;border-radius:14px;}
QFrame#toolbar{background:#122d40;border:1px solid #34566c;border-radius:12px;}
QLabel#heading{font-size:29px;font-weight:700;}
QLabel#heroTitle{font-size:44px;font-weight:750;color:#e9f2fb;}
QLabel#heroAccent{font-size:44px;font-weight:750;color:#73e5df;}
QLabel#micro{font-size:11px;font-weight:700;color:#6bdbde;}
QLabel#sub{font-size:12px;color:#9ab7c9;}
QLabel#section{font-size:17px;font-weight:700;}
QLabel#metricValue{font-size:30px;font-weight:750;}
QLabel#pill{background:#102b3a;border:1px solid #31546a;border-radius:15px;padding:7px 12px;color:#65dce4;font-size:11px;}
QLabel#status{background:#102e40;border:1px solid #31536b;border-radius:8px;padding:11px;color:#b9e5ed;font-size:12px;}
QPushButton{background:#1a3046;border:1px solid #3c5974;border-radius:8px;padding:9px 13px;color:#e5f3ff;font-weight:600;}
QPushButton:hover{background:#25445e;border-color:#58e0e0;}
QPushButton:focus{border:2px solid #58e0e0;}
QPushButton:disabled{background:#132435;color:#678095;border-color:#273a50;}
QPushButton#primary{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2cb5d0,stop:1 #4679db);border:1px solid #3985aa;color:white;}
QPushButton#nav{background:transparent;border:0;border-radius:9px;text-align:left;padding:12px 13px;font-weight:400;color:#aabbd0;}
QPushButton#nav:checked{background:#1c334b;border-left:3px solid #58e0e0;color:white;}
QPushButton#nav:hover{background:#1c334b;}
QPushButton#tool{background:#152e43;border:1px solid #30536b;border-radius:12px;text-align:left;padding:17px;}
QPushButton#tool:hover{background:#1a4055;border-color:#67dfe3;}
QPushButton#tab{background:#12283c;border:1px solid #365369;border-radius:10px;padding:11px;}
QPushButton#tab:checked{background:#156474;border-color:#5fe4e2;color:white;}
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox,QPlainTextEdit{background:#0d1929;color:#e9f2fb;border:1px solid #34506b;border-radius:8px;padding:8px;}
QLineEdit:focus,QComboBox:focus,QSpinBox:focus,QDoubleSpinBox:focus{border-color:#58e0e0;}
QComboBox QAbstractItemView{background:#102235;color:#e9f2fb;selection-background-color:#1c5267;}
QHeaderView::section{background:#20334a;color:#b9d4e7;padding:10px;border:0;font-size:12px;font-weight:700;}
QTableWidget,QListWidget{background:#0b1726;border:1px solid #294156;border-radius:9px;alternate-background-color:#13283a;gridline-color:#26394b;font-size:12px;selection-background-color:#16465b;}
QTableWidget::item{padding:7px;}
QScrollArea{border:0;background:transparent;}
QScrollBar:vertical{background:#0c1a28;width:12px;margin:0;}
QScrollBar::handle:vertical{background:#34546a;border-radius:5px;min-height:28px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}
QSlider::groove:horizontal{height:6px;background:#263b50;border-radius:3px;}
QSlider::handle:horizontal{background:#53cce2;width:16px;margin:-5px 0;border-radius:8px;}
QCheckBox{spacing:8px;}
QCheckBox::indicator{width:17px;height:17px;border:1px solid #538196;border-radius:3px;background:#0d1929;}
QCheckBox::indicator:checked{background:#2494a5;border:2px solid #8be9e8;}
"""

def frame(kind="card", margins=19):
    w=Q.QFrame(); w.setObjectName(kind)
    l=Q.QVBoxLayout(w); l.setContentsMargins(margins,margins,margins,margins); l.setSpacing(12)
    return w,l

def row():
    return theme.AdaptiveRow()

def btn(text,fn,kind=None):
    b=button(text,fn)
    if kind:b.setObjectName(kind)
    b.setMinimumHeight(36);b.setCursor(C.Qt.CursorShape.PointingHandCursor);b.setToolTip(text.replace("\n"," "))
    return b

def card_title(layout,title,subtitle=None):
    layout.addWidget(label(title,"section"))
    if subtitle:layout.addWidget(label(subtitle,"sub"))

def field(layout,title,w):
    col=Q.QVBoxLayout(); col.setSpacing(6); col.addWidget(label(title,"micro")); col.addWidget(w); layout.addLayout(col);return w

def metric(title,value="—",sub=""):
    w,l=frame("metric",18);l.setSpacing(5);l.addWidget(label(title.upper(),"micro"))
    n=label(str(value),"metricValue");l.addWidget(n)
    if sub:l.addWidget(label(sub,"sub"))
    return w,n

def kpis(parent,items,columns=4):
    grid=theme.mark_grid(Q.QGridLayout(),columns,190);grid.setSpacing(14);parent.addLayout(grid)
    out=[]
    for i,item in enumerate(items):
        w,n=metric(*item);grid.addWidget(w,i//columns,i%columns);out.append(n)
    for i in range(columns):grid.setColumnStretch(i,1)
    return out

def plot(height=310):
    p=pg.PlotWidget(background=theme.colors()["plot"])
    p.setMinimumHeight(height);p.setMinimumWidth(240);p.showGrid(x=True,y=True,alpha=.24)
    for a in ("left","bottom"):
        p.getAxis(a).setPen(pg.mkPen(theme.colors()["grid"]));p.getAxis(a).setTextPen(pg.mkPen(theme.colors()["axis"]))
    p.addLegend(offset=(12,12),labelTextColor=theme.colors()["text"])
    p.setClipToView(True)
    p._analyzer_theme=theme.MODE
    return p

def apply_plot_theme(p):
    previous=getattr(p,"_analyzer_theme","dark")
    if previous==theme.MODE:return
    c=theme.colors()
    p.setBackground(c["plot"])
    for a in ("left","bottom","right","top"):
        axis=p.getAxis(a);axis.setPen(pg.mkPen(c["grid"]));axis.setTextPen(pg.mkPen(c["axis"]))
        axis.setLabel(text=axis.labelText,units=axis.labelUnits,unitPrefix=getattr(axis,"labelUnitPrefix",""),color=c["axis"])
    legend=p.plotItem.legend
    if legend is not None and hasattr(legend,"setLabelTextColor"):legend.setLabelTextColor(c["text"])
    mapping=dict(zip(theme.DARK_TRACES,theme.LIGHT_TRACES)) if theme.MODE=="light" else dict(zip(theme.LIGHT_TRACES,theme.DARK_TRACES))
    def paint(value,brush=False):
        if value is None:return None
        try:
            obj=pg.mkBrush(value) if brush else pg.mkPen(value)
            name=obj.color().name()
            if name not in mapping:return None
            obj.setColor(G.QColor(mapping[name]));return obj
        except (TypeError,ValueError):return None
    for item in p.plotItem.items:
        if isinstance(item,pg.PlotDataItem):
            pen=paint(item.opts.get("pen"))
            if pen is not None:item.setPen(pen)
            brush=paint(item.opts.get("symbolBrush"),True)
            if brush is not None:item.setSymbolBrush(brush)
            symbol_pen=paint(item.opts.get("symbolPen"))
            if symbol_pen is not None:item.setSymbolPen(symbol_pen)
        elif isinstance(item,pg.BarGraphItem):
            brush=paint(item.opts.get("brush"),True);pen=paint(item.opts.get("pen"));opts={}
            if brush is not None:opts["brush"]=brush
            if pen is not None:opts["pen"]=pen
            if opts:item.setOpts(**opts)
        elif isinstance(item,pg.InfiniteLine):
            pen=paint(item.pen)
            if pen is not None:item.setPen(pen)
            if getattr(item,"label",None) is not None:item.label.setColor(c["text"])
    p._analyzer_theme=theme.MODE

def draw(p,curves,colors=None):
    apply_plot_theme(p);p.clear()
    for i,(x,y,n) in enumerate(curves):
        col=(colors or PALETTE)[i%len(colors or PALETTE)]
        col=theme.trace_color(col)
        x=np.asarray(x);y=np.asarray(y)
        if n=="Histogram" and len(x)>1:
            p.addItem(pg.BarGraphItem(x=x,height=y,width=.9*abs(x[1]-x[0]),brush=col,pen=None))
        else:
            scatter=n in ("Flags","XY","Outliers","Residuals","Violations")
            p.plot(x,y,name=n,pen=None if scatter else pg.mkPen(col,width=1.8),symbol="o" if scatter else None,symbolBrush=col,symbolPen=None,symbolSize=5,connect="finite",autoDownsample=True,downsampleMethod="peak")
    p.enableAutoRange()

def chart(parent,title,height=310,subtitle=None):
    w,l=frame();card_title(l,title,subtitle);p=plot(height);l.addWidget(p);parent.addWidget(w);return w,p

def table_card(parent,title,headers,rows,minimum=240):
    w,l=frame();card_title(l,title);t=table(headers,rows);t.setMinimumHeight(minimum);t.setSelectionBehavior(Q.QAbstractItemView.SelectionBehavior.SelectRows);t.verticalHeader().hide();l.addWidget(t);parent.addWidget(w);return t

def combo(names,index=0):
    w=Q.QComboBox();w.addItems(names);w.setCurrentIndex(min(index,len(names)-1));w.setMinimumContentsLength(9);w.setToolTip(w.currentText());w.currentTextChanged.connect(w.setToolTip);w.setSizeAdjustPolicy(Q.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);return w

def number(value,lo=-1e9,hi=1e9,step=1,integer=False):
    w=Q.QSpinBox() if integer else Q.QDoubleSpinBox()
    if not integer:w.setDecimals(4)
    w.setRange(int(lo) if integer else lo,int(hi) if integer else hi);w.setSingleStep(int(step) if integer else step);w.setValue(int(value) if integer else value);return w

def password():
    w=Q.QLineEdit();w.setEchoMode(Q.QLineEdit.EchoMode.Password);w.setMaxLength(256);return w

def reference_demo():
    t=np.arange(600,dtype=float)*.1;i=np.arange(600)
    return [Channel(f"Parameter {j:03}",25+(j%10)*9+np.sin(t*2*np.pi/(8+(j%7)*4)+j*.24)*(6+(j%6)*2)+np.sin(t*1.1+j*.33)*2+(t*.08 if j%4==0 else 0)+(17*((i>370)&(i<420)) if j%9==0 else 0),t.copy(),"","s") for j in range(100)]

class Orbit(Q.QWidget):
    def __init__(self):
        super().__init__();self.setMinimumSize(235,230)
    def paintEvent(self,event):
        p=G.QPainter(self);p.setRenderHint(G.QPainter.RenderHint.Antialiasing)
        cx,cy=self.width()/2,self.height()/2
        p.setPen(G.QPen(G.QColor("#408798"),1))
        p.drawEllipse(C.QPointF(cx,cy),102,102)
        pen=G.QPen(G.QColor("#418d9b"),1,C.Qt.PenStyle.DashLine);p.setPen(pen);p.drawEllipse(C.QPointF(cx,cy),77,77)
        grad=G.QLinearGradient(cx-50,cy-50,cx+50,cy+50);grad.setColorAt(0,G.QColor("#1d8d9c"));grad.setColorAt(1,G.QColor("#1d4269"))
        p.setBrush(G.QBrush(grad));p.setPen(G.QPen(G.QColor("#83e6e9"),1));p.drawRoundedRect(C.QRectF(cx-50,cy-50,100,100),26,26)
        p.setPen(G.QColor("#e9ffff"));f=G.QFont(theme.FONT,32);f.setBold(True);p.setFont(f);p.drawText(C.QRectF(cx-50,cy-50,100,100),C.Qt.AlignmentFlag.AlignCenter,"IA")
        p.setFont(G.QFont(theme.FONT,8));p.setPen(G.QColor(theme.colors()["muted"]));p.drawText(C.QRectF(0,0,self.width(),18),C.Qt.AlignmentFlag.AlignCenter,"S I G N A L   I N T E L L I G E N C E");p.drawText(C.QRectF(0,self.height()-18,self.width(),18),C.Qt.AlignmentFlag.AlignCenter,"1 0 0 - C H A N N E L   R E A D Y")
        p.end()

class Login(Q.QDialog):
    def __init__(self,store,parent=None,allow_demo=True):
        super().__init__(parent);self.store=store;self.allow_demo=allow_demo;self.session=None;self.setWindowTitle("INDUSTRIAL / ANALYZER — Secure Engineering Workspace");self.resize(1080,600);self.setMinimumSize(840,520)
        layout=Q.QHBoxLayout();layout.setSpacing(16);self.setLayout(layout)
        art,al=frame("hero",42);layout.addWidget(art,5);al.addWidget(label("INDUSTRIAL / ANALYZER","section"));al.addStretch();al.addWidget(label("SECURE ENGINEERING WORKSPACE","micro"));al.addWidget(label("Intelligence\nbehind every","heroTitle"));al.addWidget(label("signal.","heroAccent"));al.addWidget(label("Explore trends, investigate anomalies and turn recorded machine data into engineering decisions.","sub"));al.addStretch();al.addWidget(label("OFFLINE ANALYSIS · ROLE-AWARE WORKSPACE · V12","micro"))
        w,l=frame("card",30);layout.addWidget(w,4);l.addStretch();self.first=store.empty()
        theme_row=Q.QHBoxLayout();theme_row.addWidget(label("FIRST-TIME SETUP" if self.first else "ACCESS CONTROL","micro"),1);choice=combo(["Dark","Light"],0 if theme.MODE=="dark" else 1);choice.setMaximumWidth(110);theme_row.addWidget(choice);l.addLayout(theme_row)
        def switch(text):
            theme.apply(Q.QApplication.instance(),STYLE,text.lower());C.QSettings("Robokks","IndustrialAnalyzer").setValue("theme",text.lower())
        choice.currentTextChanged.connect(switch);l.addWidget(label("Create administrator" if self.first else "Welcome back","heading"));l.addWidget(label("Create a local administrator to open real datasets." if self.first else "Sign in to continue to your analysis workspace.","sub"))
        self.user=Q.QLineEdit();self.user.setMaxLength(40);self.user.setPlaceholderText("Enter username");self.pw=password();self.pw.setPlaceholderText("Enter password")
        l.addWidget(label("Username","sub"));l.addWidget(self.user);l.addWidget(label("Password","sub"));l.addWidget(self.pw);self.confirm=password()
        if self.first:l.addWidget(label("Confirm password","sub"));l.addWidget(self.confirm)
        self.error=label("","status");self.error.hide();l.addWidget(self.error)
        if self.allow_demo:l.addWidget(btn("Explore demo (no account)",self.demo))
        submit=btn("Create administrator →" if self.first else "Sign in →",self.submit,"primary");submit.setDefault(True);l.addWidget(submit)
        l.addWidget(label("Demo access uses synthetic data only. Local accounts are protected by password hashing and OS file permissions; this is not a tamper-proof security boundary.","sub"));l.addStretch()
    def demo(self):
        if self.allow_demo:self.session=Session("Demo Engineer","Administrator",True);self.accept()
    def submit(self):
        try:
            if self.first:
                if self.pw.text()!=self.confirm.text():raise ValueError("Passwords do not match.")
                self.session=self.store.setup(self.user.text().strip(),self.pw.text())
            else:self.session=self.store.login(self.user.text(),self.pw.text())
            self.pw.clear();self.confirm.clear();self.accept()
        except (ValueError,PermissionError) as exc:
            self.error.setText(str(exc));self.error.show();self.pw.clear();self.confirm.clear()

class Desktop(LegacyApp):
    def __init__(self,store,session):
        Q.QMainWindow.__init__(self)
        self.store=store;self.session=session;self.data=reference_demo();self.source="Telegram_Demo_100_Parameters";self.selected=set(range(4));self.colors={};self.page=0;self.pages={};self.dirty=set(range(9));self._data_identity=id(self.data);self._stats={};self.last_activity=time.monotonic();self.recordings=[];self.file_channel_count=0;self._active_job=None;self._theme_changing=False
        self.setWindowTitle("INDUSTRIAL / ANALYZER — V12.2 Desktop");self.resize(1440,900);self.setMinimumSize(1024,640)
        root=Q.QWidget();root.setObjectName("workspace");self.setCentralWidget(root);outer=Q.QHBoxLayout(root);outer.setContentsMargins(0,0,0,0);outer.setSpacing(0)
        side=Q.QFrame();side.setObjectName("sidebar");side.setFixedWidth(236);sl=Q.QVBoxLayout(side);sl.setContentsMargins(13,22,13,20);sl.setSpacing(5);outer.addWidget(side)
        brand=Q.QHBoxLayout();brand.setSpacing(10);logo=label("IA","brandLogo");logo.setFixedSize(38,38);logo.setAlignment(C.Qt.AlignmentFlag.AlignCenter);brand.addWidget(logo);bl=Q.QVBoxLayout();bl.setSpacing(2);bl.addWidget(label("INDUSTRIAL","section"));bl.addWidget(label("D A T A   A N A L Y Z E R","micro"));brand.addLayout(bl,1);sl.addLayout(brand)
        line=Q.QFrame();line.setFrameShape(Q.QFrame.Shape.HLine);line.setObjectName("separator");sl.addSpacing(14);sl.addWidget(line);sl.addSpacing(12)
        self.nav=[]
        for i,n in enumerate(PAGES):
            b=btn(f"{i+1:02d}   {n}",lambda checked=False,i=i:self.show_page(i),"nav");b.setCheckable(True);b.setMinimumHeight(37);sl.addWidget(b);self.nav.append(b)
        sl.addSpacing(10);self.extra_btn=btn("     Extended tools",self.extended_tools,"nav");sl.addWidget(self.extra_btn);self.account_btn=btn("     Access & Users",self.account,"nav");sl.addWidget(self.account_btn);sl.addWidget(btn("     Lock / Sign out",self.lock,"nav"));sl.addStretch();sl.addWidget(label("OFFLINE WORKSPACE · V12.2\nMulti-recording workspace","sub"))
        self.main=Q.QVBoxLayout();self.main.setContentsMargins(24,18,24,0);self.main.setSpacing(14);outer.addLayout(self.main,1)
        top=Q.QHBoxLayout();top.setSpacing(12);title=Q.QVBoxLayout();title.setSpacing(4);title.addWidget(label("ANALYSIS CONTROL CENTER","micro"));self.title=label(TITLES[0],"heading");title.addWidget(self.title);top.addLayout(title,1)
        self.theme_selector=combo(["Dark","Light"],0 if theme.MODE=="dark" else 1);self.theme_selector.setAccessibleName("Color theme");self.theme_selector.setMaximumWidth(110);top.addWidget(self.theme_selector)
        self.open_btn=btn("Open data file",self.open_file,"primary");top.addWidget(self.open_btn);top.addWidget(btn("Reset Demo",self.reset));self.main.addLayout(top)
        status_row=Q.QHBoxLayout();status_row.setSpacing(8);self.userchip=label("","pill");self.badge=label("","pill");self.badge.setMaximumWidth(420);status_row.addWidget(self.userchip);status_row.addWidget(self.badge);status_row.addStretch(1);self.main.addLayout(status_row)
        self.theme_selector.currentTextChanged.connect(self.change_theme)
        divider=Q.QFrame();divider.setFrameShape(Q.QFrame.Shape.HLine);divider.setObjectName("separator");self.main.addWidget(divider)
        self.scroll=Q.QScrollArea();self.scroll.setWidgetResizable(True);self.scroll.setAlignment(C.Qt.AlignmentFlag.AlignTop);self.main.addWidget(self.scroll,1)
        self.layout_timer=C.QTimer(self);self.layout_timer.setSingleShot(True);self.layout_timer.setInterval(40);self.layout_timer.timeout.connect(self.reflow_page)
        self.apply_role();self.show_page(0);Q.QApplication.instance().installEventFilter(self)
        self.idle= C.QTimer(self);self.idle.timeout.connect(self.check_idle);self.idle.start(30000)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,"layout_timer") and not getattr(self,"_theme_changing",False):self.layout_timer.start()
    def reflow_page(self):
        if not hasattr(self,"scroll") or self._theme_changing:return
        w=self.scroll.widget()
        if w:
            theme.reflow(w.layout(),max(300,self.scroll.viewport().width()-24))
            w.layout().activate()
    def refresh_page_theme(self):
        page=self.pages.get(self.page)
        if page is None:return
        # Do not repaint inactive cached pages or inactive workbenches on theme changes.
        for p in page.findChildren(pg.PlotWidget):
            if p.isVisibleTo(page):apply_plot_theme(p)
        for w in page.findChildren(Orbit):w.update()
        for table_widget in page.findChildren(Q.QTableWidget):
            # Explicitly colored correlation cells require their own contrast.
            if table_widget.property("correlationTable"):
                for r in range(table_widget.rowCount()):
                    for j in range(1,table_widget.columnCount()):
                        item=table_widget.item(r,j)
                        if item is not None and item.background().style()!=C.Qt.BrushStyle.NoBrush:
                            item.setForeground(G.QColor(theme.contrasting_text(item.background().color().name())))
    def change_theme(self,text):
        mode=text.lower()
        if self._theme_changing or mode not in ("dark","light"):return
        if theme.MODE==mode and Q.QApplication.instance().styleSheet():return
        self._theme_changing=True;self.layout_timer.stop()
        self.setUpdatesEnabled(False)
        try:
            app=Q.QApplication.instance();theme.apply(app,STYLE,mode)
            pg.setConfigOptions(background=theme.colors()["plot"],foreground=theme.colors()["text"])
            C.QSettings("Robokks","IndustrialAnalyzer").setValue("theme",mode)
            self.refresh_page_theme()
        finally:
            self.setUpdatesEnabled(True);self._theme_changing=False;self.layout_timer.start()
    def eventFilter(self,obj,event):
        if event.type() in (C.QEvent.Type.MouseMove,C.QEvent.Type.KeyPress,C.QEvent.Type.MouseButtonPress):
            self.last_activity=time.monotonic()
        return False
    def check_idle(self):
        if time.monotonic()-self.last_activity>=900:
            if self._active_job is not None:self._active_job.cancel.set()
            else:self.lock()
    def apply_role(self):
        self.userchip.setText(self.session.username+" · "+("Demo" if self.session.demo else self.session.role))
        self.open_btn.setEnabled(True)
        self.open_btn.setText("Open data file" if self.session.allows("Open data files") else "Open data · Sign in")
        self.open_btn.setToolTip("Select TDMS, TXT, CSV or Excel recordings." if self.session.allows("Open data files") else "Sign in or create a local administrator to import real recordings.")
        for i in (6,7):self.nav[i].setEnabled(self.session.allows("Advanced diagnostics"))
        self.account_btn.setText("     Access & Users" if self.session.allows("Manage users") else "     My Account")
    def permitted(self,key):
        if not self.session.allows(key):return False
        if self.session.demo:return True
        try:self.store.require(self.session,key);return True
        except PermissionError:return False
    def audit(self,action,detail=""):
        if not self.session.demo:self.store.audit(self.session.username,action,detail)
    def stats_for(self,i):
        if i not in self._stats:self._stats[i]=describe(self.data[i].y)
        return self._stats[i]
    def dataset_changed(self):
        if id(self.data)==self._data_identity:return
        old=self.scroll.takeWidget()
        if old:old.setParent(None)
        for w in self.pages.values():w.deleteLater()
        self.pages.clear();self.dirty=set(range(9));self._data_identity=id(self.data);self._stats.clear();self.colors.clear()
    def selection_changed(self):
        self.dirty.update((0,1,2,5,8))
    def ensure_access(self,key):
        if self.permitted(key):return True
        if self.session.demo:
            dlg=Login(self.store,self,allow_demo=False)
            dlg.setWindowTitle("Sign in to open real measurements")
            result=dlg.exec()
            self.theme_selector.blockSignals(True)
            self.theme_selector.setCurrentText(theme.MODE.title())
            self.theme_selector.blockSignals(False)
            self.refresh_page_theme()
            if result!=Q.QDialog.DialogCode.Accepted or dlg.session is None or dlg.session.demo:return False
            self.session=dlg.session;self.apply_role();self.last_activity=time.monotonic()
            # Clear cached controls constructed under demo permissions.
            self.dirty.update(range(9));self.show_page(0)
            if self.permitted(key):return True
        Q.QMessageBox.information(self,"Access required",f"Your account does not have permission: {key}.")
        return False
    def extended_tools(self):
        try:
            import extra_ui as ex
            ex.open_tool_catalog(self)
        except Exception as exc:
            logging.exception("Extended tools failed")
            Q.QMessageBox.warning(self,"Extended tools",str(exc))
    def open_file(self):
        try:
            if not self.ensure_access("Open data files"):return
            from extra_ui import open_recordings
            open_recordings(self)
        except Exception as exc:
            logging.exception("Open data failed")
            Q.QMessageBox.warning(self,"Open data",str(exc))
    def reset(self):
        self.recordings=[];self.file_channel_count=0;self.data=reference_demo();self.source="Telegram_Demo_100_Parameters";self.selected=set(range(4));self.show_page(self.page)
    def do_export(self,headers,rows):
        from extra_ui import export_rows
        export_rows(self,headers,rows)
    def export_selected(self):
        if not self.permitted("Export data & reports"):return
        self.do_export(["Channel","Unit","Time unit","Time","Value"],((c.name,c.unit,c.time_unit,t,y) for i,c in enumerate(self.data) if i in self.selected for t,y in zip(c.t,c.y)))
    def lock(self):
        self.idle.stop()
        for dlg in self.findChildren(Q.QDialog):
            if dlg.isVisible():dlg.reject()
        self.audit("Sign out");self.hide();self.recordings=[];self.file_channel_count=0;self.data=reference_demo();self.source="Telegram_Demo_100_Parameters";self.selected=set(range(4));self.dataset_changed()
        dlg=Login(self.store,self)
        if dlg.exec()!=Q.QDialog.DialogCode.Accepted:self.close();return
        self.session=dlg.session;self.last_activity=time.monotonic();self.apply_role();self.show_page(0);self.show();self.idle.start(30000)
    def show_page(self,i):
        if i in (6,7) and not self.permitted("Advanced diagnostics"):return
        self.dataset_changed();self.page=i;self.title.setText(TITLES[i]);self.badge.setText(f"{'SIMULATED DATA' if self.source=='Telegram_Demo_100_Parameters' else self.source} · {len(self.data)} CHANNELS")
        for j,b in enumerate(self.nav):b.setChecked(i==j)
        old=self.scroll.takeWidget()
        if old:old.setParent(None)
        if i not in self.pages or i in self.dirty:
            if i in self.pages:self.pages[i].deleteLater()
            w=Q.QWidget();w.setObjectName("page");v=Q.QVBoxLayout(w);v.setContentsMargins(0,0,2,25);v.setSpacing(17)
            [self.overview,self.explorer,self.trends,self.statistics,self.thresholds,self.comparison,self.engineering,self.advanced,self.reports][i](v);v.addStretch();self.pages[i]=w;self.dirty.discard(i)
        self.scroll.setWidget(self.pages[i]);self.refresh_page_theme();self.reflow_page();self.layout_timer.start();self.scroll.verticalScrollBar().setValue(0);self.audit("Navigate",PAGES[i])
    def span(self):
        if not all(c.time_unit=="s" for c in self.data):return "Sample index"
        return f"{max((c.t[-1]-c.t[0] for c in self.data if len(c.t)),default=0):.3f} s"
    def overview(self,v):
        h,hl=frame("hero",36);h.setMinimumHeight(310);v.addWidget(h);r=row();hl.addLayout(r);left=Q.QVBoxLayout();left.setSpacing(10);r.addLayout(left,5);left.addWidget(label("ENGINEERING INTELLIGENCE / WORKSPACE 01","micro"));left.addWidget(label("From recorded signals","heroTitle"));left.addWidget(label("to clear decisions.","heroAccent"));left.addWidget(label("Explore the complete dataset, inspect operating behavior and move directly into the analysis that matters.","sub"));actions=row();left.addLayout(actions);actions.addWidget(btn("Explore signal trends ↗",lambda:self.show_page(2),"primary"));actions.addWidget(btn("View all statistics →",lambda:self.show_page(3)));actions.addStretch();r.addWidget(Orbit(),3)
        kpis(v,[("Channels discovered",len(self.data),"Available for analysis"),("Samples per channel",max(map(lambda c:len(c.y),self.data)),"Maximum imported observations"),("Recording span",self.span(),"Available time coverage"),("Active selection",len(self.selected),"Signals in trend workspace")])
        bottom=row();v.addLayout(bottom);w,l=frame();bottom.addWidget(w,3);l.addWidget(label("SIGNAL PREVIEW","micro"));rr=row();l.addLayout(rr);rr.addWidget(label("Recording at a glance","section"),1);rr.addWidget(btn("Full trend workspace ↗",lambda:self.show_page(2)));p=plot(310);l.addWidget(p);self.trend_plot(p,sorted(self.selected)[:4],100,0,preview=True)
        w,l=frame();bottom.addWidget(w,2);l.addWidget(label("YOUR ANALYSIS TOOLS","micro"));l.addWidget(label("Choose an investigation","heading"));l.addWidget(label("Go straight from an observation to the right engineering tool.","sub"));g=theme.mark_grid(Q.QGridLayout(),2,180);l.addLayout(g)
        for k,(name,desc,i) in enumerate([("▤  Channel explorer","Browse all signals →",1),("▥  Statistical analysis","All-channel table →",3),("⚑  Limit investigation","Find excursions →",4),("⇄  Signal comparison","Compare behavior →",5)]):
            b=btn(name+"\n\n"+desc,lambda checked=False,i=i:self.show_page(i),"tool");b.setMinimumHeight(94);g.addWidget(b,k//2,k%2)
        w,l=frame();v.addWidget(w);l.addWidget(label("CURRENT ANALYSIS SESSION","micro"));card_title(l,"Dataset information");l.addWidget(label(f"DATASET NAME    {self.source}     ·     RECORDING SPAN    {self.span()}     ·     CHANNELS    {len(self.data)}","sub"))
    def explorer(self,v):
        top=row();v.addLayout(top);top.addWidget(label("Channel Library","section"),1);search=Q.QLineEdit();search.setPlaceholderText("Search name or index…");top.addWidget(search);select=btn("Select filtered",lambda:bulk(True));clear=btn("Clear selection",lambda:bulk(False));top.addWidget(select);top.addWidget(clear);top.addWidget(btn("Channel properties",lambda:properties()))
        nums=kpis(v,[("All channels",len(self.data)),("Selected",len(self.selected)),("Numeric",len(self.data)),("Current source","Demo" if self.source.startswith("Telegram_Demo") else "Imported")])
        w,l=frame();v.addWidget(w);t=table([],[]);t.setMinimumHeight(500);t.verticalHeader().hide();l.addWidget(t);shown=[]
        def refresh(*_):
            q=search.text().casefold();shown[:]=[i for i,c in enumerate(self.data) if q in f"{i} {c.name}".casefold()]
            t.blockSignals(True)
            try:
                fill(t,["Display","Index","Channel name","Samples","Minimum","Maximum","Status"],[["",i,self.data[i].name,self.stats_for(i)["Valid"],self.stats_for(i).get("Min","—"),self.stats_for(i).get("Max","—"),"Numeric"] for i in shown])
                for r,i in enumerate(shown[:10000]):
                    it=t.item(r,0);it.setFlags(it.flags()|C.Qt.ItemFlag.ItemIsUserCheckable);it.setCheckState(C.Qt.CheckState.Checked if i in self.selected else C.Qt.CheckState.Unchecked);it.setData(C.Qt.ItemDataRole.UserRole,i)
                t.horizontalHeader().setSectionResizeMode(2,Q.QHeaderView.ResizeMode.Stretch)
            finally:t.blockSignals(False)
        def changed(it):
            if it.column()!=0:return
            i=it.data(C.Qt.ItemDataRole.UserRole)
            if i is None:return
            if it.checkState()==C.Qt.CheckState.Checked:self.selected.add(i)
            else:self.selected.discard(i)
            nums[1].setText(str(len(self.selected)));self.selection_changed()
        def bulk(on):
            if on:self.selected.update(shown)
            else:self.selected.clear()
            nums[1].setText(str(len(self.selected)));self.selection_changed();refresh()
        def properties():
            r=t.currentRow()
            if r<0 or r>=len(shown):return
            c=self.data[shown[r]];dlg=Q.QDialog(self);dlg.setWindowTitle("Channel properties");dlg.resize(740,480);layout=Q.QVBoxLayout(dlg)
            layout.addWidget(label(c.name,"heading"))
            values=[("Unit",c.unit or "Unspecified"),("Samples",len(c.y)),("Time unit",c.time_unit),("Time source",c.metadata.get("time_source","Imported or generated")),("Clock origin",c.metadata.get("clock_id","Unspecified"))]
            values.extend(c.metadata.get("properties",{}).items())
            table_card(layout,"Channel metadata",["Property","Value"],values,300);layout.addWidget(btn("Close",dlg.accept));dlg.exec()
        t.itemChanged.connect(changed);search.textChanged.connect(refresh);refresh()
    def channel_browser(self):
        dlg=Q.QDialog(self);dlg.setWindowTitle("Choose channels to visualize");dlg.resize(1050,760);l=Q.QVBoxLayout(dlg);l.setContentsMargins(25,25,25,25);l.setSpacing(14)
        l.addWidget(label("SIGNAL LIBRARY / SEPARATE WORKSPACE","micro"));l.addWidget(label("Choose channels to visualize","heading"));l.addWidget(label("Browse the entire dataset without reducing the graph display area.","sub"))
        summary=label("","status");l.addWidget(summary);bar=row();l.addLayout(bar);search=Q.QLineEdit();search.setPlaceholderText("⌕ Search among all parameters");bar.addWidget(search,1);bar.addWidget(btn("Select first 12",lambda:bulk(True)));bar.addWidget(btn("Clear traces",lambda:bulk(False)))
        sc=Q.QScrollArea();sc.setWidgetResizable(True);l.addWidget(sc,1)
        def sync():summary.setText(f"● All channels: {len(self.data)}    ● Active: {len(self.selected)}")
        def changed(i,on):
            if on:self.selected.add(i)
            else:self.selected.discard(i)
            sync();self.selection_changed()
        def refresh(*_):
            w=Q.QWidget();g=Q.QGridLayout(w);g.setAlignment(C.Qt.AlignmentFlag.AlignTop);g.setSpacing(10);j=0
            for i,c in enumerate(self.data):
                if search.text().casefold() not in f"{i} {c.name}".casefold():continue
                card,cl=frame("toolbar",12);ck=Q.QCheckBox(c.name);ck.setChecked(i in self.selected);ck.toggled.connect(lambda on,i=i:changed(i,on));cl.addWidget(ck);cl.addWidget(label(f"Index {i} · {len(c.y)} samples","sub"));g.addWidget(card,j//3,j%3);j+=1
            sc.setWidget(w);sync()
        def bulk(on):
            self.selected=set(range(min(12,len(self.data)))) if on else set();self.selection_changed();refresh()
        search.textChanged.connect(refresh);refresh();l.addWidget(label("The first six selected channels appear above and the next six below. Additional selected signals remain available for export.","sub"));l.addWidget(btn("✓ Return to signal trends",dlg.accept,"primary"));dlg.exec()
    def trend_data(self,ids,pct,pos,raw=False,preview=False):
        curves=[];cols=[];mixed=len({self.data[i].time_unit for i in ids})>1
        selected_colors={i:j for j,i in enumerate(sorted(self.selected))}
        for i in ids:
            c=self.data[i];n=max(1,round(len(c.y)*pct/100));start=round(max(0,len(c.y)-n)*pos/100);y=c.y[start:start+n];x=np.arange(start,start+len(y)) if mixed else c.t[start:start+n]
            if raw:z=y
            else:
                good=y[np.isfinite(y)]
                if not len(good):z=np.full(len(y),np.nan)
                else:z=(y-good.min())*100/(np.ptp(good) or 1)
            if preview:
                ix=preview_indices(z);x=x[ix];z=z[ix]
            curves.append((x,z,c.name+(f' ({c.unit})' if raw and c.unit else '')));cols.append(self.colors.get(i,PALETTE[selected_colors[i]%len(PALETTE)]))
        return curves,cols,("Sample index (mixed time bases)" if mixed else ("Time (s)" if ids and self.data[ids[0]].time_unit=="s" else "Sample index"))
    def trend_plot(self,p,ids,pct,pos,raw=False,preview=False):
        curves,cols,xlabel=self.trend_data(ids,pct,pos,raw,preview);draw(p,curves,cols)
        units={self.data[i].unit or "unspecified" for i in ids}
        p.setLabel("left",(" / ".join(sorted(units)) if len(units)==1 else "Raw value (mixed units)") if raw else "Normalized (%)")
        p.setLabel("bottom",xlabel)
        if not raw:p.setYRange(0,100,padding=.03)
    def trends(self,v):
        h=row();v.addLayout(h);left=Q.QVBoxLayout();left.addWidget(label("WORKSPACE 03 / SIGNAL INVESTIGATION","micro"));left.addWidget(label("Signal Analysis Studio   ·   IMMERSIVE V7","heading"));left.addWidget(label("An expansive signal canvas with synchronized investigation panels.","sub"));h.addLayout(left,1)
        def browse():
            self.channel_browser();redraw();trace_table()
        def restore():
            self.selected=set(range(min(4,len(self.data))));self.selection_changed();redraw();trace_table()
        h.addWidget(btn(f"☷ Browse {len(self.data)} channels ↗",browse,"primary"));h.addWidget(btn("↺ Restore four traces",restore));nums=kpis(v,[("Available signals",len(self.data)),("Active traces",len(self.selected)),("Visible samples",max(len(c.y) for c in self.data)),("Time window","Full")])
        bar,bl=frame("toolbar");v.addWidget(bar);rr=row();bl.addLayout(rr);width=field(rr,"WINDOW WIDTH",combo(["Full recording","50% of recording","25% of recording","10% of recording"]));pos=Q.QSlider(C.Qt.Orientation.Horizontal);pos.setRange(0,100);field(rr,"MOVE THROUGH RECORDING",pos);mode=field(rr,"CHART ARRANGEMENT",combo(["Two synchronized panels","One large panel"]));rr.addWidget(btn("↓ Export selected CSV / Excel",self.export_selected,"primary"))
        extra=row();bl.addLayout(extra);scale=field(extra,"Y-AXIS SCALE",combo(["Normalized (%)","Raw engineering values"]));dual=Q.QCheckBox("Dual measurement cursors");extra.addWidget(dual);extra.addStretch()
        extra.addWidget(btn("A/B range statistics",lambda:interval_stats()));extra.addWidget(btn("Export A/B range",lambda:interval_export()))
        wa,la=frame();v.addWidget(wa);la.addWidget(label("PANEL A / PRIMARY SIGNALS","micro"));card_title(la,"Operating signal trends");p1=plot(420);la.addWidget(p1);read1=label("Hover over the graph to inspect values at the cursor.","status");la.addWidget(read1)
        wb,lb=frame();v.addWidget(wb);lb.addWidget(label("PANEL B / ADDITIONAL SIGNALS","micro"));card_title(lb,"Secondary signal trends");p2=plot(355);lb.addWidget(p2);read2=label("Hover over this graph to inspect secondary signals.","status");lb.addWidget(read2);p2.setXLink(p1)
        measurements=table_card(v,"A/B Cursor Measurements — panel A",["Signal","Unit","Δ time / samples","A value","B value","Δ value"],[],160)
        measurements.parentWidget().hide()
        cursor_lines=[pg.InfiniteLine(angle=90,movable=True,pen=pg.mkPen(theme.trace_color("#ffbe67"),width=2),label="A",labelOpts={"color":theme.colors()["text"]}),pg.InfiniteLine(angle=90,movable=True,pen=pg.mkPen(theme.trace_color("#58e0e0"),width=2),label="B",labelOpts={"color":theme.colors()["text"]})]
        tw,tl=frame();v.addWidget(tw);tl.addWidget(label("TRACE MANAGEMENT","micro"));card_title(tl,"Active channels & signal ranges");tt=table([],[]);tt.setMinimumHeight(200);tl.addWidget(tt)
        def ids():return sorted(self.selected)[:12]
        def redraw(*_):
            pct=[100,50,25,10][width.currentIndex()];split=mode.currentIndex()==0;ss=ids();a=ss[:6] if split else ss;b=ss[6:] if split else []
            raw=scale.currentIndex()==1
            self.trend_plot(p1,a,pct,pos.value(),raw);self.trend_plot(p2,b,pct,pos.value(),raw);wb.setVisible(split)
            bases={(self.data[i].time_unit,self.data[i].metadata.get("clock_id")) for i in ss}
            p2.setXLink(p1 if len(bases)<=1 else None)
            if dual.isChecked() and a:
                p1.getPlotItem().vb.updateAutoRange();xr=p1.viewRange()[0]
                for f,line in zip((.25,.75),cursor_lines):
                    p1.addItem(line,ignoreBounds=True);line.setValue(xr[0]+f*(xr[1]-xr[0]))
            update_measurements()
            nums[1].setText(str(len(self.selected)));nums[2].setText(str(round(max((len(self.data[i].y) for i in ss),default=0)*pct/100)));nums[3].setText(f"{pct}% · {pos.value()}%")
        def update_measurements(*_):
            measurements.parentWidget().setVisible(dual.isChecked())
            if not dual.isChecked():return
            ss=ids();ss=ss[:6] if mode.currentIndex()==0 else ss
            mixed=len({self.data[i].time_unit for i in ss})>1
            rows=[]
            for i in ss:
                c=self.data[i];a=cursor_lines[0].value();b=cursor_lines[1].value()
                if mixed:
                    if 0<=a<len(c.y) and 0<=b<len(c.y):
                        j=min(len(c.y)-1,int(round(a)));k=min(len(c.y)-1,int(round(b)));m=(k-j,c.y[j],c.y[k],c.y[k]-c.y[j])
                    else:m=None
                else:m=cursor_measurement(c.t,c.y,a,b,c.time_ordered)
                rows.append([c.name,c.unit,*m] if m else [c.name,c.unit,"—","—","—","—"])
            fill(measurements,["Signal","Unit","Δ time / samples","A value","B value","Δ value"],rows)
        def interval_channels():
            if not dual.isChecked():raise ValueError("Enable A/B cursors first")
            ss=ids();ss=ss[:6] if mode.currentIndex()==0 else ss
            mixed=len({self.data[i].time_unit for i in ss})>1
            lo,hi=sorted(line.value() for line in cursor_lines)
            for i in ss:
                c=self.data[i]
                if mixed:
                    a=max(0,int(np.ceil(lo)));b=min(len(c.y),int(np.floor(hi))+1);ix=slice(a,max(a,b))
                elif c.time_ordered:ix=slice(np.searchsorted(c.t,lo,"left"),np.searchsorted(c.t,hi,"right"))
                else:ix=(c.t>=lo)&(c.t<=hi)
                yield c,c.t[ix],c.y[ix]
        def interval_stats():
            from extra_ui import job,warn
            try:
                intervals=list(interval_channels());rows=job(self,"Cursor-range statistics",lambda stop:[(c.name,c.unit,*[d.get(k,"—") for k in ("Valid","Min","Max","Mean","RMS")]) for c,t,y in intervals for d in [describe(y)]])
                d=Q.QDialog(self);d.resize(950,400);d.setWindowTitle("Cursor-range statistics");l=Q.QVBoxLayout(d);table_card(l,"Full-resolution samples within A/B",["Signal","Unit","Valid","Min","Max","Mean","RMS"],rows,250);l.addWidget(btn("Close",d.accept));d.exec()
            except Exception as exc:warn(self,"Cursor range",exc)
        def interval_export():
            if not self.permitted("Export data & reports"):return
            try:
                # Snapshot GUI state on the GUI thread, not from the export worker.
                intervals=list(interval_channels())
                self.do_export(["Signal","Unit","Time unit","Time","Value"],((c.name,c.unit,c.time_unit,t,y) for c,ts,ys in intervals for t,y in zip(ts,ys)))
            except ValueError as exc:Q.QMessageBox.warning(self,"Cursor range",str(exc))
        for line in cursor_lines:line.sigPositionChanged.connect(update_measurements)
        def color(i):
            col=Q.QColorDialog.getColor(G.QColor(self.colors.get(i,PALETTE[sorted(self.selected).index(i)%len(PALETTE)])),self)
            if col.isValid():self.colors[i]=col.name();redraw();trace_table()
        def remove(i):
            self.selected.discard(i);self.selection_changed();redraw();trace_table()
        def trace_table():
            ss=sorted(self.selected);fill(tt,["Signal","Color","Minimum","Maximum","Action"],[[self.data[i].name,"",self.stats_for(i).get("Min","—"),self.stats_for(i).get("Max","—"),""] for i in ss])
            for j,i in enumerate(ss[:10000]):
                b=btn("Color",lambda checked=False,i=i:color(i));swatch=self.colors.get(i,PALETTE[j%len(PALETTE)]);b.setStyleSheet("background:"+swatch+";color:"+theme.contrasting_text(swatch)+";");tt.setCellWidget(j,1,b);tt.setCellWidget(j,4,btn("Remove",lambda checked=False,i=i:remove(i)))
        def cursor(p,out,second):
            def move(point):
                if not p.getPlotItem().sceneBoundingRect().contains(point):return
                x=p.getPlotItem().vb.mapSceneToView(point).x();ss=ids();ss=ss[6:] if second else (ss[:6] if mode.currentIndex()==0 else ss);mixed=len({self.data[i].time_unit for i in ss})>1;values=[]
                for i in ss:
                    c=self.data[i]
                    if not len(c.y):continue
                    k=(int(round(x)) if 0<=x<=len(c.y)-1 else None) if mixed else nearest_index(c.t,x,c.time_ordered)
                    if k is not None:values.append(f"{c.name}: {fmt(c.y[k])} {c.unit}")
                out.setText(f"Cursor {x:.3f}  |  "+"   ·   ".join(values))
            p.scene().sigMouseMoved.connect(move)
        cursor(p1,read1,False);cursor(p2,read2,True);width.currentIndexChanged.connect(redraw);timer=C.QTimer(wb);timer.setSingleShot(True);timer.setInterval(85);timer.timeout.connect(redraw)
        pos.valueChanged.connect(lambda _:timer.start());mode.currentIndexChanged.connect(redraw);scale.currentIndexChanged.connect(redraw);dual.toggled.connect(redraw);redraw();trace_table()
    def tabs(self,parent,names,factory,columns=5):
        bar=theme.mark_grid(Q.QGridLayout(),columns,175);parent.addLayout(bar);bar.setSpacing(8);stack=theme.ResponsiveStack();parent.addWidget(stack);buttons=[];pages=[]
        def activate(i):
            stack.setCurrentIndex(i)
            for j,b in enumerate(buttons):b.setChecked(j==i)
            # QStackedWidget normally sizes to its largest child; size to selected pane.
            for j,w in enumerate(pages):w.setSizePolicy(Q.QSizePolicy.Policy.Preferred if j==i else Q.QSizePolicy.Policy.Ignored,Q.QSizePolicy.Policy.Preferred if j==i else Q.QSizePolicy.Policy.Ignored)
            theme.reflow(pages[i].layout(),max(300,self.scroll.viewport().width()-32));stack.updateGeometry()
            self.refresh_page_theme()
            self.layout_timer.start()
        for i,n in enumerate(names):
            b=btn(n,lambda checked=False,i=i:activate(i),"tab");b.setCheckable(True);bar.addWidget(b,i//columns,i%columns);buttons.append(b);w=factory(n);pages.append(w);stack.addWidget(w)
        activate(0);return stack
    def statistics(self,v):
        w,l=frame();v.addWidget(w);top=row();l.addLayout(top);top.addWidget(label("All-Parameter Statistical Analysis","section"),1);headers=["Index","Parameter","Valid","Min","Max","Mean","Median","RMS","Std Dev","Peak-to-Peak"]
        def get_rows():
            return [[i,c.name]+[self.stats_for(i).get(k,"—") for k in headers[2:]] for i,c in enumerate(self.data)]
        top.addWidget(btn("Export All Statistics CSV",lambda:self.do_export(headers,get_rows())));search=Q.QLineEdit();search.setPlaceholderText("Search parameter name or index…");l.addWidget(search);tbl=table(headers,[]);tbl.setMinimumHeight(350);l.addWidget(tbl);visible=[]
        def refresh(*_):
            q=search.text().casefold();visible[:]=[r for r in get_rows() if q in f"{r[0]} {r[1]}".casefold()];fill(tbl,headers,visible)
        detail,dl=frame();v.addWidget(detail);dl.addWidget(label("SELECTED PARAMETER · DESCRIPTIVE STATISTICS","micro"));sel=combo(self.names());dl.addWidget(sel);nums=kpis(dl,[(x,"—") for x in ("Min","Max","Mean","Median","RMS","Std Dev","Peak-to-Peak","Valid")]);charts=row();dl.addLayout(charts);_,hist=chart(charts,"Distribution of Selected Parameter",290);dt=table_card(charts,"Detailed Descriptive Statistics",["Measure","Result"],[],290)
        deep,dd=frame("hero");v.addWidget(deep);dd.addWidget(label("STATISTICAL INVESTIGATION / V11","micro"));dd.addWidget(label("Deep Statistics Workstation","heading"));dd.addWidget(label("Full-dataset table above · detailed investigation of the selected channel below","sub"))
        controls,cl=frame("toolbar");v.addWidget(controls);r=row();cl.addLayout(r);start=field(r,"ANALYSIS START (%)",number(0,0,99,1,True));end=field(r,"ANALYSIS END (%)",number(100,1,100,1,True));roll=field(r,"ROLLING WINDOW",number(25,3,250,1,True));bins=field(r,"HISTOGRAM BINS",number(24,5,80,1,True));r.addWidget(btn("↻ Recalculate",lambda:recalc(),"primary"));r.addWidget(btn("↓ Export detailed statistics",lambda:save_details()))
        panes={}
        def factory(name):
            w=Q.QWidget();l=Q.QVBoxLayout(w);l.setContentsMargins(0,0,0,0);r=row();l.addLayout(r)
            titles={"Distribution & Percentiles":("Frequency Distribution","Empirical Cumulative Distribution"),"Rolling Statistics":("Raw Signal & Rolling Mean","Rolling Standard Deviation"),"Quality & Outliers":("Outlier Map · Tukey IQR","Data Quality Breakdown"),"Segment Comparison":("First Half vs Second Half","Segment Measurements")}[name]
            _,p=chart(r,titles[0],280)
            if name in ("Quality & Outliers","Segment Comparison"):p2=None;t=table_card(r,titles[1],[],[],280)
            else:_,p2=chart(r,titles[1],280);t=table_card(l,"Complete descriptive measurements" if name.startswith("Distribution") else "Rolling measurements",[],[],180)
            panes[name]=(p,p2,t);return w
        self.tabs(v,["Distribution & Percentiles","Rolling Statistics","Quality & Outliers","Segment Comparison"],factory,4);status=label("","status");v.addWidget(status);last=[]
        def recalc(*_):
            i=sel.currentIndex();c=self.data[i];d=self.stats_for(i)
            for n,k in zip(nums,("Min","Max","Mean","Median","RMS","Std Dev","Peak-to-Peak","Valid")):n.setText(fmt(d.get(k,"—")))
            finite=c.y[np.isfinite(c.y)];fill(dt,["Measure","Result"],list(d.items()))
            if len(finite):
                h,e=np.histogram(finite,bins=24);draw(hist,[((e[:-1]+e[1:])/2,h,"Histogram")])
            else:hist.clear()
            if start.value()>=end.value():status.setText("Start must be less than end.");last.clear();return
            a=int(len(c.y)*start.value()/100);b=max(a+1,int(np.ceil(len(c.y)*end.value()/100)));cc=Channel(c.name,c.y[a:b],c.t[a:b],c.unit,c.time_unit);y=cc.y;t=cc.t;good=y[np.isfinite(y)];d=describe(y);last[:]=list(d.items())
            try:
                curves,_,_=analyze("Statistics",cc,p=bins.value());p,p2,tab=panes["Distribution & Percentiles"];draw(p,curves[:1]);draw(p2,curves[1:]);fill(tab,["Measure","Result"],last)
                curves,_,_=analyze("Rolling Statistics",cc,p=roll.value());p,p2,tab=panes["Rolling Statistics"];draw(p,curves[:2]);draw(p2,curves[2:]);fill(tab,["Window","Samples"],[["Trailing window",roll.value()]])
                curves,_,rows=analyze("Quality & Outliers",cc,p=1.5);p,_,tab=panes["Quality & Outliers"];draw(p,curves);fill(tab,["Check","Result"],[("Valid",len(good)),("Missing/nonfinite",len(y)-len(good)),("IQR flags",len(rows))])
                p,_,tab=panes["Segment Comparison"];mid=len(y)//2;draw(p,[(t[:mid],y[:mid],"First half"),(t[mid:],y[mid:],"Second half")]);d1=describe(y[:mid]);d2=describe(y[mid:]);fill(tab,["Measure","First half","Second half","Difference"],[(k,d1[k],d2[k],d2[k]-d1[k]) for k in d1 if k in d2]);status.setText(f"Analysis window: {start.value()}–{end.value()}% · {len(y)} samples · exploratory statistics")
            except ValueError as exc:
                for p,p2,tab in panes.values():
                    p.clear()
                    if p2:p2.clear()
                    fill(tab,[],[])
                status.setText(str(exc));last.clear()
        def save_details():
            if last:self.do_export(["Measure","Result"],last)
        def pick(r,c):
            if r<len(visible):sel.setCurrentIndex(visible[r][0])
        tbl.cellClicked.connect(pick);search.textChanged.connect(refresh);sel.currentIndexChanged.connect(recalc);refresh();recalc()
    def thresholds(self,v):
        r=row();v.addLayout(r);w,l=frame();r.addWidget(w,1);card_title(l,"Threshold Configuration","Analyze selected channel values against inclusive user-configured low and high limits.");sel=combo(self.names());l.addWidget(sel);rr=row();l.addLayout(rr);lo=field(rr,"LOWER LIMIT",number(0));hi=field(rr,"UPPER LIMIT",number(1));rr.addWidget(btn("Run Analysis",lambda:run(),"primary"));status=label("Choose a signal and run threshold analysis.","status");l.addWidget(status)
        w,l=frame();r.addWidget(w,1);card_title(l,"Violation Summary");nums=kpis(l,[(x,"—") for x in ("Below limit","Above limit","Within limits","Missing")],2)
        records=table_card(v,"Violation Records (first 100)",["Sample","Time","Value","Type"],[],230)
        w,l=frame();v.addWidget(w);top=row();l.addLayout(top);top.addWidget(label("Limit Excursion Timeline & Event Groups","section"),1);last=[];top.addWidget(btn("Export event groups CSV",lambda:self.do_export(["Side","Start sample","End sample","Start","End","Duration","Peak violation"],last)));p=plot(280);l.addWidget(p);et=table([],[]);et.setMinimumHeight(250);l.addWidget(et)
        def defaults(*_):
            d=self.stats_for(sel.currentIndex());mn=d.get("Min",0);mx=d.get("Max",1);span=mx-mn;lo.setValue(mn+.1*span);hi.setValue(mx-.1*span if span else mx+1)
        def run():
            c=self.data[sel.currentIndex()];y=c.y;t=c.t;good=np.isfinite(y);low=lo.value();high=hi.value()
            if low>=high:status.setText("Lower limit must be less than upper limit.");return
            masks=[good&(y<low),good&(y>high)];bad=masks[0]|masks[1];last.clear()
            for side,m in zip(("Low","High"),masks):
                for a,b,ts,te,d in events(t,m):
                    peak=low-y[a:b+1].min() if side=="Low" else y[a:b+1].max()-high
                    last.append((side,a,b,ts,te,d,peak))
            last.sort(key=lambda z:z[1]);nums[0].setText(str(masks[0].sum()));nums[1].setText(str(masks[1].sum()));nums[2].setText(str((good&~bad).sum()));nums[3].setText(str((~good).sum()));status.setText(f"{bad.sum()} violations · {len(last)} grouped events · time base: {c.time_unit}")
            fill(records,["Sample","Time","Value","Type"],[(i,t[i],y[i],"Low" if y[i]<low else "High") for i in np.flatnonzero(bad)[:100]]);fill(et,["Side","Start sample","End sample","Start","End","Duration","Peak violation"],last);draw(p,[(t,y,c.name),(t,np.full(len(y),low),"Lower"),(t,np.full(len(y),high),"Upper"),(t[bad],y[bad],"Violations")])
        sel.currentIndexChanged.connect(defaults);defaults();run()
        if not self.session.allows("Modify analysis settings"):lo.setEnabled(False);hi.setEnabled(False)
    def comparison(self,v):
        w,l=frame();v.addWidget(w);bar=row();l.addLayout(bar);bar.addWidget(label("Two-Signal Comparison","section"),1);a=combo(self.names());b=combo(self.names(),1);bar.addWidget(a);bar.addWidget(label("vs","sub"));bar.addWidget(b);bar.addWidget(btn("Compare",lambda:run(),"primary"));p=plot(390);l.addWidget(p);nums=kpis(l,[(x,"—") for x in ("Pearson r","Slope","R squared")],3);status=label("","status");l.addWidget(status)
        def run():
            try:
                curves,m,_=analyze("Comparison",self.data[a.currentIndex()],self.data[b.currentIndex()]);draw(p,curves)
                for n,k in zip(nums,("Pearson r","Slope","R squared")):n.setText(fmt(m[k]))
                status.setText("Matched time bases. Correlation describes association, not causation.")
            except ValueError as exc:p.clear();status.setText(str(exc))
        w,l=frame();v.addWidget(w);top=row();l.addLayout(top);top.addWidget(label("Multi-Channel Correlation Matrix","section"),1);n=combo(["4","6","8"],1);top.addWidget(n);last=[[],[]];top.addWidget(btn("Calculate matrix",lambda:matrix(),"primary"));top.addWidget(btn("Export matrix CSV",lambda:self.do_export(*last)));mt=table([],[]);mt.setProperty("correlationTable",True);mt.setMinimumHeight(260);l.addWidget(mt);l.addWidget(label("Pairwise Pearson correlation uses aligned finite samples. Mismatched time bases are not automatically resampled.","sub"))
        def matrix():
            ids=sorted(self.selected)[:int(n.currentText())];headers=["Channel"]+[self.data[i].name for i in ids];rows=[]
            for i in ids:
                values=[self.data[i].name]
                for j in ids:
                    try:
                        x,y=paired(self.data[i],self.data[j]);m=np.isfinite(x)&np.isfinite(y);x=x[m];y=y[m];values.append(np.corrcoef(x,y)[0,1] if len(x)>1 and np.ptp(x)>0 and np.ptp(y)>0 else np.nan)
                    except ValueError:values.append(np.nan)
                rows.append(values)
            last[:]=[headers,rows];fill(mt,headers,rows)
            for i,rr in enumerate(rows):
                for j,value in enumerate(rr[1:],1):
                    if np.isfinite(value):
                        color=G.QColor.fromHsvF(.48 if value>=0 else .03,min(abs(value),1),.27+min(abs(value),1)*.25);mt.item(i,j).setBackground(color);mt.item(i,j).setForeground(G.QColor(theme.contrasting_text(color.name())))
        run();matrix()
    def engineering(self,v):
        w,l=frame("hero",26);v.addWidget(w);l.addWidget(label("WORKSPACE 09 / INDUSTRIAL INVESTIGATION","micro"));l.addWidget(label("Engineering Analysis Lab   ·   V9 / 5 WORKBENCHES","heading"));l.addWidget(label("One integrated investigation environment: distributions and outliers, process capability, operating states, signal relationships and rolling stability.","sub"));self.tabs(v,LAB,lambda name:AnalysisPane(self,name),5)
    def advanced(self,v):
        w,l=frame("hero",26);v.addWidget(w);r=row();l.addLayout(r);a=Q.QVBoxLayout();r.addLayout(a,1);a.addWidget(label("ENGINEERING LAB / NEXT-LEVEL ANALYSIS","micro"));a.addWidget(label("Advanced Signal Diagnostics   ·   V11 / 10 TOOLS","heading"));a.addWidget(label("Ten focused workbenches for signal integrity, frequency content, transients and channel relationships.","sub"));r.addWidget(btn("↗ Immersive Trend Studio",lambda:self.show_page(2),"primary"));self.tabs(v,ADV,lambda name:AnalysisPane(self,name),5)
    def reports(self,v):
        rr=row();v.addLayout(rr);w,l=frame();rr.addWidget(w,1);card_title(l,"Report Builder","Generate a concise engineering summary of the current dataset and selected signals.");bar=row();l.addLayout(bar);bar.addWidget(btn("Generate Summary",lambda:generate(),"primary"));bar.addWidget(btn("Download Report TXT",lambda:save()));l.addWidget(btn("Export Selected CSV / Excel",self.export_selected));l.addWidget(btn("Download PDF report",lambda:save_pdf()));l.addWidget(label("Export is generated locally on this desktop. No data is uploaded to a server.","status"))
        w,l=frame();rr.addWidget(w,1);card_title(l,"Export Contents")
        for name,val in [("Source and channel count","Included"),("Selected signal statistics","Included"),("Time range and sample count","Included"),("CSV measurement data","Separate")]:
            r=row();r.addWidget(label(name,"sub"),1);r.addWidget(label(val));l.addLayout(r)
        w,l=frame();v.addWidget(w);card_title(l,"Engineering Analysis Report");edit=Q.QPlainTextEdit();edit.setReadOnly(True);edit.setMinimumHeight(350);edit.setPlainText("Click Generate Summary to create a report from the current dataset.");l.addWidget(edit);generated=False
        def generate():
            nonlocal generated
            if not self.permitted("Export data & reports"):return
            lines=["ENGINEERING ANALYSIS REPORT",f"Dataset: {self.source}",f"Channels: {len(self.data)}",f"Recording span: {self.span()}",""]
            for i in sorted(self.selected):
                c=self.data[i];lines.append(f"{c.name} · {c.unit} · {len(c.y)} samples");lines.extend(f"  {k}: {fmt(x)}" for k,x in self.stats_for(i).items());lines.append("")
            edit.setPlainText("\n".join(lines));generated=True
        def save_pdf():
            from extra_ui import pdf_report
            if not generated:generate()
            if generated:pdf_report(self,edit.toPlainText())
        def save():
            if not self.permitted("Export data & reports") or not generated:return
            path,_=Q.QFileDialog.getSaveFileName(self,"Save report","","Text (*.txt)")
            if path:
                try:Path(path).write_text(edit.toPlainText(),encoding="utf-8");self.audit("Report exported")
                except OSError as exc:Q.QMessageBox.warning(self,"Export failed",str(exc))
    def account(self):
        dlg=Q.QDialog(self);dlg.resize(1050,720);dlg.setWindowTitle("Workspace Security Center");l=Q.QVBoxLayout(dlg);l.setContentsMargins(25,25,25,25);l.addWidget(label("IDENTITY & ACCESS","micro"));l.addWidget(label("Workspace Security Center","heading"));l.addWidget(label(self.session.username+" · "+self.session.role,"sub"));l.addWidget(label("Local security: passwords are salted and hashed. Audit records are not tamper-proof. Protect the application-data directory using OS access controls.","status"))
        tabs=Q.QTabWidget();l.addWidget(tabs,1)
        u=Q.QWidget();ul=Q.QVBoxLayout(u);tabs.addTab(u,"Users & Roles");t=table_card(ul,"Registered Users",["Username","Role","Status"],[],250)
        def refresh():
            fill(t,["Username","Role","Status"],[(n,r,"Active" if e else "Disabled") for n,r,e in self.store.users(self.session)])
        if self.permitted("Manage users"):
            w,wl=frame();ul.addWidget(w);card_title(wl,"Create a user");name=Q.QLineEdit();name.setMaxLength(40);pw=password();role=combo(list(ROLES),1);r=row();wl.addLayout(r);field(r,"USERNAME",name);field(r,"TEMPORARY PASSWORD (12+)",pw);field(r,"ACCESS ROLE",role)
            def create():
                try:self.store.create(self.session,name.text().strip(),pw.text(),role.currentText());name.clear();pw.clear();refresh()
                except (ValueError,PermissionError) as exc:Q.QMessageBox.warning(dlg,"Account",str(exc))
            def toggle():
                if t.currentRow()<0:return
                try:self.store.toggle(self.session,t.item(t.currentRow(),0).text());refresh()
                except (ValueError,PermissionError) as exc:Q.QMessageBox.warning(dlg,"Account",str(exc))
            r.addWidget(btn("＋ Create user",create,"primary"));ul.addWidget(btn("Enable / Disable selected user",toggle))
        refresh()
        if self.permitted("Manage users"):
            w=Q.QWidget();wl=Q.QVBoxLayout(w);table_card(wl,"Permission Matrix",["Function",*ROLES],[(key,*["✓" if x else "—" for x in values]) for key,values in MATRIX.items()],300);tabs.addTab(w,"Permission Matrix")
        if self.permitted("View audit history"):
            w=Q.QWidget();wl=Q.QVBoxLayout(w);headers=["Time","User","Action","Details"];history=self.store.history(self.session);table_card(wl,"Latest 300 audit events",headers,history,320);wl.addWidget(btn("↓ Export audit CSV",lambda:self.do_export(headers,self.store.history(self.session))));tabs.addTab(w,"Audit History")
        if not self.session.demo:
            w=Q.QWidget();wl=Q.QVBoxLayout(w);card_title(wl,"Change my password");old=password();new=password();confirm=password()
            for title,x in [("Current password",old),("New password (12+)",new),("Confirm password",confirm)]:wl.addWidget(label(title,"sub"));wl.addWidget(x)
            def change():
                try:
                    if new.text()!=confirm.text():raise ValueError("Passwords do not match.")
                    self.store.change(self.session,old.text(),new.text());old.clear();new.clear();confirm.clear();Q.QMessageBox.information(dlg,"Account","Password updated.")
                except (ValueError,PermissionError) as exc:Q.QMessageBox.warning(dlg,"Account",str(exc))
            wl.addWidget(btn("Update password",change,"primary"));wl.addStretch();tabs.addTab(w,"My Password")
        l.addWidget(btn("✕ Close",dlg.accept));dlg.exec()

CHART_TITLES={
"Distribution":("Histogram · frequency distribution","Box & whisker · quartiles / fences"),
"Process Capability":("Distribution against specification limits","Process trend · LSL / target / USL"),
"State & Events":("Operating state timeline · threshold crossings",),
"Relationships":("XY scatter · least-squares regression","Residuals · prediction error"),
"Stability & SPC":("Individual values · center line / control limits","Rolling mean and rolling standard deviation"),
"Frequency Spectrum":("Amplitude spectrum",),
"Signal Conditioning":("Signal conditioning workspace",),
"Anomaly Detection":("Detected event timeline",),
"Lag & Correlation":("Cross-correlation by sample lag",),
"Data Quality":("Data Quality & Integrity — primary view","Diagnostic detail"),
"Transients":("Transient & Step Response — primary view","Diagnostic detail"),
"Envelope & Peaks":("Envelope, Peaks & Excursions — primary view","Diagnostic detail"),
"Autocorrelation":("Autocorrelation & Periodicity — primary view","Diagnostic detail"),
"Band Energy":("Spectral Band Energy — primary view","Diagnostic detail"),
"Change Detection":("Baseline Shift & Change Detection — primary view","Diagnostic detail"),
}
RESULT_TITLES={"Distribution":"Detailed distribution statistics","Process Capability":"Capability and compliance breakdown","State & Events":"Transitions, durations and event records","Relationships":"Regression and association metrics","Stability & SPC":"Control limit violations and drift candidates"}
RUN_NAMES={"Distribution":"Calculate distribution","Process Capability":"Analyze capability","State & Events":"Extract operating states","Relationships":"Analyze relationship","Stability & SPC":"Evaluate stability","Frequency Spectrum":"Analyze spectrum","Signal Conditioning":"Apply processing","Anomaly Detection":"Detect unusual samples","Lag & Correlation":"Calculate lag"}
class AnalysisPane(Q.QWidget):
    def __init__(self,app,tool):
        super().__init__();self.app=app;self.tool=tool;self.rows=[];self.headers=[];self.params=[];v=Q.QVBoxLayout(self);v.setContentsMargins(0,4,0,0);v.setSpacing(15)
        w,l=frame("toolbar");v.addWidget(w);bar=theme.mark_grid(Q.QGridLayout(),4,185);bar.setSpacing(12);l.addLayout(bar)
        def control(title,widget):
            box=Q.QWidget();col=Q.QVBoxLayout(box);col.setContentsMargins(0,0,0,0);col.setSpacing(6);col.addWidget(label(title,"micro"));col.addWidget(widget);i=bar.count();bar.addWidget(box,i//4,i%4);return widget
        self.a=control("X / REFERENCE CHANNEL" if tool=="Relationships" else "ANALYSIS CHANNEL",combo(app.names()));self.b=combo(app.names(),1)
        if tool in ("Relationships","Lag & Correlation"):control("Y / RESPONSE CHANNEL",self.b)
        for i,(n,d) in enumerate(PARAM.get(tool,[])):
            if tool=="Frequency Spectrum":
                x=combo(["256 samples","512 samples","1024 samples","2048 samples"],1) if i==0 else combo(["Hann (recommended)","Rectangular"])
            elif tool=="Signal Conditioning" and i==1:x=combo(["Original + smoothed","Rate of change (per second)"])
            else:x=number(d)
            self.params.append(control(n.upper(),x))
        if tool=="Distribution":self.params.append(control("IQR OUTLIER FACTOR",number(1.5,.5,5,.5)))
        if tool=="Relationships":self.params.append(control("RESPONSE LAG (SAMPLES)",number(0,-100,100,1,True)))
        for p in self.params:p.setEnabled(app.session.allows("Modify analysis settings"))
        actions=row();l.addLayout(actions);actions.addWidget(btn(RUN_NAMES.get(tool,"Run diagnostics"),self.run,"primary"));actions.addWidget(btn("Export results CSV",lambda:app.do_export(self.headers,self.rows)));actions.addStretch(1)
        self.status=label("Choose a channel to begin the investigation.","status");v.addWidget(self.status);self.metrics=Q.QWidget();self.ml=theme.mark_grid(Q.QGridLayout(self.metrics),4,175);self.ml.setContentsMargins(0,0,0,0);v.addWidget(self.metrics)
        r=row();v.addLayout(r);self.plots=[]
        for title in CHART_TITLES[tool]:
            _,p=chart(r,title,330 if len(CHART_TITLES[tool])>1 else 410);self.plots.append(p)
        self.tbl=table_card(v,RESULT_TITLES.get(tool,"Detected observations & calculated results"),[],[],230);v.addWidget(label("Exploratory engineering diagnostics. Interpret results against equipment-specific thresholds and sampling conditions; not a certified fault determination.","sub"))
    def show_metrics(self,m):
        while self.ml.count():
            item=self.ml.takeAt(0)
            if item.widget():item.widget().deleteLater()
        for i,(k,x) in enumerate(m.items()):
            w,_=metric(k,fmt(x));self.ml.addWidget(w,i//4,i%4)
        self.ml.current_columns=None
        theme.reflow(self.ml,max(300,self.app.scroll.viewport().width()-32));self.app.layout_timer.start()
    def run(self):
        a=self.app.data[self.a.currentIndex()];b=self.app.data[self.b.currentIndex()];tool=self.tool;self.rows=[];self.headers=[]
        try:
            vals=[]
            for i,x in enumerate(self.params):
                if isinstance(x,Q.QComboBox):
                    if tool=="Frequency Spectrum":vals.append([256,512,1024,2048][x.currentIndex()] if i==0 else int(x.currentIndex()==0))
                    else:vals.append(x.currentIndex())
                else:vals.append(x.value())
            args=dict(zip(("p","q","r"),vals))
            if tool=="Relationships":
                lag=int(vals[0]);x,y=paired(a,b)
                if abs(lag)>=len(x)-1:raise ValueError("Lag leaves too few samples")
                if lag>=0:aa=slice(0,len(x)-lag);bb=slice(lag,len(y))
                else:aa=slice(-lag,len(x));bb=slice(0,len(y)+lag)
                t=a.t[aa];a=Channel(a.name,x[aa],t,a.unit,a.time_unit);b=Channel(b.name,y[bb],t,b.unit,b.time_unit);args={}
            if tool=="State & Events" and a.time_unit!="s" and args.get("q",0)>0:raise ValueError("Minimum dwell in seconds requires a known time base")
            if tool=="Transients" or tool=="Signal Conditioning" and args.get("q",0):
                if a.time_unit!="s":raise ValueError("Rate per second requires a known time base")
            curves,m,rows=analyze(tool,a,b,**args);groups=[curves]
            y=a.y;t=a.t;good=y[np.isfinite(y)];d=describe(y)
            self.headers=["Measure","Value"] if max(map(len,rows),default=2)==2 else [f"Field {i+1}" for i in range(max(map(len,rows),default=2))]
            if tool=="Distribution":
                factor=vals[1];q1=d["Q1"];q3=d["Q3"];iqr=d["IQR"];lo=q1-factor*iqr;hi=q3+factor*iqr;inside=good[(good>=lo)&(good<=hi)];out=good[(good<lo)|(good>hi)];low=inside.min();high=inside.max();med=d["Median"]
                # Actual box-and-whisker geometry, not a second line chart.
                p=self.plots[1];draw(self.plots[0],curves[:1]);p.clear();p.addItem(pg.BarGraphItem(x=[1],y0=[q1],height=[q3-q1],width=.45,brush=theme.trace_color("#245a70"),pen=pg.mkPen(theme.trace_color("#58e0e0"))));p.plot([1,1],[low,q1],pen=theme.trace_color("#58e0e0"));p.plot([1,1],[q3,high],pen=theme.trace_color("#58e0e0"));p.plot([.75,1.25],[med,med],pen=pg.mkPen(theme.trace_color("#ffbe67"),width=2));p.plot([.87,1.13],[low,low],pen=theme.trace_color("#58e0e0"));p.plot([.87,1.13],[high,high],pen=theme.trace_color("#58e0e0"));p.plot(np.ones(len(out)),out,pen=None,symbol="o",symbolBrush=theme.trace_color("#ff7588"));p.setXRange(.5,1.5);p.enableAutoRange(axis="y");m.update({"IQR outliers":len(out)});rows=list(d.items())+[("Lower fence",lo),("Upper fence",hi),("Outlier count",len(out))];self.headers=["Measure","Value"];groups=[]
            elif tool=="Process Capability":
                lo,hi,target=vals;h,e=np.histogram(good,bins=24);groups=[[((e[:-1]+e[1:])/2,h,"Histogram")],curves];mr=np.abs(np.diff(y));mr=mr[np.isfinite(mr)];sigma=mr.mean()/1.128 if len(mr) else np.nan;overall=d["Std Dev"];mu=d["Mean"];m.update({"Cp":(hi-lo)/(6*sigma) if sigma>0 else np.nan,"Cpk":min(hi-mu,mu-lo)/(3*sigma) if sigma>0 else np.nan,"Pp":(hi-lo)/(6*overall) if overall>0 else np.nan,"Ppk":min(hi-mu,mu-lo)/(3*overall) if overall>0 else np.nan});rows=list(m.items())+[("Within sigma (MR/1.128)",sigma),("Overall sigma",overall),("Target",target)];self.headers=["Indicator","Result"]
            elif tool=="State & Events":
                mask=np.isfinite(y)&(y>=vals[0]);off=np.isfinite(y)&~mask;rr=[]
                for state,ms in [("ON",mask),("OFF",off)]:
                    for i,j,ts,te,duration in events(t,ms):
                        if duration>=vals[1]:rr.append((state,i,j,ts,te,duration,j-i+1))
                rr.sort(key=lambda z:z[1]);rows=rr;self.headers=["State","Start sample","End sample","Start","End","Duration","Samples"];m["Events"]=len(rr)
            elif tool=="Relationships":
                arr=np.array(rows,dtype=float);groups=[curves,[(arr[:,0],arr[:,2],"Residuals")]];self.headers=["X","Y","Residual"]
            elif tool=="Stability & SPC":
                groups=[[curves[0],*curves[3:]],[curves[1],curves[2]]];self.headers=["Time","Value"]
            elif tool=="Data Quality":
                dt=np.diff(t);groups=[curves,[(t[1:],dt,"Sample interval")]];flat=np.r_[False,np.isfinite(y[1:])&np.isfinite(y[:-1])&(np.diff(y)==0)];m["Repeated adjacent samples"]=int(flat.sum());rows=[(i,t[i],y[i],"Nonfinite") for i in np.flatnonzero(~np.isfinite(y))]+[(i,t[i],y[i],"Repeated value") for i in np.flatnonzero(flat)];self.headers=["Index","Time","Value","Finding"]
            elif tool=="Transients":
                groups=[[curves[0],curves[-1]],[curves[1]]];self.headers=["Sample","Time","Value"]
            elif tool=="Envelope & Peaks":
                trough,_=signal.find_peaks(-y,prominence=vals[0]);peaks,_=signal.find_peaks(y,prominence=vals[0]);groups=[curves,[(t[peaks],y[peaks],"Flags"),(t[trough],y[trough],"Outliers")]];m["Troughs"]=len(trough);rows=[(i,t[i],y[i],"Peak") for i in peaks]+[(i,t[i],y[i],"Trough") for i in trough];self.headers=["Sample","Time","Value","Type"]
            elif tool=="Autocorrelation":
                x,z,_=curves[0];peaks,_=signal.find_peaks(z);groups=[curves,[(x[peaks],z[peaks],"Flags")]];m["First positive peak lag"]=x[peaks[0]] if len(peaks) else np.nan;self.headers=["Lag","Correlation"]
            elif tool=="Band Energy":
                fs=a.rate();f,psd=signal.periodogram(y,fs=fs,detrend="constant");groups=[curves,[(f,psd,"Power spectral density")]];m.update(dict(rows));self.headers=["Band","Power"]
            elif tool=="Change Detection":
                groups=[curves[:2],curves[2:]];self.headers=["Time","Shift"]
            elif tool=="Anomaly Detection":
                self.headers=["Sample","Time","Value"]
            elif tool=="Lag & Correlation":
                self.headers=["Lag (samples)","Pearson r"]
            for p,g in zip(self.plots,groups):draw(p,g)
            if not m:m={"Valid samples":d["Valid"],"Missing":d["Missing"],"Mean":d.get("Mean",np.nan)}
            self.show_metrics(m);self.rows=rows;fill(self.tbl,self.headers,rows);self.status.setText(f"{a.name} · {len(a.y)} samples · Analysis complete")
        except (ValueError,IndexError,ArithmeticError) as exc:
            for p in self.plots:p.clear()
            self.show_metrics({});fill(self.tbl,[],[]);self.status.setText("Analysis not completed: "+str(exc))

def run():
    if len(sys.argv)==3 and sys.argv[1]=="--self-test":
        from release_smoke import run_smoke
        return run_smoke(Path(sys.argv[2]))
    app=Q.QApplication(sys.argv);app.setApplicationName("IndustrialAnalyzer");app.setOrganizationName("Robokks");theme.apply(app,STYLE,C.QSettings("Robokks","IndustrialAnalyzer").value("theme","dark") if C.QSettings("Robokks","IndustrialAnalyzer").value("theme","dark") in ("dark","light") else "dark")
    directory=C.QStandardPaths.writableLocation(C.QStandardPaths.StandardLocation.AppLocalDataLocation)
    root=Path(directory);root.mkdir(parents=True,exist_ok=True)
    from logging.handlers import RotatingFileHandler
    handler=RotatingFileHandler(root/"analyzer.log",maxBytes=1_000_000,backupCount=2,encoding="utf-8")
    logging.basicConfig(level=logging.INFO,handlers=[handler])
    def exception_hook(kind,value,tb):
        logging.error("Unhandled UI error",exc_info=(kind,value,tb))
        Q.QMessageBox.critical(None,"Industrial Analyzer",f"{kind.__name__}: {value}\n\nDiagnostic log: {root / 'analyzer.log'}")
    sys.excepthook=exception_hook
    store=AccessStore(root/"accounts.sqlite3")
    try:
        dlg=Login(store)
        if dlg.exec()!=Q.QDialog.DialogCode.Accepted:return 0
        win=Desktop(store,dlg.session);win.show();return app.exec()
    finally:store.close()

if __name__=="__main__":sys.exit(run())
