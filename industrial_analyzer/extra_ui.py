"""Extended native dialogs and cancellable I/O operations."""
import os
import logging
import tempfile
import threading
from pathlib import Path
import numpy as np
from PySide6 import QtWidgets as Q, QtCore as C, QtGui as G
import pyqtgraph as pg
from engine import Channel, describe, paired
from safe_export import export_table
import data_workspace as dw
import engineering_tools as et
import live_capture
import recording_ops as ro
import ui_theme as theme

def ui():
    import v12_ui
    return v12_ui

class Worker(C.QThread):
    def __init__(self,fn):
        super().__init__();self.fn=fn;self.cancel=threading.Event();self.value=None;self.error=None
    def run(self):
        try:self.value=self.fn(self.cancel.is_set)
        except Exception as exc:self.error=exc

class BusyDialog(Q.QDialog):
    def __init__(self,parent,worker,title):
        super().__init__(parent);self.worker=worker;self.setWindowTitle(title);self.setMinimumWidth(440)
        l=Q.QVBoxLayout(self);l.addWidget(ui().label(title,"heading"));self.msg=ui().label("Working in the background. Cancellation is checked between supported operations.","sub");l.addWidget(self.msg)
        p=Q.QProgressBar();p.setRange(0,0);l.addWidget(p);self.cancel_btn=ui().btn("Cancel",self.reject);l.addWidget(self.cancel_btn)
    def reject(self):
        if self.worker.isRunning():
            self.worker.cancel.set();self.cancel_btn.setEnabled(False);self.msg.setText("Cancellation requested; waiting for the current operation.")
        else:super().reject()
    def closeEvent(self,e):
        if self.worker.isRunning():self.reject();e.ignore()
        else:super().closeEvent(e)

def job(app,title,fn):
    if getattr(app,"_active_job",None) is not None:raise RuntimeError("Another job is active")
    w=Worker(fn);dlg=BusyDialog(app,w,title);app._active_job=w
    w.finished.connect(dlg.accept,C.Qt.ConnectionType.QueuedConnection)
    # Start only after the modal event loop begins; fast jobs cannot finish before exec().
    C.QTimer.singleShot(0,w.start)
    try:
        dlg.exec();w.wait()
        if w.cancel.is_set():raise InterruptedError("Operation cancelled")
        if w.error is not None:raise w.error
        return w.value
    finally:
        if w.isRunning():w.cancel.set();w.wait()
        app._active_job=None;dlg.deleteLater();w.deleteLater()

def warn(app,title,exc):
    if not isinstance(exc,InterruptedError):
        logging.error("%s: %s",title,exc,exc_info=(type(exc),exc,exc.__traceback__))
        Q.QMessageBox.warning(app,title,str(exc))

def install_data(app,channels,specs=None,selection=None,colors=None):
    app.data=channels;app.recordings=list(specs or []);app.source=f"{len(app.recordings)} recording(s)" if app.recordings else "Derived / captured data"
    app.selected=set(range(min(4,len(channels)))) if selection is None else {i for i in selection if 0<=i<len(channels)}
    app.dataset_changed()
    if colors:app.colors={int(k):v for k,v in colors.items() if int(k)<len(channels)}
    app.show_page(0)

def import_options(app,path):
    ext=Path(path).suffix.lower();o={}
    if ext==".tdms":return o
    if ext in (".xlsx",".xls",".xlsm"):
        x,ok=Q.QInputDialog.getText(app,"Excel worksheet",f"{Path(path).name}: sheet name (blank = first sheet)")
        if not ok:return None
        o["sheet"]=x if x else 0
    else:
        x,ok=Q.QInputDialog.getItem(app,"Text delimiter",Path(path).name,["Automatic",",","Tab",";","|"],0,False)
        if not ok:return None
        o["delimiter"]={"Automatic":None,"Tab":"\t","|":r"\|"}.get(x,x)
    t,ok=Q.QInputDialog.getText(app,"Time base","Time column name (seconds or datetime), blank = none")
    if not ok:return None
    o["time_column"]=t.strip() or None
    if not t.strip():
        fs,ok=Q.QInputDialog.getDouble(app,"Sampling rate","Hz (0 = sample index)",0.,0.,1e9,6)
        if not ok:return None
        o["sample_rate"]=fs or None
    return o

def open_recordings(app,append=False):
    if not app.permitted("Open data files"):return
    paths,_=Q.QFileDialog.getOpenFileNames(app,"Open recording(s)","","Supported files (*.tdms *.csv *.txt *.xlsx *.xls *.xlsm);;All files (*)",options=Q.QFileDialog.Option.DontUseNativeDialog)
    if not paths:return
    try:
        specs=[]
        for p in paths:
            o=import_options(app,p)
            if o is None:return
            specs.append({"path":str(Path(p).resolve()),"options":o})
        if append:
            if not app.recordings:raise ValueError("Append requires an existing file-backed workspace; open recordings first")
            if len(app.data)!=getattr(app,"file_channel_count",len(app.data)):raise ValueError("Save/export derived channels before appending files")
            specs=app.recordings+specs
        data=job(app,"Import recordings",lambda stop:dw.load_workspace(specs,stop))
        if not app.permitted("Open data files"):return
        install_data(app,data,specs);app.file_channel_count=len(data);app.audit("Recordings imported",str(len(specs)))
    except Exception as exc:warn(app,"Import",exc)

def range_browser(app):
    if not app.permitted("Open data files"):return
    path,_=Q.QFileDialog.getOpenFileName(app,"Browse large TDMS recording","","TDMS (*.tdms)",options=Q.QFileDialog.Option.DontUseNativeDialog)
    if not path:return
    try:meta=job(app,"Read TDMS metadata",lambda stop:dw.catalog(path))
    except Exception as exc:warn(app,"TDMS metadata",exc);return
    if not meta:Q.QMessageBox.information(app,"TDMS","No numeric channels");return
    d=Q.QDialog(app);d.resize(950,640);d.setWindowTitle("TDMS group / channel browser");l=Q.QVBoxLayout(d);l.addWidget(ui().label("TDMS range & streaming analysis","heading"));l.addWidget(ui().label("Browse metadata without importing all samples. Select a channel and either calculate whole-channel streaming statistics or load a bounded sample range.","sub"))
    tree=Q.QTreeWidget();tree.setHeaderLabels(["Group / Channel","Samples","Unit","Type"]);l.addWidget(tree,1);groups={}
    for i,(group,name,n,unit,dtype) in enumerate(meta):
        if group not in groups:groups[group]=Q.QTreeWidgetItem(tree,[group])
        it=Q.QTreeWidgetItem(groups[group],[name,str(n),unit,dtype]);it.setData(0,C.Qt.ItemDataRole.UserRole,i)
    tree.expandAll()
    limits=Q.QHBoxLayout();l.addLayout(limits);a=Q.QLineEdit("0");b=Q.QLineEdit("10000");ui().field(limits,"START (inclusive)",a);ui().field(limits,"STOP (exclusive)",b)
    summary=ui().label("Select a numeric channel.","status");l.addWidget(summary)
    def chosen():
        it=tree.currentItem()
        if it is None or it.data(0,C.Qt.ItemDataRole.UserRole) is None:raise ValueError("Select a numeric channel")
        return meta[it.data(0,C.Qt.ItemDataRole.UserRole)]
    def stats():
        try:
            group,name,*_=chosen();m=job(app,"Stream full-channel statistics",lambda stop:dw.stream_stats(path,group,name,stop));summary.setText("  ·  ".join(f"{k}: {ui().fmt(v)}" for k,v in m.items()))
        except Exception as exc:warn(d,"TDMS statistics",exc)
    def load_range():
        try:
            group,name,*_=chosen();spec={"path":str(Path(path).resolve()),"range":[group,name,int(a.text()),int(b.text())]}
            data=job(app,"Load selected sample range",lambda stop:dw.load_workspace([spec],stop))
            if not app.permitted("Open data files"):return
            install_data(app,data,[spec]);app.file_channel_count=len(data);app.audit("TDMS range imported");d.accept()
        except Exception as exc:warn(d,"TDMS range",exc)
    row=Q.QHBoxLayout();l.addLayout(row);row.addWidget(ui().btn("Calculate full-channel statistics",stats));row.addWidget(ui().btn("Load selected range",load_range,"primary"));row.addWidget(ui().btn("Close",d.accept));d.exec()

def save_workspace(app):
    if not app.permitted("Export data & reports"):return
    if not app.recordings or len(app.data)!=getattr(app,"file_channel_count",0):
        Q.QMessageBox.information(app,"Workspace","Only unchanged file-backed workspaces can be saved. Export derived or live data separately.");return
    path,_=Q.QFileDialog.getSaveFileName(app,"Save workspace","","Workspace JSON (*.json)")
    if path:
        try:dw.write_manifest(path,app.recordings,sorted(app.selected),app.colors);app.audit("Workspace saved")
        except Exception as exc:warn(app,"Workspace",exc)

def restore_workspace(app):
    if not app.permitted("Open data files"):return
    path,_=Q.QFileDialog.getOpenFileName(app,"Restore workspace","","Workspace JSON (*.json)")
    if not path:return
    try:
        p=dw.read_manifest(path)
        paths="\n".join(s["path"] for s in p["recordings"])
        if Q.QMessageBox.question(app,"Confirm referenced files","Open these referenced measurement files?\n\n"+paths)!=Q.QMessageBox.StandardButton.Yes:return
        data=job(app,"Restore workspace",lambda stop:dw.load_workspace(p["recordings"],stop))
        if not app.permitted("Open data files"):return
        install_data(app,data,p["recordings"],p["selected"],p["colors"]);app.file_channel_count=len(data);app.audit("Workspace restored")
    except Exception as exc:warn(app,"Workspace",exc)

def export_rows(app,headers,rows):
    if not app.permitted("Export data & reports"):return
    path,_=Q.QFileDialog.getSaveFileName(app,"Export","","CSV (*.csv);;Excel (*.xlsx)")
    if not path:return
    def operation(stop):
        def checked():
            for i,row in enumerate(rows):
                if i%1024==0 and stop():raise InterruptedError("Cancelled")
                yield row
            if stop():raise InterruptedError("Cancelled")
        export_table(path,headers,checked())
    try:job(app,"Export measurements",operation);app.audit("Data exported")
    except Exception as exc:warn(app,"Export",exc)

def pdf_report(app,text):
    if not app.permitted("Export data & reports"):return
    path,_=Q.QFileDialog.getSaveFileName(app,"Save PDF report","","PDF (*.pdf)")
    if not path:return
    fd,tmp=tempfile.mkstemp(suffix=".pdf",dir=Path(path).parent);os.close(fd)
    try:
        writer=G.QPdfWriter(tmp);writer.setPageSize(G.QPageSize(G.QPageSize.PageSizeId.A4));writer.setResolution(150)
        doc=G.QTextDocument();doc.setDefaultFont(G.QFont("Segoe UI",10));doc.setPlainText(text);doc.print_(writer);del writer
        os.replace(tmp,path);app.audit("PDF report exported")
    except Exception as exc:warn(app,"PDF export",exc)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def capture_dialog(app):
    if not app.permitted("Open data files") or not app.permitted("Modify analysis settings"):return
    proto,ok=Q.QInputDialog.getItem(app,"LabVIEW capture","Loopback only: LabVIEW connects to 127.0.0.1. UTF-8 JSON per newline (TCP) or datagram (UDP).",["TCP","UDP"],0,False)
    if not ok:return
    port,ok=Q.QInputDialog.getInt(app,"Local port","Port (1024–65535)",8765,1024,65535)
    if not ok:return
    sec,ok=Q.QInputDialog.getInt(app,"Capture duration","Seconds (1–120)",15,1,120)
    if not ok:return
    try:
        channels,rejected=job(app,"Receiving local measurement data",lambda stop:live_capture.capture(port,sec,proto,stop))
        if not app.permitted("Open data files"):return
        install_data(app,channels);app.source=f"LabVIEW {proto} capture";app.show_page(0);app.audit("Live capture",f"{rejected} rejected frames")
        Q.QMessageBox.information(app,"Capture",f"{len(channels[0].y)} samples; {rejected} invalid frames rejected.")
    except Exception as exc:warn(app,"LabVIEW capture",exc)

# A separate engineering workstation preserves the original reference screens.
TOOLS={
"Mechanical power (rpm × Nm)":(2,["Speed rpm","Torque Nm"],[]),
"Efficiency (kW in/out)":(2,["Input kW","Output kW"],[("Minimum input kW",.01)]),
"Loss torque referred to shaft":(3,["Shaft rpm","Input kW","Output kW"],[("Minimum abs rpm",1)]),
"Torque-speed XY map":(2,["Speed rpm","Torque Nm"],[]),
"Electrical power (single phase)":(2,["Voltage V","Current A"],[]),
"Electrical power (three phase)":(6,["VA (V)","IA (A)","VB (V)","IB (A)","VC (V)","IC (A)"],[]),
"Harmonics and THD":(1,["Voltage/current"],[("Fundamental Hz",50),("Max harmonic",20)]),
"Low-pass Butterworth":(1,["Signal"],[("Cutoff Hz",2),("Filter order",4)]),
"High-pass Butterworth":(1,["Signal"],[("Cutoff Hz",2),("Filter order",4)]),
"Integration":(1,["Signal"],[]),
"Differentiation":(1,["Signal"],[]),
"Linear detrend":(1,["Signal"],[]),
"Envelope spectrum / crest factor":(1,["Vibration"],[("Lower band Hz",1),("Upper band Hz",4)]),
"Order tracking (rpm channel)":(2,["Vibration","Speed rpm"],[("Samples/rev",128)]),
"Bearing characteristic frequencies":(0,[],[("Shaft RPM",1500),("Rolling elements",8),("Ball diameter",10),("Pitch diameter",50),("Contact angle °",0)]),
"Spectrogram":(1,["Signal"],[("FFT window",256)]),
"Waterfall spectrum":(1,["Signal"],[("FFT window",256)]),
"Tolerance / baseline comparison":(2,["Baseline","Current"],[("Absolute tolerance",1)]),
"Derived channel expression":(2,["A","B"],[]),
"Unit conversion (factor + offset)":(1,["Signal"],[("Multiplier",1),("Offset",0)]),
"Resample (linear interpolation)":(1,["Signal"],[("Target Hz",20)]),
}

class EngineeringDialog(Q.QDialog):
    def __init__(self,app):
        super().__init__(app);self.app=app;self.setWindowTitle("Extended Engineering Workstation");self.resize(1220,850);self.result=None;self.rows=[];self.headers=[]
        l=Q.QVBoxLayout(self);l.addWidget(ui().label("ENGINEERING / EXTENDED TOOLKIT","micro"));l.addWidget(ui().label("Mechanical · Electrical · Vibration · Mathematics","heading"))
        self.tool=ui().combo(list(TOOLS));l.addWidget(self.tool)
        self.control=Q.QWidget();self.form=Q.QGridLayout(self.control);self.form.setHorizontalSpacing(12);self.form.setVerticalSpacing(8);l.addWidget(self.control)
        r=theme.AdaptiveRow();l.addLayout(r);r.addWidget(ui().btn("Calculate",self.calculate,"primary"));r.addWidget(ui().btn("Add result as derived channel",self.add));r.addWidget(ui().btn("Export results",self.export));r.addWidget(ui().btn("Save graph PNG",self.png));r.addWidget(ui().btn("Close",self.accept))
        self.status=ui().label("Select a tool. Input values must use the units shown in the channel selectors.","status");l.addWidget(self.status)
        self.plot=ui().plot(330);l.addWidget(self.plot,1);self.table=ui().table([],[]);self.table.setMinimumHeight(200);l.addWidget(self.table,1);self.tool.currentIndexChanged.connect(self.rebuild);self.rebuild()
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self.layout():theme.reflow(self.layout(),self.width()-36)
    def rebuild(self,*_):
        while self.form.count():
            it=self.form.takeAt(0)
            if it.widget():it.widget().deleteLater()
        self.channels=[];self.params=[];self.expr=None;self.unit=None;self.result=None;self.rows=[];self.headers=[];self.plot.clear();ui().fill(self.table,[],[])
        name=self.tool.currentText();n,roles,parameters=TOOLS[name]
        def field(title,w,i):
            self.form.addWidget(ui().label(title,"micro"),2*(i//3),i%3);self.form.addWidget(w,2*(i//3)+1,i%3);return w
        for i,role in enumerate(roles):
            choices=[f"{c.name} [{c.unit or 'unspecified'}]" for c in self.app.data]
            self.channels.append(field(role,ui().combo(choices,i),i))
        for j,(name,value) in enumerate(parameters,n):
            self.params.append(field(name,ui().number(value),j))
        if self.tool.currentText()=="Derived channel expression":
            self.expr=field("Expression (A, B, pi; abs/sqrt/sin/cos/log/exp)",Q.QLineEdit("A+B"),n)
        if self.tool.currentText() in ("Derived channel expression","Unit conversion (factor + offset)"):
            self.unit=field("Output engineering unit",Q.QLineEdit(""),n+1)
    def calculate(self):
        if not self.app.permitted("Modify analysis settings") or not self.app.permitted("Advanced diagnostics"):return
        tool=self.tool.currentText();cs=[self.app.data[x.currentIndex()] for x in self.channels];p=[x.value() for x in self.params];expr=self.expr.text() if self.expr else "";unit=self.unit.text()[:80] if self.unit else "";self.result=None;self.rows=[];self.headers=[];self.plot.clear();self.plot.setLabel("left","");self.plot.setLabel("bottom","");ui().fill(self.table,[],[])
        def compute(stop):
            z=None;metrics={};curves=[];image=None;outunit=cs[0].unit if cs else "";base=cs[0] if cs else None
            if tool.startswith("Mechanical power"):z=et.mechanical_power(*cs);outunit="kW"
            elif tool.startswith("Efficiency"):z=et.efficiency(*cs,p[0]);outunit="%"
            elif tool.startswith("Loss torque"):z=et.loss_torque(*cs,p[0]);outunit="Nm"
            elif tool=="Torque-speed XY map":
                x,y=et.aligned(*cs);curves=[(x,y,"XY")];metrics={"Points":len(x),"Maximum torque Nm":np.max(y)}
            elif tool=="Electrical power (single phase)":metrics,z=et.electrical(*cs);outunit="W"
            elif tool=="Electrical power (three phase)":metrics,z=et.three_phase(cs);outunit="W"
            elif tool=="Harmonics and THD":
                x,y,metrics=et.harmonic_metrics(cs[0],p[0],int(p[1]));curves=[(x,y,"Harmonics RMS")]
            elif tool in ("Low-pass Butterworth","High-pass Butterworth"):z=et.filter_signal(cs[0],p[0],"lowpass" if tool.startswith("Low") else "highpass",int(p[1]))
            elif tool=="Integration":z=et.integrate_signal(cs[0]);outunit=(outunit+"·s").strip("·")
            elif tool=="Differentiation":z=et.differentiate(cs[0]);outunit=outunit+"/s"
            elif tool=="Linear detrend":
                from scipy.signal import detrend
                z=detrend(et.finite(cs[0].y))
            elif tool.startswith("Envelope spectrum"):
                x,y,metrics=et.envelope_spectrum(cs[0],*p);curves=[(x,y,"Envelope PSD")]
            elif tool.startswith("Order tracking"):
                x,y=et.order_spectrum(*cs,int(p[0]));curves=[(x,y,"Order amplitude")];metrics={"Peak order":x[np.argmax(y)]}
            elif tool.startswith("Bearing characteristic"):metrics=et.bearing_frequencies(*p)
            elif tool in ("Spectrogram","Waterfall spectrum"):
                t,f,s=et.spectrogram(cs[0],int(p[0]))
                if tool=="Spectrogram":image=(t,f,s)
                else:
                    ids=np.linspace(0,len(t)-1,min(20,len(t)),dtype=int);curves=[(f,s[:,i]+j*30,f"{t[i]:.2f}s (+{j*30} dB)") for j,i in enumerate(ids)]
                metrics={"Time frames":len(t),"Frequency bins":len(f)}
            elif tool.startswith("Tolerance"):metrics,z=et.comparison_metrics(*cs,p[0])
            elif tool.startswith("Derived"):z=et.expression(expr,cs);outunit=unit
            elif tool.startswith("Unit conversion"):z=cs[0].y*p[0]+p[1];outunit=unit
            elif tool.startswith("Resample"):
                base=et.resample(cs[0],p[0]);z=base.y
            else:raise ValueError("Unknown engineering tool")
            result=None
            if z is not None:
                result=Channel(tool,z,base.t,outunit,base.time_unit,dict(base.metadata));curves=[(result.t,result.y,tool)];metrics.update({k:v for k,v in describe(z).items() if k in ("Valid","Missing","Min","Max","Mean","RMS")})
            return result,curves,metrics,image
        try:
            self.result,curves,metrics,image=job(self.app,"Engineering calculation",compute)
            ui().draw(self.plot,curves)
            if image is not None:
                t,f,s=image;item=pg.ImageItem(s,axisOrder="row-major");self.plot.addItem(item)
                dt=t[1]-t[0] if len(t)>1 else 1/cs[0].rate();df=f[1]-f[0]
                item.setRect(C.QRectF(t[0]-dt/2,f[0]-df/2,max(dt,len(t)*dt),len(f)*df));self.plot.setLabel("left","Frequency Hz");self.plot.setLabel("bottom","Time s");self.plot.enableAutoRange()
            self.headers=["Measure","Value"];self.rows=list(metrics.items());ui().fill(self.table,self.headers,self.rows);self.status.setText("Calculation complete · verify sensor units, alignment and engineering assumptions before use.")
        except Exception as exc:self.status.setText("Calculation failed: "+str(exc))
    def add(self):
        if self.result is None or not self.app.permitted("Modify analysis settings"):return
        if len(self.app.data)>=dw.MAX_CHANNELS or sum(len(c.y) for c in self.app.data)+len(self.result.y)>dw.MAX_SAMPLES:
            Q.QMessageBox.warning(self,"Derived channel","Working set limit exceeded");return
        n,ok=Q.QInputDialog.getText(self,"Derived channel","Channel name",text=self.result.name)
        if not ok or not n.strip():return
        n=n.strip()[:120]
        if n in self.app.names():Q.QMessageBox.warning(self,"Derived channel","Name already exists");return
        c=self.result;data=[*self.app.data,Channel(n,c.y,c.t,c.unit,c.time_unit,dict(c.metadata))]
        self.app.data=data;self.app.selected.add(len(data)-1);self.app.dataset_changed();self.app.show_page(2);self.app.audit("Derived channel created",n);self.accept()
    def export(self):
        if self.result is not None:
            c=self.result;self.app.do_export(["Time","Time unit","Value","Unit"],((t,c.time_unit,y,c.unit) for t,y in zip(c.t,c.y)))
        elif self.rows:self.app.do_export(self.headers,self.rows)
    def png(self):
        if not self.app.permitted("Export data & reports"):return
        path,_=Q.QFileDialog.getSaveFileName(self,"Save graph","","PNG (*.png)")
        if path and not self.plot.grab().save(path):Q.QMessageBox.warning(self,"Graph","Could not save graph")


def graph_studio(app):
    d=Q.QDialog(app);d.setWindowTitle("Independent-axis Graph Studio");d.resize(1180,790);l=Q.QVBoxLayout(d)
    l.addWidget(ui().label("Independent Y axes · synchronized X when compatible","heading"))
    r=theme.AdaptiveRow();l.addLayout(r);a=ui().field(r,"LEFT AXIS",ui().combo(app.names()));b=ui().field(r,"RIGHT AXIS",ui().combo(app.names(),1));r.addWidget(ui().btn("Draw",lambda:render(),"primary"))
    p=ui().plot(420);l.addWidget(p,1);right=pg.ViewBox();pi=p.getPlotItem();pi.showAxis("right");pi.scene().addItem(right);pi.getAxis("right").linkToView(right);right.setXLink(pi.vb)
    def resize():
        right.setGeometry(pi.vb.sceneBoundingRect());right.linkedViewChanged(pi.vb,right.XAxis)
    pi.vb.sigResized.connect(resize)
    note=ui().label("","status");l.addWidget(note);annotation=Q.QLineEdit();annotation.setPlaceholderText("Annotation or bookmark label");l.addWidget(annotation)
    marks=[];saved=[]
    def render():
        p.clear();right.clear();marks.clear();saved.clear();x=app.data[a.currentIndex()];y=app.data[b.currentIndex()]
        if x.time_unit!=y.time_unit or x.metadata.get("clock_id")!=y.metadata.get("clock_id"):
            note.setText("Cannot link independent clocks. Use separate trend panels.");return
        p.plot(x.t,x.y,name=x.name,pen=pg.mkPen(theme.trace_color("#58e0e0"),width=2),autoDownsample=True,downsampleMethod="peak",connect="finite")
        right.addItem(pg.PlotDataItem(y.t,y.y,pen=pg.mkPen(theme.trace_color("#ffbe67"),width=2),autoDownsample=True,downsampleMethod="peak",connect="finite"))
        p.setLabel("left",x.name,units=x.unit or None,color=theme.trace_color("#58e0e0"));p.setLabel("right",y.name,units=y.unit or None,color=theme.trace_color("#ffbe67"));p.setLabel("bottom","Time (s)" if x.time_unit=="s" else "Sample index")
        p.enableAutoRange();right.enableAutoRange();resize();note.setText("Left: "+x.name+"  ·  Right: "+y.name+"  ·  Bookmark positions are session-local.")
    def annotate():
        text=annotation.text().strip()[:80]
        if not text:return
        lo,hi=p.viewRange()[0];x=(lo+hi)/2;line=pg.InfiniteLine(pos=x,angle=90,movable=True,label=text.replace("{","{{").replace("}","}}"),pen=pg.mkPen(theme.trace_color("#ffbe67")),labelOpts={"color":theme.colors()["text"]});p.addItem(line,ignoreBounds=True);marks.append(line);saved.append((text,x));annotation.clear()
    def export_bookmarks():
        app.do_export(["Label","Position"],[(name,line.value()) for (name,_),line in zip(saved,marks)])
    def save_png():
        if not app.permitted("Export data & reports"):return
        path,_=Q.QFileDialog.getSaveFileName(d,"Save graph","","PNG (*.png)")
        if path and not p.grab().save(path):Q.QMessageBox.warning(d,"Graph","Could not save image")
    row=Q.QHBoxLayout();l.addLayout(row);row.addWidget(ui().btn("Add annotation at view center",annotate));row.addWidget(ui().btn("Export bookmarks",export_bookmarks));row.addWidget(ui().btn("Save PNG",save_png));row.addWidget(ui().btn("Close",d.accept));render();d.exec()

def batch_summary(app):
    if not app.permitted("Open data files") or not app.permitted("Export data & reports"):return
    paths,_=Q.QFileDialog.getOpenFileNames(app,"Batch statistical report","","Supported (*.tdms *.csv *.txt *.xlsx *.xls *.xlsm)")
    if not paths:return
    specs=[]
    try:
        if len(paths)>32:raise ValueError("Choose at most 32 recordings")
        for path in paths:
            o=import_options(app,path)
            if o is None:return
            specs.append({"path":str(Path(path).resolve()),"options":o})
        path,_=Q.QFileDialog.getSaveFileName(app,"Save batch summary","","CSV (*.csv);;Excel (*.xlsx)")
        if not path:return
        def calculate(stop):
            def rows():
                for spec in specs:
                    if stop():raise InterruptedError("Cancelled")
                    for c in dw.load_workspace([spec],stop):
                        if stop():raise InterruptedError("Cancelled")
                        d=describe(c.y)
                        yield (Path(spec["path"]).name,c.name,c.unit,d.get("Valid"),d.get("Min"),d.get("Max"),d.get("Mean"),d.get("RMS"),d.get("Std Dev"))
            export_table(path,["Recording","Channel","Unit","Valid","Min","Max","Mean","RMS","Sample SD"],rows())
        job(app,"Batch statistical report",calculate);app.audit("Batch summary exported")
    except Exception as exc:warn(app,"Batch report",exc)


def recording_editor(app):
    """Explicit alignment and bounded merge/split of channels, without altering source files."""
    if not app.permitted("Modify analysis settings"):return
    d=Q.QDialog(app);d.setWindowTitle("Recording alignment / merge / split");d.resize(1000,570);l=Q.QVBoxLayout(d)
    l.addWidget(ui().label("Recording operations","heading"))
    l.addWidget(ui().label("Create new channels only. For alignment, explicitly confirm the offset (added to B time). No automatic synchronization or anti-alias downsampling.","status"))
    r=theme.AdaptiveRow();l.addLayout(r);a=ui().field(r,"CHANNEL A",ui().combo(app.names()));b=ui().field(r,"CHANNEL B",ui().combo(app.names(),1))
    rr=theme.AdaptiveRow();l.addLayout(rr);offset=ui().field(rr,"B CLOCK OFFSET (seconds)",ui().number(0));index=ui().field(rr,"SPLIT A AT SAMPLE INDEX",ui().number(1,1,dw.MAX_SAMPLES,1,True))
    status=ui().label("","status");l.addWidget(status)
    def apply(kind):
        try:
            x=app.data[a.currentIndex()];y=app.data[b.currentIndex()]
            if kind=="align":
                if Q.QMessageBox.question(d,"Confirm alignment","The entered offset is an operator assumption, not verified hardware synchronization. Continue?")!=Q.QMessageBox.StandardButton.Yes:return
                added=job(app,"Align recordings",lambda stop:ro.align_recordings(x,y,offset_value))
            elif kind=="split":added=ro.split_channel(x,int(index.value()))
            else:added=[ro.concatenate_channels(x,y)]
            if len(app.data)+len(added)>dw.MAX_CHANNELS or sum(len(c.y) for c in [*app.data,*added])>dw.MAX_SAMPLES:raise ValueError("Working set limit exceeded")
            names=set(app.names())
            for c in added:
                base=c.name;k=2
                while c.name in names:c.name=f"{base} [{k}]";k+=1
                names.add(c.name)
            original=len(app.data);app.data=[*app.data,*added];app.selected=set(range(original,len(app.data)));app.dataset_changed();app.show_page(2);app.audit("Recording operation",kind);d.accept()
        except Exception as exc:status.setText(str(exc))
    def align():
        nonlocal offset_value
        offset_value=offset.value();apply("align")
    offset_value=0.
    r=Q.QHBoxLayout();l.addLayout(r)
    r.addWidget(ui().btn("Align overlapping recordings",align,"primary"));r.addWidget(ui().btn("Split channel A",lambda:apply("split")));r.addWidget(ui().btn("Merge A then B",lambda:apply("merge")));r.addWidget(ui().btn("Close",d.accept));l.addStretch();d.exec()

def operating_map(app):
    if not app.permitted("Modify analysis settings"):return
    d=Q.QDialog(app);d.setWindowTitle("Efficiency operating map");d.resize(1200,820);l=Q.QVBoxLayout(d);l.addWidget(ui().label("Speed × Torque · power-weighted efficiency","heading"))
    rr=theme.AdaptiveRow();l.addLayout(rr);selectors=[ui().field(rr,n,ui().combo(app.names(),i)) for i,n in enumerate(("Speed rpm","Torque Nm","Input kW","Output kW"))]
    rr=theme.AdaptiveRow();l.addLayout(rr);bins=ui().field(rr,"Bins per axis",ui().number(16,2,64,1,True));minimum=ui().field(rr,"Minimum input kW",ui().number(.01,.0001,1e9,.01));count=ui().field(rr,"Minimum samples per bin",ui().number(3,1,100000,1,True))
    p=ui().plot(460);l.addWidget(p,1);p.setLabel("left","Torque",units="Nm");p.setLabel("bottom","Speed",units="rpm")
    status=ui().label("Select calibrated inputs. Positive motoring flow only; each occupied cell is 100 × sum(output kW) / sum(input kW). Values above 100% are not clipped.","status");l.addWidget(status);last=[]
    def run():
        try:
            cs=[app.data[x.currentIndex()] for x in selectors];n=int(bins.value());m=minimum.value();k=int(count.value())
            xe,ye,z,counts=job(app,"Operating map",lambda stop:ro.efficiency_map(*cs,n,m,k));p.clear();last.clear()
            img=pg.ImageItem(z.T,axisOrder="row-major");p.addItem(img);img.setRect(C.QRectF(xe[0],ye[0],xe[-1]-xe[0],ye[-1]-ye[0]));img.setLevels((0,100));img.setLookupTable(pg.colormap.get("viridis").getLookupTable());p.enableAutoRange()
            last.extend((xe[i],xe[i+1],ye[j],ye[j+1],int(counts[i,j]),z[i,j]) for i in range(len(xe)-1) for j in range(len(ye)-1))
            status.setText(f"{np.isfinite(z).sum()} populated bins · display color scale 0–100%; exported results retain actual values.")
        except Exception as exc:status.setText(str(exc));p.clear();last.clear()
    bar=Q.QHBoxLayout();l.addLayout(bar);bar.addWidget(ui().btn("Calculate map",run,"primary"));bar.addWidget(ui().btn("Export bins CSV / Excel",lambda:app.do_export(["RPM low","RPM high","Nm low","Nm high","Count","Efficiency %"],last) if last else None));bar.addWidget(ui().btn("Close",d.accept));d.exec()


class ToolCatalog(Q.QDialog):
    """Visible native launcher; permissions are explained, not silently hidden."""
    def __init__(self,app):
        super().__init__(app);self.app=app;self.chosen=None
        self.setWindowTitle("Extended Tools");self.resize(850,720);self.setMinimumSize(620,460)
        outer=Q.QVBoxLayout(self);outer.setContentsMargins(22,18,22,18);outer.setSpacing(12)
        outer.addWidget(ui().label("EXTENDED ENGINEERING WORKSPACE","micro"))
        outer.addWidget(ui().label("Choose a tool","heading"))
        outer.addWidget(ui().label("Demo mode: explore engineering and graph tools with sample data. File import, saved recordings and live capture require sign-in." if app.session.demo else "Choose a recording, engineering, graph or reporting operation.","sub"))
        sc=Q.QScrollArea();sc.setWidgetResizable(True);outer.addWidget(sc,1)
        content=Q.QWidget();content.setObjectName("page");sc.setWidget(content);v=Q.QVBoxLayout(content);v.setSpacing(12)
        entries=[
            ("Recordings & workspace",[
                ("Open multiple recordings","Import TDMS, CSV, TXT or Excel.",lambda:open_recordings(app),("Open data files",)),
                ("Append recordings","Add files to an existing file-backed workspace.",lambda:open_recordings(app,True),("Open data files",)),
                ("Large TDMS range browser","Inspect groups and stream whole-channel statistics.",lambda:range_browser(app),("Open data files",)),
                ("Save workspace","Save file references, selections and colors.",lambda:save_workspace(app),("Open data files","Export data & reports")),
                ("Restore workspace","Open a previously saved workspace.",lambda:restore_workspace(app),("Open data files",)),
            ]),
            ("Engineering & graph studio",[
                ("Extended engineering workstation","Mechanical, electrical, vibration and mathematical tools.",lambda:EngineeringDialog(app).exec(),("Advanced diagnostics","Modify analysis settings")),
                ("Independent-axis graph studio","Two engineering axes, annotations and PNG export.",lambda:graph_studio(app),("View trends & statistics",)),
                ("Align / split / merge recordings","Create new channels without changing source files.",lambda:recording_editor(app),("Modify analysis settings",)),
                ("Speed-torque efficiency map","Power-weighted operating-point analysis.",lambda:operating_map(app),("Modify analysis settings","Advanced diagnostics")),
            ]),
            ("Reporting & LabVIEW",[
                ("Batch statistical report","Summarize a collection of recordings.",lambda:batch_summary(app),("Open data files","Export data & reports")),
                ("LabVIEW local TCP / UDP capture","Receive measurement frames on localhost.",lambda:capture_dialog(app),("Open data files","Modify analysis settings")),
                ("Export all-channel statistical summary","Save measurement statistics.",lambda:app.do_export(["Channel","Unit","Samples","Min","Max","Mean","RMS"],((c.name,c.unit,len(c.y),d.get("Min"),d.get("Max"),d.get("Mean"),d.get("RMS")) for c in app.data for d in [describe(c.y)])),("Export data & reports",)),
            ])
        ]
        self.tool_buttons={}
        for section,items in entries:
            card,cl=ui().frame();v.addWidget(card);ui().card_title(cl,section)
            for title,desc,callback,keys in items:
                allowed=all(app.permitted(k) for k in keys)
                text=title if allowed else title+(" · Sign in" if app.session.demo else " · Restricted")
                button=ui().btn(text,lambda checked=False,cb=callback,ks=keys:self.select(cb,ks))
                button.setObjectName("tool");button.setMinimumHeight(40)
                button.setToolTip(desc if allowed else desc+" Account permission required.")
                button.setEnabled(allowed or app.session.demo);self.tool_buttons[title]=button
                cl.addWidget(button);cl.addWidget(ui().label(desc,"sub"))
        v.addStretch(1);outer.addWidget(ui().btn("Close",self.reject))
    def select(self,callback,keys):
        self.chosen=(callback,keys);self.accept()

def open_tool_catalog(app):
    dlg=ToolCatalog(app)
    if dlg.exec()!=Q.QDialog.DialogCode.Accepted or dlg.chosen is None:return
    callback,keys=dlg.chosen
    if all(app.ensure_access(k) for k in keys):callback()
