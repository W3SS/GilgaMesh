<# Testa SSH em todos os nodes a partir do Windows. Uso: .\mesh-status.ps1 [-Sync] #>
param([switch]$Sync)
$MeshDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($Sync) { git -C $MeshDir pull --ff-only; Write-Host 'Rode bootstrap-windows.ps1 de novo (admin) para reaplicar chaves/config.' }
$nodes = Get-Content (Join-Path $MeshDir 'nodes.conf') | Where-Object { $_ -notmatch '^\s*(#|$)' } | ForEach-Object { $p = $_.Split('|'); [pscustomobject]@{ Name=$p[0]; Alias=$p[1]; Os=$p[3] } }
foreach ($n in $nodes) {
  if ($n.Os -notin @('macos','linux','windows') -or $n.Name -eq $env:COMPUTERNAME.ToLower()) { continue }
  $out = ssh -o BatchMode=yes -o ConnectTimeout=6 $n.Alias hostname 2>&1
  if ($LASTEXITCODE -eq 0) { Write-Host ("OK   {0,-9} {1}" -f $n.Alias, $out) -ForegroundColor Green }
  else { Write-Host ("FAIL {0,-9} {1}" -f $n.Alias, ($out | Select-Object -Last 1)) -ForegroundColor Red }
}
