import numpy as np
import pytest
from pathlib import Path
from engine import Channel, load, paired
from performance import preview_indices, nearest_index, cursor_measurement
from safe_export import export_table

def test_preview_preserves_extrema_and_order():
    y=np.zeros(200000);y[23456]=9876;y[23458]=-4321
    ids=preview_indices(y,1000)
    assert len(ids)<=1000
    assert ids[0]==0 and ids[-1]==len(y)-1
    assert 23456 in ids and 23458 in ids
    assert (np.diff(ids)>0).all()

def test_preview_keeps_missing_samples():
    y=np.zeros(5000);y[100]=np.nan
    ids=preview_indices(y,1000)
    assert 100 in ids

def test_preview_rust_agrees_with_numpy():
    pytest.importorskip("analyzer_native")
    y=np.random.default_rng(42).normal(size=200123)
    assert np.array_equal(preview_indices(y,1200,"rust"),preview_indices(y,1200))

def test_cursor_measurement():
    t=np.arange(10)*.1;y=np.arange(10)*3.
    assert nearest_index(t,.24)==2
    assert nearest_index(t,-1) is None
    assert nearest_index(t,2) is None
    assert nearest_index(np.array([3.,1.,2.]),2.1,False)==2
    assert cursor_measurement(t,y,.2,.7)==pytest.approx((.5,6.,21.,15.))
    assert cursor_measurement(t,y,-1,.7) is None

def test_stream_export_atomic(tmp_path):
    p=tmp_path/"data.csv";p.write_text("existing",encoding="utf-8")
    def invalid():
        yield [1,2]
        raise ValueError("generator failure")
    with pytest.raises(ValueError,match="generator failure"):export_table(p,["a","b"],invalid())
    assert p.read_text(encoding="utf-8")=="existing"
    assert list(tmp_path.iterdir())==[p]
    export_table(p,["a","b"],((i,i*2) for i in range(30000)))
    with p.open(encoding="utf-8") as f:assert sum(1 for _ in f)==30001

def test_stream_excel_formula_and_missing(tmp_path):
    from openpyxl import load_workbook
    p=tmp_path/"data.xlsx";export_table(p,["=column","value"],[["=1+1",np.nan],[np.int64(3),np.float64(2.5)]])
    book=load_workbook(p,read_only=True)
    try:
        rows=list(book.active.values)
        assert rows[0][0]=="'=column"
        assert rows[1][0]=="'=1+1"
        assert len(rows[1])==1 or rows[1][1] is None
        assert rows[2]==(3,2.5)
    finally:book.close()

def test_tdms_timestamp_mapping_and_properties(tmp_path):
    td=pytest.importorskip("nptdms")
    p=tmp_path/"clock.tdms"
    t=np.datetime64("2025-01-01T00:00:00","ms")+np.arange(4)*np.timedelta64(100,"ms")
    with td.TdmsWriter(p) as w:
        w.write_segment([td.ChannelObject("Motor","Timestamp",t),td.ChannelObject("Motor","Speed",np.arange(4,dtype=float),properties={"unit_string":"rpm"}),td.ChannelObject("Motor","Torque",np.arange(4,dtype=float)*2,properties={"unit_string":"Nm"})])
    data=load(p);a,b=data
    assert a.rate()==pytest.approx(10)
    assert a.metadata["group"]=="Motor"
    assert a.metadata["properties"]["unit_string"]=="rpm"
    assert a.metadata["time_source"]=="Timestamp channel: Timestamp"
    assert np.array_equal(paired(a,b)[0],a.y)

def test_tdms_ambiguous_clocks_do_not_align(tmp_path):
    td=pytest.importorskip("nptdms")
    p=tmp_path/"ambiguous.tdms"
    with td.TdmsWriter(p) as w:
        w.write_segment([td.ChannelObject("G","Time",np.arange(4,dtype=float),properties={"unit_string":"s"}),td.ChannelObject("G","Timestamp",np.arange(4,dtype=float)+5,properties={"unit_string":"s"}),td.ChannelObject("G","A",np.arange(4,dtype=float)),td.ChannelObject("G","B",np.arange(4,dtype=float))])
    data={c.name:c for c in load(p)}
    assert data["G/A"].time_unit=="sample"
    with pytest.raises(ValueError,match="clock origins"):paired(data["G/A"],data["G/B"])
