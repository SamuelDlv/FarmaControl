@echo off
setlocal
title FarmaControl - Servidor

cd /d "%~dp0"
set "FARMACONTROL_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%FARMACONTROL_PYTHON%" (
    echo Ambiente Python nao encontrado em .venv.
    echo Siga docs\TRANSFERENCIA.md para criar a .venv.
    pause
    exit /b 1
)

if not exist "backend\.env" (
    echo Configure backend\.env conforme backend\.env.example antes de iniciar.
    pause
    exit /b 1
)

rem Abre o navegador padrao apos 2 segundos, enquanto o servidor inicia.
start "" /b powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://localhost:5000/pages/acesso/acesso.html'"

echo Mantenha esta janela aberta enquanto usar o FarmaControl. Ctrl+C encerra o servidor.
"%FARMACONTROL_PYTHON%" "%~dp0backend\app.py"
if errorlevel 1 (
    echo O servidor nao iniciou ou terminou com erro. Confira a mensagem acima.
    pause
    exit /b 1
)

endlocal
exit /b
