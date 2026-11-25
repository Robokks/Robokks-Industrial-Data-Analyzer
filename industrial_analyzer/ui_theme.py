"""Native Qt theme and responsive layout primitives."""
import re
import os
from pathlib import Path
from PySide6 import QtWidgets as Q, QtGui as G, QtCore as C

DARK={"background":"#081321","plot":"#0b1726","text":"#e9f2fb","muted":"#9ab7c9","axis":"#a7bdce","grid":"#34536a","accent":"#58e0e0"}
LIGHT={"background":"#eaf1f8","plot":"#ffffff","text":"#142d43","muted":"#49647a","axis":"#36546b","grid":"#c2d2e1","accent":"#087d98"}
LIGHT_REPLACEMENTS={
"#081321":"#eaf1f8","#0a1828":"#f4f8fc","#102235":"#ffffff","#142337":"#ffffff","#101c2d":"#edf5fc",
"#163b52":"#d7eef6","#122a43":"#e5edff","#153e4b":"#d9f4ee","#142a40":"#ffffff","#0e1f30":"#eef5fc",
"#122d40":"#e4eff8","#102b3a":"#e3f3f6","#102e40":"#e6f1fa","#1a3046":"#f9fcff","#25445e":"#d8eaf8",
"#132435":"#e0e8ef","#1c334b":"#d8e9f9","#152e43":"#f4f9fd","#1a4055":"#dcecf8","#12283c":"#edf5fc",
"#0d1929":"#ffffff","#20334a":"#dbe8f4","#0b1726":"#ffffff","#13283a":"#eef5fb","#16465b":"#cbe6f3",
"#0c1a28":"#e3eaf1","#34546a":"#9cb4c8","#263b50":"#c8d9e9","#294156":"#b9cbdb","#325873":"#a8c8d9",
"#34566c":"#aecbdb","#31546a":"#b6d3df","#31536b":"#b8cedf","#3c5974":"#b6ccdd","#273a50":"#bdcedb",
"#30536b":"#b7cddd","#365369":"#b8cedf","#34506b":"#b6c9da","#26394b":"#d5e1eb",
"#e9f2fb":"#142d43","#73e5df":"#087d98","#6bdbde":"#087386","#9ab7c9":"#49647a","#65dce4":"#087d98",
"#b9e5ed":"#24516a","#e5f3ff":"#17354d","#aabbd0":"#47647d","#b9d4e7":"#34536a","#678095":"#778b9c",
"#1c5267":"#cbe6f3","#538196":"#7994aa","#2494a5":"#087d98","#8be9e8":"#b1e3ec","#156474":"#087d98","#3985aa":"#087d98","#2cb5d0":"#087d98","#4679db":"#315cb4","#58e0e0":"#0b8ca6","#67dfe3":"#108ba2","#5fe4e2":"#0a8299","#53cce2":"#168fab",
}
FONT="Segoe UI"
MODE="dark"
_FONT_READY=False
_STYLE_READY=False
_APPLIED_MODE=None
_APPLIED_SHEET=None

def configure_font(app):
    global FONT,_FONT_READY
    if _FONT_READY:return FONT
    db=G.QFontDatabase
    roots=[]
    if os.name=="nt":
        roots.append(Path(os.environ.get("WINDIR",r"C:\Windows"))/"Fonts")
    else:
        roots.extend([Path("/usr/share/fonts/truetype/dejavu"),Path("/usr/share/fonts/truetype/liberation2")])
    for root in roots:
        for name in ("segoeui.ttf","segoeuib.ttf","arial.ttf","arialbd.ttf","DejaVuSans.ttf","DejaVuSans-Bold.ttf","LiberationSans-Regular.ttf"):
            p=root/name
            if p.is_file():db.addApplicationFont(str(p))
    available=set(db.families())
    for name in ("Segoe UI","Arial","DejaVu Sans","Liberation Sans"):
        if name in available:
            font=G.QFont(name,10)
            raw=G.QRawFont.fromFont(font)
            if raw.isValid() and all(raw.supportsCharacter(ord(c)) for c in "Analysis 0123456789"):
                FONT=name;app.setFont(font);_FONT_READY=True;return name
    font=app.font();raw=G.QRawFont.fromFont(font)
    if not raw.isValid() or not all(raw.supportsCharacter(ord(c)) for c in "Analysis 0123456789"):
        raise RuntimeError("No usable UI font found. Install Segoe UI, Arial or DejaVu Sans.")
    FONT=font.family();_FONT_READY=True;return FONT

def colors():return LIGHT if MODE=="light" else DARK

def stylesheet(base,mode):
    global MODE
    if mode not in ("dark","light"):raise ValueError("Unknown theme")
    MODE=mode
    result=base.replace("'Segoe UI'", "'"+FONT+"'")
    if mode=="light":
        result=re.sub(r"#[0-9a-fA-F]{6}\b",lambda m:LIGHT_REPLACEMENTS.get(m.group().lower(),m.group()),result)
        result=result.replace("QPushButton#nav:checked{background:#d8e9f9;border-left:3px solid #0b8ca6;color:white;","QPushButton#nav:checked{background:#d8e9f9;border-left:3px solid #0b8ca6;color:#142d43;")
    result+=f"""
QPushButton {{min-height:18px; padding:8px 12px;}}
QPushButton#nav {{min-height:22px; padding:8px 10px; font-size:13px;}}
QLabel#heading {{font-size:26px; font-weight:700;}}
QLabel#heroTitle,QLabel#heroAccent {{font-size:36px; font-weight:700;}}
QLabel#metricValue {{font-size:26px; font-weight:700;}}
QComboBox {{min-height:20px;}}
QDialog,QMenu {{background:{colors()['background']};color:{colors()['text']};}}
QMenu::item {{padding:9px 18px;}}
QMenu::item:selected {{background:{'#cbe6f3' if mode=='light' else '#25445e'};}}
QTabWidget::pane {{border:1px solid {colors()['grid']};border-radius:8px;}}
QTabBar::tab {{background:{colors()['background']};padding:10px 14px;border:1px solid {colors()['grid']};}}
QTabBar::tab:selected {{background:{'#d8e9f9' if mode=='light' else '#1c334b'};}}
QWidget#page,QWidget#workspace,QDialog,QMenu {{background:{colors()['background']};}}
QTreeWidget,QTableWidget,QListWidget {{background:{colors()['plot']};color:{colors()['text']};alternate-background-color:{'#eef5fb' if mode=='light' else '#13283a'};selection-background-color:{'#cbe6f3' if mode=='light' else '#16465b'};selection-color:{colors()['text']};}}
QAbstractItemView::item:hover {{background:{'#e0edf7' if mode=='light' else '#20384e'};}}
QLineEdit:disabled,QComboBox:disabled,QAbstractSpinBox:disabled {{background:{'#e3eaf1' if mode=='light' else '#132435'};color:{colors()['muted']};}}
QProgressBar {{border:1px solid {colors()['grid']};border-radius:6px;background:{colors()['plot']};color:{colors()['text']};text-align:center;}}
QProgressBar::chunk {{background:{colors()['accent']};border-radius:5px;}}
QScrollBar:horizontal {{background:{colors()['background']};height:12px;margin:0;}}
QScrollBar::handle:horizontal {{background:{'#9cb4c8' if mode=='light' else '#34546a'};border-radius:5px;min-width:28px;}}
QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal {{width:0;}}
QFrame#separator {{color:{colors()['grid']};}}
QLabel#brandLogo {{background:#087d98;color:white;border-radius:10px;}}
QToolTip {{color:{colors()['text']};background:{colors()['plot']};border:1px solid {colors()['grid']};}}
"""
    return result

def apply(app,base,mode):
    """Set Fusion once. Do not rebuild the style engine on each theme change."""
    global _STYLE_READY,_APPLIED_MODE,_APPLIED_SHEET
    configure_font(app)
    if not _STYLE_READY:
        app.setStyle("Fusion")
        _STYLE_READY=True
    sheet=stylesheet(base,mode)
    if _APPLIED_MODE==mode and _APPLIED_SHEET==sheet and app.styleSheet()==sheet:
        return False
    c=colors();pal=G.QPalette()
    import pyqtgraph as pg
    pg.setConfigOptions(background=c["plot"],foreground=c["text"])
    for role,key in [(G.QPalette.ColorRole.Window,"background"),(G.QPalette.ColorRole.WindowText,"text"),(G.QPalette.ColorRole.Base,"plot"),(G.QPalette.ColorRole.Text,"text"),(G.QPalette.ColorRole.Button,"background"),(G.QPalette.ColorRole.ButtonText,"text"),(G.QPalette.ColorRole.ToolTipBase,"plot"),(G.QPalette.ColorRole.ToolTipText,"text"),(G.QPalette.ColorRole.Link,"accent")]:
        pal.setColor(role,G.QColor(c[key]))
    pal.setColor(G.QPalette.ColorRole.Highlight,G.QColor("#cbe6f3" if mode=="light" else "#16465b"))
    pal.setColor(G.QPalette.ColorRole.HighlightedText,G.QColor(c["text"]))
    pal.setColor(G.QPalette.ColorRole.AlternateBase,G.QColor("#eef5fb" if mode=="light" else "#13283a"))
    for role in (G.QPalette.ColorRole.Text,G.QPalette.ColorRole.WindowText,G.QPalette.ColorRole.ButtonText):
        pal.setColor(G.QPalette.ColorGroup.Disabled,role,G.QColor(c["muted"]))
    app.setPalette(pal)
    app.setStyleSheet(sheet)
    _APPLIED_MODE=mode;_APPLIED_SHEET=sheet
    return True

DARK_TRACES=["#4dd9e8","#ffbe67","#8e95ff","#55d6a0","#ff7588","#cb91ef","#78b6ff","#f4d35e","#58e0e0","#245a70"]
LIGHT_TRACES=["#087d98","#ae6006","#5656c0","#14845b","#c43f62","#8752a6","#286ab1","#a7780b","#087d98","#c1e3ee"]

def trace_color(color,mode=None):
    mode=mode or MODE
    return dict(zip(DARK_TRACES,LIGHT_TRACES)).get(color.lower(),color) if mode=="light" else color

def contrasting_text(color):
    c=G.QColor(color)
    def linear(v):return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
    luminance=sum(w*linear(v) for w,v in zip((.2126,.7152,.0722),(c.redF(),c.greenF(),c.blueF())))
    return "#101820" if luminance>.18 else "#ffffff"

class ResponsiveStack(Q.QStackedWidget):
    """Hidden workbenches must not impose their minimum width on the visible page."""
    def minimumSizeHint(self):
        w=self.currentWidget()
        return w.minimumSizeHint() if w is not None else C.QSize(0,0)
    def sizeHint(self):
        w=self.currentWidget()
        return w.sizeHint() if w is not None else C.QSize(0,0)

class AdaptiveRow(Q.QBoxLayout):
    """Reflows entire controls/cards instead of shrinking text or clipping them."""
    def __init__(self):
        super().__init__(Q.QBoxLayout.Direction.LeftToRight)
        self.setSpacing(12)
    def adapt(self,width):
        widths=[]
        for i in range(self.count()):
            item=self.itemAt(i)
            if item.spacerItem():continue
            w=item.widget()
            if w is not None and w.isHidden():continue
            widths.append(max(item.minimumSize().width(),min(item.sizeHint().width(),460)))
        required=sum(widths)+max(0,len(widths)-1)*self.spacing()
        direction=self.Direction.TopToBottom if required>width else self.Direction.LeftToRight
        if self.direction()!=direction:self.setDirection(direction)

def mark_grid(grid,columns,minimum=210):
    grid.adaptive_columns=columns;grid.adaptive_minimum=minimum
    return grid

def reflow(layout,width,_visited=None):
    if layout is None or width<=0:return
    if _visited is None:_visited=set()
    key=(layout,int(width))
    if key in _visited:return
    _visited.add(key)
    margins=layout.contentsMargins()
    available=max(120,width-margins.left()-margins.right())
    if isinstance(layout,Q.QStackedLayout):
        w=layout.currentWidget()
        if w is not None:reflow(w.layout(),available,_visited)
        return
    if isinstance(layout,Q.QGridLayout) and hasattr(layout,"adaptive_columns"):
        items=[]
        for i in range(layout.count()):
            item=layout.itemAt(i)
            if item.widget() is not None:items.append(item.widget())
        minimum=max([layout.adaptive_minimum]+[w.minimumSizeHint().width() for w in items])
        n=max(1,min(layout.adaptive_columns,(available+layout.spacing())//(minimum+layout.spacing())))
        if getattr(layout,"current_columns",None)!=n:
            for w in items:layout.removeWidget(w)
            for j in range(max(layout.columnCount(),layout.adaptive_columns)):
                layout.setColumnStretch(j,0);layout.setColumnMinimumWidth(j,0)
            for j,w in enumerate(items):layout.addWidget(w,j//n,j%n)
            for j in range(n):layout.setColumnStretch(j,1)
            layout.current_columns=n
            layout.invalidate()
        child_width=max(120,(available-(n-1)*layout.spacing())//n)
    elif isinstance(layout,AdaptiveRow):
        # First allow children to compact before calculating horizontal requirements.
        for i in range(layout.count()):
            item=layout.itemAt(i)
            if item.layout():reflow(item.layout(),available,_visited)
            elif item.widget() and item.widget().layout() and not isinstance(item.widget(),(Q.QAbstractItemView,Q.QComboBox,Q.QAbstractSpinBox,Q.QGraphicsView,Q.QAbstractScrollArea)):reflow(item.widget().layout(),available,_visited)
        layout.adapt(available)
        n=sum(1 for i in range(layout.count()) if not layout.itemAt(i).spacerItem())
        child_width=max(120,(available-max(0,n-1)*layout.spacing())//max(1,n)) if layout.direction()==layout.Direction.LeftToRight else available
    else:child_width=available
    for i in range(layout.count()):
        item=layout.itemAt(i);w=item.widget()
        if item.layout():reflow(item.layout(),child_width,_visited)
        elif w is not None and w.layout() and not isinstance(w,(Q.QAbstractItemView,Q.QComboBox,Q.QAbstractSpinBox,Q.QGraphicsView,Q.QAbstractScrollArea)):
            reflow(w.layout(),child_width,_visited)
    # Qt invalidates modified grids and rows itself. Avoid repeated global geometry churn.
