"""Executable smoke checks using temporary accounts and generated measurement files.

The real desktop buttons and modal dialogs are exercised. Only file-picker paths
and import options are supplied automatically. No production credentials/data used.
"""
import json
import tempfile
import time
import traceback
from pathlib import Path
from unittest.mock import patch
from PySide6 import QtCore as C, QtWidgets as Q
import pyqtgraph as pg
from access import AccessStore, Session

def require(condition,detail):
    if not condition:raise RuntimeError(str(detail))

def exercise(win,app,store,root):
    from v12_ui import Login
    from extra_ui import ToolCatalog, EngineeringDialog, job
    import extra_ui
    import ui_theme as theme
    result={}
    # Demo restriction must explain itself, not dead-end. Test cancellation first.
    def cancel_login():
        dlg=app.activeModalWidget()
        if isinstance(dlg,Login):dlg.reject()
    require(win.open_btn.isEnabled(),"Open Data button disabled in demo")
    C.QTimer.singleShot(0,cancel_login)
    win.open_btn.click()
    require(win.session.demo and win.source=="Telegram_Demo_100_Parameters","Cancelling login changed demo session")
    result["demo_cancel"]="pass"

    source=root/"smoke.csv";source.write_text("Time,Speed,Torque\n0,1500,20\n0.1,1600,21\n0.2,1700,22\n",encoding="utf-8")
    errors=[]
    def message(*args,**kwargs):
        errors.append(str(args[2] if len(args)>2 else args))
        return Q.QMessageBox.StandardButton.Ok
    def submit_login():
        dlg=app.activeModalWidget()
        if isinstance(dlg,Login):
            dlg.user.setText("smoke_admin")
            dlg.pw.setText("Temporary QA password")
            dlg.confirm.setText("Temporary QA password")
            dlg.submit()
    with patch.object(Q.QFileDialog,"getOpenFileNames",return_value=([str(source)],"CSV")),patch.object(extra_ui,"import_options",return_value={"delimiter":",","time_column":"Time"}),patch.object(Q.QMessageBox,"warning",side_effect=message):
        C.QTimer.singleShot(0,submit_login)
        win.open_btn.click()
    require(not errors,errors)
    require(not win.session.demo and win.session.role=="Administrator","Sign-in did not create administrator session")
    require(len(win.data)==2 and win.data[0].name.endswith("/Speed"),"CSV import did not replace demo data")
    require(list(win.data[0].y)==[1500.,1600.,1700.],"Imported values differ")
    result["open_data"]="pass"

    # Test that clicking Extended Tools displays the real catalog and launches the real
    # engineering dialog. A timer observes both modal dialogs and drives their buttons.
    seen=[]
    timer=C.QTimer();timer.setInterval(25);deadline=time.monotonic()+8
    def drive():
        dlg=app.activeModalWidget()
        if isinstance(dlg,ToolCatalog) and "catalog" not in seen:
            seen.append("catalog")
            dlg.tool_buttons["Extended engineering workstation"].click()
        elif isinstance(dlg,EngineeringDialog) and "engineering" not in seen:
            seen.append("engineering");dlg.accept()
        elif time.monotonic()>deadline:
            if isinstance(dlg,Q.QDialog):dlg.reject()
    timer.timeout.connect(drive);timer.start()
    try:
        with patch.object(Q.QMessageBox,"warning",side_effect=message):
            win.extra_btn.click()
    finally:timer.stop()
    require(seen==["catalog","engineering"],seen)
    require(not errors,errors)
    result["extended_tools"]="pass"
    for _ in range(5):require(job(win,"Fast background job",lambda stop:42)==42,"Background worker failed")
    result["background_jobs"]="pass"

    # Load all pages and then toggle with populated page cache.
    win.reset()
    for i in range(9):win.show_page(i);app.processEvents()
    durations=[]
    for mode in ("Light","Dark","Light","Dark"):
        t=time.monotonic();win.theme_selector.setCurrentText(mode);app.processEvents()
        durations.append(round(time.monotonic()-t,3))
        require(theme.MODE==mode.lower(),"Theme selector did not apply mode")
        require(durations[-1]<10,("Theme switching exceeds ten seconds",durations))
        for i in range(9):
            win.show_page(i);app.processEvents()
            page=win.pages[i]
            for p in page.findChildren(pg.PlotWidget):
                if p.isVisibleTo(page):
                    require(p.backgroundBrush().color().name()==theme.colors()["plot"],(mode,i,"plot background"))
                    require(p.getAxis("left").textPen().color().name()==theme.colors()["axis"],(mode,i,"axis color"))
    result["theme"]="pass";result["theme_switch_seconds"]=durations
    return result

def run_smoke(report):
    from v12_ui import Desktop,STYLE
    import ui_theme as theme
    output={"status":"failed"}
    app=Q.QApplication.instance() or Q.QApplication(["IndustrialAnalyzerSmoke"])
    with tempfile.TemporaryDirectory(prefix="analyzer-smoke-") as temp:
        root=Path(temp)
        C.QSettings.setDefaultFormat(C.QSettings.Format.IniFormat)
        C.QSettings.setPath(C.QSettings.Format.IniFormat,C.QSettings.Scope.UserScope,temp)
        theme.apply(app,STYLE,"dark")
        store=AccessStore(root/"accounts.sqlite3");win=None
        try:
            win=Desktop(store,Session("Demo Engineer","Administrator",True));win.resize(1440,900);win.show();app.processEvents()
            output.update(exercise(win,app,store,root));output["status"]="passed"
        except Exception:
            output["error"]=traceback.format_exc()
        finally:
            if win is not None:
                win.idle.stop();win.layout_timer.stop();app.removeEventFilter(win);win.close();app.processEvents()
            store.close()
    Path(report).write_text(json.dumps(output,indent=2),encoding="utf-8")
    return 0 if output["status"]=="passed" else 1
