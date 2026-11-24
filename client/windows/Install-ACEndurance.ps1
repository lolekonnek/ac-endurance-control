param(
    [string]$AssettoRoot,
    [string]$ServerUrl,
    [string]$Token
)

$ErrorActionPreference = 'Stop'

function Read-RequiredValue([string]$Prompt, [string]$Value) {
    if (-not [string]::IsNullOrWhiteSpace($Value)) { return $Value.Trim() }
    return (Read-Host $Prompt).Trim()
}

if ([string]::IsNullOrWhiteSpace($AssettoRoot)) {
    $guesses = @(
        'C:\Program Files (x86)\Steam\steamapps\common\assettocorsa',
        'C:\Program Files\Steam\steamapps\common\assettocorsa'
    )
    $AssettoRoot = $guesses | Where-Object { Test-Path (Join-Path $_ 'acs.exe') } | Select-Object -First 1
    if (-not $AssettoRoot) {
        $AssettoRoot = Read-Host 'Podaj katalog glowny Assetto Corsa (zawierajacy acs.exe)'
    }
}
$AssettoRoot = (Resolve-Path -LiteralPath $AssettoRoot).Path
if (-not (Test-Path -LiteralPath (Join-Path $AssettoRoot 'acs.exe'))) {
    throw "Nie znaleziono acs.exe w: $AssettoRoot"
}

$ServerUrl = Read-RequiredValue 'Adres backendu WSS (np. wss://race.example.org/ws/client)' $ServerUrl
if ($ServerUrl -notmatch '^wss://[A-Za-z0-9.-]+(?::[0-9]{1,5})?/ws/client$') {
    throw 'Adres musi miec postac wss://host[:port]/ws/client.'
}
$Token = Read-RequiredValue 'Token klienta przypisany do kierowcy' $Token
if ($Token -notmatch '^[A-Za-z0-9_-]{20,200}$') {
    throw 'Token ma nieprawidlowy format. Wygeneruj token przez mint_client_token.py.'
}

$manifestSource = Join-Path $PSScriptRoot 'manifest.ini'
$luaSource = Join-Path $PSScriptRoot 'ac_endurance_client.lua'
foreach ($source in @($manifestSource, $luaSource)) {
    if (-not (Test-Path -LiteralPath $source)) { throw "Brak pliku paczki: $source" }
}

$appsRoot = Join-Path $AssettoRoot 'apps\lua'
$destination = Join-Path $appsRoot 'ac_endurance_client'
New-Item -ItemType Directory -Force -Path $appsRoot | Out-Null
$staging = Join-Path $appsRoot ('.ac_endurance_client.new-' + [guid]::NewGuid().ToString('N'))
$backup = $null

try {
    New-Item -ItemType Directory -Path $staging | Out-Null
    Copy-Item -LiteralPath $manifestSource -Destination (Join-Path $staging 'manifest.ini')
    $lua = [System.IO.File]::ReadAllText($luaSource)
    $lua = $lua.Replace('wss://race.example.org/ws/client', $ServerUrl)
    $lua = $lua.Replace('SET_DRIVER_TOKEN', $Token)
    $utf8NoBom = New-Object System.Text.UTF8Encoding -ArgumentList $false
    [System.IO.File]::WriteAllText((Join-Path $staging 'ac_endurance_client.lua'), $lua, $utf8NoBom)

    if (Test-Path -LiteralPath $destination) {
        $backup = $destination + '.backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
        Move-Item -LiteralPath $destination -Destination $backup
    }
    Move-Item -LiteralPath $staging -Destination $destination
} catch {
    if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
    if ($backup -and (Test-Path -LiteralPath $backup) -and -not (Test-Path -LiteralPath $destination)) {
        Move-Item -LiteralPath $backup -Destination $destination
    }
    throw
}

Write-Host "Zainstalowano AC Endurance Control: $destination"
if ($backup) { Write-Host "Poprzednia wersja zostala zachowana: $backup" }
Write-Host 'W Content Manager wlacz CSP Lua Apps (CSP 0.2.0+) i pokaz aplikacje Endurance Control w sesji.'
Write-Host 'Token zapisano w pliku Lua na tym komputerze. Nie udostepniaj tego pliku.'
