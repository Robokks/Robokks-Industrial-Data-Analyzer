import os
from pathlib import Path
import numpy as np
import pytest
from engine import Channel, paired
import engineering_tools as et
import data_workspace as dw
from live_capture import parse_frame

def channel(y,rate=1000,unit=""):
    y=np.asarray(y,dtype=float);return Channel("x",y,np.arange(len(y))/rate,unit,"s")

def test_power_efficiency_loss():
    speed=channel([1500,1500],unit="rpm");torque=channel([100,100],unit="Nm")
    p=et.mechanical_power(speed,torque)
    assert p==pytest.approx([5*np.pi,5*np.pi])
    assert et.efficiency(channel([10,0]),channel([8,0]))[0]==80
    assert np.isnan(et.efficiency(channel([10,0]),channel([8,0]))[1])
    assert et.loss_torque(speed,channel([10,10]),channel([8,8]))==pytest.approx([40/np.pi]*2)

def test_electrical():
    t=np.arange(1000)/1000;v=channel(230*np.sqrt(2)*np.sin(2*np.pi*50*t));i=channel(10*np.sqrt(2)*np.sin(2*np.pi*50*t-np.pi/3))
    m,_=et.electrical(v,i)
    assert m["Voltage RMS (V)"]==pytest.approx(230)
    assert m["True power factor"]==pytest.approx(.5)
    m,_=et.three_phase([v,i,v,i,v,i]);assert m["Total real power (W)"]==pytest.approx(3450)

def test_harmonic_thd():
    t=np.arange(2000)/1000
    c=channel(np.sin(2*np.pi*50*t)+.1*np.sin(2*np.pi*150*t))
    f,r,m=et.harmonic_metrics(c,50,5)
    assert m["THD (% of fundamental)"]==pytest.approx(10,abs=1e-7)

def test_filters_integration_derivative():
    t=np.arange(2000)/1000;c=channel(np.sin(2*np.pi*5*t)+np.sin(2*np.pi*150*t))
    lp=et.filter_signal(c,20)
    assert np.std(lp[100:-100]-np.sin(2*np.pi*5*t[100:-100]))<.01
    assert et.integrate_signal(channel(np.ones(1000)))[-1]==pytest.approx(.999)
    assert et.differentiate(channel(t))==pytest.approx(np.ones(len(t)))

def test_order_and_bearings():
    t=np.arange(4000)/1000
    x,y=et.order_spectrum(channel(np.sin(2*np.pi*60*t)),channel(np.full(len(t),1800)))
    assert x[np.argmax(y)]==pytest.approx(2,abs=.02)
    m=et.bearing_frequencies(1800,8,10,50)
    assert m["BPFO Hz"]==pytest.approx(96)
    assert m["BPFI Hz"]==pytest.approx(144)

def test_envelope_and_spectrogram():
    t=np.arange(2000)/1000;c=channel((1+.5*np.sin(2*np.pi*10*t))*np.sin(2*np.pi*200*t))
    f,p,_=et.envelope_spectrum(c,150,250)
    assert f[np.argmax(p)]==pytest.approx(10,abs=1)
    t,f,s=et.spectrogram(c,128);assert s.shape==(len(f),len(t))

@pytest.mark.parametrize("bad",["A.__class__","A[0]","open('x')","A**100","(lambda:1)()","[x for x in A]"])
def test_expression_rejects_unsupported(bad):
    with pytest.raises(ValueError):et.expression(bad,[channel([1,2]),channel([2,3])])

def test_expression_and_comparison():
    a=channel([1,2,3]);b=channel([2,3,4])
    assert et.expression("sqrt(A*A)+B/2",[a,b])==pytest.approx([2,3.5,5])
    m,d=et.comparison_metrics(a,b,1);assert m["RMSE"]==1 and m["Within tolerance (%)"]==100
    assert len(et.resample(a,2000).y)==5
    with pytest.raises(ValueError):et.resample(a,500)

def test_tdms_range_and_stream(tmp_path):
    td=pytest.importorskip("nptdms");p=tmp_path/"fixture.tdms";y=np.arange(600000,dtype=float);y[7]=np.nan
    with td.TdmsWriter(p) as w:w.write_segment([td.ChannelObject("M","Torque",y,properties={"wf_increment":.1,"wf_start_offset":2.,"unit_string":"Nm"})])
    assert dw.catalog(p)[0][2]==len(y)
    c=dw.tdms_range(p,"M","Torque",20,30)
    assert c.y==pytest.approx(y[20:30]);assert c.t[0]==pytest.approx(4)
    d=dw.stream_stats(p,"M","Torque")
    assert d["Valid"]==len(y)-1 and d["Missing"]==1
    assert d["Mean"]==pytest.approx(np.nanmean(y))
    assert d["Population SD"]==pytest.approx(np.nanstd(y))
    with pytest.raises(InterruptedError):dw.stream_stats(p,"M","Torque",lambda:True)

def test_workspace_multiple_files(tmp_path):
    a=tmp_path/"a.csv";b=tmp_path/"b.csv"
    a.write_text("t,x\n0,2\n1,3\n",encoding="utf-8");b.write_text("t,x\n0,4\n1,5\n",encoding="utf-8")
    specs=[{"path":str(p),"options":{"time_column":"t","delimiter":","}} for p in (a,b)]
    data=dw.load_workspace(specs)
    assert len(data)==2 and data[0].name!=data[1].name
    with pytest.raises(ValueError):paired(*data)
    p=tmp_path/"manifest.json";dw.write_manifest(p,specs,[0,1],{0:"#58e0e0"})
    m=dw.read_manifest(p);assert m["recordings"]==specs and m["colors"]["0"]=="#58e0e0"

def test_manifest_rejects_invalid(tmp_path):
    p=tmp_path/"bad.json";p.write_text('{"version":1,"recordings":[{"path":"relative.csv"}]}')
    with pytest.raises(ValueError):dw.read_manifest(p)

@pytest.mark.parametrize("raw",[b'{"t":NaN,"values":{"x":2}}',b'{"t":0,"values":{"x":true}}',b'{"t":1,"values":{} }',b'{"t":1,"values":{"x":2},"command":"stop"}',b'invalid'])
def test_live_invalid(raw):
    with pytest.raises(ValueError):parse_frame(raw)

def test_live_frame():
    assert parse_frame(b'{"t":0.1,"values":{"RPM":1500,"Nm":20}}')==(.1,{"RPM":1500.,"Nm":20.})

def test_extended_gui(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
    qt=pytest.importorskip("PySide6.QtWidgets");pytest.importorskip("pyqtgraph")
    from access import AccessStore, Session
    from v12_ui import Desktop,STYLE
    from extra_ui import EngineeringDialog,job
    app=qt.QApplication.instance() or qt.QApplication([]);app.setStyleSheet(STYLE)
    store=AccessStore(tmp_path/"accounts.sqlite")
    win=Desktop(store,Session("Demo Engineer","Administrator",True))
    try:
        assert job(win,"Smoke test",lambda cancel:42)==42
        dlg=EngineeringDialog(win);dlg.show();app.processEvents();dlg.calculate()
        assert dlg.result is not None and dlg.result.unit=="kW",dlg.status.text()
        p=Path("ui_review");p.mkdir(exist_ok=True);assert dlg.grab().save(str(p/"extended-engineering.png"))
        dlg.close()
    finally:win.idle.stop();app.removeEventFilter(win);win.close();app.processEvents();store.close()
