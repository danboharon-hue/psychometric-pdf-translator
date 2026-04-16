@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Starting PDF Translator with Download Interface...
python app.py
pause
