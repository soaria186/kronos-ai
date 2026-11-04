# kronos-revertir-tarea (Windows) - Active Response de Kronos AI
#
# Lo lanza kronos-revertir-tarea.cmd. El agente de Wazuh entrega por la entrada estandar
# una linea JSON; Kronos (SOAR-EXECUTE) pone la operacion y la tarea en
# parameters.extra_args:
#
#   {"version":1,"command":"add","parameters":{"extra_args":["aplicar","\\Actualizador0"]}}
#
#   aplicar   <\carpeta\tarea> -> deshabilita la tarea programada (como schtasks /DISABLE)
#   habilitar <\carpeta\tarea> -> la vuelve a habilitar, SOLO si la deshabilito Kronos
#
# Reglas de seguridad (igual que ejecucion/ordenes.py, como segunda barrera):
# - Solo dos operaciones y exactamente una tarea; cualquier otra cosa se rechaza.
# - Nombre \carpeta\tarea con una lista blanca de caracteres (sin comodines, comillas ni
#   caracteres de shell), sin "." ni "..". No se limpia ni se recorta.
# - Nunca las tareas del agente de Wazuh, de Kronos, de NetBird ni de Windows Defender.
# - Estado: al deshabilitar se deja la marca active-response\kronos-estado\tarea-<huella>.txt.
#   Habilitar solo actua si existe esa marca. Aplicar y habilitar son idempotentes, y
#   despues de actuar se comprueba el estado.
# - Deshabilitar no detiene una ejecucion en curso: para eso esta kronos-terminar-proceso.
#
# Salida: 0 si quedo como se pidio, 1 si se rechazo o fallo. El resultado va a
# active-response\active-responses.log del agente. Necesita la PowerShell de 64 bits (el
# modulo ScheduledTasks): por eso el .cmd usa Sysnative. Compatible con Windows PowerShell 5.1.

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$NOMBRE = 'kronos-revertir-tarea'
$RAIZ_AR = Split-Path -Parent $PSScriptRoot
$LOG = Join-Path $RAIZ_AR 'active-responses.log'
$ESTADO = Join-Path $RAIZ_AR 'kronos-estado'
$TRAMO = '[\w .()+#@,-]{1,255}'
$PATRON = '^\\(?:' + $TRAMO + '\\)*' + $TRAMO + '$'
$PROTEGIDAS = @('wazuh', 'ossec', 'kronos', 'netbird', '\microsoft\windows\windows defender\')

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

function Ruta-Marca([string]$tarea) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { $bytes = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($tarea.ToLowerInvariant())) }
    finally { $sha.Dispose() }
    $clave = -join ($bytes[0..15] | ForEach-Object { $_.ToString('x2') })
    return (Join-Path $ESTADO ('tarea-{0}.txt' -f $clave))
}

function Estado-Tarea([string]$carpeta, [string]$hoja) {
    return [string](Get-ScheduledTask -TaskPath $carpeta -TaskName $hoja -ErrorAction Stop).State
}

# ------------------------------------------------------------------------------------

if ($null -eq (Get-Command Disable-ScheduledTask -ErrorAction SilentlyContinue)) {
    Terminar 1 'ERROR falta el modulo ScheduledTasks (se lanzo la PowerShell de 32 bits?)'
}

$argumentos = Leer-Argumentos
if ($argumentos.Count -ne 2) { Terminar 1 ('ERROR se esperaban 2 argumentos y llegaron {0}' -f $argumentos.Count) }
$operacion = $argumentos[0]
$tarea = $argumentos[1]
if ($operacion -cne 'aplicar' -and $operacion -cne 'habilitar') { Terminar 1 "ERROR operacion no permitida: $operacion" }
if ($tarea.Length -gt 238 -or $tarea -notmatch $PATRON) { Terminar 1 "ERROR nombre de tarea no permitido: $tarea" }
foreach ($tramo in $tarea.Split('\') | Select-Object -Skip 1) {
    if ($tramo -eq '.' -or $tramo -eq '..' -or $tramo -ne $tramo.Trim() -or $tramo.EndsWith('.')) {
        Terminar 1 "ERROR nombre de tarea con tramos no permitidos: $tarea"
    }
}
$minuscula = $tarea.ToLowerInvariant()
foreach ($p in $PROTEGIDAS) { if ($minuscula.Contains($p)) { Terminar 1 "ERROR tarea protegida: $tarea" } }

$corte = $tarea.LastIndexOf('\')
$carpeta = $tarea.Substring(0, $corte + 1)
$hoja = $tarea.Substring($corte + 1)
# El patron ya excluye * ? [ ], asi que el nombre no se interpreta como comodin.
try { $estado = Estado-Tarea $carpeta $hoja } catch { Terminar 1 "ERROR no existe la tarea programada: $tarea" }
$marca = Ruta-Marca $tarea

if ($operacion -ceq 'aplicar') {
    if ($estado -eq 'Disabled') {
        if (Test-Path -LiteralPath $marca) { Terminar 0 "aplicar $tarea sin cambios (ya la habia deshabilitado Kronos)" }
        Terminar 0 "aplicar $tarea sin cambios (ya estaba deshabilitada; no la deshabilito Kronos)"
    }
    try {
        New-Item -ItemType Directory -Path $ESTADO -Force | Out-Null
        $desde = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        # La marca va antes de deshabilitar: si se escribiera despues y fallara, la tarea
        # quedaria deshabilitada sin que Kronos pudiera habilitarla.
        [System.IO.File]::WriteAllText($marca, "$tarea`r`nDeshabilitada por Kronos AI el $desde UTC`r`n")
    } catch { Terminar 1 "ERROR no se pudo escribir la marca de estado: $($_.Exception.Message)" }
    try { Disable-ScheduledTask -TaskPath $carpeta -TaskName $hoja -ErrorAction Stop | Out-Null }
    catch {
        Remove-Item -LiteralPath $marca -Force -ErrorAction SilentlyContinue
        Terminar 1 "ERROR no se pudo deshabilitar $($tarea): $($_.Exception.Message)"
    }
    if ((Estado-Tarea $carpeta $hoja) -ne 'Disabled') {
        Remove-Item -LiteralPath $marca -Force -ErrorAction SilentlyContinue
        Terminar 1 "ERROR $tarea sigue habilitada despues de deshabilitarla"
    }
    Terminar 0 "aplicar $tarea OK"
} else {
    if (-not (Test-Path -LiteralPath $marca)) { Terminar 0 "habilitar $tarea sin cambios (no la deshabilito Kronos; se deja como esta)" }
    if ($estado -eq 'Disabled') {
        try { Enable-ScheduledTask -TaskPath $carpeta -TaskName $hoja -ErrorAction Stop | Out-Null }
        catch { Terminar 1 "ERROR no se pudo habilitar $($tarea): $($_.Exception.Message)" }
        if ((Estado-Tarea $carpeta $hoja) -eq 'Disabled') { Terminar 1 "ERROR $tarea sigue deshabilitada despues de habilitarla" }
    }
    try { Remove-Item -LiteralPath $marca -Force -ErrorAction Stop }
    catch { Escribir-Log "ADVERTENCIA no se pudo borrar la marca de $($tarea): $($_.Exception.Message)" }
    Terminar 0 "habilitar $tarea OK"
}
