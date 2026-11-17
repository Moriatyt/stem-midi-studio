# Optional piano-specialist dependencies, in the existing CPU environment.
$ErrorActionPreference = 'Stop'
$projectWork = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../work'))
$python = Join-Path $projectWork 'demucs-env/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run install-separator.ps1 first.' }
$ErrorActionPreference = 'Continue'
& $python -m pip install piano-transcription-inference==0.0.6 'numpy<2' --index-url https://pypi.org/simple
if ($LASTEXITCODE -ne 0) { throw 'Piano dependency installation failed.' }
$ErrorActionPreference = 'Stop'
$modelFolder = Join-Path $projectWork 'model-cache/piano'
[void](New-Item -ItemType Directory -Path $modelFolder -Force)
$checkpoint = Join-Path $modelFolder 'high_resolution.pth'
if (-not (Test-Path -LiteralPath $checkpoint) -or (Get-Item -LiteralPath $checkpoint).Length -lt 160000000) {
    Invoke-WebRequest 'https://zenodo.org/records/4034264/files/CRNN_note_F1%3D0.9677_pedal_F1%3D0.9186.pth?download=1' -OutFile $checkpoint -UseBasicParsing
}
Write-Host 'Piano specialist installed. It runs on CPU and does not use the online GPU quota.'
