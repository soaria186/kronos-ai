# kronos-bloquear-destino (Windows) - Active Response de Kronos AI
#
# Lo lanza kronos-bloquear-destino.cmd. El agente de Wazuh entrega por la entrada
# estandar una linea JSON; Kronos (SOAR-EXECUTE) pone la operacion y el objetivo en
# parameters.extra_args:
#
#   {"version":1,"command":"add","parameters":{"extra_args":["aplicar","198.51.100.66"], ...}}
#
#   aplicar <ip>  -> agrega una regla de SALIDA que bloquea la IP de destino (netsh)
#   quitar  <ip>  -> borra esa regla
#
# Corta la comunicacion del equipo con un servidor externo (por ejemplo, el de comando y
# control de un malware). La regla se llama Kronos-destino-<ip>.
#
# Reglas de seguridad (segunda barrera despues de ejecucion/ordenes.py):
# - Solo dos operaciones y exactamente un objetivo; cualquier otra cosa se rechaza.
# - La IP se parsea y debe coincidir con su forma canonica: no se limpia ni se recorta.
# - Nunca se bloquea loopback, 0.0.0.0, multicast, enlace local, difusion, una IP del
#   propio equipo, su puerta de enlace, sus servidores DNS ni la red de NetBird
#   (100.64.0.0/10): dejarian al equipo sin red o sin acceso remoto.
# - Nunca se bloquea el manager de Wazuh (la direccion de <server> en ossec.conf): se
#   cortaria el canal por el que llega la orden de quitar. Si no se puede leer, no actua.
# - netsh recibe los argumentos como lista; nada pasa por un interprete de comandos.
# - Aplicar y quitar son idempotentes.
#
# Salida: 0 si quedo hecho, 1 si se rechazo o fallo. El resultado va a
# active-response\active-responses.log del agente. Compatible con Windows PowerShell 5.1.

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

# PowerShell no distingue mayusculas en los nombres de variables: ninguna otra variable
# puede llamarse $nombre, porque pisaria a $NOMBRE.
$NOMBRE = 'kronos-bloquear-destino'
$PREFIJO_REGLA = 'Kronos-destino-'
$RAIZ_AR = Split-Path -Parent $PSScriptRoot
$LOG = Join-Path $RAIZ_AR 'active-responses.log'
$OSSEC_CONF = Join-Path (Split-Path -Parent $RAIZ_AR) 'ossec.conf'

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

# IP del manager segun ossec.conf (puede ser un nombre: se resuelve). $null si no se puede.
function Ips-Manager {
    # Con una expresion regular y no como XML: ossec.conf puede traer mas de un bloque raiz.
    try { $conf = Get-Content -LiteralPath $script:OSSEC_CONF -Raw -ErrorAction Stop } catch { return $null }
    $patron = '(?s)<server>.*?<address>\s*([^<\s]+)\s*</address>'
    $direcciones = @([regex]::Matches($conf, $patron) | ForEach-Object { $_.Groups[1].Value })
    if ($direcciones.Count -eq 0) { return $null }
    $ips = @()
    foreach ($direccion in $direcciones) {
        $ip = $null
        if ([System.Net.IPAddress]::TryParse($direccion, [ref]$ip)) { $ips += $ip.ToString(); continue }
        try {
            $ips += @([System.Net.Dns]::GetHostAddresses($direccion) | ForEach-Object { ($_.ToString() -split '%')[0] })
        } catch { return $null }
    }
    if ($ips.Count -eq 0) { return $null }
    return , $ips
}

function En-NetBird([System.Net.IPAddress]$ip) {
    if ($ip.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) { return $false }
    $b = $ip.GetAddressBytes()
    return ($b[0] -eq 100 -and $b[1] -ge 64 -and $b[1] -le 127)
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
    if (En-NetBird $ip) { Terminar 1 "ERROR es de la red de NetBird: $texto" }
    $propias = @(Get-NetIPAddress -ErrorAction SilentlyContinue | ForEach-Object { ($_.IPAddress -split '%')[0] })
    if ($propias -contains $texto) { Terminar 1 "ERROR es una IP del propio equipo: $texto" }
    $puertas = @(Get-NetRoute -DestinationPrefix '0.0.0.0/0', '::/0' -ErrorAction SilentlyContinue |
        ForEach-Object { ($_.NextHop -split '%')[0] })
    if ($puertas -contains $texto) { Terminar 1 "ERROR es la puerta de enlace del equipo: $texto" }
    $dns = @(Get-DnsClientServerAddress -ErrorAction SilentlyContinue | ForEach-Object { $_.ServerAddresses } |
        ForEach-Object { ([string]$_ -split '%')[0] })
    if ($dns -contains $texto) { Terminar 1 "ERROR es un servidor DNS del equipo: $texto" }
    $manager = Ips-Manager
    if ($null -eq $manager) { Terminar 1 "ERROR no se pudo leer la direccion del manager; no se actua sobre $texto" }
    if ($manager -contains $texto) { Terminar 1 "ERROR es el manager de Wazuh: $texto" }
}

function Regla-Existe([string]$regla) {
    & netsh.exe advfirewall firewall show rule "name=$regla" | Out-Null
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
    & netsh.exe advfirewall firewall add rule "name=$regla" 'dir=out' 'action=block' "remoteip=$texto" 'enable=yes' 'profile=any' "description=Kronos AI: salida bloqueada $desde UTC; lo revierte SOAR-EXECUTE" | Out-Null
    if ($LASTEXITCODE -ne 0) { Terminar 1 "ERROR netsh no pudo agregar la regla ($LASTEXITCODE)" }
    Advertir-Si-Firewall-Apagado
    Terminar 0 "aplicar $texto OK"
} else {
    if (-not (Regla-Existe $regla)) { Terminar 0 "quitar $texto OK (la regla no existia)" }
    & netsh.exe advfirewall firewall delete rule "name=$regla" | Out-Null
    if ($LASTEXITCODE -ne 0) { Terminar 1 "ERROR netsh no pudo borrar la regla ($LASTEXITCODE)" }
    Terminar 0 "quitar $texto OK"
}
