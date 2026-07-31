@echo off
chcp 65001 >nul
title 祁智运平台 - 一键启动
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\demo-control.ps1" -Action Start
