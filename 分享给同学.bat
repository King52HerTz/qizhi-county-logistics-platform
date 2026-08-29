@echo off
chcp 65001 >nul
title 祁智运平台 - 分享给同学
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\share-demo.ps1"
