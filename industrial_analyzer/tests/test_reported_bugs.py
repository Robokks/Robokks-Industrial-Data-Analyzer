"""Regression tests for the four defects reported against the packaged Windows build."""
import json
import os
from pathlib import Path
import subprocess
import sys
import numpy as np
import pytest

def test_reported_bugs_in_entrypoint(tmp_path):
    report=tmp_path/"smoke.json"
    env=dict(os.environ);env.setdefault("QT_QPA_PLATFORM","offscreen")
    result=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/"main.py"),"--self-test",str(report)],env=env,capture_output=True,text=True,timeout=150)
    assert report.exists(),(result.returncode,result.stdout,result.stderr)
    evidence=json.loads(report.read_text(encoding="utf-8"))
    assert result.returncode==0 and evidence["status"]=="passed",evidence
    for key in ("demo_cancel","open_data","extended_tools","background_jobs","theme"):assert evidence[key]=="pass"

def test_open_data_button_all_formats(tmp_path,monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
    from PySide6 import QtWidgets as Q
    from access import AccessStore
    from v12_ui import Desktop,STYLE
    import extra_ui
    import ui_theme as theme
    from openpyxl import Workbook
    from nptdms import TdmsWriter,ChannelObject
    app=Q.QApplication.instance() or Q.QApplication([])
    theme.apply(app,STYLE,"dark")
    csv=tmp_path/"recording.csv";csv.write_text("Time,Speed\n0,10\n1,20\n2,30\n",encoding="utf-8")
    txt=tmp_path/"recording.txt";txt.write_text("Time\tSpeed\n0\t10\n1\t20\n2\t30\n",encoding="utf-8")
    xlsx=tmp_path/"recording.xlsx";book=Workbook();book.active.append(["Time","Speed"])
    for i in range(3):book.active.append([i,(i+1)*10])
    book.save(xlsx);book.close()
    tdms=tmp_path/"recording.tdms"
    with TdmsWriter(tdms) as writer:
        writer.write_segment([ChannelObject("Motor","Speed",np.array([10.,20.,30.]),properties={"wf_increment":1.,"wf_start_offset":0.,"unit_string":"rpm"})])
    def options(parent,path):
        ext=Path(path).suffix
        return {} if ext==".tdms" else {"sheet":0,"time_column":"Time"} if ext==".xlsx" else {"time_column":"Time","delimiter":"\t" if ext==".txt" else ","}
    errors=[]
    monkeypatch.setattr(Q.QMessageBox,"warning",lambda *a,**kw:errors.append(str(a[2])))
    monkeypatch.setattr(extra_ui,"import_options",options)
    monkeypatch.setattr(Q.QFileDialog,"getOpenFileNames",lambda *a,**kw:([str(x) for x in (csv,txt,xlsx,tdms)],""))
    store=AccessStore(tmp_path/"accounts.sqlite3");win=Desktop(store,store.setup("qa_admin","Temporary QA password"));win.show()
    try:
        win.open_btn.click();app.processEvents()
        assert not errors,errors
        assert len(win.data)==4 and len(win.recordings)==4
        assert all(list(c.y)==[10.,20.,30.] for c in win.data)
        previous=win.data
        monkeypatch.setattr(Q.QFileDialog,"getOpenFileNames",lambda *a,**kw:([],""))
        win.open_btn.click();assert win.data is previous
        output=Path("ui_review");output.mkdir(exist_ok=True)
        assert win.grab().save(str(output/"bugfix-imported-four-formats.png"))
        catalog=extra_ui.ToolCatalog(win)
        try:
            for mode in ("Dark","Light"):
                win.theme_selector.setCurrentText(mode);catalog.show();app.processEvents()
                assert all(b.isEnabled() for b in catalog.tool_buttons.values())
                assert catalog.grab().save(str(output/f"bugfix-tool-catalog-{mode.lower()}.png"))
                catalog.hide()
        finally:catalog.close()
    finally:
        win.idle.stop();win.layout_timer.stop();app.removeEventFilter(win);win.close();app.processEvents();store.close()
        theme.apply(app,STYLE,"dark")

def test_theme_recolors_histogram_scatter_and_cursor():
    os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
    from PySide6 import QtWidgets as Q
    import pyqtgraph as pg
    from v12_ui import STYLE,plot,draw,apply_plot_theme
    import ui_theme as theme
    app=Q.QApplication.instance() or Q.QApplication([])
    theme.apply(app,STYLE,"dark")
    p=plot();p.show()
    try:
        x=np.arange(6,dtype=float);draw(p,[(x,x,"Histogram"),(x,x,"XY"),(x,x,"Trend")])
        cursor=pg.InfiniteLine(angle=90,pen=pg.mkPen("#ffbe67"),label="A");p.addItem(cursor)
        bar=next(i for i in p.plotItem.items if isinstance(i,pg.BarGraphItem))
        scatter=next(i for i in p.listDataItems() if i.name()=="XY")
        old=pg.mkBrush(bar.opts["brush"]).color().name()
        theme.apply(app,STYLE,"light");apply_plot_theme(p)
        assert p.backgroundBrush().color().name()=="#ffffff"
        assert pg.mkBrush(bar.opts["brush"]).color().name()==theme.trace_color(old)
        assert pg.mkBrush(scatter.opts["symbolBrush"]).color().name()=="#ae6006"
        assert cursor.pen.color().name()=="#ae6006"
        assert not theme.apply(app,STYLE,"light")
        theme.apply(app,STYLE,"dark");apply_plot_theme(p)
        assert p.backgroundBrush().color().name()=="#0b1726"
        assert pg.mkBrush(bar.opts["brush"]).color().name()==old or old=="#4dd9e8" and pg.mkBrush(bar.opts["brush"]).color().name()=="#58e0e0"
    finally:p.close();theme.apply(app,STYLE,"dark")
