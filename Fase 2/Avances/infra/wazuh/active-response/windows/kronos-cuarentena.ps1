# kronos-cuarentena (Windows) - Active Response de Kronos AI
#
# Lo lanza kronos-cuarentena.cmd. El agente de Wazuh entrega por la entrada estandar una
# linea JSON; Kronos (SOAR-EXECUTE) pone la operacion y la ruta en parameters.extra_args:
#
#   {"version":1,"command":"add","parameters":{"extra_args":["aplicar","C:\\Users\\Public\\upd.exe"]}}
#
#   aplicar   <ruta> -> mueve el archivo a C:\ProgramData\Kronos\cuarentena (solo
#                       Administradores y SYSTEM) y deja un registro con la ruta original,
#                       su SHA-256 y sus permisos (SDDL).
#   restaurar <ruta> -> lo devuelve a su ruta, con sus permisos, si la huella sigue siendo
#                       la misma y la ruta no fue ocupada por otro archivo.
#
# Reglas de seguridad (igual que ejecucion/ordenes.py, como segunda barrera):
# - Solo dos operaciones y exactamente una ruta; cualquier otra cosa se rechaza.
# - Ruta absoluta C:\..., con una lista blanca de caracteres: sin comodines, sin "~" (los
#   nombres cortos como PROGRA~2 esquivarian las carpetas protegidas), sin ":" fuera de la
#   unidad (flujos alternativos), sin "." ni ".." y sin tramos que terminen en punto o
#   espacio. No se limpia ni se recorta.
# - Nunca en C:\Windows, las carpetas del agente, de NetBird ni de Kronos.
# - Nunca a traves de un enlace o una union (reparse point) en la ruta.
# - Solo archivos, nunca carpetas. Si el archivo esta en uso (un proceso abierto), se
#   rechaza: primero hay que terminar el proceso.
# - Idempotente: si ya estaba en cuarentena, o ya estaba restaurado, "sin cambios".
# - Nunca se pierde el archivo: se copia, se comprueba la huella y recien entonces se borra
#   el original.
#
# Salida: 0 si quedo como se pidio, 1 si se rechazo o fallo. El resultado va a
# active-response\active-responses.log del agente. Compatible con Windows PowerShell 5.1.

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$NOMBRE = 'kronos-cuarentena'
$RAIZ_AR = Split-Path -Parent $PSScriptRoot
$LOG = Join-Path $RAIZ_AR 'active-responses.log'
$CUARENTENA = Join-Path $env:ProgramData 'Kronos\cuarentena'
$LARGO_MAXIMO = 260
$TRAMO = '[\w .()+#@,-]{1,255}'
$PATRON = '^[A-Za-z]:\\(?:' + $TRAMO + '\\)*' + $TRAMO + '$'
$PROTEGIDAS = @(
    [string]$env:SystemRoot,
    'C:\Windows\',
    'C:\Program Files (x86)\ossec-agent\',
    'C:\Program Files\ossec-agent\',
    'C:\Program Files\NetBird\',
    'C:\ProgramData\Kronos\',
    ([string]$env:ProgramData + '\Kronos\')
)
$SID_ADMINISTRADORES = 'S-1-5-32-544'
$SID_SYSTEM = 'S-1-5-18'

# Siempre $script:NOMBRE: una variable local $nombre en una funcion lo taparia (PowerShell
# no distingue mayusculas), como paso en kronos-deshabilitar-cuenta el 02-11.
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

function Validar-Ruta([string]$ruta) {
    if ($ruta.Length -gt $LARGO_MAXIMO -or $ruta -notmatch $PATRON) { Terminar 1 "ERROR ruta no permitida: $ruta" }
    foreach ($tramo in $ruta.Split('\') | Select-Object -Skip 1) {
        if ($tramo -eq '.' -or $tramo -eq '..' -or $tramo -ne $tramo.Trim() -or $tramo.EndsWith('.')) {
            Terminar 1 "ERROR ruta con tramos no permitidos: $ruta"
        }
    }
    $minuscula = $ruta.ToLowerInvariant() + '\'
    foreach ($carpeta in $PROTEGIDAS) {
        if ([string]::IsNullOrEmpty($carpeta)) { continue }
        $c = $carpeta.ToLowerInvariant()
        if (-not $c.EndsWith('\')) { $c = $c + '\' }
        if ($minuscula.StartsWith($c)) { Terminar 1 "ERROR ruta protegida: $ruta" }
    }
}

# Ningun tramo de la ruta (ni el archivo) puede ser un enlace o una union: podrian llevar
# a una carpeta protegida.
function Validar-Sin-Enlaces([string]$ruta) {
    $actual = $ruta
    while ($actual.Length -gt 3) {
        if (Test-Path -LiteralPath $actual) {
            $item = Get-Item -LiteralPath $actual -Force
            if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
                Terminar 1 "ERROR la ruta pasa por un enlace o una union: $actual"
            }
        }
        $actual = Split-Path -Parent $actual
    }
}

function Rutas-De([string]$ruta) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($ruta.ToLowerInvariant()))
    } finally { $sha.Dispose() }
    $clave = -join ($bytes | ForEach-Object { $_.ToString('x2') })
    return @{ Guardado = (Join-Path $CUARENTENA ($clave + '.bin')); Registro = (Join-Path $CUARENTENA ($clave + '.json')) }
}

function Huella([string]$ruta) {
    return (Get-FileHash -LiteralPath $ruta -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Preparar-Carpeta {
    if (-not (Test-Path -LiteralPath $CUARENTENA)) {
        New-Item -ItemType Directory -Path $CUARENTENA -Force | Out-Null
    }
    # Solo Administradores y SYSTEM, sin herencia. Con SID, para que no dependa del idioma.
    & icacls.exe $CUARENTENA /inheritance:r /grant:r "*$($SID_ADMINISTRADORES):(OI)(CI)F" "*$($SID_SYSTEM):(OI)(CI)F" | Out-Null
    if ($LASTEXITCODE -ne 0) { Terminar 1 'ERROR no se pudo proteger la carpeta de la cuarentena' }
}

# Copia, comprueba la huella y recien entonces borra el origen.
function Copiar-Y-Verificar([string]$origen, [string]$destino, [string]$esperada) {
    $parcial = $destino + '.parcial'
    Copy-Item -LiteralPath $origen -Destination $parcial -Force
    if ((Huella $parcial) -ne $esperada) {
        Remove-Item -LiteralPath $parcial -Force -ErrorAction SilentlyContinue
        throw 'la copia no coincide con el original; no se movio nada'
    }
    Move-Item -LiteralPath $parcial -Destination $destino -Force
    Remove-Item -LiteralPath $origen -Force
}

function Archivo-En-Uso([string]$ruta) {
    try {
        $fs = [System.IO.File]::Open($ruta, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::None)
        $fs.Dispose()
        return $false
    } catch { return $true }
}

function Aplicar([string]$ruta) {
    $r = Rutas-De $ruta
    if (Test-Path -LiteralPath $r.Registro) {
        if (-not (Test-Path -LiteralPath $ruta)) { Terminar 0 "aplicar $ruta sin cambios (ya estaba en cuarentena)" }
        Terminar 1 "ERROR ya hay un archivo en cuarentena para esa ruta y la ruta se volvio a ocupar: $ruta"
    }
    if (-not (Test-Path -LiteralPath $ruta -PathType Leaf)) { Terminar 1 "ERROR no existe o no es un archivo: $ruta" }
    if (Archivo-En-Uso $ruta) { Terminar 1 "ERROR el archivo esta en uso (terminar el proceso primero): $ruta" }
    Preparar-Carpeta
    $sha = Huella $ruta
    $datos = [ordered]@{
        ruta   = $ruta
        sha256 = $sha
        tamano = (Get-Item -LiteralPath $ruta -Force).Length
        sddl   = (Get-Acl -LiteralPath $ruta).Sddl
        fecha  = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    }
    # El registro va antes de mover: si se escribiera despues y fallara, el archivo
    # quedaria en cuarentena sin que Kronos supiera devolverlo.
    try { [System.IO.File]::WriteAllText($r.Registro, ($datos | ConvertTo-Json -Compress)) }
    catch { Terminar 1 "ERROR no se pudo escribir el registro de la cuarentena: $($_.Exception.Message)" }
    try {
        Copiar-Y-Verificar $ruta $r.Guardado $sha
    } catch {
        $mensaje = $_.Exception.Message
        if ((Test-Path -LiteralPath $r.Guardado) -and -not (Test-Path -LiteralPath $ruta)) {
            Terminar 1 "ERROR al terminar de mover $($ruta): $mensaje (queda en cuarentena con su registro)"
        }
        Remove-Item -LiteralPath $r.Registro -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $r.Guardado -Force -ErrorAction SilentlyContinue
        Terminar 1 "ERROR no se pudo mover $($ruta): $mensaje"
    }
    # El archivo guardado hereda solo Administradores y SYSTEM, y sin ejecucion para nadie.
    & icacls.exe $r.Guardado /reset | Out-Null
    & icacls.exe $r.Guardado /deny "*$($SID_ADMINISTRADORES):(X)" "*$($SID_SYSTEM):(X)" | Out-Null
    Terminar 0 "aplicar $ruta OK (sha256 $sha)"
}

function Restaurar([string]$ruta) {
    $r = Rutas-De $ruta
    if (-not (Test-Path -LiteralPath $r.Registro)) { Terminar 0 "restaurar $ruta sin cambios (no estaba en cuarentena)" }
    try { $datos = [System.IO.File]::ReadAllText($r.Registro) | ConvertFrom-Json }
    catch { Terminar 1 "ERROR el registro de la cuarentena no se puede leer: $ruta" }
    if ([string]$datos.ruta -ne $ruta) { Terminar 1 "ERROR el registro de la cuarentena no corresponde a esa ruta: $ruta" }
    if (Test-Path -LiteralPath $ruta) { Terminar 1 "ERROR la ruta ya esta ocupada; no se sobrescribe: $ruta" }
    $carpeta = Split-Path -Parent $ruta
    if (-not (Test-Path -LiteralPath $carpeta -PathType Container)) { Terminar 1 "ERROR no existe la carpeta de destino: $carpeta" }
    & icacls.exe $r.Guardado /remove:d "*$($SID_ADMINISTRADORES)" "*$($SID_SYSTEM)" | Out-Null
    if ((Huella $r.Guardado) -ne [string]$datos.sha256) { Terminar 1 "ERROR la huella del archivo en cuarentena no coincide; no se restaura: $ruta" }
    try { Copiar-Y-Verificar $r.Guardado $ruta ([string]$datos.sha256) }
    catch { Terminar 1 "ERROR no se pudo restaurar $($ruta): $($_.Exception.Message)" }
    try {
        $acl = Get-Acl -LiteralPath $ruta
        $acl.SetSecurityDescriptorSddlForm([string]$datos.sddl)
        Set-Acl -LiteralPath $ruta -AclObject $acl
    } catch { Escribir-Log "ADVERTENCIA $ruta restaurado, pero sin sus permisos originales: $($_.Exception.Message)" }
    try { Remove-Item -LiteralPath $r.Registro -Force }
    catch { Escribir-Log "ADVERTENCIA no se pudo borrar el registro de $($ruta): $($_.Exception.Message)" }
    Terminar 0 "restaurar $ruta OK (sha256 $($datos.sha256))"
}

# ------------------------------------------------------------------------------------

$argumentos = Leer-Argumentos
if ($argumentos.Count -ne 2) { Terminar 1 ('ERROR se esperaban 2 argumentos y llegaron {0}' -f $argumentos.Count) }
$operacion = $argumentos[0]
$ruta = $argumentos[1]
if ($operacion -cne 'aplicar' -and $operacion -cne 'restaurar') { Terminar 1 "ERROR operacion no permitida: $operacion" }
Validar-Ruta $ruta
Validar-Sin-Enlaces $ruta
if ($operacion -ceq 'aplicar') { Aplicar $ruta } else { Restaurar $ruta }
