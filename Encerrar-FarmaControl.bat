@echo off
setlocal
title FarmaControl - Encerrar
rem Sinaliza somente o servidor desta pasta; aguarda as requisicoes terminarem.
rem Nao mata processos nem encerra servicos MySQL/MariaDB, Apache ou XAMPP.
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0scripts\stop_local_server.ps1" -AppPath "%~dp0backend\app.py"
if errorlevel 1 (
    pause
    exit /b 1
)

endlocal
exit /b 0
