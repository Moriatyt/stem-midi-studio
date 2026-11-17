$ErrorActionPreference = 'Stop'
$project = $PSScriptRoot
$python = Join-Path $project '../../work/venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Missing work/venv. Install requirements.txt or restore the project environment.' }
& $python (Join-Path $project 'app.py')
