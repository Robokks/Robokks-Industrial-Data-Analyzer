"""Account management interaction tests, using a temporary account database."""
import os
from pathlib import Path

def test_security_center_create_user_button(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
    from PySide6 import QtWidgets as Q, QtCore as C
    from access import AccessStore
    from v12_ui import Desktop, STYLE
    import ui_theme as theme
    app=Q.QApplication.instance() or Q.QApplication([])
    theme.apply(app,STYLE,"dark")
    store=AccessStore(tmp_path/"accounts.sqlite3")
    admin=store.setup("qa_admin","Temporary QA password")
    win=Desktop(store,admin);win.show();app.processEvents()
    errors=[];done=[]
    def exercise():
        d=app.activeModalWidget()
        try:
            assert isinstance(d,Q.QDialog) and d.windowTitle()=="Workspace Security Center"
            name=d.findChild(Q.QLineEdit,"newUserName")
            pw=d.findChild(Q.QLineEdit,"newUserPassword")
            confirm=d.findChild(Q.QLineEdit,"newUserConfirm")
            role=d.findChild(Q.QComboBox,"newUserRole")
            feedback=d.findChild(Q.QLabel,"newUserFeedback")
            create=next(b for b in d.findChildren(Q.QPushButton) if b.text()=="Create user")
            name.setText("engineer01");role.setCurrentText("Engineer")
            pw.setText("short");confirm.setText("short");create.click()
            assert "12" in feedback.text()
            pw.setText("Temporary engineer password");confirm.setText("Different password");create.click()
            assert "do not match" in feedback.text()
            confirm.setText(pw.text());create.click()
            assert "User created successfully" in feedback.text()
            assert store.login("engineer01","Temporary engineer password").role=="Engineer"
            name.setText("ENGINEER01");pw.setText("Temporary engineer password");confirm.setText(pw.text());create.click()
            assert "already exists" in feedback.text()
            output=Path("ui_review");output.mkdir(exist_ok=True)
            assert d.grab().save(str(output/"account-creation-validation.png"))
            done.append(True)
        except BaseException as exc:errors.append(exc)
        finally:
            if isinstance(d,Q.QDialog):d.accept()
    try:
        C.QTimer.singleShot(0,exercise)
        win.account_btn.click()
        assert not errors,errors
        assert done
        assert any(row[0]=="engineer01" for row in store.users(admin))
    finally:
        win.idle.stop();win.layout_timer.stop();app.removeEventFilter(win);win.close();app.processEvents();store.close()
