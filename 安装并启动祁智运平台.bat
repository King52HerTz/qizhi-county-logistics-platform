@echo off
chcp 65001 >nul
title 祁智运平台 - 安装与启动向导
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install-and-start.ps1"
