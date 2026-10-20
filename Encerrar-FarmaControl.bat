@echo off
setlocal
title FarmaControl - Encerrar
set "FARMACONTROL_APP=%~dp0backend\app.py"

rem O iniciador usa o caminho absoluto para identificar somente este projeto.
powershell.exe -NoProfile -NonInteractive -Command "$ErrorActionPreference = 'Stop'; try { $appPattern = [regex]::Escape($env:FARMACONTROL_APP); $servers = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^pythonw?(\d+(\.\d+)*)?\.exe$' -and $_.CommandLine -match $appPattern }); if ($servers.Count -gt 0) { foreach ($server in $servers) { if (Get-Process -Id $server.ProcessId -ErrorAction SilentlyContinue) { Stop-Process -Id $server.ProcessId -Force } }; Write-Host 'FarmaControl encerrado.' } else { Write-Host 'Nenhum servidor FarmaControl desta pasta em execucao.' } } catch { Write-Host ('Nao foi possivel encerrar: ' + $_.Exception.Message); exit 1 }"
if errorlevel 1 (
    pause
    exit /b 1
)

endlocal
exit /b 0
