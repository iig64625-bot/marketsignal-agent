# SignalPulse 部署文档

> AI 竞品分析平台 — Windows 本地部署  
> 版本: V5 | 最后更新: 2026-06-30

## 1. 概述

SignalPulse 是 AI 竞品分析平台，自动跟踪竞品发布 / 新闻 / 技术更新，生成分析报告。

| 项 | 值 |
|---|---|
| UI | http://localhost:8501 |
| 数据 | SQLite (data/marketsignal.db) |
| 进程 | Microsoft Store Python 3.11 |
| 依赖 | Python venv (.venv) |
| 自启 | Startup 文件夹快捷方式 |

## 2. 系统要求

Windows 10/11，Python 3.11.x，2 GB+ 磁盘，4 GB+ 内存，8501 端口。

## 3. 目录结构
D:\marketsignal-agent
├── .venv/                    # venv (不入 git)
├── src/signalpulse/          # 源码
├── tests/                    # 202+ tests
├── configs/ data/ logs/ ops/  # 配置 / 数据 / 日志 / 管理
├── run_streamlit.bat         # 启动 wrapper
└── .env                      # 环境变量 (不入 git)

## 4. 安装

```powershell
git clone https://github.com/iig64625-bot/marketsignal-agent.git
cd marketsignal-agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install pydantic pydantic-settings fastapi sqlalchemy httpx beautifulsoup4 trafilatura readability-lxml feedparser tenacity langdetect pytest
Copy-Item .env.example .env -Force
notepad .env  # 填 OPENAI_API_KEY
.\.venv\Scripts\python.exe -m pytest -q   # 202 passed, 14 skipped
## 5. 杩愯

```powershell
.\ops\start.ps1     # 鍚姩
.\ops\status.ps1    # 鐪嬬姸鎬侊紙杩涚▼ / 绔彛 / health锛?.\ops\stop.ps1      # 鍋滄
.\ops\restart.ps1   # 閲嶅惎
# 娴忚鍣細http://localhost:8501
git pull origin main
.\.venv\Scripts\python.exe -m pip install pydantic pydantic-settings fastapi sqlalchemy httpx
.\ops\restart.ps1
.\ops\stop.ps1
Remove-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\SignalPulse.lnk"
Remove-Item D:\marketsignal-agent -Recurse -Force
GitHub: https://github.com/iig64625-bot/marketsignal-agent
Issue: GitHub Issues
