import os
from pathlib import Path
import pytest
from access import AccessStore, Session

def test_account_permissions(tmp_path):
    store=AccessStore(tmp_path/"account.sqlite3")
    try:
        admin=store.setup("admin01","Strong demo password")
        assert store.login("ADMIN01","Strong demo password")==admin
        assert admin.allows("Manage users")
        with pytest.raises(PermissionError):store.setup("admin02","Strong other password")
        store.create(admin,"viewer01","Viewer test password","Viewer")
        viewer=store.login("viewer01","Viewer test password")
        assert viewer.allows("Open data files")
        assert not viewer.allows("Export data & reports")
        assert not viewer.allows("Advanced diagnostics")
        assert not Session("Demo Engineer","Administrator",True).allows("Open data files")
        with pytest.raises(PermissionError):store.create(viewer,"bad01","Not permitted password","Engineer")
        with pytest.raises(PermissionError):store.history(viewer)
        with pytest.raises(ValueError):store.toggle(admin,"admin01")
        store.change(viewer,"Viewer test password","New viewer password")
        assert store.login("viewer01","New viewer password")==viewer
        store.toggle(admin,"viewer01")
        with pytest.raises(ValueError):store.login("viewer01","New viewer password")
        assert store.history(admin)
    finally:store.close()

def test_failed_login_throttling(tmp_path):
    store=AccessStore(tmp_path/"account.sqlite3")
    try:
        store.setup("admin01","Strong demo password")
        for _ in range(5):
            with pytest.raises(ValueError,match="Invalid username"):store.login("admin01","Wrong password")
        with pytest.raises(ValueError,match="Too many"):store.login("admin01","Strong demo password")
    finally:store.close()

def test_native_reference_screens(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
    qt=pytest.importorskip("PySide6.QtWidgets")
    pytest.importorskip("pyqtgraph")
    from v12_ui import Desktop, Login, AnalysisPane, TITLES, STYLE, LAB, ADV
    app=qt.QApplication.instance() or qt.QApplication([])
    import ui_theme as theme
    theme.apply(app,STYLE,"dark")
    store=AccessStore(tmp_path/"ui.sqlite3")
    admin=store.setup("admin01","Strong demo password")
    output=Path("ui_review");output.mkdir(exist_ok=True)
    login=Login(store);login.show();app.processEvents()
    assert login.grab().save(str(output/"00-login.png"))
    login.close()
    win=Desktop(store,Session("Demo Engineer","Administrator",True));win.resize(1440,900);win.show()
    try:
        assert len(win.data)==100 and len(win.data[0].y)==600
        assert win.data[0].y[0]==25
        assert win.open_btn.isEnabled() and 'Sign in' in win.open_btn.text()
        for i,title in enumerate(TITLES):
            win.show_page(i);app.processEvents()
            assert win.title.text()==title
            assert win.grab().save(str(output/f"{i+1:02d}-page.png"))
        for page,expected in [(6,LAB),(7,ADV)]:
            win.show_page(page);app.processEvents()
            panes=win.pages[page].findChildren(AnalysisPane)
            assert {p.tool for p in panes}==set(expected)
            stack=win.pages[page].findChild(qt.QStackedWidget)
            for i in range(stack.count()):
                pane=stack.widget(i);stack.setCurrentIndex(i);pane.run();app.processEvents()
                assert "Analysis complete" in pane.status.text(), (pane.tool,pane.status.text())
                assert len(pane.plots)>=1
                assert win.grab().save(str(output/f"workbench-{page}-{i}.png"))
        win.resize(1920,1080)
        win.show_page(0);app.processEvents()
        assert win.grab().save(str(output/"overview-1920.png"))
        win.show_page(2);app.processEvents()
        assert win.grab().save(str(output/"trends-1920.png"))
        win.session=admin;win.apply_role()
        assert win.open_btn.isEnabled()
        store.create(admin,"viewer01","Viewer test password","Viewer")
        win.session=store.login("viewer01","Viewer test password");win.apply_role()
        assert not win.nav[6].isEnabled() and not win.nav[7].isEnabled()
        win.show_page(0);win.show_page(7)
        assert win.page==0
    finally:
        win.idle.stop();app.removeEventFilter(win);win.close();app.processEvents();store.close()
