"""Responsive native UI release checks and screenshot evidence."""
import os
from pathlib import Path
import pytest

def test_native_theme_and_responsive_layout(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
    from PySide6 import QtWidgets as Q,QtGui as G,QtCore as C
    from PySide6.QtTest import QTest
    import pyqtgraph as pg
    from access import AccessStore,Session
    from v12_ui import Desktop,STYLE,Login
    import ui_theme as theme
    app=Q.QApplication.instance() or Q.QApplication([])
    name=theme.configure_font(app)
    raw=G.QRawFont.fromFont(G.QFont(name,10))
    assert raw.isValid()
    assert all(raw.supportsCharacter(ord(c)) for c in "Industrial Analyzer 0123456789")
    theme.apply(app,STYLE,"dark")
    store=AccessStore(tmp_path/"responsive.sqlite3")
    win=Desktop(store,Session("Demo Engineer","Administrator",True));win.show()
    output=Path("ui_review");output.mkdir(exist_ok=True)
    try:
        for mode in ("Dark","Light"):
            win.theme_selector.setCurrentText(mode);app.processEvents()
            assert theme.MODE==mode.lower()
            for width,height in ((1280,800),(1440,900),(1920,1080)):
                win.resize(width,height);app.processEvents()
                for i in range(9):
                    win.show_page(i);win.reflow_page();QTest.qWait(80);app.processEvents()
                    page=win.pages[i]
                    overflow=win.scroll.horizontalScrollBar().maximum()
                    if overflow>2:
                        win.grab().save(str(output/f"FAIL-overflow-{mode.lower()}-{width}-{i+1:02d}.png"))
                        hints=[(w.objectName(),type(w).__name__,w.minimumSizeHint().width(),w.width()) for w in page.findChildren(Q.QWidget) if w.isVisibleTo(page) and w.minimumSizeHint().width()>win.scroll.viewport().width()]
                        pytest.fail(f"Horizontal overflow {overflow}: {mode} {width} page {i+1}, viewport={win.scroll.viewport().width()}, page minimum={page.minimumSizeHint().width()}, widgets={hints[:20]}")
                    for b in page.findChildren(Q.QPushButton):
                        if b.isVisibleTo(page):
                            assert b.height()>=30,(mode,width,i,b.text(),b.height())
                    for p in page.findChildren(pg.PlotWidget):
                        if p.isVisibleTo(page):
                            assert p.height()>=250 and p.width()>=240,(mode,width,i,p.size())
                    pm=win.grab();assert not pm.isNull()
                    assert pm.save(str(output/f"responsive-{mode.lower()}-{width}-{i+1:02d}.png"))
                    if i in (6,7):
                        stack=page.findChild(Q.QStackedWidget)
                        for j in range(stack.count()):
                            tabs=[b for b in page.findChildren(Q.QPushButton) if b.objectName()=="tab"]
                            tabs[j].click();win.reflow_page();QTest.qWait(50);app.processEvents()
                            assert win.scroll.horizontalScrollBar().maximum()<=2,(mode,width,i,j,win.scroll.horizontalScrollBar().maximum())
                        tabs[0].click();win.reflow_page()
            d=Login(store);d.show();app.processEvents();assert d.grab().save(str(output/f"responsive-{mode.lower()}-login.png"));d.close()
        assert win.theme_selector.currentText()=="Light"
    finally:
        win.idle.stop();win.layout_timer.stop();app.removeEventFilter(win);win.close();app.processEvents();store.close()
        theme.apply(app,STYLE,"dark")
