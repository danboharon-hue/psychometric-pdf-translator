@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Starting PDF Translator...
python app_download.py
pause
