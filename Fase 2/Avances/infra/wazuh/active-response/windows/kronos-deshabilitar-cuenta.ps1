# kronos-deshabilitar-cuenta (Windows) - Active Response de Kronos AI
#
# Lo lanza kronos-deshabilitar-cuenta.cmd. El agente de Wazuh entrega por la entrada
# estandar una linea JSON; Kronos (SOAR-EXECUTE) pone la operacion y la cuenta en
# parameters.extra_args:
#
#   {"version":1,"command":"add","parameters":{"extra_args":["aplicar","usuario.demo"], ...}}
#
#   aplicar   <cuenta> -> deshabilita la cuenta LOCAL (Disable-LocalUser)
#   habilitar <cuenta> -> la vuelve a habilitar, SOLO si la deshabilito Kronos
#
# Reglas de seguridad (igual que ejecucion/ordenes.py, como segunda barrera):
# - Solo dos operaciones y exactamente una cuenta; cualquier otra cosa se rechaza.
# - El nombre debe calzar con ^[A-Za-z0-9._-]{1,64}$: no se limpia ni se recorta.
# - Solo cuentas locales; las de dominio no se tocan.
# - Nunca se deshabilita una cuenta protegida: por nombre (Administrator, Guest, SYSTEM,
#   kronos...), por SID (administrador integrado -500, invitado -501, -503 y -504), ni un
#   miembro del grupo local Administradores (S-1-5-32-544), para no dejar el equipo sin
#   quien lo administre. Si no se puede saber quienes son los administradores, no se
#   actua.
# - Estado: al deshabilitar se deja la marca active-response\kronos-estado\cuenta-<nombre>.txt.
#   Habilitar solo actua si existe esa marca, para no habilitar una cuenta que el
#   encargado de TI habia deshabilitado por su cuenta.
# - Aplicar y habilitar son idempotentes, y despues de actuar se comprueba el resultado.
#
# Salida: 0 si quedo como se pidio (o no correspondia tocarla), 1 si se rechazo o fallo.
# El resultado va a active-response\active-responses.log del agente. Wazuh no devuelve
# este codigo a la API: EXECUTE solo sabe que la orden llego al agente.
#
# Necesita la PowerShell de 64 bits (el modulo Microsoft.PowerShell.LocalAccounts no existe
# en la de 32 bits): por eso el .cmd usa Sysnative. Compatible con Windows PowerShell 5.1.

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$NOMBRE = 'kronos-deshabilitar-cuenta'
$RAIZ_AR = Split-Path -Parent $PSScriptRoot
$LOG = Join-Path $RAIZ_AR 'active-responses.log'
$ESTADO = Join-Path $RAIZ_AR 'kronos-estado'
$SID_ADMINISTRADORES = 'S-1-5-32-544'
$PROTEGIDAS = @('Administrator', 'Administrador', 'Guest', 'Invitado', 'SYSTEM', 'LocalSystem',
    'DefaultAccount', 'WDAGUtilityAccount', 'kronos')
# Administrador integrado, invitado, DefaultAccount y WDAGUtilityAccount (el nombre cambia
# con el idioma; el final del SID no).
$SUFIJOS_SID_PROTEGIDOS = @('-500', '-501', '-503', '-504')

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

function Buscar-Cuenta([string]$cuenta) {
    # El patron ya excluye * ? [ ], asi que -Name no se interpreta como comodin.
    try { return Get-LocalUser -Name $cuenta -ErrorAction Stop }
    catch { Terminar 1 "ERROR no existe como cuenta local: $cuenta" }
}

function Validar-Protegida($usuario) {
    $nombre = [string]$usuario.Name
    if ($PROTEGIDAS -contains $nombre -or $nombre.EndsWith('$')) { Terminar 1 "ERROR cuenta protegida: $nombre" }
    $sid = [string]$usuario.SID.Value
    foreach ($sufijo in $SUFIJOS_SID_PROTEGIDOS) {
        if ($sid.EndsWith($sufijo)) { Terminar 1 "ERROR cuenta protegida (cuenta integrada del sistema): $nombre" }
    }
}

# SID de los miembros directos del grupo local Administradores. Get-LocalGroupMember falla
# en algunos equipos (miembros huerfanos); entonces se lee el grupo por ADSI. Si las dos
# formas fallan, devuelve $null y quien llama no actua. La coma evita que PowerShell
# desarme el arreglo al devolverlo (un grupo de un miembro llegaria como texto suelto).
function Sids-Administradores {
    try {
        return , @(Get-LocalGroupMember -SID $SID_ADMINISTRADORES -ErrorAction Stop |
            ForEach-Object { [string]$_.SID.Value })
    } catch { }
    try {
        $grupo = (New-Object System.Security.Principal.SecurityIdentifier($SID_ADMINISTRADORES)).Translate(
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

function Ruta-Marca([string]$cuenta) {
    return (Join-Path $ESTADO ('cuenta-{0}.txt' -f $cuenta.ToLowerInvariant()))
}

function Esta-Habilitada([string]$cuenta) {
    return [bool](Get-LocalUser -Name $cuenta -ErrorAction Stop).Enabled
}

# ------------------------------------------------------------------------------------

if ($null -eq (Get-Command Disable-LocalUser -ErrorAction SilentlyContinue)) {
    Terminar 1 'ERROR falta el modulo LocalAccounts (se lanzo la PowerShell de 32 bits?)'
}

$argumentos = Leer-Argumentos
if ($argumentos.Count -ne 2) { Terminar 1 ('ERROR se esperaban 2 argumentos y llegaron {0}' -f $argumentos.Count) }
$operacion = $argumentos[0]
$cuenta = $argumentos[1]
if ($operacion -cne 'aplicar' -and $operacion -cne 'habilitar') { Terminar 1 "ERROR operacion no permitida: $operacion" }
if ($cuenta -cnotmatch '^[A-Za-z0-9._-]{1,64}$') { Terminar 1 "ERROR nombre de cuenta no permitido: $cuenta" }

$usuario = Buscar-Cuenta $cuenta
Validar-Protegida $usuario
$marca = Ruta-Marca $cuenta

if ($operacion -ceq 'aplicar') {
    if (-not $usuario.Enabled) {
        if (Test-Path -LiteralPath $marca) { Terminar 0 "aplicar $cuenta OK (ya la habia deshabilitado Kronos)" }
        Terminar 0 "aplicar $cuenta OK (ya estaba deshabilitada; no la deshabilito Kronos)"
    }
    Validar-No-Administrador $usuario
    try {
        New-Item -ItemType Directory -Path $ESTADO -Force | Out-Null
        $desde = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        # La marca va antes de deshabilitar: si se escribiera despues y fallara, la cuenta
        # quedaria deshabilitada sin que Kronos pudiera revertirla.
        [System.IO.File]::WriteAllText($marca, "Deshabilitada por Kronos AI el $desde UTC`r`n")
    } catch { Terminar 1 "ERROR no se pudo escribir la marca de estado: $($_.Exception.Message)" }
    try { Disable-LocalUser -Name $cuenta -ErrorAction Stop }
    catch {
        Remove-Item -LiteralPath $marca -Force -ErrorAction SilentlyContinue
        Terminar 1 "ERROR no se pudo deshabilitar $($cuenta): $($_.Exception.Message)"
    }
    if (Esta-Habilitada $cuenta) {
        Remove-Item -LiteralPath $marca -Force -ErrorAction SilentlyContinue
        Terminar 1 "ERROR $cuenta sigue habilitada despues de Disable-LocalUser"
    }
    Terminar 0 "aplicar $cuenta OK"
} else {
    if (-not (Test-Path -LiteralPath $marca)) { Terminar 0 "habilitar $cuenta OK (no la deshabilito Kronos; se deja como esta)" }
    if (-not $usuario.Enabled) {
        try { Enable-LocalUser -Name $cuenta -ErrorAction Stop }
        catch { Terminar 1 "ERROR no se pudo habilitar $($cuenta): $($_.Exception.Message)" }
        if (-not (Esta-Habilitada $cuenta)) { Terminar 1 "ERROR $cuenta sigue deshabilitada despues de Enable-LocalUser" }
    }
    try { Remove-Item -LiteralPath $marca -Force -ErrorAction Stop }
    catch { Escribir-Log "ADVERTENCIA no se pudo borrar la marca de $($cuenta): $($_.Exception.Message)" }
    Terminar 0 "habilitar $cuenta OK"
}
