@echo off
set PYTHONPATH=D:\marketsignal-agent\src
cd /d D:\marketsignal-agent
D:\marketsignal-agent\.python\python.exe -m streamlit run D:\marketsignal-agent\src\signalpulse\ui\app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
