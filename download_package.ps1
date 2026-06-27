param(
    [string]$Remote = "msc",
    [string]$RemoteProjectDir = "/home/eidf018/eidf018/s2778911-aspp/msc",
    [string]$DownloadDir = (Join-Path $env:USERPROFILE "Downloads")
)

$ErrorActionPreference = "Stop"

Write-Host "Packaging project on remote host '$Remote'..."
$packageCommand = "cd '$RemoteProjectDir' && package_name=`"msc_project_`$(date +%Y%m%d_%H%M%S).zip`" && python3 package_project.py --output `"`$package_name`" >/dev/null && printf '%s\n' `"`$package_name`""
$remoteZip = ssh $Remote $packageCommand
$remoteZip = $remoteZip.Trim()

if ([string]::IsNullOrWhiteSpace($remoteZip)) {
    throw "Remote packaging did not return a package file name."
}

New-Item -ItemType Directory -Force -Path $DownloadDir | Out-Null
$destination = Join-Path $DownloadDir $remoteZip

Write-Host "Downloading $remoteZip to $destination..."
scp "${Remote}:${RemoteProjectDir}/${remoteZip}" "$destination"

Write-Host "Removing remote package $remoteZip..."
ssh $Remote "cd '$RemoteProjectDir' && rm -f -- '$remoteZip'"

Write-Host "Downloaded package: $destination"
