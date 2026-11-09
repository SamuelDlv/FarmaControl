@echo off
rem Guia de manutencao: solicita parada cooperativa da copia localizada nesta pasta.
rem O caminho de backend/app.py identifica o servidor; Done confirma o fim das requisicoes.
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
