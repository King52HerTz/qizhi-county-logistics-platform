@echo off
chcp 65001 >nul
title 祁智运平台 - 停止分享链接
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-share-demo.ps1"
