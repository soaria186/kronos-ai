# kronos-aislar-equipo (Windows) - Active Response de Kronos AI
#
# Lo lanza kronos-aislar-equipo.cmd. El agente de Wazuh entrega por la entrada estandar
# una linea JSON; Kronos (SOAR-EXECUTE) pone la operacion en parameters.extra_args. Esta
# medida actua sobre el propio equipo, asi que no lleva objetivo:
#
#   {"version":1,"command":"add","parameters":{"extra_args":["aplicar"], ...}}
#
#   aplicar -> corta todo el trafico del equipo SALVO el canal del agente con el manager
#   quitar  -> deja el firewall exactamente como estaba antes de aplicar
#
# Requisito critico: mientras el equipo esta aislado, el agente debe seguir conectado al
# manager. Si pierde el canal, la orden "quitar" nunca llega y el equipo queda aislado
# hasta que alguien vaya a la maquina. Por eso:
# - Antes de tocar nada se guarda la politica completa del firewall
#   (netsh advfirewall export) en active-response\kronos-estado\aislamiento.wfw.
# - Se leen el o los manager de ossec.conf (<client><server><address>, <port>, <protocol>)
#   y se crean las reglas de excepcion ANTES de bloquear: salida al manager, DHCP y, si
#   la direccion del manager es un nombre, DNS hacia los servidores configurados.
# - Se bloquea con la accion por omision de los perfiles (entrada y salida en Block) y
#   deshabilitando las reglas de permitir que no son de Kronos. No se crea una regla
#   "bloquear todo": en Windows las reglas de bloqueo le ganan a las de permitir y
#   cortarian tambien el canal del manager.
# - Si algo falla a mitad, se restaura la copia y se sale con 1.
#
# Quitar importa la copia (netsh advfirewall import), que restaura reglas, el estado de
# cada regla y la configuracion de los perfiles. Si falla, la copia no se borra.
#
# Aplicar y quitar son idempotentes. Salida: 0 si quedo hecho, 1 si se rechazo o fallo.
# El resultado va a active-response\active-responses.log del agente. Wazuh no devuelve
# este codigo a la API: EXECUTE solo sabe que la orden llego al agente.
#
# Compatible con Windows PowerShell 5.1 (de 64 bits, por el .cmd).

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$NOMBRE = 'kronos-aislar-equipo'
$RAIZ_AR = Split-Path -Parent $PSScriptRoot
$RAIZ_AGENTE = Split-Path -Parent $RAIZ_AR
$LOG = Join-Path $RAIZ_AR 'active-responses.log'
$ESTADO = Join-Path $RAIZ_AR 'kronos-estado'
$COPIA = Join-Path $ESTADO 'aislamiento.wfw'
$OSSEC_CONF = Join-Path $RAIZ_AGENTE 'ossec.conf'
$PREFIJO = 'Kronos-aislamiento-'
$GRUPO = 'Kronos AI aislamiento'

# El agente de Wazuh tiene abierto active-responses.log: se abre en modo compartido.
# Si aun asi no se puede escribir, se dice por la salida de error en vez de esconderlo.
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

# Manager(s) del agente segun ossec.conf. El archivo no es XML valido (tiene varios
# bloques raiz), asi que se lee con expresiones regulares, sin los comentarios.
# Devuelve objetos con Ips, Puerto, Protocolo, Direccion y EsNombre; si no logra al menos
# una IP, devuelve un arreglo vacio.
function Leer-Managers {
    if (-not (Test-Path -LiteralPath $OSSEC_CONF)) { return , @() }
    $texto = [System.IO.File]::ReadAllText($OSSEC_CONF)
    $texto = [regex]::Replace($texto, '(?s)<!--.*?-->', '')
    $managers = @()
    foreach ($cliente in [regex]::Matches($texto, '(?s)<client>(.*?)</client>')) {
        foreach ($servidor in [regex]::Matches($cliente.Groups[1].Value, '(?s)<server>(.*?)</server>')) {
            $bloque = $servidor.Groups[1].Value
            $direccion = [regex]::Match($bloque, '<address>\s*([^<]+?)\s*</address>')
            if (-not $direccion.Success) { continue }
            $direccion = $direccion.Groups[1].Value
            if ($direccion -notmatch '^[A-Za-z0-9.:_-]{1,253}$') { continue }
            $puerto = 1514
            $p = [regex]::Match($bloque, '<port>\s*(\d{1,5})\s*</port>')
            if ($p.Success) { $puerto = [int]$p.Groups[1].Value }
            if ($puerto -lt 1 -or $puerto -gt 65535) { continue }
            $protocolo = 'TCP'
            $q = [regex]::Match($bloque, '<protocol>\s*(\w+)\s*</protocol>')
            if ($q.Success -and $q.Groups[1].Value -ieq 'udp') { $protocolo = 'UDP' }
            $ip = $null
            $esNombre = -not [System.Net.IPAddress]::TryParse($direccion, [ref]$ip)
            $ips = @()
            if ($esNombre) {
                try { $ips = @([System.Net.Dns]::GetHostAddresses($direccion) | ForEach-Object { $_.ToString() }) } catch { $ips = @() }
            } else {
                $ips = @($ip.ToString())
            }
            if ($ips.Count -gt 0) {
                $managers += New-Object PSObject -Property @{
                    Ips = $ips; Puerto = $puerto; Protocolo = $protocolo; Direccion = $direccion; EsNombre = $esNombre
                }
            }
        }
    }
    return , $managers
}

function Quitar-Reglas-Kronos {
    Get-NetFirewallRule -DisplayName ($PREFIJO + '*') -ErrorAction SilentlyContinue |
        Remove-NetFirewallRule -ErrorAction SilentlyContinue
}

function Importar-Copia {
    & netsh.exe advfirewall import $COPIA | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Nueva-Regla([string]$nombre, [hashtable]$parametros) {
    New-NetFirewallRule -DisplayName ($PREFIJO + $nombre) -Group $GRUPO -Action Allow -Profile Any `
        -Enabled True @parametros -ErrorAction Stop | Out-Null
}

# ------------------------------------------------------------------------------------

if ($null -eq (Get-Command New-NetFirewallRule -ErrorAction SilentlyContinue)) {
    Terminar 1 'ERROR falta el modulo NetSecurity (se lanzo la PowerShell de 32 bits?)'
}

$argumentos = Leer-Argumentos
if ($argumentos.Count -ne 1) { Terminar 1 ('ERROR se esperaba 1 argumento y llegaron {0}' -f $argumentos.Count) }
$operacion = $argumentos[0]
if ($operacion -cne 'aplicar' -and $operacion -cne 'quitar') { Terminar 1 "ERROR operacion no permitida: $operacion" }

if ($operacion -ceq 'aplicar') {
    if (Test-Path -LiteralPath $COPIA) { Terminar 0 'aplicar OK (ya estaba aislado)' }

    # 1. Manager: si no se sabe a donde se conecta el agente, no se toca nada.
    $managers = Leer-Managers
    if ($managers.Count -eq 0) { Terminar 1 "ERROR no se obtuvo la IP del manager desde $OSSEC_CONF; no se toca nada" }
    $dns = @()
    if (@($managers | Where-Object { $_.EsNombre }).Count -gt 0) {
        try {
            $dns = @(Get-DnsClientServerAddress -ErrorAction Stop |
                ForEach-Object { $_.ServerAddresses } | Where-Object { $_ } | Sort-Object -Unique)
        } catch { $dns = @() }
        if ($dns.Count -eq 0) { Terminar 1 'ERROR el manager es un nombre y no hay servidores DNS configurados; no se toca nada' }
    }

    # 2. Copia de la politica actual. Si falla, no se toca nada.
    try { New-Item -ItemType Directory -Path $ESTADO -Force | Out-Null }
    catch { Terminar 1 "ERROR no se pudo crear $($ESTADO): $($_.Exception.Message)" }
    & netsh.exe advfirewall export $COPIA | Out-Null
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $COPIA)) {
        Remove-Item -LiteralPath $COPIA -Force -ErrorAction SilentlyContinue
        Terminar 1 "ERROR netsh no pudo exportar la politica del firewall ($LASTEXITCODE); no se toca nada"
    }

    try {
        # 3. Excepciones, antes de bloquear.
        $i = 0
        foreach ($m in $managers) {
            $i++
            Nueva-Regla "manager-$i" @{ Direction = 'Outbound'; Protocol = $m.Protocolo; RemotePort = $m.Puerto; RemoteAddress = $m.Ips }
        }
        Nueva-Regla 'dhcp-salida' @{ Direction = 'Outbound'; Protocol = 'UDP'; LocalPort = 68; RemotePort = 67 }
        Nueva-Regla 'dhcp-entrada' @{ Direction = 'Inbound'; Protocol = 'UDP'; LocalPort = 68; RemotePort = 67 }
        if ($dns.Count -gt 0) {
            Nueva-Regla 'dns-udp' @{ Direction = 'Outbound'; Protocol = 'UDP'; RemotePort = 53; RemoteAddress = $dns }
            Nueva-Regla 'dns-tcp' @{ Direction = 'Outbound'; Protocol = 'TCP'; RemotePort = 53; RemoteAddress = $dns }
        }

        # 4. Bloquear el resto: una regla de permitir le gana a la accion por omision, asi
        #    que sin deshabilitarlas el bloqueo seria parcial.
        Get-NetFirewallRule -Action Allow -Enabled True -ErrorAction Stop |
            Where-Object { $_.DisplayName -notlike ($PREFIJO + '*') } |
            Disable-NetFirewallRule -ErrorAction Stop
        Set-NetFirewallProfile -All -Enabled True -DefaultInboundAction Block -DefaultOutboundAction Block -ErrorAction Stop
    } catch {
        $error_aplicar = $_.Exception.Message
        if (Importar-Copia) {
            Quitar-Reglas-Kronos
            Remove-Item -LiteralPath $COPIA -Force -ErrorAction SilentlyContinue
            Terminar 1 "ERROR al aislar: $error_aplicar; se restauro la politica anterior"
        }
        Terminar 1 "ERROR al aislar: $error_aplicar; y NO se pudo restaurar la copia $COPIA (restaurar a mano con netsh advfirewall import)"
    }

    $destinos = ($managers | ForEach-Object { '{0} ({1}) {2}/{3}' -f $_.Direccion, ($_.Ips -join ','), $_.Protocolo, $_.Puerto }) -join '; '
    Terminar 0 "aplicar OK; manager permitido: $destinos"
} else {
    if (-not (Test-Path -LiteralPath $COPIA)) { Terminar 0 'quitar OK (no estaba aislado)' }
    if (-not (Importar-Copia)) { Terminar 1 "ERROR netsh no pudo importar $COPIA ($LASTEXITCODE); la copia se conserva" }
    Quitar-Reglas-Kronos
    try { Remove-Item -LiteralPath $COPIA -Force -ErrorAction Stop }
    catch { Terminar 1 "ERROR politica restaurada, pero no se pudo borrar la copia: $($_.Exception.Message)" }
    Terminar 0 'quitar OK; politica restaurada'
}
