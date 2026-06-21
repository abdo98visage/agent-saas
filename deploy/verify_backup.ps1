param(
  [Parameter(Mandatory = $true)][string]$ManifestPath
)

$ErrorActionPreference = "Stop"

$manifest = Get-Content (Resolve-Path $ManifestPath) -Raw | ConvertFrom-Json

function Assert-BackupFile($FileInfo) {
  $resolvedPath = Resolve-Path $FileInfo.path
  $actualHash = (Get-FileHash -Algorithm SHA256 $resolvedPath).Hash
  if ($actualHash -ne $FileInfo.sha256) {
    throw "Backup verification failed for $resolvedPath"
  }
}

Assert-BackupFile $manifest.database_backup
Assert-BackupFile $manifest.hermes_profiles_backup
Write-Output "Backup manifest verification passed."
