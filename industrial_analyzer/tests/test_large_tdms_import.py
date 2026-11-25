"""Large TDMS automatic fallback and bounded multi-channel import."""
import os
from pathlib import Path
import numpy as np
import pytest
import data_workspace as dw
from nptdms import TdmsWriter,ChannelObject

@pytest.fixture
def recording(tmp_path):
    path=tmp_path/"large.tdms"
    with TdmsWriter(path) as w:
        w.write_segment([
            ChannelObject("Motor","Time",np.arange(30)*.1,properties={"unit_string":"s"}),
            ChannelObject("Motor","Speed",np.arange(30)+1000.,properties={"unit_string":"rpm"}),
            ChannelObject("Motor","Torque",np.arange(30)+50.,properties={"unit_string":"Nm"}),
        ])
    return path

def test_oversized_tdms_detected_before_full_read(recording,monkeypatch):
    monkeypatch.setattr(dw,"MAX_SAMPLES",20)
    def fail(*a,**kw):pytest.fail("Full import must not be attempted")
    monkeypatch.setattr(dw,"load",fail)
    with pytest.raises(dw.TdmsRangeRequired) as e:
        dw.load_workspace([{"path":str(recording)}])
    assert e.value.path==str(recording.resolve())
    assert e.value.sample_budget==20
    monkeypatch.setattr(dw,"MAX_IMPORT_BYTES",1)
    with pytest.raises(dw.TdmsRangeRequired):dw.load_workspace([{"path":str(recording)}])

def test_multichannel_exact_range_and_manifest(recording,tmp_path,monkeypatch):
    monkeypatch.setattr(dw,"MAX_SAMPLES",20)
    spec={"path":str(recording),"ranges":[["Motor","Speed",10,15],["Motor","Torque",10,15]]}
    channels=dw.load_workspace([spec])
    assert len(channels)==2
    assert list(channels[0].y)==list(np.arange(1010.,1015.))
    assert list(channels[1].y)==list(np.arange(60.,65.))
    assert channels[0].t==pytest.approx(np.arange(10,15)*.1)
    assert channels[1].time_unit=="s"
    assert channels[0].metadata["clock_id"]==channels[1].metadata["clock_id"]
    assert channels[0].metadata["source_samples"]==30
    manifest=tmp_path/"workspace.json"
    dw.write_manifest(manifest,[spec],[0,1],{})
    restored=dw.load_workspace(dw.read_manifest(manifest)["recordings"])
    assert np.array_equal(restored[0].y,channels[0].y)
    assert dw.stream_stats(recording,"Motor","Speed")["Valid"]==30
    with pytest.raises(ValueError):dw.load_workspace([{"path":str(recording),"ranges":[["Motor","Speed",0,15],["Motor","Torque",0,15]]}])
    with pytest.raises(ValueError):dw.load_workspace([{"path":str(recording),"ranges":[["Motor","Speed",0,5],["Motor","Speed",5,10]]}])
    with pytest.raises(ValueError):dw.load_workspace([{"path":str(recording),"ranges":[["Motor","Speed",29,31]]}])
    with pytest.raises(InterruptedError):dw.load_workspace([spec],lambda:True)

def test_large_tdms_open_button_automatic_dialog(recording,tmp_path,monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
    from PySide6 import QtWidgets as Q,QtCore as C
    from access import AccessStore
    from v12_ui import Desktop,STYLE
    import ui_theme as theme
    app=Q.QApplication.instance() or Q.QApplication([])
    theme.apply(app,STYLE,"dark")
    store=AccessStore(tmp_path/"accounts.sqlite3")
    win=Desktop(store,store.setup("qa_admin","Temporary QA password"));win.show();app.processEvents()
    monkeypatch.setattr(dw,"MAX_SAMPLES",20)
    errors=[];seen=[]
    monkeypatch.setattr(Q.QFileDialog,"getOpenFileNames",lambda *args,**kw:([str(recording)],"TDMS"))
    monkeypatch.setattr(Q.QMessageBox,"warning",lambda *args,**kw:errors.append(str(args[2])))
    timer=C.QTimer();timer.setInterval(25)
    def drive():
        d=app.activeModalWidget()
        if not isinstance(d,Q.QDialog) or d.windowTitle()!="Large TDMS · Select channels and range":return
        try:
            tree=d.findChild(Q.QTreeWidget,"tdmsRangeTree")
            for i in range(tree.topLevelItem(0).childCount()):
                item=tree.topLevelItem(0).child(i)
                item.setCheckState(0,C.Qt.CheckState.Unchecked if item.text(0)=="Time" else C.Qt.CheckState.Checked)
            d.findChild(Q.QLineEdit,"tdmsStartSample").setText("10")
            d.findChild(Q.QLineEdit,"tdmsStopSample").setText("25")
            button=d.findChild(Q.QPushButton,"tdmsLoadRanges")
            assert not button.isEnabled()
            d.findChild(Q.QLineEdit,"tdmsStopSample").setText("15")
            assert button.isEnabled()
            output=Path("ui_review");output.mkdir(exist_ok=True)
            assert d.grab().save(str(output/"large-tdms-range-selection.png"))
            seen.append(True);button.click()
        except BaseException as exc:errors.append(str(exc));d.reject()
    timer.timeout.connect(drive);timer.start()
    try:
        win.open_btn.click();app.processEvents()
        assert not errors,errors
        assert seen==[True]
        assert len(win.data)==2
        assert win.data[0].y==pytest.approx(np.arange(1010.,1015.))
        assert "selected TDMS ranges" in win.source
        assert len(win.recordings[0]["ranges"])==2
    finally:
        timer.stop();win.idle.stop();win.layout_timer.stop();app.removeEventFilter(win);win.close();app.processEvents();store.close()
