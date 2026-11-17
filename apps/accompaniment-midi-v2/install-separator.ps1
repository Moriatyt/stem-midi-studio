# Optional CPU separation environment; leaves the V1 environment untouched.
$ErrorActionPreference = 'Stop'
function Invoke-InstallCommand {
    param([string]$Executable, [string[]]$CommandArguments)
    # Windows PowerShell can wrap harmless native stderr as NativeCommandError.
    # Judge native commands by their exit code, while still showing stderr.
    $ErrorActionPreference = 'Continue'
    & $Executable @CommandArguments 2>&1 | ForEach-Object { $_.ToString() }
    if ($LASTEXITCODE -ne 0) { throw "Installation command failed (exit $LASTEXITCODE): $Executable" }
}
$environment = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../work/demucs-env'))
$condaExecutable = $env:CONDA_EXE
if (-not $condaExecutable -or -not (Test-Path -LiteralPath $condaExecutable)) {
    $condaExecutable = (Get-Command conda -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
}
$python = Join-Path $environment 'python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    # Override user-configured mirrors for this operation only.
    Invoke-InstallCommand $condaExecutable @('create', '--prefix', $environment, 'python=3.11', 'pip', '-y', '--override-channels', '--channel', 'https://repo.anaconda.com/pkgs/main')
}
Invoke-InstallCommand $python @('-m', 'pip', 'install', 'torch==2.5.1', 'torchaudio==2.5.1', '--index-url', 'https://download.pytorch.org/whl/cpu')
Invoke-InstallCommand $python @('-m', 'pip', 'install', 'demucs==4.0.1', 'soundfile', 'imageio-ffmpeg', 'numpy<2', '--index-url', 'https://pypi.org/simple')
Invoke-InstallCommand $python @('-c', "import torch, torchaudio, demucs, soundfile, imageio_ffmpeg; print('CPU separation dependencies are ready.')")
Write-Host 'Setup complete. The first separation will download model weights. Allow several GB of disk space.'
