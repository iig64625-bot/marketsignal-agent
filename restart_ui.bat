@echo off
chcp 65001 >nul
call "%~dp0stop_ui.bat"
timeout /t 2 /nobreak >nul
call "%~dp0start_ui.bat"
