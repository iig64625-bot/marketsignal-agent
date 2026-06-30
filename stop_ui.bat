@echo off
chcp 65001 >nul
echo Killing all streamlit processes...
taskkill /IM streamlit.exe /F >nul 2>&1
taskkill /IM python.exe /FI "WINDOWTITLE eq streamlit*" /F >nul 2>&1
echo Done.
