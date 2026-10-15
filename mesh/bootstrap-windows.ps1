<#
.SYNOPSIS
  Bootstrap do mesh no Windows (desktop-p765rni). Rode no PowerShell COMO ADMINISTRADOR.
.DESCRIPTION
  Ativa o OpenSSH Server (aberto só para a tailnet), gera a chave do mesh, escreve o
  ~/.ssh/config com todos os nodes, autoriza as chaves de mesh\pubkeys e instala o Claude Code.
.PARAMETER Projects
  Pastas de projeto que terão `claude remote-control` (uma janela por projeto).
.PARAMETER StartService
  Registra tarefa agendada que sobe o claude remote-control a cada logon.
.PARAMETER Start
  Sobe o claude remote-control agora.
.PARAMETER TailnetOnly
  Desativa a regra padrão do OpenSSH (qualquer origem) e mantém só a da tailnet.
.PARAMETER PowerShellDefault
  Define o PowerShell como shell padrão do SSH (em vez do cmd).
.EXAMPLE
  .\bootstrap-windows.ps1 -Projects 'C:\dev\GilgaMesh' -StartService -TailnetOnly
#>
[CmdletBinding()]
param(
  [string[]]$Projects = @("$HOME\projects"),
  [switch]$StartService,
  [switch]$Start,
  [switch]$TailnetOnly,
  [switch]$PowerShellDefault
)
$ErrorActionPreference = 'Stop'

function Log($m)  { Write-Host "[mesh] $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "[mesh] $m" -ForegroundColor Yellow }

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { throw 'Execute o PowerShell como Administrador.' }

$MeshDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$NodesFile = Join-Path $MeshDir 'nodes.conf'
$PubDir    = Join-Path $MeshDir 'pubkeys'
$SshDir    = Join-Path $HOME '.ssh'
$Key       = Join-Path $SshDir 'id_ed25519_mesh'
$Begin     = '# >>> gilgamesh-mesh >>>'
$End       = '# <<< gilgamesh-mesh <<<'

# nodes.conf -> objetos
$nodes = Get-Content $NodesFile | Where-Object { $_ -notmatch '^\s*(#|$)' } | ForEach-Object {
  $p = $_.Split('|')
  [pscustomobject]@{ Name = $p[0]; Alias = $p[1]; Ip = $p[2]; Os = $p[3]; User = $(if ($p.Count -gt 4) { $p[4] } else { '' }) }
}

# Identifica esta máquina (IP da tailnet ou nome do computador)
$selfIp = $null
$tsCmd = Get-Command tailscale -ErrorAction SilentlyContinue
if (-not $tsCmd) { Warn 'Tailscale não encontrado no PATH. Instale: https://tailscale.com/download/windows' }
else { $selfIp = (& tailscale ip -4 2>$null | Select-Object -First 1) }
$self = $nodes | Where-Object { ($selfIp -and $_.Ip -eq $selfIp) -or $_.Name -eq $env:COMPUTERNAME.ToLower() } | Select-Object -First 1
if (-not $self) { throw "Não identifiquei esta máquina ($env:COMPUTERNAME) em nodes.conf." }
Log "Máquina: $($self.Name)"

# OpenSSH Server
$cap = Get-WindowsCapability -Online -Name 'OpenSSH.Server*' | Select-Object -First 1
if ($cap.State -ne 'Installed') { Log 'Instalando OpenSSH Server'; Add-WindowsCapability -Online -Name $cap.Name | Out-Null }
Set-Service sshd -StartupType Automatic
Start-Service sshd

# Firewall: SSH liberado para a faixa da tailnet (CGNAT 100.64.0.0/10)
if (-not (Get-NetFirewallRule -Name 'sshd-tailnet' -ErrorAction SilentlyContinue)) {
  New-NetFirewallRule -Name 'sshd-tailnet' -DisplayName 'OpenSSH (Tailnet only)' -Direction Inbound `
    -Protocol TCP -LocalPort 22 -RemoteAddress '100.64.0.0/10' -Action Allow | Out-Null
}
if ($TailnetOnly) {
  Get-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue | Disable-NetFirewallRule
  Log 'Regra padrão do OpenSSH desativada: SSH só pela tailnet.'
}
if ($PowerShellDefault) {
  $ps = (Get-Command powershell.exe).Source
  New-Item -Path HKLM:\SOFTWARE\OpenSSH -Force | Out-Null
  New-ItemProperty -Path HKLM:\SOFTWARE\OpenSSH -Name DefaultShell -Value $ps -PropertyType String -Force | Out-Null
}

# Chave do mesh
New-Item -ItemType Directory -Force -Path $SshDir, $PubDir | Out-Null
if (-not (Test-Path $Key)) {
  Log "Gerando chave SSH do mesh: $Key"
  # cmd /c garante passphrase vazia igual no PS 5.1 e 7+
  cmd.exe /c "ssh-keygen.exe -q -t ed25519 -N `"`" -C mesh-$($self.Name) -f `"$Key`""
}
Copy-Item "$Key.pub" (Join-Path $PubDir "$($self.Name).pub") -Force

# ~/.ssh/config (bloco gerenciado)
$cfgPath = Join-Path $SshDir 'config'
$text = if (Test-Path $cfgPath) { Get-Content $cfgPath -Raw } else { '' }
if ($null -eq $text) { $text = '' }
$text = [regex]::Replace($text, "(?s)$([regex]::Escape($Begin)).*?$([regex]::Escape($End))\r?\n?", '')
$block = "$Begin`n# Gerado por mesh/ - edite nodes.conf, nao este bloco.`n"
foreach ($n in $nodes) {
  if ($n.Name -eq $self.Name -or $n.Os -notin @('macos','linux','windows')) { continue }
  $hosts = if ($n.Alias -eq $n.Name) { $n.Name } else { "$($n.Alias) $($n.Name)" }
  $block += "Host $hosts`n  HostName $($n.Ip)`n"
  if ($n.User) { $block += "  User $($n.User)`n" }
  $block += "  IdentityFile ~/.ssh/id_ed25519_mesh`n  IdentitiesOnly yes`n  ServerAliveInterval 30`n  StrictHostKeyChecking accept-new`n"
}
$block += "$End`n"
Set-Content -Path $cfgPath -Value ($text.TrimEnd() + "`n" + $block) -Encoding ascii
Log '~/.ssh/config atualizado'

# authorized_keys (conta admin usa administrators_authorized_keys)
$isAdminUser = $false
try { $isAdminUser = [bool](Get-LocalGroupMember -Group 'Administrators' | Where-Object { $_.Name -like "*\$env:USERNAME" }) } catch {}
if ($isAdminUser) { $akPath = Join-Path $env:ProgramData 'ssh\administrators_authorized_keys' }
else { $akPath = Join-Path $SshDir 'authorized_keys' }
if (-not (Test-Path $akPath)) { New-Item -ItemType File -Force -Path $akPath | Out-Null }
$existing = @(Get-Content $akPath -ErrorAction SilentlyContinue)
$added = 0
foreach ($f in Get-ChildItem $PubDir -Filter *.pub -ErrorAction SilentlyContinue) {
  $k = (Get-Content $f.FullName -Raw).Trim()
  # from= igual ao teste SEC-10: a chave só vale vinda da tailnet
  if ($k -and -not ($existing | Where-Object { $_ -like "*$k*" })) { Add-Content -Path $akPath -Value "from=`"100.64.0.0/10`" $k" -Encoding ascii; $added++ }
}
if ($isAdminUser) {
  icacls.exe $akPath /inheritance:r /grant 'Administrators:F' /grant 'SYSTEM:F' | Out-Null
}
Log "authorized_keys ($akPath): $added chave(s) nova(s)"
Restart-Service sshd

# Claude Code
$env:Path += ";$HOME\.local\bin"
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
  Log 'Instalando Claude Code (instalador oficial)'
  Invoke-RestMethod https://claude.ai/install.ps1 | Invoke-Expression
} else { Log "Claude Code já instalado: $(claude --version)" }

# claude remote-control por projeto
function Start-RemoteControl([string]$dir) {
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  $cmd = "Set-Location '$dir'; `$env:Path += ';$HOME\.local\bin'; claude remote-control"
  Start-Process powershell.exe -ArgumentList '-NoExit', '-Command', $cmd
}
if ($StartService) {
  $i = 0
  foreach ($dir in $Projects) {
    $i++
    $cmd = "Set-Location '$dir'; `$env:Path += ';$HOME\.local\bin'; claude remote-control"
    $action  = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoExit -WindowStyle Minimized -Command `"$cmd`""
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    Register-ScheduledTask -TaskName "GilgamesMesh-Claude-$i" -Action $action -Trigger $trigger -Force | Out-Null
    Log "Tarefa agendada GilgamesMesh-Claude-$i -> $dir"
  }
}
if ($Start) { foreach ($dir in $Projects) { Start-RemoteControl $dir } }

Write-Host @"

Pronto em $($self.Name). Próximos passos:
  1. Se ainda não logou no Claude Code: rode 'claude' e use /login.
  2. Faça commit/push de mesh\pubkeys\$($self.Name).pub (ou copie para as outras máquinas).
  3. Depois do 'git pull' em cada máquina: .\mesh-status.ps1  (Windows) ou ./meshctl.sh sync / status (Unix)
"@
