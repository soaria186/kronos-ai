@echo off
rem kronos-revertir-tarea (Windows) - lanzador del script de PowerShell.
rem El agente de Wazuh es de 32 bits: Sysnative evita que Windows lo redirija a la
rem PowerShell de 32 bits. Si no existe (consola de 64 bits), se usa System32.
rem El modulo ScheduledTasks (Disable-ScheduledTask) solo existe en la de
rem 64 bits, asi que Sysnative es indispensable aqui.
rem La entrada estandar (el JSON de Wazuh) pasa tal cual a PowerShell.
setlocal
set "PS=%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS%" set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
"%PS%" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0kronos-revertir-tarea.ps1"
exit /b %ERRORLEVEL%
