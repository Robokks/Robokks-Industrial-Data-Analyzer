@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -3.12 -m venv .venv
if errorlevel 1 exit /b 1
set "PY=.venv\Scripts\python.exe"
%PY% -m pip install -r requirements.txt pytest pyinstaller bandit pip-audit
if errorlevel 1 exit /b 1
%PY% -m pytest -q
if errorlevel 1 exit /b 1
%PY% -m bandit main.py engine.py safe_export.py v12_ui.py access.py
if errorlevel 1 exit /b 1
%PY% -m pip_audit
if errorlevel 1 exit /b 1
%PY% -m PyInstaller --noconfirm --clean --windowed --name IndustrialAnalyzer --collect-all pyqtgraph --collect-all nptdms --hidden-import v12_ui main.py
if errorlevel 1 exit /b 1
 echo Build output: dist\IndustrialAnalyzer\IndustrialAnalyzer.exe
