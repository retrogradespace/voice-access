# Audio accessibility audit.
# Reports what the machine can ACTUALLY do for sound, in and out.
# Read-only: changes nothing. Needs no admin.
#
# Run with:  powershell -NoProfile -ExecutionPolicy Bypass -File audit-audio.ps1

$ErrorActionPreference = 'Continue'

function Section($t) { ""; "=== $t ===" }

Section "EXECUTION POLICY (Restricted silently blocks profiles)"
$policies = Get-ExecutionPolicy -List
$policies | Format-Table -AutoSize | Out-String
# The list is in order of precedence. Process is left out: it only describes this run, which
# the Bypass above makes unrepresentative of a window the person opens themselves.
$own = $policies | Where-Object { $_.Scope -ne 'Process' -and $_.ExecutionPolicy -ne 'Undefined' } | Select-Object -First 1
$ownPolicy = if ($own) { $own.ExecutionPolicy } else { 'Restricted' }
"Policy in a window the person opens: $ownPolicy"
if ($ownPolicy -in 'Restricted', 'AllSigned') { "WARNING: profiles will not load as they stand. See the pitfalls page." }

Section "PROFILE"
"Path   : $PROFILE"
"Exists : $(Test-Path $PROFILE)"
if (Test-Path $PROFILE) {
    $errs = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($PROFILE, [ref]$null, [ref]$errs)
    if ($errs) { "Syntax : BROKEN - profile will not load:"; $errs | ForEach-Object { "   line $($_.Extent.StartLineNumber): $($_.Message)" } }
    else { "Syntax : OK" }
}

Section "AUDIO ENDPOINTS (state codes: 1 active, 2 disabled, 4 absent, 8 unplugged)"
foreach ($dir in 'Render', 'Capture') {
    "-- $dir --"
    $base = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\$dir"
    Get-ChildItem $base -ErrorAction SilentlyContinue | ForEach-Object {
        $props = Get-ItemProperty "$($_.PSPath)\Properties" -ErrorAction SilentlyContinue
        $name  = $props.'{a45c254e-df1c-4efd-8020-67d146a850e0},2'
        $state = (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).DeviceState
        # Windows can set higher flag bits; the state is in the low four.
        $label = switch ($state -band 0xF) { 1 {'ACTIVE     '} 2 {'DISABLED   '} 4 {'NOT PRESENT'} 8 {'UNPLUGGED  '} default {"state=$state"} }
        "  [$label] $name"
    }
}

Section "PNP ENDPOINT STATUS"
Get-PnpDevice -Class AudioEndpoint -ErrorAction SilentlyContinue |
    Select-Object Status, FriendlyName | Sort-Object Status, FriendlyName |
    Format-Table -AutoSize | Out-String

Section "DEFAULTS, VOLUME AND MUTE"
$haveModule = $null -ne (Get-Module -ListAvailable AudioDeviceCmdlets)
if (-not $haveModule) {
    "AudioDeviceCmdlets is not installed, so volume and default-device state cannot be read."
    "Install (user scope, no admin):"
    "  Install-PackageProvider -Name NuGet -Scope CurrentUser -Force"
    "  Install-Module AudioDeviceCmdlets -Scope CurrentUser -Force -AllowClobber"
} else {
    Import-Module AudioDeviceCmdlets -ErrorAction SilentlyContinue
    try { Get-AudioDevice -List | Select-Object Index, Default, Type, Name | Format-Table -AutoSize | Out-String }
    catch { "Could not enumerate devices." }

    function VolNum($raw) {
        if ($null -eq $raw) { return 0 }
        $c = ([string]$raw) -replace '[^\d\.]', ''
        if ([string]::IsNullOrWhiteSpace($c)) { return 0 }
        [math]::Round([double]$c)
    }
    try {
        $p = Get-AudioDevice -Playback -ErrorAction Stop
        "OUT : $($p.Name)"
        "      volume $(VolNum (Get-AudioDevice -PlaybackVolume))%  muted=$(Get-AudioDevice -PlaybackMute)"
    } catch { "OUT : NO DEFAULT PLAYBACK DEVICE" }
    try {
        $r = Get-AudioDevice -Recording -ErrorAction Stop
        "IN  : $($r.Name)"
        "      volume $(VolNum (Get-AudioDevice -RecordingVolume))%  muted=$(Get-AudioDevice -RecordingMute)"
    } catch { "IN  : NO DEFAULT RECORDING DEVICE" }
}

Section "PHANTOM OUTPUT WARNINGS"
$warn = @()
try {
    $def = (Get-AudioDevice -Playback -ErrorAction Stop).Name
    if ($def -match 'Display Audio|HDMI|DisplayPort|LG |Samsung TV|Generic Monitor') {
        $warn += "Default output is a DISPLAY ($def). The audio sink exists whether or not the panel has speakers. Verify by ear."
    }
    if ($def -match 'Yeti|Blue |Microphone') {
        $warn += "Default output is a MICROPHONE's headphone jack ($def). Silent unless headphones are plugged into the mic itself."
    }
    if ($def -match 'Bluetooth|Headphones \(') {
        $warn += "Default output may be BLUETOOTH ($def). Can idle-sleep and drop while still reporting as paired."
    }
} catch { }
$onlyOneOutput = $false
try { $onlyOneOutput = @(Get-AudioDevice -List | Where-Object { $_.Type -eq 'Playback' }).Count -le 1 } catch { }
if ($onlyOneOutput) { $warn += "Only one playback device exists. If it is a display or an empty jack, there is no working speaker at all." }
if (-not $haveModule) { "NOT CHECKED: these checks need AudioDeviceCmdlets. See the install steps above." }
elseif ($warn.Count -eq 0) { "None detected." }
else { $warn | ForEach-Object { "  ! $_" } }

Section "VOICES AND RECOGNIZERS"
try {
    Add-Type -AssemblyName System.Speech
    $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
    "Voices:"
    $s.GetInstalledVoices() | ForEach-Object { "  $($_.VoiceInfo.Name) ($($_.VoiceInfo.Culture), $($_.VoiceInfo.Gender))" }
    $s.Dispose()
    $rec = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers()
    if ($rec.Count -eq 0) { "Recognizers: NONE - microphone level testing unavailable" }
    else { "Recognizers:"; $rec | ForEach-Object { "  $($_.Name) ($($_.Culture))" } }
} catch { "System.Speech unavailable: $($_.Exception.Message)" }

Section "BLUETOOTH"
Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue |
    Select-Object Status, FriendlyName | Format-Table -AutoSize | Out-String
$bt = Get-Service bthserv -ErrorAction SilentlyContinue
if ($bt) { "bthserv: $($bt.Status)" } else { "bthserv: not present" }
"Paired peripherals:"
Get-PnpDevice -ErrorAction SilentlyContinue |
    Where-Object { $_.InstanceId -match '^BTHENUM\\DEV_' } |
    Select-Object Status, FriendlyName | Format-Table -AutoSize | Out-String

Section "INPUT HARDWARE"
Get-CimInstance Win32_Keyboard -ErrorAction SilentlyContinue | Select-Object Name, Status | Format-Table -AutoSize | Out-String
Get-CimInstance Win32_PointingDevice -ErrorAction SilentlyContinue | Select-Object Name, Status | Format-Table -AutoSize | Out-String

Section "NEXT STEPS"
"1. Do NOT conclude sound works from this report. Speak a specific word and have"
"   the person repeat it back. 'Did you hear that?' does not establish anything."
"2. If any PHANTOM OUTPUT WARNING fired, that device is the first suspect."
"3. If execution policy is Restricted, fix that before building any commands."
""
