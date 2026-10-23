@echo off
setlocal
title FarmaControl - Servidor

cd /d "%~dp0"
rem Prefere o ambiente criado pelo instalador de dependencias.
set "FARMACONTROL_PYTHON="
if exist ".venv\Scripts\python.exe" set "FARMACONTROL_PYTHON=.venv\Scripts\python.exe"
if not defined FARMACONTROL_PYTHON (
    py -3 -c "import sys; sys.exit(sys.version_info.major != 3)" >nul 2>&1
    if not errorlevel 1 set "FARMACONTROL_PYTHON=py -3"
)
if not defined FARMACONTROL_PYTHON (
    python -c "import sys; sys.exit(sys.version_info.major != 3)" >nul 2>&1
    if not errorlevel 1 set "FARMACONTROL_PYTHON=python"
)
if not defined FARMACONTROL_PYTHON (
    echo Python 3 nao encontrado. Instale o Python e habilite sua inclusao no PATH.
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
%FARMACONTROL_PYTHON% "%~dp0backend\app.py"
if errorlevel 1 (
    echo O servidor nao iniciou ou terminou com erro. Confira a mensagem acima.
    echo Se faltarem dependencias, execute nesta pasta:
    echo %FARMACONTROL_PYTHON% -m pip install -r backend\requirements.txt
    pause
    exit /b 1
)

endlocal
exit /b
