@echo off
REM Launch the Audio Transcriber GUI.
REM Set CONDA_ENV to your environment name (default: base).
setlocal
set "CONDA_ENV=base"

REM Locate conda installation (checks common install paths).
set "CONDA_BASE="
if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat"     set "CONDA_BASE=%USERPROFILE%\miniconda3"
if exist "%USERPROFILE%\anaconda3\Scripts\activate.bat"      set "CONDA_BASE=%USERPROFILE%\anaconda3"
if exist "%LOCALAPPDATA%\miniconda3\Scripts\activate.bat"    set "CONDA_BASE=%LOCALAPPDATA%\miniconda3"
if exist "%LOCALAPPDATA%\anaconda3\Scripts\activate.bat"     set "CONDA_BASE=%LOCALAPPDATA%\anaconda3"

if not "%CONDA_BASE%"=="" (
    call "%CONDA_BASE%\Scripts\activate.bat" "%CONDA_ENV%"
    python "%~dp0app.py"
    goto :eof
)

REM Fallback: plain python (must be on PATH).
python "%~dp0app.py"
