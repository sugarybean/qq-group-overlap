@echo off
rem QQ group overlap analyzer - Windows GUI launcher
rem Double-click this file, or run: scripts\start-gui.bat

setlocal

rem Change to project root (this script lives under scripts\)
cd /d "%~dp0.."

rem Use UTF-8 codepage to avoid garbled Chinese output
chcp 65001 >nul

rem Locate Python interpreter: prefer py launcher, fall back to python
set "PY=python"
where py >nul 2>nul && set "PY=py -3"

rem Add src to the module search path
set "PYTHONPATH=%CD%\src"

rem Launch the GUI; %* forwards extra args (--snapshot, --api, etc.)
%PY% -m qq_group_overlap.gui %*

set "exit_code=%errorlevel%"
endlocal & exit /b %exit_code%
