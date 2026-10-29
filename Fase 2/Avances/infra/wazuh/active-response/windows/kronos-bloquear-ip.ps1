# kronos-bloquear-ip (Windows) - Active Response de Kronos AI
#
# Lo lanza kronos-bloquear-ip.cmd. El agente de Wazuh entrega por la entrada estandar
# una linea JSON; Kronos (SOAR-EXECUTE) pone la operacion y el objetivo en
# parameters.extra_args:
#
#   {"version":1,"command":"add","parameters":{"extra_args":["aplicar","203.0.113.50"], ...}}
#
#   aplicar <ip>  -> agrega una regla de entrada que bloquea la IP (netsh advfirewall)
#   quitar  <ip>  -> borra esa regla
#
# Reglas de seguridad (igual que ejecucion/ordenes.py, como segunda barrera):
# - Solo dos operaciones y exactamente un objetivo; cualquier otra cosa se rechaza.
# - La IP se parsea y debe coincidir con su forma canonica: no se limpia ni se recorta.
# - Nunca se bloquea loopback, 0.0.0.0, multicast, enlace local, difusion, una IP del
#   propio equipo ni su puerta de enlace (bloquearla deja al equipo sin red).
# - netsh recibe los argumentos como lista; nada pasa por un interprete de comandos.
# - Aplicar y quitar son idempotentes: repetirlos no cambia el resultado.
#
# Salida: 0 si quedo hecho, 1 si se rechazo o fallo. El resultado va a
# active-response\active-responses.log del agente. Wazuh no devuelve este codigo a la
# API: EXECUTE solo sabe que la orden llego al agente.
#
# Compatible con Windows PowerShell 5.1.

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$NOMBRE = 'kronos-bloquear-ip'
$PREFIJO_REGLA = 'Kronos-bloqueo-'
$LOG = Join-Path (Split-Path -Parent $PSScriptRoot) 'active-responses.log'

# El agente de Wazuh tiene abierto active-responses.log: se abre en modo compartido
# (Add-Content fallaba). Si aun asi no se puede escribir, se dice por la salida de error en
# vez de esconderlo.
function Escribir-Log([string]$texto) {
    $linea = '{0} {1}: {2}' -f (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'), $NOMBRE, $texto
    try {
        $fs = [System.IO.File]::Open($LOG, [System.IO.FileMode]::Append, [System.IO.FileAccess]::Write,
            [System.IO.FileShare]'ReadWrite, Delete')
        $sw = New-Object System.IO.StreamWriter($fs, (New-Object System.Text.UTF8Encoding($false)))
        try { $sw.WriteLine($linea) } finally { $sw.Dispose() }
    } catch {
        [Console]::Error.WriteLine("$NOMBRE no pudo escribir en el registro: $($_.Exception.Message)")
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

function Validar-Ip([string]$texto) {
    $ip = $null
    if (-not [System.Net.IPAddress]::TryParse($texto, [ref]$ip)) { Terminar 1 "ERROR IP invalida: $texto" }
    # TryParse acepta formas raras ('1', '0x7f.1'); se exige la forma canonica.
    if ($ip.ToString() -ne $texto) { Terminar 1 "ERROR IP no canonica: $texto" }
    if ([System.Net.IPAddress]::IsLoopback($ip)) { Terminar 1 "ERROR no se bloquea loopback: $texto" }
    if ($ip.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork) {
        $b = $ip.GetAddressBytes()
        if ($b[0] -eq 0) { Terminar 1 "ERROR direccion no especificada: $texto" }
        if ($b[0] -ge 224 -and $b[0] -le 239) { Terminar 1 "ERROR multicast: $texto" }
        if ($b[0] -eq 169 -and $b[1] -eq 254) { Terminar 1 "ERROR enlace local: $texto" }
        if ($texto -eq '255.255.255.255') { Terminar 1 "ERROR difusion: $texto" }
    } else {
        if ($ip.Equals([System.Net.IPAddress]::IPv6None)) { Terminar 1 "ERROR direccion no especificada: $texto" }
        if ($ip.IsIPv6Multicast) { Terminar 1 "ERROR multicast: $texto" }
        if ($ip.IsIPv6LinkLocal) { Terminar 1 "ERROR enlace local: $texto" }
    }
    $propias = @(Get-NetIPAddress -ErrorAction SilentlyContinue | ForEach-Object { ($_.IPAddress -split '%')[0] })
    if ($propias -contains $texto) { Terminar 1 "ERROR es una IP del propio equipo: $texto" }
    $puertas = @(Get-NetRoute -DestinationPrefix '0.0.0.0/0', '::/0' -ErrorAction SilentlyContinue |
        ForEach-Object { ($_.NextHop -split '%')[0] })
    if ($puertas -contains $texto) { Terminar 1 "ERROR es la puerta de enlace del equipo: $texto" }
}

function Regla-Existe([string]$nombre) {
    & netsh.exe advfirewall firewall show rule "name=$nombre" | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Advertir-Si-Firewall-Apagado {
    try {
        $apagados = @(Get-NetFirewallProfile -ErrorAction Stop | Where-Object { -not $_.Enabled } | ForEach-Object { $_.Name })
        if ($apagados.Count -gt 0) {
            Escribir-Log ('ADVERTENCIA firewall apagado en: {0}; la regla no tiene efecto en esos perfiles' -f ($apagados -join ', '))
        }
    } catch { }
}

# ------------------------------------------------------------------------------------

$argumentos = Leer-Argumentos
if ($argumentos.Count -ne 2) { Terminar 1 ('ERROR se esperaban 2 argumentos y llegaron {0}' -f $argumentos.Count) }
$operacion = $argumentos[0]
$texto = $argumentos[1]
if ($operacion -cne 'aplicar' -and $operacion -cne 'quitar') { Terminar 1 "ERROR operacion no permitida: $operacion" }

Validar-Ip $texto
$regla = $PREFIJO_REGLA + $texto

if ($operacion -ceq 'aplicar') {
    if (Regla-Existe $regla) { Terminar 0 "aplicar $texto OK (la regla ya existia)" }
    $desde = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    & netsh.exe advfirewall firewall add rule "name=$regla" 'dir=in' 'action=block' "remoteip=$texto" 'enable=yes' 'profile=any' "description=Kronos AI: bloqueo aplicado $desde UTC; lo revierte SOAR-EXECUTE" | Out-Null
    if ($LASTEXITCODE -ne 0) { Terminar 1 "ERROR netsh no pudo agregar la regla ($LASTEXITCODE)" }
    Advertir-Si-Firewall-Apagado
    Terminar 0 "aplicar $texto OK"
} else {
    if (-not (Regla-Existe $regla)) { Terminar 0 "quitar $texto OK (la regla no existia)" }
    & netsh.exe advfirewall firewall delete rule "name=$regla" | Out-Null
    if ($LASTEXITCODE -ne 0) { Terminar 1 "ERROR netsh no pudo borrar la regla ($LASTEXITCODE)" }
    Terminar 0 "quitar $texto OK"
}
