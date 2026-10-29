@echo off
rem kronos-aislar-equipo (Windows) - lanzador del script de PowerShell.
rem El agente de Wazuh es de 32 bits: Sysnative evita que Windows lo redirija a la
rem PowerShell de 32 bits. Si no existe (consola de 64 bits), se usa System32.
rem La entrada estandar (el JSON de Wazuh) pasa tal cual a PowerShell.
setlocal
set "PS=%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS%" set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
"%PS%" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0kronos-aislar-equipo.ps1"
exit /b %ERRORLEVEL%
