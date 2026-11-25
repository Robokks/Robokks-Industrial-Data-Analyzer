import numpy as np
import pytest
from engine import Channel, analyze, demo, describe, load, paired, events
from safe_export import safe_cell, export_table

@pytest.mark.parametrize('tool,p,q,r',[
('Frequency Spectrum',512,1,0),('Signal Conditioning',11,1,0),('Anomaly Detection',3,0,0),('Lag & Correlation',40,0,0),('Data Quality',3,0,0),('Transients',30,0,0),('Envelope & Peaks',5,0,0),('Autocorrelation',150,0,0),('Band Energy',2,1,0),('Change Detection',30,5,0),('Distribution',24,0,0),('Process Capability',25,75,50),('State & Events',50,0,0),('Relationships',0,0,0),('Stability & SPC',25,3,0),('Thresholds',25,75,0),('Comparison',0,0,0),('Statistics',24,0,0),('Rolling Statistics',25,0,0),('Quality & Outliers',1.5,0,0),('Segment Comparison',0,0,0)])
def test_tools(tool,p,q,r):
    a,b=demo()[:2]; curves,metrics,rows=analyze(tool,a,b,p,q,r); assert curves; assert all(len(x)==len(y) for x,y,_ in curves)

def test_fft():
    t=np.arange(1000)/1000; a=Channel('s',3*np.sin(2*np.pi*50*t),t,time_unit='s'); _,m,_=analyze('Frequency Spectrum',a,p=1000,q=0); assert m['Peak Hz']==pytest.approx(50); assert m['Peak amplitude']==pytest.approx(3)

def test_stats():
    d=describe(np.array([1,2,3,np.nan])); assert d['Mean']==2; assert d['Std Dev']==1; assert d['Missing']==1

def test_events():
    assert events(np.arange(5),np.array([0,1,1,0,1],bool))==[(1,2,1,2,1),(4,4,4,4,0)]

def test_alignment():
    a,b=demo()[:2]; b.t=b.t+1; assert pytest.raises(ValueError,paired,a,b)

def test_invalid_fft():
    a=Channel('s',[1,2,3],[0,1,3],time_unit='s'); assert pytest.raises(ValueError,analyze,'Frequency Spectrum',a,p=3)

@pytest.mark.parametrize('ext,sep',[('csv',','),('txt','\t')])
def test_text(tmp_path,ext,sep):
    p=tmp_path/('data.'+ext); p.write_text(f't{sep}v\n0{sep}10\n1{sep}20\n'); a=load(p,delimiter=sep,time_column='t')[0]; assert list(a.y)==[10,20]; assert a.rate()==1

def test_excel(tmp_path):
    p=tmp_path/'data.xlsx'; export_table(p,['v'],[[1],[2]]); assert list(load(p)[0].y)==[1,2]

@pytest.mark.parametrize('s',['=1+1','  +1','@SUM(A1)','-1+2','\tfoo'])
def test_formula(s): assert safe_cell(s).startswith("'")

def test_export(tmp_path):
    p=tmp_path/'x.csv'; export_table(p,['=bad'],[['=bad'],[-1]]); assert "'=bad" in p.read_text(); assert '-1' in p.read_text()

def test_invalid_params():
    assert pytest.raises(ValueError,analyze,'Distribution',demo()[0],p=10000)

def test_unsupported(tmp_path): assert pytest.raises(ValueError,load,tmp_path/'x.exe')
