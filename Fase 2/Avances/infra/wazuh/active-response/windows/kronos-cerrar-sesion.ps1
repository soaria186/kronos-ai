# kronos-cerrar-sesion (Windows) - Active Response de Kronos AI
#
# Lo lanza kronos-cerrar-sesion.cmd. El agente de Wazuh entrega por la entrada estandar
# una linea JSON; Kronos (SOAR-EXECUTE) pone la operacion y la cuenta en
# parameters.extra_args:
#
#   {"version":1,"command":"add","parameters":{"extra_args":["aplicar","usuario.demo"], ...}}
#
#   aplicar <cuenta> -> cierra todas las sesiones de la cuenta LOCAL (quser + logoff)
#
# Esta medida no se revierte: no hay nada que deshacer, y la persona puede volver a entrar
# (para impedirlo esta kronos-deshabilitar-cuenta).
#
# Reglas de seguridad (las mismas de kronos-deshabilitar-cuenta, como segunda barrera
# despues de ejecucion/ordenes.py):
# - Solo la operacion aplicar y exactamente una cuenta; cualquier otra cosa se rechaza.
# - El nombre debe calzar con ^[A-Za-z0-9._-]{1,64}$: no se limpia ni se recorta.
# - Solo cuentas locales; las de dominio no se tocan.
# - Nunca se cierra la sesion de una cuenta protegida (por nombre o por SID integrado) ni
#   la de un miembro del grupo local Administradores (S-1-5-32-544): podria ser quien esta
#   respondiendo al incidente. Si no se puede leer el grupo, no se actua.
# - Si la cuenta no tiene sesiones, no hace nada. Despues de cerrar, comprueba que no
#   queden sesiones.
#
# Salida: 0 si quedo como se pidio (o no correspondia actuar), 1 si se rechazo o fallo.
# El resultado va a active-response\active-responses.log del agente. Necesita la
# PowerShell de 64 bits (modulo LocalAccounts): el .cmd usa Sysnative. Compatible con
# Windows PowerShell 5.1.

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

# PowerShell no distingue mayusculas en los nombres de variables: ninguna otra variable
# puede llamarse $nombre, porque pisaria a $NOMBRE y el registro saldria con otro prefijo.
$NOMBRE = 'kronos-cerrar-sesion'
$RAIZ_AR = Split-Path -Parent $PSScriptRoot
$LOG = Join-Path $RAIZ_AR 'active-responses.log'
$SID_ADMINISTRADORES = 'S-1-5-32-544'
$PROTEGIDAS = @('Administrator', 'Administrador', 'Guest', 'Invitado', 'SYSTEM', 'LocalSystem',
    'DefaultAccount', 'WDAGUtilityAccount', 'kronos')
$SUFIJOS_SID_PROTEGIDOS = @('-500', '-501', '-503', '-504')

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

function Buscar-Cuenta([string]$cuenta) {
    try { return Get-LocalUser -Name $cuenta -ErrorAction Stop }
    catch { Terminar 1 "ERROR no existe como cuenta local: $cuenta" }
}

function Validar-Protegida($usuario) {
    $corto = [string]$usuario.Name
    if ($script:PROTEGIDAS -contains $corto -or $corto.EndsWith('$')) { Terminar 1 "ERROR cuenta protegida: $corto" }
    $sid = [string]$usuario.SID.Value
    foreach ($sufijo in $script:SUFIJOS_SID_PROTEGIDOS) {
        if ($sid.EndsWith($sufijo)) { Terminar 1 "ERROR cuenta protegida (cuenta integrada del sistema): $corto" }
    }
}

# Igual que en kronos-deshabilitar-cuenta: si las dos formas fallan, devuelve $null.
function Sids-Administradores {
    try {
        return , @(Get-LocalGroupMember -SID $script:SID_ADMINISTRADORES -ErrorAction Stop |
            ForEach-Object { [string]$_.SID.Value })
    } catch { }
    try {
        $grupo = (New-Object System.Security.Principal.SecurityIdentifier($script:SID_ADMINISTRADORES)).Translate(
            [System.Security.Principal.NTAccount]).Value.Split('\')[-1]
        $adsi = [ADSI]"WinNT://$env:COMPUTERNAME/$grupo,group"
        return , @($adsi.Invoke('Members') | ForEach-Object {
            $bytes = $_.GetType().InvokeMember('objectSid', 'GetProperty', $null, $_, $null)
            (New-Object System.Security.Principal.SecurityIdentifier($bytes, 0)).Value
        })
    } catch { }
    return $null
}

function Validar-No-Administrador($usuario) {
    $sids = Sids-Administradores
    if ($null -eq $sids) { Terminar 1 "ERROR no se pudo leer el grupo Administradores; no se actua sobre $($usuario.Name)" }
    if ($sids -contains [string]$usuario.SID.Value) { Terminar 1 "ERROR cuenta protegida (miembro de Administradores): $($usuario.Name)" }
}

# Numeros de sesion de la cuenta segun quser. Las columnas cambian con el idioma, pero el
# orden no: USUARIO, [SESION], ID, ESTADO... La primera columna puede traer '>' (sesion
# actual) y quser corta el nombre a 20 caracteres. Sin sesiones, quser sale con codigo 1.
function Sesiones([string]$cuenta) {
    $salida = @(& quser.exe $cuenta 2>$null)
    if ($LASTEXITCODE -ne 0) { return , @() }
    $ids = @()
    foreach ($linea in ($salida | Select-Object -Skip 1)) {
        $partes = @(([string]$linea).Trim().TrimStart('>').Split(' ', [System.StringSplitOptions]::RemoveEmptyEntries))
        if ($partes.Count -lt 3) { continue }
        $usuarioQ = $partes[0]
        $coincide = ($usuarioQ -ieq $cuenta) -or ($cuenta.Length -gt 20 -and $cuenta.Substring(0, 20) -ieq $usuarioQ)
        if (-not $coincide) { continue }
        foreach ($p in $partes[1..2]) {
            if ($p -match '^\d+$') { $ids += [int]$p; break }
        }
    }
    return , $ids
}

# ------------------------------------------------------------------------------------

if ($null -eq (Get-Command Get-LocalUser -ErrorAction SilentlyContinue)) {
    Terminar 1 'ERROR falta el modulo LocalAccounts (se lanzo la PowerShell de 32 bits?)'
}

$argumentos = Leer-Argumentos
if ($argumentos.Count -ne 2) { Terminar 1 ('ERROR se esperaban 2 argumentos y llegaron {0}' -f $argumentos.Count) }
$operacion = $argumentos[0]
$cuenta = $argumentos[1]
if ($operacion -cne 'aplicar') { Terminar 1 "ERROR operacion no permitida: $operacion (esta medida no se revierte)" }
if ($cuenta -cnotmatch '^[A-Za-z0-9._-]{1,64}$') { Terminar 1 "ERROR nombre de cuenta no permitido: $cuenta" }

$usuario = Buscar-Cuenta $cuenta
Validar-Protegida $usuario
Validar-No-Administrador $usuario

$ids = Sesiones $cuenta
if ($ids.Count -eq 0) { Terminar 0 "aplicar $cuenta OK (sin cambios: no tenia sesiones abiertas)" }

foreach ($id in $ids) {
    & logoff.exe $id 2>$null
    if ($LASTEXITCODE -ne 0) { Terminar 1 "ERROR logoff de la sesion $id de $cuenta (codigo $LASTEXITCODE)" }
}
Start-Sleep -Seconds 2
$quedan = Sesiones $cuenta
if ($quedan.Count -gt 0) { Terminar 1 ("ERROR {0} sigue con sesiones abiertas: {1}" -f $cuenta, ($quedan -join ', ')) }
Terminar 0 ("aplicar {0} OK ({1} sesion(es) cerrada(s))" -f $cuenta, $ids.Count)
