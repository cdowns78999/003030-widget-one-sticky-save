@echo off
cd /d "C:\Users\chad\003030-widget-one-sticky-save"
git pull origin main >nul 2>&1
copy /Y "widget.html" "C:\Users\chad\claude-token-widget\widget.html" >nul
copy /Y "poll.py" "C:\Users\chad\claude-token-widget\poll.py" >nul
