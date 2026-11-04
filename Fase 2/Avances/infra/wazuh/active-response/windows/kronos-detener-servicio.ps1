# kronos-detener-servicio (Windows) - Active Response de Kronos AI
#
# Lo lanza kronos-detener-servicio.cmd. El agente de Wazuh entrega por la entrada
# estandar una linea JSON; Kronos (SOAR-EXECUTE) pone la operacion y el servicio en
# parameters.extra_args:
#
#   {"version":1,"command":"add","parameters":{"extra_args":["aplicar","Spooler"], ...}}
#
#   aplicar <servicio> -> detiene el servicio (Stop-Service)
#   iniciar <servicio> -> lo vuelve a poner en marcha, SOLO si lo detuvo Kronos
#
# Reglas de seguridad (igual que ejecucion/ordenes.py, como segunda barrera):
# - Solo dos operaciones y exactamente un servicio; cualquier otra cosa se rechaza.
# - El nombre debe calzar con ^[A-Za-z0-9._@][A-Za-z0-9._@-]{0,127}$: no se limpia ni se
#   recorta, y sin * ? [ ] no se interpreta como comodin.
# - Nunca se detiene un servicio protegido: el agente de Wazuh, SSH, NetBird, el firewall,
#   Defender, la red, el registro de eventos ni los servicios basicos de Windows.
# - No se detiene un servicio que tenga servicios dependientes en marcha: Stop-Service los
#   detendria tambien y podria llevarse uno protegido. No se usa -Force.
# - Estado: al detener se deja la marca active-response\kronos-estado\servicio-<nombre>.txt.
#   Iniciar solo actua si existe esa marca, para no poner en marcha un servicio que el
#   encargado de TI habia detenido por su cuenta.
# - Aplicar e iniciar son idempotentes, y despues de actuar se comprueba el resultado.
#
# Salida: 0 si quedo como se pidio (o no correspondia tocarlo), 1 si se rechazo o fallo.
# El resultado va a active-response\active-responses.log del agente. Compatible con
# Windows PowerShell 5.1.

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

# PowerShell no distingue mayusculas en los nombres de variables: ninguna otra variable
# puede llamarse $nombre, porque pisaria a $NOMBRE y el registro saldria con otro prefijo.

$NOMBRE = 'kronos-detener-servicio'
$RAIZ_AR = Split-Path -Parent $PSScriptRoot
$LOG = Join-Path $RAIZ_AR 'active-responses.log'
$ESTADO = Join-Path $RAIZ_AR 'kronos-estado'
$ESPERA_SEGUNDOS = 30
$PROTEGIDOS = @('WazuhSvc', 'OssecSvc', 'sshd', 'ssh-agent', 'NetBird', 'netbird', 'mpssvc', 'BFE',
    'WinDefend', 'WdNisSvc', 'SecurityHealthService', 'EventLog', 'RpcSs', 'RpcEptMapper',
    'DcomLaunch', 'LSM', 'SamSs', 'Dhcp', 'Dnscache', 'nsi', 'NlaSvc', 'netprofm', 'Winmgmt',
    'TermService', 'LanmanWorkstation', 'CryptSvc', 'gpsvc', 'Schedule', 'ProfSvc',
    'UserManager', 'Power', 'PlugPlay', 'Audiosrv', 'VBoxService', 'kronos')

# El agente de Wazuh tiene abierto active-responses.log: se abre en modo compartido.
# Si aun asi no se puede escribir, se dice por la salida de error en vez de esconderlo.
function Escribir-Log([string]$texto) {
    $linea = '{0} {1}: {2}' -f (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'), $script:NOMBRE, $texto
    try {
        $fs = [System.IO.File]::Open($script:LOG, [System.IO.FileMode]::Append, [System.IO.FileAccess]::Write,
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

function Buscar-Servicio([string]$pedido) {
    try { return Get-Service -Name $pedido -ErrorAction Stop }
    catch { Terminar 1 "ERROR no existe el servicio: $pedido" }
}

function Validar-Protegido($servicio) {
    # Se compara el nombre corto (no el que se ve en pantalla) sin distinguir mayusculas.
    $corto = [string]$servicio.Name
    foreach ($p in $script:PROTEGIDOS) {
        if ($corto -ieq $p) { Terminar 1 "ERROR servicio protegido: $corto" }
    }
}

function Ruta-Marca([string]$corto) {
    return (Join-Path $script:ESTADO ('servicio-{0}.txt' -f $corto.ToLowerInvariant()))
}

function Esperar-Estado([string]$corto, [string]$estado) {
    $servicio = Get-Service -Name $corto -ErrorAction Stop
    try { $servicio.WaitForStatus($estado, [TimeSpan]::FromSeconds($script:ESPERA_SEGUNDOS)) } catch { }
    $servicio.Refresh()
    return ([string]$servicio.Status -eq $estado)
}

# ------------------------------------------------------------------------------------

$argumentos = Leer-Argumentos
if ($argumentos.Count -ne 2) { Terminar 1 ('ERROR se esperaban 2 argumentos y llegaron {0}' -f $argumentos.Count) }
$operacion = $argumentos[0]
$pedido = $argumentos[1]
if ($operacion -cne 'aplicar' -and $operacion -cne 'iniciar') { Terminar 1 "ERROR operacion no permitida: $operacion" }
if ($pedido -cnotmatch '^[A-Za-z0-9._@][A-Za-z0-9._@-]{0,127}$') { Terminar 1 "ERROR nombre de servicio no permitido: $pedido" }

$servicio = Buscar-Servicio $pedido
Validar-Protegido $servicio
$corto = [string]$servicio.Name
$marca = Ruta-Marca $corto

if ($operacion -ceq 'aplicar') {
    if ([string]$servicio.Status -eq 'Stopped') {
        if (Test-Path -LiteralPath $marca) { Terminar 0 "aplicar $corto OK (ya lo habia detenido Kronos)" }
        Terminar 0 "aplicar $corto OK (ya estaba detenido; no lo detuvo Kronos)"
    }
    $dependientes = @($servicio.DependentServices | Where-Object { [string]$_.Status -ne 'Stopped' })
    if ($dependientes.Count -gt 0) {
        $lista = ($dependientes | ForEach-Object { $_.Name }) -join ', '
        Terminar 1 "ERROR $corto tiene servicios dependientes en marcha ($lista); no se detiene"
    }
    try {
        New-Item -ItemType Directory -Path $ESTADO -Force | Out-Null
        $desde = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        # La marca va antes de detener: si se escribiera despues y fallara, el servicio
        # quedaria detenido sin que Kronos pudiera volver a iniciarlo.
        [System.IO.File]::WriteAllText($marca, "Detenido por Kronos AI el $desde UTC`r`n")
    } catch { Terminar 1 "ERROR no se pudo escribir la marca de estado: $($_.Exception.Message)" }
    try { Stop-Service -Name $corto -ErrorAction Stop }
    catch {
        Remove-Item -LiteralPath $marca -Force -ErrorAction SilentlyContinue
        Terminar 1 "ERROR no se pudo detener $($corto): $($_.Exception.Message)"
    }
    if (-not (Esperar-Estado $corto 'Stopped')) {
        Remove-Item -LiteralPath $marca -Force -ErrorAction SilentlyContinue
        Terminar 1 "ERROR $corto sigue en marcha despues de Stop-Service"
    }
    Terminar 0 "aplicar $corto OK"
} else {
    if (-not (Test-Path -LiteralPath $marca)) { Terminar 0 "iniciar $corto OK (no lo detuvo Kronos; se deja como esta)" }
    if ([string]$servicio.Status -ne 'Running') {
        try { Start-Service -Name $corto -ErrorAction Stop }
        catch { Terminar 1 "ERROR no se pudo iniciar $($corto): $($_.Exception.Message)" }
        if (-not (Esperar-Estado $corto 'Running')) { Terminar 1 "ERROR $corto no quedo en marcha despues de Start-Service" }
    }
    try { Remove-Item -LiteralPath $marca -Force -ErrorAction Stop }
    catch { Escribir-Log "ADVERTENCIA no se pudo borrar la marca de $($corto): $($_.Exception.Message)" }
    Terminar 0 "iniciar $corto OK"
}
