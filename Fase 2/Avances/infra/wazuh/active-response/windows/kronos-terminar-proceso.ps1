# kronos-terminar-proceso (Windows) - Active Response de Kronos AI
#
# Lo lanza kronos-terminar-proceso.cmd. El agente de Wazuh entrega por la entrada estandar
# una linea JSON; Kronos (SOAR-EXECUTE) pone la operacion, el PID y el ejecutable en
# parameters.extra_args:
#
#   {"version":1,"command":"add","parameters":{"extra_args":["aplicar","4312","C:\\Users\\Public\\upd.exe"]}}
#
#   aplicar <pid> <ejecutable> -> termina el proceso, si sigue siendo ese programa.
#
# No tiene inversa: el programa se vuelve a abrir si corresponde (accion de la persona).
#
# Reglas de seguridad (igual que ejecucion/ordenes.py, como segunda barrera):
# - Solo "aplicar", un PID numerico de 5 o mas y una ruta C:\... con una lista blanca de
#   caracteres. Cualquier otra cosa se rechaza.
# - El PID tiene que seguir siendo el mismo programa: la ruta del ejecutable del proceso
#   (Win32_Process.ExecutablePath) debe ser la de la alerta, sin distinguir mayusculas. Si
#   no, otro proceso heredo el PID y no se toca. Antes de terminarlo se vuelve a comprobar
#   con la misma hora de inicio.
# - Nunca termina procesos protegidos: los del sistema (csrss, lsass, winlogon...), el
#   agente de Wazuh, Sysmon, el antivirus, NetBird, SSH, ni este mismo script ni su padre.
# - Si el proceso ya no existe: "sin cambios".
#
# Salida: 0 si quedo como se pidio, 1 si se rechazo o fallo. El resultado va a
# active-response\active-responses.log del agente. Compatible con Windows PowerShell 5.1.

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$NOMBRE = 'kronos-terminar-proceso'
$RAIZ_AR = Split-Path -Parent $PSScriptRoot
$LOG = Join-Path $RAIZ_AR 'active-responses.log'
$PID_MINIMO = 5
$ESPERA_SEGUNDOS = 10
$TRAMO = '[\w .()+#@,-]{1,255}'
$PATRON = '^[A-Za-z]:\\(?:' + $TRAMO + '\\)*' + $TRAMO + '$'
# Nombre del ejecutable (sin la carpeta) de los procesos que nunca se terminan.
$PROTEGIDOS = @('System', 'Registry', 'smss.exe', 'csrss.exe', 'wininit.exe', 'winlogon.exe',
    'services.exe', 'lsass.exe', 'lsaiso.exe', 'svchost.exe', 'fontdrvhost.exe', 'dwm.exe',
    'MsMpEng.exe', 'NisSrv.exe', 'MpDefenderCoreService.exe', 'SecurityHealthService.exe',
    'Sysmon.exe', 'Sysmon64.exe', 'wazuh-agent.exe', 'ossec-agent.exe', 'netbird.exe',
    'netbird-ui.exe', 'sshd.exe', 'VBoxService.exe', 'VBoxTray.exe')
$CARPETAS_PROTEGIDAS = @('c:\program files (x86)\ossec-agent\', 'c:\program files\ossec-agent\',
    'c:\programdata\kronos\')

# Siempre $script:NOMBRE: una variable local $nombre lo taparia (PowerShell no distingue
# mayusculas y el alcance es dinamico).
function Escribir-Log([string]$texto) {
    $linea = '{0} {1}: {2}' -f (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'), $script:NOMBRE, $texto
    try {
        $fs = [System.IO.File]::Open($LOG, [System.IO.FileMode]::Append, [System.IO.FileAccess]::Write,
            [System.IO.FileShare]'ReadWrite, Delete')
        $sw = New-Object System.IO.StreamWriter($fs, (New-Object System.Text.UTF8Encoding($false)))
        try { $sw.WriteLine($linea) } finally { $sw.Dispose() }
    } catch {
        [Console]::Error.WriteLine("$($script:NOMBRE) no pudo escribir en el registro: $($_.Exception.Message)")
    }
}

function Terminar([int]$codigo, [string]$texto) {
    Escribir-Log $texto
    exit $codigo
}

function Leer-Argumentos {
    $linea = [Console]::In.ReadLine()
    if ([string]::IsNullOrWhiteSpace($linea)) { Terminar 1 'ERROR sin entrada JSON' }
    try { $mensaje = $linea | ConvertFrom-Json } catch { Terminar 1 'ERROR la entrada no es JSON' }
    $parametros = $mensaje.PSObject.Properties['parameters']
    if ($null -eq $parametros -or $null -eq $parametros.Value) { Terminar 1 'ERROR falta parameters' }
    $extra = $parametros.Value.PSObject.Properties['extra_args']
    if ($null -eq $extra -or $null -eq $extra.Value) { Terminar 1 'ERROR falta parameters.extra_args' }
    return , @($extra.Value | ForEach-Object { [string]$_ })
}

function Leer-Proceso([int]$id) {
    return Get-CimInstance -ClassName Win32_Process -Filter ("ProcessId = {0}" -f $id) -ErrorAction SilentlyContinue
}

# ------------------------------------------------------------------------------------

$argumentos = Leer-Argumentos
if ($argumentos.Count -ne 3) { Terminar 1 ('ERROR se esperaban 3 argumentos y llegaron {0}' -f $argumentos.Count) }
$operacion = $argumentos[0]
$textoPid = $argumentos[1]
$ruta = $argumentos[2]
if ($operacion -cne 'aplicar') { Terminar 1 "ERROR operacion no permitida: $operacion" }
if ($textoPid -cnotmatch '^\d{1,10}$' -or [int64]$textoPid -lt $PID_MINIMO) { Terminar 1 "ERROR PID no permitido: $textoPid" }
$id = [int]$textoPid
if ($ruta.Length -gt 260 -or $ruta -notmatch $PATRON) { Terminar 1 "ERROR ruta no permitida: $ruta" }
foreach ($tramo in $ruta.Split('\') | Select-Object -Skip 1) {
    if ($tramo -eq '.' -or $tramo -eq '..' -or $tramo -ne $tramo.Trim() -or $tramo.EndsWith('.')) {
        Terminar 1 "ERROR ruta con tramos no permitidos: $ruta"
    }
}

$proceso = Leer-Proceso $id
if ($null -eq $proceso) { Terminar 0 "aplicar $id sin cambios (el proceso ya no esta en marcha)" }
$real = [string]$proceso.ExecutablePath
if ([string]::IsNullOrEmpty($real)) { Terminar 1 "ERROR no se puede leer el ejecutable del PID $id; no se toca" }
if ($real -ne $ruta) { Terminar 1 "ERROR el PID $id ahora es $real, no $ruta; no se toca" }
$base = Split-Path -Leaf $real
foreach ($p in $PROTEGIDOS) { if ($base -ieq $p) { Terminar 1 "ERROR proceso protegido: $real" } }
$minuscula = $real.ToLowerInvariant()
foreach ($c in $CARPETAS_PROTEGIDAS) { if ($minuscula.StartsWith($c)) { Terminar 1 "ERROR proceso protegido: $real" } }
$propio = Leer-Proceso $PID
if ($id -eq $PID -or ($null -ne $propio -and $id -eq [int]$propio.ParentProcessId)) {
    Terminar 1 "ERROR el PID $id es de este script o de quien lo lanzo"
}

# Justo antes de terminarlo: mismo PID, mismo programa y misma hora de inicio.
try { $vivo = Get-Process -Id $id -ErrorAction Stop } catch { Terminar 0 "aplicar $id sin cambios (el proceso termino solo)" }
$otraVez = Leer-Proceso $id
if ($null -eq $otraVez -or [string]$otraVez.ExecutablePath -ne $ruta -or $otraVez.CreationDate -ne $proceso.CreationDate) {
    Terminar 1 "ERROR el PID $id cambio de programa mientras se comprobaba; no se toca"
}
try { $vivo.Kill() } catch {
    if ($null -eq (Leer-Proceso $id)) { Terminar 0 "aplicar $id sin cambios (el proceso termino solo)" }
    Terminar 1 "ERROR no se pudo terminar el PID $($id): $($_.Exception.Message)"
}
if (-not $vivo.WaitForExit($ESPERA_SEGUNDOS * 1000)) { Terminar 1 "ERROR el PID $id sigue vivo despues de terminarlo" }
Terminar 0 "aplicar $id $ruta OK"
