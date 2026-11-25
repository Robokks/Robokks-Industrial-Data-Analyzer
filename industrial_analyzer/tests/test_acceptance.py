"""Requirements-based acceptance tests on native Qt, with actual screenshot evidence."""
import os
from pathlib import Path
import socket
import threading
import time
import json
import numpy as np
import pytest
from engine import Channel, paired
from recording_ops import align_recordings,split_channel,concatenate_channels,efficiency_map
from live_capture import capture

def ch(name,values,t,unit="",clock="same"):
    return Channel(name,np.asarray(values,dtype=float),np.asarray(t,dtype=float),unit,"s",{"clock_id":clock})

def test_fr_recording_alignment_split_merge():
    a=ch("A",[10,20,30,40],[0,1,2,3],"Nm","A")
    b=ch("B",[11,21,31,41],[2,3,4,5],"Nm","B")
    with pytest.raises(ValueError):paired(a,b)
    x,y=align_recordings(a,b,-2)
    assert np.array_equal(x.t,y.t)
    assert np.array_equal(paired(x,y)[1],b.y)
    assert np.array_equal(a.t,[0,1,2,3])
    first,second=split_channel(a,2)
    merged=concatenate_channels(first,second)
    assert np.array_equal(merged.y,a.y) and np.array_equal(merged.t,a.t)
    with pytest.raises(ValueError):concatenate_channels(second,first)
    with pytest.raises(ValueError):align_recordings(a,b,100)

def test_fr_efficiency_map():
    t=np.arange(12);a=ch("speed",np.tile([1000,2000],6),t)
    b=ch("torque",np.repeat([10,20],6),t)
    pin=ch("input",np.full(12,10.),t);pout=ch("output",np.full(12,8.),t)
    x,y,z,n=efficiency_map(a,b,pin,pout,2,.01,3)
    assert n.sum()==12 and np.isfinite(z).sum()==4
    assert np.allclose(z[np.isfinite(z)],80)

@pytest.mark.parametrize("proto",["TCP","UDP"])
def test_fr_loopback_capture(proto):
    # No remote traffic, real socket I/O. Retry startup to avoid race.
    kind=socket.SOCK_STREAM if proto=="TCP" else socket.SOCK_DGRAM
    with socket.socket(socket.AF_INET,kind) as sock:
        sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
    result=[]
    def run():
        try:result.append(capture(port,3,proto))
        except Exception as exc:result.append(exc)
    thread=threading.Thread(target=run);thread.start()
    try:
        time.sleep(.25)
        with socket.socket(socket.AF_INET,kind) as client:
            client.settimeout(.3)
            if proto=="TCP":
                for i in range(10):
                    try:client.connect(("127.0.0.1",port));break
                    except OSError:time.sleep(.05)
                else:pytest.fail("Loopback listener did not start")
            for i in range(4):
                frame=json.dumps({"t":i*.1,"values":{"Speed":1500+i,"Torque":20}}).encode()
                if proto=="TCP":client.sendall(frame+b"\n")
                else:client.sendto(frame,("127.0.0.1",port));time.sleep(.03)
    finally:thread.join(6)
    assert not thread.is_alive()
    assert result and not isinstance(result[0],Exception),result
    channels,rejected=result[0];assert rejected==0
    assert {c.name for c in channels}=={"Speed","Torque"}
    assert len(channels[0].y)==4

@pytest.fixture
def desktop(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
    qt=pytest.importorskip("PySide6.QtWidgets")
    pytest.importorskip("pyqtgraph")
    from access import AccessStore,Session
    from v12_ui import Desktop,STYLE
    app=qt.QApplication.instance() or qt.QApplication([])
    app.setStyleSheet(STYLE)
    store=AccessStore(tmp_path/"acceptance.sqlite3")
    win=Desktop(store,Session("Demo Engineer","Administrator",True))
    win.resize(1440,900);win.show();app.processEvents()
    try:yield app,win,store,qt
    finally:
        win.idle.stop();app.removeEventFilter(win);win.close();app.processEvents();store.close()

def save_widget(widget,name):
    p=Path("ui_review");p.mkdir(exist_ok=True)
    pm=widget.grab()
    assert not pm.isNull() and pm.width()>100 and pm.height()>100
    assert pm.save(str(p/name))

def click_text(root,qt,text):
    matches=[b for b in root.findChildren(qt.QPushButton) if b.text()==text]
    assert len(matches)==1,text
    assert matches[0].isEnabled(),text
    matches[0].click()

def test_fr_gui_search_selection_cursor_report(desktop,tmp_path,monkeypatch):
    app,win,store,qt=desktop
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    win.nav[1].click();app.processEvents();page=win.pages[1]
    search=next(x for x in page.findChildren(qt.QLineEdit) if "Search" in x.placeholderText())
    QTest.keyClicks(search,"Parameter 042");app.processEvents()
    table=page.findChild(qt.QTableWidget)
    assert table.rowCount()==1 and table.item(0,2).text()=="Parameter 042"
    click_text(page,qt,"Clear selection");assert not win.selected
    table.item(0,0).setCheckState(Qt.CheckState.Checked);assert win.selected=={42}
    save_widget(win,"acceptance-explorer-filter.png")
    win.nav[2].click();app.processEvents();page=win.pages[2]
    dual=next(x for x in page.findChildren(qt.QCheckBox) if "Dual" in x.text())
    QTest.mouseClick(dual,Qt.MouseButton.LeftButton);app.processEvents();assert dual.isChecked()
    measure=next(t for t in page.findChildren(qt.QTableWidget) if t.columnCount()==6)
    assert measure.rowCount()==1 and measure.item(0,0).text()=="Parameter 042"
    mode=next(x for x in page.findChildren(qt.QComboBox) if x.itemText(0)=="Normalized (%)")
    mode.setCurrentIndex(1);app.processEvents();assert mode.currentIndex()==1
    win.scroll.ensureWidgetVisible(measure);app.processEvents();save_widget(win,"acceptance-cursor-measurements.png")
    win.nav[8].click();app.processEvents();page=win.pages[8]
    click_text(page,qt,"Generate Summary");edit=page.findChild(qt.QPlainTextEdit)
    assert "Parameter 042" in edit.toPlainText()
    pdf=tmp_path/"report.pdf"
    monkeypatch.setattr(qt.QFileDialog,"getSaveFileName",lambda *args,**kwargs:(str(pdf),"PDF (*.pdf)"))
    click_text(page,qt,"Download PDF report")
    assert pdf.read_bytes().startswith(b"%PDF")
    save_widget(win,"acceptance-report.png")

def test_fr_gui_login_submit(desktop):
    app,win,store,qt=desktop
    from v12_ui import Login
    d=Login(store);d.show();app.processEvents();save_widget(d,"acceptance-first-run.png")
    d.user.setText("qa_admin");d.pw.setText("qa secure password");d.confirm.setText("qa secure password")
    d.submit();assert d.session and d.session.role=="Administrator"
    d.close()
    d=Login(store);d.show();app.processEvents();save_widget(d,"acceptance-sign-in.png")
    d.user.setText("qa_admin");d.pw.setText("qa secure password");d.submit()
    assert d.session.username=="qa_admin";d.close()

def test_fr_gui_extended_tools(desktop):
    app,win,store,qt=desktop
    from extra_ui import EngineeringDialog,TOOLS
    t=np.arange(2048)/1000.
    signal=np.sin(2*np.pi*50*t)+.1*np.sin(2*np.pi*150*t)
    win.data=[ch("Signal",signal,t),ch("Speed",np.full(len(t),1800.),t),ch("Torque",np.full(len(t),50.),t),ch("Power in",np.full(len(t),10.),t),ch("Power out",np.full(len(t),8.),t)]
    win.selected={0,1,2,3};win.dataset_changed();win.show_page(0)
    d=EngineeringDialog(win);d.show();app.processEvents()
    choices={
        "Mechanical power (rpm × Nm)":([1,2],[]),
        "Efficiency (kW in/out)":([3,4],[]),
        "Loss torque referred to shaft":([1,3,4],[]),
        "Torque-speed XY map":([1,2],[]),
        "Harmonics and THD":([0],[50,5]),
        "Order tracking (rpm channel)":([0,1],[128]),
        "Envelope spectrum / crest factor":([0],[40,200]),
        "Resample (linear interpolation)":([0],[2000]),
    }
    try:
        for i,name in enumerate(TOOLS):
            d.tool.setCurrentIndex(i);app.processEvents()
            ids,params=choices.get(name,([],[]))
            for w,j in zip(d.channels,ids):w.setCurrentIndex(j)
            for w,x in zip(d.params,params):w.setValue(x)
            d.calculate();app.processEvents()
            assert "Calculation complete" in d.status.text(),(name,d.status.text())
            save_widget(d,f"acceptance-extended-{i:02d}.png")
    finally:d.close()
