param(
    [string]$Remote = "msc",
    [string]$RemoteProjectDir = "/home/eidf018/eidf018/s2778911-aspp/msc",
    [string]$DownloadDir = (Join-Path $env:USERPROFILE "Downloads"),
    [switch]$Package
)

$ErrorActionPreference = "Stop"

if ($Package) {
    Write-Host "Packaging project on remote host '$Remote'..."
    ssh $Remote "cd '$RemoteProjectDir' && python3 package_project.py"
}

Write-Host "Finding latest package on remote host '$Remote'..."
$remoteZip = ssh $Remote "cd '$RemoteProjectDir' && ls -1t msc_project_*.zip 2>/dev/null | head -n 1"
$remoteZip = $remoteZip.Trim()

if ([string]::IsNullOrWhiteSpace($remoteZip)) {
    throw "No package matching msc_project_*.zip was found in $RemoteProjectDir. Run package_project.py first, or use -Package."
}

New-Item -ItemType Directory -Force -Path $DownloadDir | Out-Null
$destination = Join-Path $DownloadDir $remoteZip

Write-Host "Downloading $remoteZip to $destination..."
scp "${Remote}:${RemoteProjectDir}/${remoteZip}" "$destination"

Write-Host "Downloaded package: $destination"
