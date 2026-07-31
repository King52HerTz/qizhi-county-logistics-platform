@echo off
chcp 65001 >nul
title 祁智运平台 - 恢复标准演示数据
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\demo-control.ps1" -Action Reset
