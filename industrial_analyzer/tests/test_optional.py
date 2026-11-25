import os
import numpy as np
import pytest
from engine import load

def test_tdms(tmp_path):
    td=pytest.importorskip('nptdms')
    p=tmp_path/'fixture.tdms'
    with td.TdmsWriter(p) as w:
        w.write_segment([td.ChannelObject('Motor','Speed',np.array([1.,2.,3.]),properties={'wf_increment':0.1,'wf_start_offset':0.,'unit_string':'rpm'})])
    c=load(p)[0]; assert c.name=='Motor/Speed'; assert c.unit=='rpm'; assert c.rate()==pytest.approx(10)

def test_gui():
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    qt=pytest.importorskip('PySide6.QtWidgets'); pytest.importorskip('pyqtgraph')
    from main import App, PAGES
    app=qt.QApplication.instance() or qt.QApplication([])
    w=App()
    for i in range(len(PAGES)):
        w.show_page(i); app.processEvents(); assert w.title.text()==PAGES[i]
    w.close()

def test_rust():
    n=pytest.importorskip('analyzer_native'); assert n.bucket_extrema([4.,1.,9.,2.],4)==[(1,1.),(2,9.)]
