@echo off
chcp 65001 >nul
title SNMP & LLDP 设备探测诊断小工具
echo 正在启动 WebWeaver SNMP & LLDP 设备探测诊断小工具...
cd /d "%~dp0"
python main.py
if %errorlevel% neq 0 (
    echo.
    echo 启动遇到错误，请确认系统已安装 Python 3 且已添加到 PATH 环境变量。
    pause
)
