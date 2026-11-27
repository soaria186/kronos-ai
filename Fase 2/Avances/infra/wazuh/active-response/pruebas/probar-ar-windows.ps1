# Prueba de los scripts de Active Response de Kronos en EP-WKS-01 (a mano, sin la API).
# Uso, en PowerShell como administrador dentro de la VM:
#   powershell -ExecutionPolicy Bypass -File C:\Users\labadmin\probar-ar-windows.ps1 -Parte bloquear
#   powershell -ExecutionPolicy Bypass -File C:\Users\labadmin\probar-ar-windows.ps1 -Parte cuenta
#   powershell -ExecutionPolicy Bypass -File C:\Users\labadmin\probar-ar-windows.ps1 -Parte aislar
#   powershell -ExecutionPolicy Bypass -File C:\Users\labadmin\probar-ar-windows.ps1 -Parte verificar
# Cada parte deja su salida en C:\Users\labadmin\prueba-ar-<parte>-<fecha>.txt
# Siempre partir del snapshot listo-demo. Solo IP de documentacion (203.0.113.0/24).
param([Parameter(Mandatory = $true)][ValidateSet('bloquear', 'cuenta', 'aislar', 'verificar')][string]$Parte)

$bin = 'C:\Program Files (x86)\ossec-agent\active-response\bin'
$log = 'C:\Program Files (x86)\ossec-agent\active-response\active-responses.log'
$casa = 'C:\Users\labadmin'
$antes = Join-Path $casa 'aislamiento-antes.json'
$salida = Join-Path $casa ("prueba-ar-$Parte-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.txt')
$script:fallas = 0
Start-Transcript -Path $salida | Out-Null
Push-Location $bin

function Orden([string]$archivo, [string[]]$argumentos, $crudo = $null) {
    if ($null -ne $crudo) { $json = [string]$crudo }
    else { $json = @{ version = 1; command = 'add'; parameters = @{ extra_args = @($argumentos) } } | ConvertTo-Json -Compress -Depth 5 }
    $json | cmd /c $archivo | Out-Host
    return $LASTEXITCODE
}
function Esperar([string]$nombre, $obtenido, $esperado) {
    if ($obtenido -eq $esperado) { Write-Host "OK     $nombre (obtenido: $obtenido)" }
    else { Write-Host "FALLA  $nombre (obtenido: $obtenido, esperado: $esperado)"; $script:fallas++ }
}
function Regla([string]$ip) { [bool](Get-NetFirewallRule -DisplayName "Kronos-bloqueo-$ip" -ErrorAction SilentlyContinue) }
function Habilitada([string]$cuenta) { (Get-LocalUser -Name $cuenta).Enabled }
function Estado() {
    [pscustomobject]@{
        reglas    = (Get-NetFirewallRule).Count
        activas   = @(Get-NetFirewallRule -Enabled True).Count
        perfiles  = (Get-NetFirewallProfile | ForEach-Object { "$($_.Name):$($_.Enabled):$($_.DefaultInboundAction):$($_.DefaultOutboundAction)" }) -join ' '
    }
}

Write-Host "== Kronos, prueba '$Parte' en $env:COMPUTERNAME, $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') (hora local)"

switch ($Parte) {
    'bloquear' {
        $s = 'kronos-bloquear-ip.cmd'; $ip = '203.0.113.50'
        Esperar 'aplicar'                (Orden $s @('aplicar', $ip)) 0
        Esperar 'la regla existe'        (Regla $ip) $true
        Esperar 'aplicar de nuevo'       (Orden $s @('aplicar', $ip)) 0
        Esperar 'quitar'                 (Orden $s @('quitar', $ip)) 0
        Esperar 'la regla ya no existe'  (Regla $ip) $false
        Esperar 'quitar de nuevo'        (Orden $s @('quitar', $ip)) 0
        $propia = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | Select-Object -First 1).IPAddress
        $puerta = (Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Sort-Object RouteMetric | Select-Object -First 1).NextHop
        Write-Host "   (IP propia: $propia; puerta de enlace: $puerta)"
        Esperar 'rechaza 127.0.0.1'          (Orden $s @('aplicar', '127.0.0.1')) 1
        Esperar 'rechaza la IP propia'       (Orden $s @('aplicar', $propia)) 1
        Esperar 'rechaza la puerta de enlace' (Orden $s @('aplicar', $puerta)) 1
        Esperar "rechaza '1'"                (Orden $s @('aplicar', '1')) 1
        Esperar 'rechaza IP con & calc'      (Orden $s @('aplicar', '203.0.113.50 & calc')) 1
        Esperar 'rechaza tres argumentos'    (Orden $s @('aplicar', $ip, 'extra')) 1
        Esperar "rechaza operacion 'borrar'" (Orden $s @('borrar', $ip)) 1
        Esperar 'rechaza entrada vacia'      (Orden $s @() '') 1
        Esperar 'rechaza JSON roto'          (Orden $s @() '{roto') 1
        Esperar 'no quedo ninguna regla Kronos-bloqueo' (@(Get-NetFirewallRule -DisplayName 'Kronos-bloqueo-*' -ErrorAction SilentlyContinue).Count) 0
    }
    'cuenta' {
        $s = 'kronos-deshabilitar-cuenta.cmd'; $c = 'usuario.demo'; $yo = $env:USERNAME
        Esperar 'aplicar'                        (Orden $s @('aplicar', $c)) 0
        Esperar 'la cuenta quedo deshabilitada'  (Habilitada $c) $false
        Esperar 'aplicar de nuevo'               (Orden $s @('aplicar', $c)) 0
        Esperar 'habilitar'                      (Orden $s @('habilitar', $c)) 0
        Esperar 'la cuenta quedo habilitada'     (Habilitada $c) $true
        Esperar 'habilitar de nuevo'             (Orden $s @('habilitar', $c)) 0
        Write-Host '   (cuenta deshabilitada por otra persona: Kronos no debe habilitarla)'
        Disable-LocalUser -Name $c
        Esperar 'aplicar sobre cuenta ya deshabilitada' (Orden $s @('aplicar', $c)) 0
        Esperar 'habilitar no la toca'           (Orden $s @('habilitar', $c)) 0
        Esperar 'sigue deshabilitada'            (Habilitada $c) $false
        Enable-LocalUser -Name $c
        Esperar 'rechaza Administrador'          (Orden $s @('aplicar', 'Administrador')) 1
        Esperar "rechaza al administrador ($yo)" (Orden $s @('aplicar', $yo)) 1
        Esperar 'rechaza nombre con & calc'      (Orden $s @('aplicar', 'usuario.demo & calc')) 1
        Esperar 'rechaza cuenta que no existe'   (Orden $s @('aplicar', 'noexiste01')) 1
        Esperar 'rechaza tres argumentos'        (Orden $s @('aplicar', $c, 'extra')) 1
        Esperar "rechaza operacion 'borrar'"     (Orden $s @('borrar', $c)) 1
        Esperar 'rechaza entrada vacia'          (Orden $s @() '') 1
        Esperar 'rechaza JSON roto'              (Orden $s @() '{roto') 1
        Esperar "$yo sigue habilitado"           (Habilitada $yo) $true
        Esperar "$c sigue habilitada"            (Habilitada $c) $true
        if (-not (Habilitada $yo)) { Enable-LocalUser -Name $yo; Write-Host "   (se volvio a habilitar $yo)" }
    }
    'aislar' {
        $s = 'kronos-aislar-equipo.cmd'
        $e = Estado
        $e | ConvertTo-Json | Set-Content -Path $antes -Encoding ASCII
        Write-Host "   antes: $($e.reglas) reglas, $($e.activas) activas; $($e.perfiles)"
        Esperar 'rechaza dos argumentos'     (Orden $s @('aplicar', '203.0.113.50')) 1
        Esperar 'rechaza sin argumentos'     (Orden $s @()) 1
        Esperar "rechaza operacion 'borrar'" (Orden $s @('borrar')) 1
        Esperar 'rechaza entrada vacia'      (Orden $s @() '') 1
        Esperar 'rechaza JSON roto'          (Orden $s @() '{roto') 1
        Esperar 'los rechazos no tocaron el firewall' ((Estado | ConvertTo-Json) -eq ($e | ConvertTo-Json)) $true
        Esperar 'aplicar'                    (Orden $s @('aplicar')) 0
        Esperar 'internet bloqueado (1.1.1.1:443)' ((Test-NetConnection 1.1.1.1 -Port 443 -WarningAction SilentlyContinue).TcpTestSucceeded) $false
        Get-NetFirewallRule -DisplayName 'Kronos-aislamiento-*' | Select-Object DisplayName, Direction, Enabled | Format-Table -AutoSize | Out-Host
        Esperar 'aplicar de nuevo'           (Orden $s @('aplicar')) 0
        Esperar 'servicio del agente en marcha' ((Get-Service WazuhSvc).Status.ToString()) 'Running'
        Write-Host '   AHORA: espera 5 minutos, revisa en el servidor que el agente 002 siga Active y quita el aislamiento POR LA API.'
    }
    'verificar' {
        $s = 'kronos-aislar-equipo.cmd'
        if (-not (Test-Path $antes)) { Write-Host 'FALTA  no existe aislamiento-antes.json: corre primero la parte aislar'; $script:fallas++ }
        else {
            $a = Get-Content $antes -Raw | ConvertFrom-Json
            $d = Estado
            Write-Host "   antes:   $($a.reglas) reglas, $($a.activas) activas; $($a.perfiles)"
            Write-Host "   despues: $($d.reglas) reglas, $($d.activas) activas; $($d.perfiles)"
            Esperar 'mismo numero de reglas'   $d.reglas $a.reglas
            Esperar 'mismas reglas activas'    $d.activas $a.activas
            Esperar 'mismos perfiles'          $d.perfiles $a.perfiles
        }
        Esperar 'no quedan reglas Kronos-aislamiento' (@(Get-NetFirewallRule -DisplayName 'Kronos-aislamiento-*' -ErrorAction SilentlyContinue).Count) 0
        Esperar 'internet funciona (1.1.1.1:443)' ((Test-NetConnection 1.1.1.1 -Port 443 -WarningAction SilentlyContinue).TcpTestSucceeded) $true
        Esperar 'quitar de nuevo (no estaba aislado)' (Orden $s @('quitar')) 0
    }
}

Write-Host ''
Write-Host '== Ultimas lineas de active-responses.log'
Get-Content $log -Tail 12 | Out-Host
Write-Host ''
if ($script:fallas -eq 0) { Write-Host "== RESULTADO: todo OK ($Parte)" } else { Write-Host "== RESULTADO: $($script:fallas) FALLA(S) ($Parte)" }
Pop-Location
Stop-Transcript | Out-Null
Write-Host "Salida guardada en $salida"
