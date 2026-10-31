# Windows audio diagnostics

Commands for establishing what audio hardware a machine really has. Run `scripts/audit-audio.ps1` for all of it at once; the pieces below are for targeted checks.

## Endpoints versus adapters

`Win32_SoundDevice` lists audio **controllers**. It will happily report two devices with `Status: OK` on a machine with no speaker attached and no microphone. It is nearly useless for this purpose. Use endpoints instead.

```powershell
Get-PnpDevice -Class AudioEndpoint | Select-Object Status, FriendlyName
```

A `Status` of `OK` means present and started; `Unknown` typically means the endpoint exists but is not currently active — common for a Bluetooth device that has dropped its audio profile while staying paired.

## Endpoint states from the registry

The authoritative per-endpoint state, including devices not currently listed:

```powershell
foreach ($dir in 'Render','Capture') {
    $base = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\$dir"
    Get-ChildItem $base -ErrorAction SilentlyContinue | ForEach-Object {
        $props = Get-ItemProperty "$($_.PSPath)\Properties" -ErrorAction SilentlyContinue
        $name  = $props.'{a45c254e-df1c-4efd-8020-67d146a850e0},2'
        $state = (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).DeviceState
        $label = switch ($state -band 0xF) { 1 {'ACTIVE'} 2 {'DISABLED'} 4 {'NOT PRESENT'} 8 {'UNPLUGGED'} default {"state=$state"} }
        "[$dir][$label] $name"
    }
}
```

State codes: `1` active, `2` disabled, `4` not present, `8` unplugged. Windows can set higher flag bits too, such as `268435460`, so read only the low four.

`UNPLUGGED` on a Realtek `Speaker` or `Headphone` entry means the analogue jack is empty — a reliable signal that nothing is physically connected to onboard audio. An `ACTIVE` display-audio endpoint means only that a display link exists, **not** that the panel has speakers.

## Volume, mute, and switching the default device

The built-in cmdlets cannot read volume or change the default device. Install `AudioDeviceCmdlets` (user scope, no admin):

```powershell
Install-PackageProvider -Name NuGet -Scope CurrentUser -Force
Install-Module -Name AudioDeviceCmdlets -Scope CurrentUser -Force -AllowClobber
```

Then:

```powershell
Import-Module AudioDeviceCmdlets
Get-AudioDevice -List | Select-Object Index, Default, Type, Name
Get-AudioDevice -Playback
Get-AudioDevice -PlaybackVolume      # NOTE: returns a STRING like "46%"
Get-AudioDevice -PlaybackMute
Set-AudioDevice -Index 3             # make device 3 the default
Set-AudioDevice -PlaybackVolume 55
```

**Volume comes back as a string with a percent sign**, so `[math]::Round()` on it throws. Strip non-numeric characters first:

```powershell
[math]::Round([double](((Get-AudioDevice -PlaybackVolume) -replace '[^\d\.]','')))
```

Not every build of the module exposes `-PlaybackMeter` / `-RecordingMeter`; wrap meter calls in `try/catch` and fall back to the speech-engine level method below.

## Measuring microphone level without extra dependencies

`System.Speech` ships with .NET and exposes a live audio level, which is enough to prove a mic is capturing:

```powershell
Add-Type -AssemblyName System.Speech
$rec = New-Object System.Speech.Recognition.SpeechRecognitionEngine
$rec.SetInputToDefaultAudioDevice()
$rec.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
$rec.RecognizeAsync([System.Speech.Recognition.RecognizeMode]::Multiple)
$levels = @()
for ($i = 0; $i -lt 16; $i++) { Start-Sleep -Milliseconds 500; $levels += $rec.AudioLevel }
$rec.RecognizeAsyncStop(); $rec.Dispose()
($levels | Measure-Object -Maximum).Maximum
```

A peak of `0` across all samples means no signal. Low single digits is a quiet room. `SetInputToDefaultAudioDevice()` throws if no default recording device exists — catch it and report "no microphone" rather than "mic not picking up," which is a different diagnosis.

Check `[System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers()` first; the method needs a recognizer installed.

## Speaking text

```powershell
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name }
$s.SelectVoice('Microsoft Zira Desktop')
$s.Volume = 100; $s.Rate = 0
$s.Speak("text")          # blocking
$s.SpeakAsync("text")     # returns immediately; needs the object kept alive
```

A synthesizer **binds to whatever is default when it is created**. After switching output devices, construct a new one or it will keep playing to the old device.

Prefer `SpeakAsync` plus a `SpeakAsyncCancelAll()` stop command so the person can interrupt speech mid-sentence — important when output is long.

The bundled SAPI voices (David, Zira) are intelligible but dated. Windows 11's natural/neural voices install through Settings → Accessibility → Narrator and are markedly better; mention them, but they require a download rather than a command.

## Identifying unknown hardware by ear

When someone cannot easily read model numbers off a device, have each output **announce itself**. Switch to each playback device in turn, build a fresh synthesizer, and speak its own name:

> "Device two, Anker PowerConf. If you can hear this, say: output Anker."

Whichever one they hear identifies itself. Restore the original default afterwards. This is far more reliable than asking someone to inspect cables or navigate sound settings.

## Bluetooth

```powershell
Get-PnpDevice -Class Bluetooth | Select-Object Status, FriendlyName
Get-Service bthserv
Get-PnpDevice | Where-Object { $_.InstanceId -match '^BTHENUM' } | Select-Object Status, Class, FriendlyName
Start-Process 'ms-settings:bluetooth'      # open pairing; one click for the person
```

Service-class GUIDs in the instance ID identify the profile: `0000110B` is A2DP Audio Sink, `0000110E` is AVRCP remote control. **A2DP and AVRCP nodes can both report `OK` while the AudioEndpoint is inactive** — that combination means paired but not actually streaming, usually because the device is asleep or its input source is set elsewhere.

Combo WiFi/Bluetooth cards (e.g. Realtek RTL8852BE) arbitrate both radios. A WiFi link speed above about 1 Gbps indicates 5 GHz, which reduces but does not eliminate coexistence problems. `netsh wlan show interfaces` needs Location permission **and** elevation, so infer the band from `Get-NetAdapter` link speed instead.
