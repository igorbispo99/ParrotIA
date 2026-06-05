@echo off
REM Launch the Audio Transcriber GUI.
REM Edit PYTHON below if your Python is not on PATH (e.g. a specific conda env).
setlocal
set "PYTHON=python"
"%PYTHON%" "%~dp0app.py"
